"""
Simulation API routes
Step 2: read and filter Zep entities, then prepare and run the OASIS simulation (fully automated)
"""

import os
import traceback
from contextlib import nullcontext
from flask import request, jsonify, send_file

from . import simulation_bp
from ..config import Config
from ..services.zep_entity_reader import ZepEntityReader
from ..services.oasis_profile_generator import OasisProfileGenerator
from ..services.simulation_manager import SimulationManager, SimulationStatus
from ..services.simulation_runner import (
    SimulationRunner,
    RunnerStatus,
    SimulationStopPending,
)
from ..services.simulation_analytics import build_analytics
from ..services.zep_graph_memory_updater import ZepGraphMemoryManager
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale
from ..utils.zep_lifecycle import get_graph_readers, graph_lifecycle_lock
from ..models.project import ProjectManager

logger = get_logger('hivemind.api.simulation')


def _get_default_platform(simulation_id: str) -> str:
    """
    Return the default platform from the simulation's configuration

    Reads the enable_twitter / enable_reddit settings in SimulationState and
    returns the platform this simulation actually uses, rather than a hard-coded 'reddit'.

    Args:
        simulation_id: Simulation ID

    Returns:
        'twitter' or 'reddit'
    """
    try:
        manager = SimulationManager()
        state = manager._load_simulation_state(simulation_id)
        if state:
            return state.get_default_platform()
    except Exception:
        pass
    return "reddit"


# Prefix added to interview prompts
# It stops the agent from calling tools, so it answers in plain text
INTERVIEW_PROMPT_PREFIX = "Drawing on your persona and all of your past memories and actions, reply to me directly in plain text without calling any tools: "
# Prefix used before the English translation; still recognised so older prompts are not prefixed twice
LEGACY_INTERVIEW_PROMPT_PREFIX = "结合你的人设、所有的过往记忆与行动，不调用任何工具直接用文本回复我："


def optimize_interview_prompt(prompt: str) -> str:
    """
    Prepare an interview question by adding the prefix that stops the agent from calling tools
    
    Args:
        prompt: The original question
        
    Returns:
        The question with the prefix added
    """
    if not prompt:
        return prompt
    # Don't add the prefix twice
    if prompt.startswith((INTERVIEW_PROMPT_PREFIX, LEGACY_INTERVIEW_PROMPT_PREFIX)):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"


# ============== Entity reading ==============

