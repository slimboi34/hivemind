"""
The circle: the people immediately around a run's key actors, added when the
cast is set up. See cast_growth.py for what they are and the rules they follow.

One model call for the whole cast. If it fails the run goes ahead with the
cast from the evidence; the circle is an addition, never a requirement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..utils.logger import get_logger
from . import cast_growth as growth
from .oasis_profile_generator import OasisAgentProfile
from .simulation_config_generator import AgentActivityConfig
from .zep_entity_reader import EntityNode

logger = get_logger('hivemind.cast_circle')

NEAR_NAMES = 8


def cast_rows(entities: List[EntityNode]) -> List[Dict[str, Any]]:
    """The evidence cast in the shape cast_growth works with. Agent ids are list positions."""
    rows = []
    for i, e in enumerate(entities):
        near = [str(n.get("name")) for n in (e.related_nodes or []) if n.get("name")]
        rows.append({
            "agent_id": i,
            "name": e.name,
            "entity_type": e.get_entity_type() or "Unknown",
            "summary": e.summary or "",
            "degree": len(e.related_edges or []),
            "near": near[:NEAR_NAMES],
        })
    return rows


def expand_circle(
    entities: List[EntityNode],
    question: str,
    agent_configs: List[AgentActivityConfig],
    llm_client: Any = None,
    config: Dict[str, Any] = None,
) -> Tuple[List[OasisAgentProfile], List[AgentActivityConfig]]:
    """Profiles and activity configs for the circle, numbered after the existing cast."""
    opts = growth.settings(config)
    if not opts["circle"] or not opts["circle_anchors"] or not opts["circle_per_anchor"] or not entities:
        return [], []

    cast = cast_rows(entities)
    limit = growth.cap_for(len(cast), opts["circle_anchors"] * opts["circle_per_anchor"])
    anchors = growth.pick_anchors(cast, opts["circle_anchors"])
    try:
        from ..utils.llm_client import LLMClient
        from ..utils.locale import get_language_instruction

        system, user = growth.circle_prompt(
            question, anchors, [c["name"] for c in cast], opts["circle_per_anchor"], get_language_instruction()
        )
        client = llm_client or LLMClient()
        reply = client.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.6,
            max_tokens=6000,
        )
        rows = growth.parse_accounts(
            growth.parse_json(reply),
            cast,
            limit=limit,
            per_anchor=opts["circle_per_anchor"],
            require_anchor=True,
        )
    except Exception as e:  # the circle is optional; the evidence cast still runs
        logger.warning(f"Circle not added: {e}")
        return [], []

    hours = {c.agent_id: c.active_hours for c in agent_configs}
    profiles: List[OasisAgentProfile] = []
    configs: List[AgentActivityConfig] = []
    for offset, row in enumerate(rows):
        agent_id = len(entities) + offset
        p = growth.profile_row(row, agent_id)
        profiles.append(OasisAgentProfile(
            user_id=agent_id,
            user_name=p["username"],
            name=row["name"],
            bio=row["bio"],
            persona=row["persona"],
            karma=p["karma"],
            age=p["age"],
            gender=p["gender"],
            mbti=p["mbti"],
            profession=row["profession"] or None,
            source_entity_type=row["entity_type"],
        ))
        # The circle keeps the hours of the actor it surrounds, so it is awake when they are.
        c = growth.agent_config_row(row, agent_id, growth.ORIGIN_CIRCLE,
                                    active_hours=hours.get(row["anchor_agent_id"]))
        configs.append(AgentActivityConfig(**c))
    logger.info(f"Circle added: {len(rows)} accounts around {len({r['anchor_agent_id'] for r in rows})} actors")
    return profiles, configs
