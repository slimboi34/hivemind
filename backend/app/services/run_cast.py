"""
The cast of a run as a tree: run -> group -> kind of participant -> participant.

It is available from the moment agent setup starts. The profile generator
writes the planned cast and which personas are finished (cast_progress.json),
so the tree can show agents appearing as they are spun up. Runs prepared
before that file existed fall back to the saved simulation config.

Read-only: it reshapes files a run already writes.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .oasis_profile_generator import CAST_PROGRESS_FILE
from .run_briefing import GROUP_LABEL, GROUP_ORDER, group_for, type_label

BIO_CHARS = 180


def _read(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def build_cast_tree(
    planned: List[Dict[str, Any]],
    profiles: List[Dict[str, Any]],
    agent_configs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """planned: rows of {name, entity_type, ready}. Pure function."""
    by_profile = {str(p.get("name") or ""): p for p in profiles or [] if isinstance(p, dict)}
    by_config = {str(c.get("entity_name") or ""): c for c in agent_configs or [] if isinstance(c, dict)}

    groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    total = ready = 0
    for row in planned:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        etype = str(row.get("entity_type") or "")
        profile = by_profile.get(name) or {}
        config = by_config.get(name) or {}
        is_ready = bool(row.get("ready"))
        bio = str(profile.get("bio") or "")
        agent = {
            "name": name,
            "ready": is_ready,
            "kind": "organisation" if profile.get("gender") == "other" else ("person" if profile else None),
            "profession": profile.get("profession") or None,
            "bio": bio[:BIO_CHARS] + ("…" if len(bio) > BIO_CHARS else "") if bio else None,
            "stance": config.get("stance"),
            "activity_level": config.get("activity_level"),
        }
        groups.setdefault(group_for(etype), {}).setdefault(etype, []).append(agent)
        total += 1
        ready += is_ready

    out = []
    for key in GROUP_ORDER:
        if key not in groups:
            continue
        types = [
            {"type": t, "label": type_label(t), "agents": sorted(agents, key=lambda a: a["name"].lower())}
            for t, agents in sorted(groups[key].items())
        ]
        count = sum(len(t["agents"]) for t in types)
        out.append({
            "key": key,
            "label": GROUP_LABEL[key],
            "count": count,
            "ready": sum(a["ready"] for t in types for a in t["agents"]),
            "types": types,
        })
    return {"total": total, "ready": ready, "complete": total > 0 and ready == total, "groups": out}


def get_cast(simulation_id: str) -> Dict[str, Any]:
    from .simulation_runner import SimulationRunner

    sim_dir = os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)
    config = _read(os.path.join(sim_dir, "simulation_config.json")) or {}
    agent_configs = config.get("agent_configs") or []
    profiles = _read(os.path.join(sim_dir, "reddit_profiles.json")) or []
    planned = _read(os.path.join(sim_dir, CAST_PROGRESS_FILE))
    if not isinstance(planned, list):
        planned = [
            {"name": c.get("entity_name"), "entity_type": c.get("entity_type"), "ready": True}
            for c in agent_configs
        ]
    tree = build_cast_tree(planned, profiles if isinstance(profiles, list) else [], agent_configs)
    state = _read(os.path.join(sim_dir, "state.json")) or {}
    tree.update({
        "simulation_id": simulation_id,
        "question": config.get("simulation_requirement") or "",
        "status": state.get("status"),
    })
    return tree