@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_graph_entities(graph_id: str):
    """
    Get every entity in the graph (filtered)
    
    Returns only nodes that match a predefined entity type (nodes whose labels are not just Entity)
    
    Query parameters:
        entity_types: Comma-separated list of entity types (optional, filters further)
        enrich: Whether to fetch the related edges (default true)
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        entity_types_str = request.args.get('entity_types', '')
        entity_types = [t.strip() for t in entity_types_str.split(',') if t.strip()] if entity_types_str else None
        enrich = request.args.get('enrich', 'true').lower() == 'true'
        
        logger.info(f"Getting graph entities: graph_id={graph_id}, entity_types={entity_types}, enrich={enrich}")
        
        reader = ZepEntityReader()
        result = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get graph entities: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity_detail(graph_id: str, entity_uuid: str):
    """Get the details of a single entity"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        reader = ZepEntityReader()
        entity = reader.get_entity_with_context(graph_id, entity_uuid)
        
        if not entity:
            return jsonify({
                "success": False,
                "error": t('api.entityNotFound', id=entity_uuid)
            }), 404
        
        return jsonify({
            "success": True,
            "data": entity.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get entity details: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """Get every entity of a given type"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        enrich = request.args.get('enrich', 'true').lower() == 'true'
        
        reader = ZepEntityReader()
        entities = reader.get_entities_by_type(
            graph_id=graph_id,
            entity_type=entity_type,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": {
                "entity_type": entity_type,
                "count": len(entities),
                "entities": [e.to_dict() for e in entities]
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get entities: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation management ==============

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """
    Create a new simulation
    
    Note: max_rounds and similar parameters are generated by the LLM; there is no need to set them by hand
    
    Request (JSON):
        {
            "project_id": "proj_xxxx",      // required
            "graph_id": "hivemind_xxxx",    // optional; taken from the project if omitted
            "enable_twitter": true,          // optional, default true
            "enable_reddit": true            // optional, default true
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "project_id": "proj_xxxx",
                "graph_id": "hivemind_xxxx",
                "status": "created",
                "enable_twitter": true,
                "enable_reddit": true,
                "created_at": "2025-12-01T10:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": t('api.requireProjectId')
            }), 400
        
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=project_id)
            }), 404
        
        graph_id = data.get('graph_id') or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.graphNotBuilt')
            }), 400
        
        manager = SimulationManager()
        state = manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=data.get('enable_twitter', True),
            enable_reddit=data.get('enable_reddit', True),
        )
        
        return jsonify({
            "success": True,
            "data": state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to create simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _check_simulation_prepared(simulation_id: str) -> tuple:
    """
    Check whether a simulation has finished preparing
    
    Conditions:
    1. state.json exists and its status is "ready"
    2. The required files exist: reddit_profiles.json, twitter_profiles.csv, simulation_config.json
    
    Note: the run scripts (run_*.py) stay in backend/scripts/ and are no longer copied into the simulation directory
    
    Args:
        simulation_id: Simulation ID
        
    Returns:
        (is_prepared: bool, info: dict)
    """
    import os
    from ..config import Config
    
    simulation_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
    
    # Check that the directory exists
    if not os.path.exists(simulation_dir):
        return False, {"reason": "Simulation directory does not exist"}
    
    # Required files (scripts excluded; they live in backend/scripts/)
    required_files = [
        "state.json",
        "simulation_config.json",
        "reddit_profiles.json",
        "twitter_profiles.csv"
    ]
    
    # Check that the files exist
    existing_files = []
    missing_files = []
    for f in required_files:
        file_path = os.path.join(simulation_dir, f)
        if os.path.exists(file_path):
            existing_files.append(f)
        else:
            missing_files.append(f)
    
    if missing_files:
        return False, {
            "reason": "Required files are missing",
            "missing_files": missing_files,
            "existing_files": existing_files
        }
    
    # Check the status in state.json
    state_file = os.path.join(simulation_dir, "state.json")
    try:
        import json
        with open(state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        status = state_data.get("status", "")
        config_generated = state_data.get("config_generated", False)
        
        # Detailed log
        logger.debug(f"Checking simulation preparation state: {simulation_id}, status={status}, config_generated={config_generated}")
        
        # Preparation counts as finished when config_generated=True and the files exist.
        # Each of these statuses means preparation has finished:
        # - ready: prepared and ready to run
        # - preparing: finished if config_generated=True
        # - running: running, so preparation finished long ago
        # - completed: run finished, so preparation finished long ago
        # - stopped: stopped, so preparation finished long ago
        # - failed: the run failed (but preparation was finished)
        prepared_statuses = ["ready", "preparing", "running", "completed", "stopped", "failed"]
        if status in prepared_statuses and config_generated:
            # Gather file statistics
            profiles_file = os.path.join(simulation_dir, "reddit_profiles.json")
            config_file = os.path.join(simulation_dir, "simulation_config.json")
            
            profiles_count = 0
            if os.path.exists(profiles_file):
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
                    profiles_count = len(profiles_data) if isinstance(profiles_data, list) else 0
            
            # If the status is still preparing but the files are complete, move it to ready
            if status == "preparing":
                try:
                    state_data["status"] = "ready"
                    from datetime import datetime
                    state_data["updated_at"] = datetime.now().isoformat()
                    with open(state_file, 'w', encoding='utf-8') as f:
                        json.dump(state_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Auto-updating simulation status: {simulation_id} preparing -> ready")
                    status = "ready"
                except Exception as e:
                    logger.warning(f"Failed to auto-update status: {e}")
            
            logger.info(f"Simulation {simulation_id} check result: preparation complete (status={status}, config_generated={config_generated})")
            return True, {
                "status": status,
                "entities_count": state_data.get("entities_count", 0),
                "profiles_count": profiles_count,
                "entity_types": state_data.get("entity_types", []),
                "config_generated": config_generated,
                "created_at": state_data.get("created_at"),
                "updated_at": state_data.get("updated_at"),
                "existing_files": existing_files
            }
        else:
            logger.warning(f"Simulation {simulation_id} check result: preparation not complete (status={status}, config_generated={config_generated})")
            return False, {
                "reason": f"Status is not in the prepared list or config_generated is false: status={status}, config_generated={config_generated}",
                "status": status,
                "config_generated": config_generated
            }
            
    except Exception as e:
        return False, {"reason": f"Failed to read state file: {str(e)}"}


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """
    Prepare the simulation environment (async task; the LLM generates every parameter)
    
    This takes a while, so the endpoint returns a task_id straight away;
    poll GET /api/simulation/prepare/status for progress
    
    Behaviour:
    - Detects preparation that has already finished, so nothing is generated twice
    - If preparation is already done, returns the existing result
    - Supports forcing a fresh run (force_regenerate=true)
    
    Steps:
    1. Check whether preparation has already finished
    2. Read and filter entities from the Zep graph
    3. Generate an OASIS agent profile for each entity (with retries)
    4. Have the LLM generate the simulation config (with retries)
    5. Save the config files and preset scripts
    
    Request (JSON):
        {
            "simulation_id": "sim_xxxx",                   // required, simulation ID
            "entity_types": ["Student", "PublicFigure"],  // optional, entity types to include
            "use_llm_for_profiles": true,                 // optional, whether the LLM writes the personas
            "parallel_profile_count": 5,                  // optional, personas generated in parallel, default 5
            "force_regenerate": false                     // optional, force regeneration, default false
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",           // returned for a new task
                "status": "preparing|ready",
                "message": "Preparation task started|Already prepared",
                "already_prepared": true|false    // whether preparation had already finished
            }
        }
    """
    import threading
    import os
    from ..models.task import TaskManager, TaskStatus
    from ..config import Config
    
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # Check whether a fresh run is forced
        force_regenerate = data.get('force_regenerate', False)
        logger.info(f"Handling /prepare request: simulation_id={simulation_id}, force_regenerate={force_regenerate}")
        
        # Check whether preparation has already finished (so nothing is generated twice)
        if not force_regenerate:
            logger.debug(f"Checking whether simulation {simulation_id} is already prepared...")
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            logger.debug(f"Check result: is_prepared={is_prepared}, prepare_info={prepare_info}")
            if is_prepared:
                logger.info(f"Simulation {simulation_id} is already prepared; skipping regeneration")
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "message": t('api.alreadyPrepared'),
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
            else:
                logger.info(f"Simulation {simulation_id} is not prepared; starting the preparation task")
        
        # Get what we need from the project
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404
        
        # Get the simulation requirement
        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": t('api.projectMissingRequirement')
            }), 400
        
        # Get the document text
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""
        
        entity_types_list = data.get('entity_types')
        use_llm_for_profiles = data.get('use_llm_for_profiles', True)
        parallel_profile_count = data.get('parallel_profile_count', 5)
        
        # ========== Count the entities synchronously (before the background task starts) ==========
        # so the frontend knows the expected number of agents as soon as prepare returns
        try:
            logger.info(f"Fetching entity count synchronously: graph_id={state.graph_id}")
            reader = ZepEntityReader()
            # Quick entity read (no edges needed, we only count)
            filtered_preview = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=entity_types_list,
                enrich_with_edges=False  # skip edges for speed
            )
            # Store the entity count on the state (so the frontend can read it immediately)
            state.entities_count = filtered_preview.filtered_count
            state.entity_types = list(filtered_preview.entity_types)
            logger.info(f"Expected entity count: {filtered_preview.filtered_count}, types: {filtered_preview.entity_types}")
        except Exception as e:
            logger.warning(f"Failed to fetch entity count synchronously (will retry in the background task): {e}")
            # A failure here doesn't block anything; the background task fetches the entities again
        
        # Create the async task
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_prepare",
            metadata={
                "simulation_id": simulation_id,
                "project_id": state.project_id
            }
        )
        
        # Update the simulation status (including the entity count fetched above)
        state.status = SimulationStatus.PREPARING
        manager._save_simulation_state(state)
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # Background task
        def run_prepare():
            set_locale(current_locale)
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message=t('progress.startPreparingEnv')
                )
                
                # Prepare the simulation (with a progress callback)
                # Per-stage progress details
                stage_details = {}
                
                def progress_callback(stage, progress, message, **kwargs):
                    # Work out the overall progress
                    stage_weights = {
                        "reading": (0, 20),           # 0-20%
                        "generating_profiles": (20, 70),  # 20-70%
                        "generating_config": (70, 90),    # 70-90%
                        "copying_scripts": (90, 100)       # 90-100%
                    }
                    
                    start, end = stage_weights.get(stage, (0, 100))
                    current_progress = int(start + (end - start) * progress / 100)
                    
                    # Stage names for the detailed progress
                    stage_names = {
                        "reading": t('progress.readingGraphEntities'),
                        "generating_profiles": t('progress.generatingProfiles'),
                        "generating_config": t('progress.generatingSimConfig'),
                        "copying_scripts": t('progress.preparingScripts')
                    }
                    
                    stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
                    total_stages = len(stage_weights)
                    
                    # Update the stage details
                    stage_details[stage] = {
                        "stage_name": stage_names.get(stage, stage),
                        "stage_progress": progress,
                        "current": kwargs.get("current", 0),
                        "total": kwargs.get("total", 0),
                        "item_name": kwargs.get("item_name", "")
                    }
                    
                    # Build the detailed progress info
                    detail = stage_details[stage]
                    progress_detail_data = {
                        "current_stage": stage,
                        "current_stage_name": stage_names.get(stage, stage),
                        "stage_index": stage_index,
                        "total_stages": total_stages,
                        "stage_progress": progress,
                        "current_item": detail["current"],
                        "total_items": detail["total"],
                        "item_description": message
                    }
                    
                    # Build a concise message
                    if detail["total"] > 0:
                        detailed_message = (
                            f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                            f"{detail['current']}/{detail['total']} - {message}"
                        )
                    else:
                        detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"
                    
                    task_manager.update_task(
                        task_id,
                        progress=current_progress,
                        message=detailed_message,
                        progress_detail=progress_detail_data
                    )
                
                result_state = manager.prepare_simulation(
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    defined_entity_types=entity_types_list,
                    use_llm_for_profiles=use_llm_for_profiles,
                    progress_callback=progress_callback,
                    parallel_profile_count=parallel_profile_count
                )

                if result_state.status == SimulationStatus.FAILED:
                    task_manager.fail_task(
                        task_id,
                        result_state.error or "Simulation preparation failed"
                    )
                else:
                    task_manager.complete_task(
                        task_id,
                        result=result_state.to_simple_dict()
                    )
                
            except Exception as e:
                logger.error(f"Failed to prepare simulation: {str(e)}")
                task_manager.fail_task(task_id, str(e))
                
                # Mark the simulation as failed
                state = manager.get_simulation(simulation_id)
                if state:
                    state.status = SimulationStatus.FAILED
                    state.error = str(e)
                    manager._save_simulation_state(state)
        
        # Start the background thread
        thread = threading.Thread(target=run_prepare, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": t('api.prepareStarted'),
                "already_prepared": False,
                "expected_entities_count": state.entities_count,  # expected number of agents
                "entity_types": state.entity_types  # list of entity types
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Failed to start preparation task: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """
    Get the progress of a preparation task
    
    Two ways to query:
    1. By task_id, for the progress of a running task
    2. By simulation_id, to check whether preparation has already finished
    
    Request (JSON):
        {
            "task_id": "task_xxxx",          // optional, the task_id returned by prepare
            "simulation_id": "sim_xxxx"      // optional, simulation ID (to check for finished preparation)
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|ready",
                "progress": 45,
                "message": "...",
                "already_prepared": true|false,  // whether preparation had already finished
                "prepare_info": {...}            // details, when preparation has finished
            }
        }
    """
    from ..models.task import TaskManager
    
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # If a simulation_id was given, first check whether preparation has finished
        if simulation_id:
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            if is_prepared:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "progress": 100,
                        "message": t('api.alreadyPrepared'),
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
        
        # Without a task_id, return an error
        if not task_id:
            if simulation_id:
                # A simulation_id was given but preparation hasn't finished
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "not_started",
                        "progress": 0,
                        "message": t('api.notStartedPrepare'),
                        "already_prepared": False
                    }
                })
            return jsonify({
                "success": False,
                "error": t('api.requireTaskOrSimId')
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            # The task doesn't exist, but if there's a simulation_id, check whether preparation has finished
            if simulation_id:
                is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
                if is_prepared:
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "task_id": task_id,
                            "status": "ready",
                            "progress": 100,
                            "message": t('api.taskCompletedPrepared'),
                            "already_prepared": True,
                            "prepare_info": prepare_info
                        }
                    })
            
            return jsonify({
                "success": False,
                "error": t('api.taskNotFound', id=task_id)
            }), 404
        
        task_dict = task.to_dict()
        task_dict["already_prepared"] = False
        
        return jsonify({
            "success": True,
            "data": task_dict
        })
        
    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """Get a simulation's status"""
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        result = state.to_dict()
        
        # If the simulation is ready, include the run instructions
        if state.status == SimulationStatus.READY:
            result["run_instructions"] = manager.get_run_instructions(simulation_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get simulation status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """
    List all simulations
    
    Query parameters:
        project_id: Filter by project ID (optional)
    """
    try:
        project_id = request.args.get('project_id')
        
        manager = SimulationManager()
        simulations = manager.list_simulations(project_id=project_id)
        
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in simulations],
            "count": len(simulations)
        })
        
    except Exception as e:
        logger.error(f"Failed to list simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _get_report_id_for_simulation(simulation_id: str) -> str:
    """
    Get the latest report_id for a simulation
    
    Scans the reports directory for reports whose simulation_id matches;
    if there are several, returns the newest (by created_at)
    
    Args:
        simulation_id: Simulation ID
        
    Returns:
        The report_id, or None
    """
    import json
    from datetime import datetime
    
    # Reports directory: backend/uploads/reports
    # __file__ is app/api/simulation.py, so go up two levels to backend/
    reports_dir = os.path.join(os.path.dirname(__file__), '../../uploads/reports')
    if not os.path.exists(reports_dir):
        return None
    
    matching_reports = []
    
    try:
        for report_folder in os.listdir(reports_dir):
            report_path = os.path.join(reports_dir, report_folder)
            if not os.path.isdir(report_path):
                continue
            
            meta_file = os.path.join(report_path, "meta.json")
            if not os.path.exists(meta_file):
                continue
            
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                if meta.get("simulation_id") == simulation_id:
                    matching_reports.append({
                        "report_id": meta.get("report_id"),
                        "created_at": meta.get("created_at", ""),
                        "status": meta.get("status", "")
                    })
            except Exception:
                continue
        
        if not matching_reports:
            return None
        
        # Sort newest first and return the latest
        matching_reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return matching_reports[0].get("report_id")
        
    except Exception as e:
        logger.warning(f"Failed to find the report for simulation {simulation_id}: {e}")
        return None


@simulation_bp.route('/history', methods=['GET'])
def get_simulation_history():
    """
    Get the simulation history (with project details)
    
    Used for the history list on the home page; returns simulations enriched with the project name, description and so on
    
    Query parameters:
        limit: Maximum number to return (default 20)
    
    Returns:
        {
            "success": true,
            "data": [
                {
                    "simulation_id": "sim_xxxx",
                    "project_id": "proj_xxxx",
                    "project_name": "Wuhan University opinion analysis",
                    "simulation_requirement": "If Wuhan University announces...",
                    "status": "completed",
                    "entities_count": 68,
                    "profiles_count": 68,
                    "entity_types": ["Student", "Professor", ...],
                    "created_at": "2024-12-10",
                    "updated_at": "2024-12-10",
                    "total_rounds": 120,
                    "current_round": 120,
                    "report_id": "report_xxxx",
                    "version": "v1.0.2"
                },
                ...
            ],
            "count": 7
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        manager = SimulationManager()
        simulations = manager.list_simulations()[:limit]
        
        # Enrich the simulation data, reading only from the simulation's own files
        enriched_simulations = []
        for sim in simulations:
            sim_dict = sim.to_dict()
            
            # Get the simulation config (simulation_requirement is read from simulation_config.json)
            config = manager.get_simulation_config(sim.simulation_id)
            if config:
                sim_dict["simulation_requirement"] = config.get("simulation_requirement", "")
                time_config = config.get("time_config", {})
                sim_dict["total_simulation_hours"] = time_config.get("total_simulation_hours", 0)
                # Recommended number of rounds (fallback value)
                recommended_rounds = int(
                    time_config.get("total_simulation_hours", 0) * 60 / 
                    max(time_config.get("minutes_per_round", 60), 1)
                )
            else:
                sim_dict["simulation_requirement"] = ""
                sim_dict["total_simulation_hours"] = 0
                recommended_rounds = 0
            
            # Get the run state (the actual number of rounds the user set is read from run_state.json)
            run_state = SimulationRunner.get_run_state(sim.simulation_id)
            if run_state:
                sim_dict["current_round"] = run_state.current_round
                sim_dict["runner_status"] = run_state.runner_status.value
                # Use the total_rounds the user set, or the recommended number if there is none
                sim_dict["total_rounds"] = run_state.total_rounds if run_state.total_rounds > 0 else recommended_rounds
            else:
                sim_dict["current_round"] = 0
                sim_dict["runner_status"] = "idle"
                sim_dict["total_rounds"] = recommended_rounds
            
            # File list of the linked project (at most 3)
            project = ProjectManager.get_project(sim.project_id)
            if project and hasattr(project, 'files') and project.files:
                sim_dict["files"] = [
                    {"filename": f.get("filename", "Unknown file")} 
                    for f in project.files[:3]
                ]
            else:
                sim_dict["files"] = []
            
            # Linked report_id (the simulation's latest report)
            sim_dict["report_id"] = _get_report_id_for_simulation(sim.simulation_id)
            
            # Version number
            sim_dict["version"] = "v1.0.2"
            
            # Format the date
            try:
                created_date = sim_dict.get("created_at", "")[:10]
                sim_dict["created_date"] = created_date
            except:
                sim_dict["created_date"] = ""
            
            enriched_simulations.append(sim_dict)
        
        return jsonify({
            "success": True,
            "data": enriched_simulations,
            "count": len(enriched_simulations)
        })
        
    except Exception as e:
        logger.error(f"Failed to get simulation history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id: str):
    """
    Get the simulation's agent profiles
    
    Query parameters:
        platform: Platform (reddit/twitter; defaults to the simulation's own platform)
    """
    try:
        platform = request.args.get('platform') or _get_default_platform(simulation_id)

        manager = SimulationManager()
        profiles = manager.get_profiles(simulation_id, platform=platform)
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "count": len(profiles),
                "profiles": profiles
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Failed to get profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id: str):
    """
    Get the simulation's agent profiles live (to watch progress while they are generated)
    
    Differences from the /profiles endpoint:
    - Reads the file directly, bypassing SimulationManager
    - Suited to watching progress during generation
    - Returns extra metadata (file modification time, whether generation is in progress, etc.)
    
    Query parameters:
        platform: Platform (reddit/twitter; defaults to the simulation's own platform)
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "platform": "reddit",
                "count": 15,
                "total_expected": 93,  // expected total (if known)
                "is_generating": true,  // whether generation is in progress
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "profiles": [...]
            }
        }
    """
    import json
    import csv
    from datetime import datetime
    
    try:
        platform = request.args.get('platform') or _get_default_platform(simulation_id)

        # Simulation directory
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # Work out the file path
        if platform == "reddit":
            profiles_file = os.path.join(sim_dir, "reddit_profiles.json")
        else:
            profiles_file = os.path.join(sim_dir, "twitter_profiles.csv")
        
        # Check whether the file exists
        file_exists = os.path.exists(profiles_file)
        profiles = []
        file_modified_at = None
        
        if file_exists:
            # File modification time
            file_stat = os.stat(profiles_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                if platform == "reddit":
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                else:
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        profiles = list(reader)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read the profiles file (it may still be being written): {e}")
                profiles = []
        
        # Check whether generation is in progress (from state.json)
        is_generating = False
        total_expected = None
        status = None
        error = None
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    total_expected = state_data.get("entities_count")
                    error = state_data.get("error")
            except Exception:
                pass
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "platform": platform,
                "count": len(profiles),
                "total_expected": total_expected,
                "is_generating": is_generating,
                "status": status,
                "error": error,
                "file_exists": file_exists,
                "file_modified_at": file_modified_at,
                "profiles": profiles
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get live profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id: str):
    """
    Get the simulation config live (to watch progress while it is generated)
    
    Differences from the /config endpoint:
    - Reads the file directly, bypassing SimulationManager
    - Suited to watching progress during generation
    - Returns extra metadata (file modification time, whether generation is in progress, etc.)
    - Returns partial information even before the config has been fully generated
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "is_generating": true,  // whether generation is in progress
                "generation_stage": "generating_config",  // current generation stage
                "config": {...}  // the config (if it exists)
            }
        }
    """
    import json
    from datetime import datetime
    
    try:
        # Simulation directory
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # Config file path
        config_file = os.path.join(sim_dir, "simulation_config.json")
        
        # Check whether the file exists
        file_exists = os.path.exists(config_file)
        config = None
        file_modified_at = None
        
        if file_exists:
            # File modification time
            file_stat = os.stat(config_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read the config file (it may still be being written): {e}")
                config = None
        
        # Check whether generation is in progress (from state.json)
        is_generating = False
        generation_stage = None
        status = None
        error = None
        profiles_generated = False
        config_generated = False
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    error = state_data.get("error")
                    is_generating = status == "preparing"
                    profiles_generated = state_data.get("profiles_generated", False)
                    config_generated = state_data.get("config_generated", False)
                    
                    # Work out the current stage
                    if is_generating:
                        if profiles_generated:
                            generation_stage = "generating_config"
                        else:
                            generation_stage = "generating_profiles"
                    elif status == "ready":
                        generation_stage = "completed"
                    elif status == "failed":
                        generation_stage = "failed"
            except Exception:
                pass
        
        # Build the response data
        response_data = {
            "simulation_id": simulation_id,
            "file_exists": file_exists,
            "file_modified_at": file_modified_at,
            "is_generating": is_generating,
            "status": status,
            "error": error,
            "generation_stage": generation_stage,
            "profiles_generated": profiles_generated,
            "config_generated": config_generated,
            "config": config
        }
        
        # If the config exists, pull out some key statistics
        if config:
            response_data["summary"] = {
                "total_agents": len(config.get("agent_configs", [])),
                "simulation_hours": config.get("time_config", {}).get("total_simulation_hours"),
                "initial_posts_count": len(config.get("event_config", {}).get("initial_posts", [])),
                "hot_topics_count": len(config.get("event_config", {}).get("hot_topics", [])),
                "has_twitter_config": "twitter_config" in config,
                "has_reddit_config": "reddit_config" in config,
                "generated_at": config.get("generated_at"),
                "llm_model": config.get("llm_model")
            }
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get live config: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id: str):
    """
    Get the simulation config (the full config generated by the LLM)
    
    Contains:
        - time_config: Timing (simulated duration, rounds, peak/off-peak hours)
        - agent_configs: Each agent's activity settings (activity level, posting frequency, stance, etc.)
        - event_config: Events (initial posts, hot topics)
        - platform_configs: Platform settings
        - generation_reasoning: The LLM's explanation of its choices
    """
    try:
        manager = SimulationManager()
        config = manager.get_simulation_config(simulation_id)
        
        if not config:
            return jsonify({
                "success": False,
                "error": t('api.configNotFound')
            }), 404
        
        return jsonify({
            "success": True,
            "data": config
        })
        
    except Exception as e:
        logger.error(f"Failed to get config: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_simulation_config(simulation_id: str):
    """Download the simulation config file"""
    try:
        manager = SimulationManager()
        sim_dir = manager._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return jsonify({
                "success": False,
                "error": t('api.configFileNotFound')
            }), 404
        
        return send_file(
            config_path,
            as_attachment=True,
            download_name="simulation_config.json"
        )
        
    except Exception as e:
        logger.error(f"Failed to download config: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/script/<script_name>/download', methods=['GET'])
def download_simulation_script(script_name: str):
    """
    Download a simulation run script (shared scripts in backend/scripts/)
    
    Allowed script_name values:
        - run_twitter_simulation.py
        - run_reddit_simulation.py
        - run_parallel_simulation.py
        - action_logger.py
    """
    try:
        # The scripts live in backend/scripts/
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        # Validate the script name
        allowed_scripts = [
            "run_twitter_simulation.py",
            "run_reddit_simulation.py", 
            "run_parallel_simulation.py",
            "action_logger.py"
        ]
        
        if script_name not in allowed_scripts:
            return jsonify({
                "success": False,
                "error": t('api.unknownScript', name=script_name, allowed=allowed_scripts)
            }), 400
        
        script_path = os.path.join(scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            return jsonify({
                "success": False,
                "error": t('api.scriptFileNotFound', name=script_name)
            }), 404
        
        return send_file(
            script_path,
            as_attachment=True,
            download_name=script_name
        )
        
    except Exception as e:
        logger.error(f"Failed to download script: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Profile generation (standalone) ==============

@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """
    Generate OASIS agent profiles straight from the graph (without creating a simulation)
    
    Request (JSON):
        {
            "graph_id": "hivemind_xxxx",     // required
            "entity_types": ["Student"],      // optional
            "use_llm": true,                  // optional
            "platform": "reddit"              // optional
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.requireGraphId')
            }), 400
        
        entity_types = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        platform = data.get('platform', 'reddit')
        
        reader = ZepEntityReader()
        filtered = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=True
        )
        
        if filtered.filtered_count == 0:
            return jsonify({
                "success": False,
                "error": t('api.noMatchingEntities')
            }), 400
        
        generator = OasisProfileGenerator()
        profiles = generator.generate_profiles_from_entities(
            entities=filtered.entities,
            use_llm=use_llm
        )
        
        if platform == "reddit":
            profiles_data = [p.to_reddit_format() for p in profiles]
        elif platform == "twitter":
            profiles_data = [p.to_twitter_format() for p in profiles]
        else:
            profiles_data = [p.to_dict() for p in profiles]
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "entity_types": list(filtered.entity_types),
                "count": len(profiles_data),
                "profiles": profiles_data
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to generate profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation run control ==============

@simulation_bp.route('/start', methods=['POST'])
def start_simulation():
    """
    Start running the simulation

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",          // required, simulation ID
            "platform": "parallel",                // optional: twitter / reddit / parallel (default)
            "max_rounds": 100,                     // optional: maximum rounds, to cut a long simulation short
            "enable_graph_memory_update": false,   // optional: whether agent activity is written to the Zep graph memory as it happens
            "force": false                         // optional: force a restart (stops a running simulation and clears its logs)
        }

    About force:
        - When set, a running or finished simulation is stopped first and its run logs are cleared
        - What gets cleared: run_state.json, actions.jsonl, simulation.log, etc.
        - The config file (simulation_config.json) and profile files are kept
        - Use it to run a simulation again

    About enable_graph_memory_update:
        - When set, every agent action in the simulation (posts, comments, likes, etc.) is written to the Zep graph as it happens
        - This lets the graph "remember" the simulation, for later analysis or AI chat
        - The simulation's project must have a valid graph_id
        - Updates are sent in batches to keep the number of API calls down

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "process_pid": 12345,
                "twitter_running": true,
                "reddit_running": true,
                "started_at": "2025-12-01T10:00:00",
                "graph_memory_update_enabled": true,  // whether graph memory updates are enabled
                "force_restarted": true               // whether this was a forced restart
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        platform = data.get('platform', 'parallel')
        max_rounds = data.get('max_rounds')  # optional: maximum rounds
        enable_graph_memory_update = data.get('enable_graph_memory_update', False)  # optional: enable graph memory updates
        force = data.get('force', False)  # optional: force a restart
        if not isinstance(enable_graph_memory_update, bool):
            return jsonify({
                "success": False,
                "error": "enable_graph_memory_update must be a JSON boolean",
            }), 400
        if not isinstance(force, bool):
            return jsonify({
                "success": False,
                "error": "force must be a JSON boolean",
            }), 400

        # Validate max_rounds
        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
                if max_rounds <= 0:
                    return jsonify({
                        "success": False,
                        "error": t('api.maxRoundsPositive')
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": t('api.maxRoundsInvalid')
                }), 400

        # Hivemind: honour OASIS_DEFAULT_MAX_ROUNDS as the cap when the caller sets none.
        # Upstream defined this setting but never applied it, so "auto" rounds could run
        # e.g. 168 rounds (one simulated week). Set it to 0 to disable the cap.
        if max_rounds is None and Config.OASIS_DEFAULT_MAX_ROUNDS > 0:
            max_rounds = Config.OASIS_DEFAULT_MAX_ROUNDS
        # On the public site the cap is a ceiling, not just a default.
        from ..public_mode import enabled as _public_enabled
        if _public_enabled() and Config.OASIS_DEFAULT_MAX_ROUNDS > 0:
            max_rounds = min(max_rounds or Config.OASIS_DEFAULT_MAX_ROUNDS, Config.OASIS_DEFAULT_MAX_ROUNDS)

        if platform not in ['twitter', 'reddit', 'parallel']:
            return jsonify({
                "success": False,
                "error": t('api.invalidPlatform', platform=platform)
            }), 400

        # Check that the simulation is prepared
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        force_restarted = False
        
        # Handle the status sensibly: if preparation has finished, allow a restart
        if state.status != SimulationStatus.READY:
            # Check whether preparation has finished
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)

            if is_prepared:
                run_state = SimulationRunner.get_run_state(simulation_id)
                updater = ZepGraphMemoryManager.get_updater(simulation_id)
                needs_finalization = bool(
                    run_state
                    and run_state.runner_status in {
                        RunnerStatus.RUNNING,
                        RunnerStatus.PAUSED,
                        RunnerStatus.STOPPING,
                        RunnerStatus.FAILED,
                    }
                    and (
                        run_state.runner_status
                        in {
                            RunnerStatus.RUNNING,
                            RunnerStatus.PAUSED,
                            RunnerStatus.STOPPING,
                        }
                        or updater is not None
                    )
                )
                if needs_finalization:
                    if not force:
                        return jsonify({
                            "success": False,
                            "error": t('api.simRunningForceHint')
                        }), 400
                    logger.info(f"Force mode: finishing termination of the previous simulation first {simulation_id}")
                    try:
                        stopped = SimulationRunner.stop_simulation(simulation_id)
                    except SimulationStopPending as error:
                        return jsonify({
                            "success": False,
                            "pending": True,
                            "error": str(error),
                        }), 409
                    except Exception as error:
                        return jsonify({
                            "success": False,
                            "error": (
                                "Cannot restart until the previous simulation "
                                f"finalizes safely: {error}"
                            ),
                        }), 409
                    if stopped.runner_status != RunnerStatus.STOPPED:
                        return jsonify({
                            "success": False,
                            "error": "Previous simulation did not reach STOPPED",
                        }), 409

                # In force mode, clear the run logs
                if force:
                    logger.info(f"Force mode: clearing simulation logs {simulation_id}")
                    cleanup_result = SimulationRunner.cleanup_simulation_logs(simulation_id)
                    if not cleanup_result.get("success"):
                        return jsonify({
                            "success": False,
                            "error": (
                                "Failed to clean previous simulation logs: "
                                f"{cleanup_result.get('errors')}"
                            ),
                        }), 500
                    force_restarted = True

                # The process doesn't exist or has ended: reset the status to ready
                logger.info(f"Simulation {simulation_id} preparation is complete; resetting status to ready (previous status: {state.status.value})")
                state.status = SimulationStatus.READY
                manager._save_simulation_state(state)
            else:
                # Preparation hasn't finished
                return jsonify({
                    "success": False,
                    "error": t('api.simNotReady', status=state.status.value)
                }), 400
        
        # Get the graph ID (for graph memory updates)
        graph_id = None
        if enable_graph_memory_update:
            # The project is authoritative. A graph ID copied into an older
            # simulation can outlive a project reset/rebuild and must not be
            # used to resurrect writes to a deleted graph.
            project = ProjectManager.get_project(state.project_id)
            graph_id = project.graph_id if project else None
            if not graph_id:
                return jsonify({
                    "success": False,
                    "error": t('api.graphIdRequiredForMemory')
                }), 400

        graph_guard = (
            graph_lifecycle_lock(graph_id)
            if enable_graph_memory_update
            else nullcontext()
        )
        with graph_guard:
            if enable_graph_memory_update:
                # Re-read both references under the same per-graph lock used
                # by reset/delete. Keep the lock through updater creation in
                # start_simulation so check -> claim is atomic.
                refreshed_state = manager.get_simulation(simulation_id)
                refreshed_project = (
                    ProjectManager.get_project(refreshed_state.project_id)
                    if refreshed_state
                    else None
                )
                current_graph_id = (
                    refreshed_project.graph_id if refreshed_project else None
                )
                if current_graph_id != graph_id:
                    return jsonify({
                        "success": False,
                        "error": (
                            "The project graph changed while the simulation "
                            "was starting; retry after refreshing the project"
                        ),
                    }), 409
                if (
                    refreshed_state.graph_id
                    and refreshed_state.graph_id != current_graph_id
                ):
                    return jsonify({
                        "success": False,
                        "error": (
                            "The simulation references an older graph; "
                            "prepare it again before enabling graph memory"
                        ),
                    }), 409
                active_reports = get_graph_readers(graph_id)
                if active_reports:
                    return jsonify({
                        "success": False,
                        "error": (
                            "A report is currently reading this graph; wait "
                            "for report generation to finish before enabling "
                            "graph memory updates"
                        ),
                        "active_reports": active_reports,
                    }), 409
                state = refreshed_state
                logger.info(
                    "Graph memory updates enabled: simulation_id=%s, graph_id=%s",
                    simulation_id,
                    graph_id,
                )

            # Start the simulation. With graph writes enabled, graph_guard is still held until the
            # updater's claim and the process resources have all been registered.
            run_state = SimulationRunner.start_simulation(
                simulation_id=simulation_id,
                platform=platform,
                max_rounds=max_rounds,
                enable_graph_memory_update=enable_graph_memory_update,
                graph_id=graph_id
            )
        
        response_data = run_state.to_dict()
        if max_rounds:
            response_data['max_rounds_applied'] = max_rounds
        response_data['graph_memory_update_enabled'] = enable_graph_memory_update
        response_data['force_restarted'] = force_restarted
        if enable_graph_memory_update:
            response_data['graph_id'] = graph_id
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation():
    """
    Stop the simulation
    
    Request (JSON):
        {
            "simulation_id": "sim_xxxx"  // required, simulation ID
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "stopped",
                "completed_at": "2025-12-01T12:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        run_state = SimulationRunner.stop_simulation(simulation_id)
        
        # Update the simulation status
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.STOPPED
            state.error = None
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })

    except SimulationStopPending as e:
        return jsonify({
            "success": False,
            "pending": True,
            "error": str(e),
        }), 202

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to stop simulation: {str(e)}")
        simulation_id = (request.get_json(silent=True) or {}).get('simulation_id')
        if simulation_id:
            manager = SimulationManager()
            state = manager.get_simulation(simulation_id)
            if state:
                state.status = SimulationStatus.FAILED
                state.error = str(e)
                manager._save_simulation_state(state)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Live status monitoring ==============

@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def get_run_status(simulation_id: str):
    """
    Get the simulation's live run status (polled by the frontend)
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                "total_rounds": 144,
                "progress_percent": 3.5,
                "simulated_hours": 2,
                "total_simulation_hours": 72,
                "twitter_running": true,
                "reddit_running": true,
                "twitter_actions_count": 150,
                "reddit_actions_count": 200,
                "total_actions_count": 350,
                "started_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T10:30:00"
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "current_round": 0,
                    "total_rounds": 0,
                    "progress_percent": 0,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "total_actions_count": 0,
                }
            })
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get run status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def get_run_status_detail(simulation_id: str):
    """
    Get the simulation's detailed run status (including every action)
    
    Used by the frontend's live activity feed
    
    Query parameters:
        platform: Filter by platform (twitter/reddit, optional)
    
    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                ...
                "all_actions": [
                    {
                        "round_num": 5,
                        "timestamp": "2025-12-01T10:30:00",
                        "platform": "twitter",
                        "agent_id": 3,
                        "agent_name": "Agent Name",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "..."},
                        "result": null,
                        "success": true
                    },
                    ...
                ],
                "twitter_actions": [...],  # every action on Twitter
                "reddit_actions": [...]    # every action on Reddit
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        platform_filter = request.args.get('platform')
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "all_actions": [],
                    "twitter_actions": [],
                    "reddit_actions": []
                }
            })
        
        # Get the full action list
        all_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter
        )
        
        # Get the actions per platform
        twitter_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="twitter"
        ) if not platform_filter or platform_filter == "twitter" else []
        
        reddit_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="reddit"
        ) if not platform_filter or platform_filter == "reddit" else []
        
        # Get the current round's actions (recent_actions shows only the latest round)
        current_round = run_state.current_round
        recent_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter,
            round_num=current_round
        ) if current_round > 0 else []
        
        # Basic status information
        result = run_state.to_dict()
        result["all_actions"] = [a.to_dict() for a in all_actions]
        result["twitter_actions"] = [a.to_dict() for a in twitter_actions]
        result["reddit_actions"] = [a.to_dict() for a in reddit_actions]
        result["rounds_count"] = len(run_state.rounds)
        # recent_actions shows only the latest round, for both platforms
        result["recent_actions"] = [a.to_dict() for a in recent_actions]
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get detailed status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/actions', methods=['GET'])
def get_simulation_actions(simulation_id: str):
    """
    Get the agents' action history in the simulation
    
    Query parameters:
        limit: Number to return (default 100)
        offset: Offset (default 0)
        platform: Filter by platform (twitter/reddit)
        agent_id: Filter by agent ID
        round_num: Filter by round
    
    Returns:
        {
            "success": true,
            "data": {
                "count": 100,
                "actions": [...]
            }
        }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        platform = request.args.get('platform')
        agent_id = request.args.get('agent_id', type=int)
        round_num = request.args.get('round_num', type=int)
        
        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(actions),
                "actions": [a.to_dict() for a in actions]
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get action history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_simulation_timeline(simulation_id: str):
    """
    Get the simulation timeline (summarised per round)
    
    Used by the frontend's progress bar and timeline view
    
    Query parameters:
        start_round: First round (default 0)
        end_round: Last round (default: all)
    
    Returns a summary of each round
    """
    try:
        start_round = request.args.get('start_round', 0, type=int)
        end_round = request.args.get('end_round', type=int)
        
        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id,
            start_round=start_round,
            end_round=end_round
        )
        
        return jsonify({
            "success": True,
            "data": {
                "rounds_count": len(timeline),
                "timeline": timeline
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get timeline: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id: str):
    """
    Get statistics for each agent
    
    Used by the frontend for agent activity rankings, action breakdowns and so on
    """
    try:
        stats = SimulationRunner.get_agent_stats(simulation_id)
        
        return jsonify({
            "success": True,
            "data": {
                "agents_count": len(stats),
                "stats": stats
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get agent statistics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/analytics', methods=['GET'])
def get_simulation_analytics(simulation_id: str):
    """
    Hivemind analytics: activity per round, agent interaction network,
    influence ranking and most-engaged posts, computed from the full action
    logs. Read-only; does not touch the simulation or the graph.
    """
    try:
        actions = [a.to_dict() for a in SimulationRunner.get_all_actions(simulation_id)]
        run_state = SimulationRunner.get_run_state(simulation_id)
        total_rounds = run_state.total_rounds if run_state else 0
        data = build_analytics(actions, total_rounds=total_rounds)
        data["simulation_id"] = simulation_id
        data["run"] = {
            "status": run_state.runner_status.value if run_state else None,
            "current_round": run_state.current_round if run_state else None,
            "total_rounds": total_rounds,
        }
        return jsonify({"success": True, "data": data})

    except Exception as e:
        logger.error(f"Failed to build analytics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/dynamics', methods=['GET'])
def get_simulation_dynamics(simulation_id: str):
    """
    Hivemind run dynamics: health card, cascade trees (branching / orphans),
    and engagement consensus. Read-only over sqlite traces + action logs.
    """
    try:
        from ..services.run_dynamics import build_dynamics

        data = build_dynamics(simulation_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Failed to build dynamics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/recap', methods=['GET'])
def get_simulation_recap(simulation_id: str):
    """
    Hivemind "What happened" recap: chaptered facts from the action logs plus
    the best story available without an LLM call (a cached AI-written story
    for the same data, otherwise a template). Read-only.
    """
    try:
        from ..services.run_recap import get_recap

        return jsonify({"success": True, "data": get_recap(simulation_id)})
    except Exception as e:
        logger.error(f"Failed to build recap: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/recap', methods=['POST'])
def write_simulation_recap(simulation_id: str):
    """
    Have the LLM write the "What happened" story from the run's facts and
    cache it. Body: {"force": true} rewrites even when a story for the same
    data is cached.
    """
    try:
        from ..services.run_recap import write_recap

        body = request.get_json(silent=True) or {}
        data = write_recap(simulation_id, force=bool(body.get("force")))
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Failed to write recap: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Could not write the story: {str(e)}",
        }), 502


@simulation_bp.route('/<simulation_id>/cast', methods=['GET'])
def get_simulation_cast(simulation_id: str):
    """
    The cast as a tree (group -> kind -> participant), with which personas are
    written so far. Works during agent setup and for finished runs. Read-only.
    """
    try:
        from ..services.run_cast import get_cast

        return jsonify({"success": True, "data": get_cast(simulation_id)})
    except Exception as e:
        logger.error(f"Failed to build cast: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/briefing', methods=['GET'])
def get_simulation_briefing(simulation_id: str):
    """
    Hivemind briefing: what the run means. Group and company facts plus the
    best reading available without an LLM call (a cached AI-written reading
    for the same data, otherwise a template). Read-only.
    """
    try:
        from ..services.run_briefing import get_briefing

        return jsonify({"success": True, "data": get_briefing(simulation_id)})
    except Exception as e:
        logger.error(f"Failed to build briefing: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/briefing', methods=['POST'])
def write_simulation_briefing(simulation_id: str):
    """
    Have the LLM write the briefing (bottom line, consensus, splits, group and
    company reactions) from the run's facts and cache it. Body: {"force": true}
    rewrites even when a reading for the same data is cached.
    """
    try:
        from ..services.run_briefing import write_briefing

        body = request.get_json(silent=True) or {}
        data = write_briefing(simulation_id, force=bool(body.get("force")))
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Failed to write briefing: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Could not write the briefing: {str(e)}",
        }), 502


@simulation_bp.route('/<simulation_id>/consensus-report.pdf', methods=['GET'])
def download_consensus_report_pdf(simulation_id: str):
    """
    The briefing PDF: bottom line, consensus, splits, group and company
    reactions, the story of the run, then run diagnostics as an appendix.
    ?write=1 has the LLM write the reading and the story first if the run has
    finished and they are not cached yet (slower on the first download).
    """
    try:
        from flask import send_file
        from ..services.consensus_report import build_consensus_pdf
        import io

        write = request.args.get("write", "").lower() in ("1", "true", "yes")
        pdf_bytes = build_consensus_pdf(simulation_id, write=write)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{simulation_id}-hivemind-briefing.pdf",
        )
    except Exception as e:
        logger.error(f"Failed to build consensus PDF: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Database queries ==============

@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_simulation_posts(simulation_id: str):
    """
    Get the posts in the simulation
    
    Query parameters:
        platform: Platform (twitter/reddit)
        limit: Number to return (default 50)
        offset: Offset
    
    Returns the list of posts (read from the SQLite database)
    """
    try:
        platform = request.args.get('platform') or _get_default_platform(simulation_id)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )

        db_file = f"{platform}_simulation.db"
        db_path = os.path.join(sim_dir, db_file)
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "platform": platform,
                    "count": 0,
                    "posts": [],
                    "message": t('api.dbNotExist')
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM post 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            posts = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT COUNT(*) FROM post")
            total = cursor.fetchone()[0]
            
        except sqlite3.OperationalError:
            posts = []
            total = 0
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "total": total,
                "count": len(posts),
                "posts": posts
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get posts: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/comments', methods=['GET'])
def get_simulation_comments(simulation_id: str):
    """
    Get the comments in the simulation

    Query parameters:
        platform: Platform (twitter/reddit; chosen from the simulation config if omitted)
        post_id: Filter by post ID (optional)
        limit: Number to return
        offset: Offset
    """
    try:
        platform = request.args.get('platform') or _get_default_platform(simulation_id)
        post_id = request.args.get('post_id')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_path = os.path.join(sim_dir, f"{platform}_simulation.db")
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "count": 0,
                    "comments": []
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if post_id:
                cursor.execute("""
                    SELECT * FROM comment 
                    WHERE post_id = ?
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (post_id, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM comment 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
            comments = [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.OperationalError:
            comments = []
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(comments),
                "comments": comments
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get comments: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interviews ==============

@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """
    Interview a single agent

    Note: the simulation environment must be running (after the simulation loop finishes it waits for commands)

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",       // required, simulation ID
            "agent_id": 0,                     // required, agent ID
            "prompt": "What do you think about this?", // required, the interview question
            "platform": "twitter",             // optional, platform (twitter/reddit)
                                               // if omitted, a dual-platform simulation is interviewed on both
            "timeout": 60                      // optional, timeout in seconds, default 60
        }

    Returns (no platform given, dual-platform mode):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What do you think about this?",
                "result": {
                    "agent_id": 0,
                    "prompt": "...",
                    "platforms": {
                        "twitter": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit": {"agent_id": 0, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }

    Returns (platform given):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What do you think about this?",
                "result": {
                    "agent_id": 0,
                    "response": "I think...",
                    "platform": "twitter",
                    "timestamp": "2025-12-08T10:00:00"
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        agent_id = data.get('agent_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # optional: twitter/reddit/None
        timeout = data.get('timeout', 60)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        if agent_id is None:
            return jsonify({
                "success": False,
                "error": t('api.requireAgentId')
            }), 400
        
        if not prompt:
            return jsonify({
                "success": False,
                "error": t('api.requirePrompt')
            }), 400
        
        # Validate platform
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400
        
        # Check the environment is running
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400
        
        # Add the prefix that stops the agent from calling tools
        optimized_prompt = optimize_interview_prompt(prompt)
        
        result = SimulationRunner.interview_agent(
            simulation_id=simulation_id,
            agent_id=agent_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.interviewTimeout', error=str(e))
        }), 504
        
    except Exception as e:
        logger.error(f"Interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_agents_batch():
    """
    Interview several agents in one batch

    Note: the simulation environment must be running

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",       // required, simulation ID
            "interviews": [                    // required, list of interviews
                {
                    "agent_id": 0,
                    "prompt": "What do you think of A?",
                    "platform": "twitter"      // optional, platform for this agent's interview
                },
                {
                    "agent_id": 1,
                    "prompt": "What do you think of B?"  // no platform: the default is used
                }
            ],
            "platform": "reddit",              // optional, default platform (overridden by each item's platform)
                                               // if omitted, a dual-platform simulation interviews each agent on both
            "timeout": 240                     // optional, seconds, default 240
        }

    Returns:
        {
            "success": true,
            "data": {
                "interviews_count": 2,
                "result": {
                    "interviews_count": 4,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        "twitter_1": {"agent_id": 1, "response": "...", "platform": "twitter"},
                        "reddit_1": {"agent_id": 1, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        interviews = data.get('interviews')
        platform = data.get('platform')  # optional: twitter/reddit/None
        # Each person answers on both platforms; under API rate limits that can pass two minutes.
        timeout = data.get('timeout', 240)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not interviews or not isinstance(interviews, list):
            return jsonify({
                "success": False,
                "error": t('api.requireInterviews')
            }), 400

        # Validate platform
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400

        # Validate each interview item
        for i, interview in enumerate(interviews):
            if 'agent_id' not in interview:
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListMissingAgentId', index=i+1)
                }), 400
            if 'prompt' not in interview:
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListMissingPrompt', index=i+1)
                }), 400
            # Validate each item's platform (if given)
            item_platform = interview.get('platform')
            if item_platform and item_platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListInvalidPlatform', index=i+1)
                }), 400

        # Check the environment is running
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400

        # Add the prefix that stops the agent from calling tools to each interview prompt
        optimized_interviews = []
        for interview in interviews:
            optimized_interview = interview.copy()
            optimized_interview['prompt'] = optimize_interview_prompt(interview.get('prompt', ''))
            optimized_interviews.append(optimized_interview)

        result = SimulationRunner.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=optimized_interviews,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.batchInterviewTimeout', error=str(e))
        }), 504

    except Exception as e:
        logger.error(f"Batch interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/all', methods=['POST'])
def interview_all_agents():
    """
    Global interview: ask every agent the same question

    Note: the simulation environment must be running

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",            // required, simulation ID
            "prompt": "What do you think of this overall?", // required, the question (every agent gets the same one)
            "platform": "reddit",                   // optional, platform (twitter/reddit)
                                                    // if omitted, a dual-platform simulation interviews each agent on both
            "timeout": 180                          // optional, timeout in seconds, default 180
        }

    Returns:
        {
            "success": true,
            "data": {
                "interviews_count": 50,
                "result": {
                    "interviews_count": 100,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        ...
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # optional: twitter/reddit/None
        timeout = data.get('timeout', 180)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not prompt:
            return jsonify({
                "success": False,
                "error": t('api.requirePrompt')
            }), 400

        # Validate platform
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400

        # Check the environment is running
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400

        # Add the prefix that stops the agent from calling tools
        optimized_prompt = optimize_interview_prompt(prompt)

        result = SimulationRunner.interview_all_agents(
            simulation_id=simulation_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.globalInterviewTimeout', error=str(e))
        }), 504

    except Exception as e:
        logger.error(f"Global interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/history', methods=['POST'])
def get_interview_history():
    """
    Get the interview history

    Reads every interview record from the simulation database

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",  // required, simulation ID
            "platform": "reddit",          // optional, platform (reddit/twitter)
                                           // if omitted, history from both platforms is returned
            "agent_id": 0,                 // optional, only this agent's interviews
            "limit": 100                   // optional, number to return, default 100
        }

    Returns:
        {
            "success": true,
            "data": {
                "count": 10,
                "history": [
                    {
                        "agent_id": 0,
                        "response": "I think...",
                        "prompt": "What do you think about this?",
                        "timestamp": "2025-12-08T10:00:00",
                        "platform": "reddit"
                    },
                    ...
                ]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        platform = data.get('platform')  # if omitted, history from both platforms is returned
        agent_id = data.get('agent_id')
        limit = data.get('limit', 100)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(history),
                "history": history
            }
        })

    except Exception as e:
        logger.error(f"Failed to get interview history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/env-status', methods=['POST'])
def get_env_status():
    """
    Get the simulation environment's status

    Checks whether the simulation environment is alive (able to take interview commands)

    Request (JSON):
        {
            "simulation_id": "sim_xxxx"  // required, simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "env_alive": true,
                "twitter_available": true,
                "reddit_available": true,
                "message": "Environment is running and ready for Interview commands"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        env_alive = SimulationRunner.check_env_alive(simulation_id)
        
        # Get more detailed status information
        env_status = SimulationRunner.get_env_status_detail(simulation_id)

        if env_alive:
            message = t('api.envRunning')
        else:
            message = t('api.envNotRunningShort')

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "env_alive": env_alive,
                "twitter_available": env_status.get("twitter_available", False),
                "reddit_available": env_status.get("reddit_available", False),
                "message": message
            }
        })

    except Exception as e:
        logger.error(f"Failed to get environment status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/close-env', methods=['POST'])
def close_simulation_env():
    """
    Close the simulation environment
    
    Sends the simulation a close-environment command so it leaves wait-for-commands mode cleanly.
    
    Note: this differs from /stop. /stop kills the process,
    whereas this endpoint lets the simulation close its environment and exit gracefully.
    
    Request (JSON):
        {
            "simulation_id": "sim_xxxx",  // required, simulation ID
            "timeout": 30                  // optional, timeout in seconds, default 30
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "message": "Environment close command sent",
                "result": {...},
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        timeout = data.get('timeout', 30)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        result = SimulationRunner.close_simulation_env(
            simulation_id=simulation_id,
            timeout=timeout
        )
        
        # Update the simulation status
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.COMPLETED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to close environment: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
