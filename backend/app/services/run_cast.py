"""
The cast of a run as a tree: run -> group -> kind of participant -> participant
-> the people around that participant.

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

from .cast_growth import GROWTH_FILE, ORIGIN_CIRCLE, ORIGIN_EVIDENCE, ORIGIN_JOINED
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
    """
    planned: rows of {name, entity_type, ready}. Pure function.

    Accounts that were added around a key actor (the circle) or that joined
    mid-run because of one are nested under that actor as its "circle", so the
    tree shows who surrounds whom. Newcomers with no anchor sit in their group.
    """
    by_profile = {str(p.get("name") or ""): p for p in profiles or [] if isinstance(p, dict)}
    by_config = {str(c.get("entity_name") or ""): c for c in agent_configs or [] if isinstance(c, dict)}

    # The planned cast is written when setup starts; anyone added since is only in the config.
    rows = [dict(r) for r in planned if isinstance(r, dict)]
    known = {str(r.get("name") or "").strip() for r in rows}
    for c in agent_configs or []:
        name = str(c.get("entity_name") or "").strip()
        if name and name not in known:
            rows.append({"name": name, "entity_type": c.get("entity_type"), "ready": True})
            known.add(name)

    agents: Dict[str, Dict[str, Any]] = {}
    placed: List[tuple] = []
    origins = {ORIGIN_EVIDENCE: 0, ORIGIN_CIRCLE: 0, ORIGIN_JOINED: 0}
    total = ready = 0
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name or name in agents:
            continue
        etype = str(row.get("entity_type") or "")
        profile = by_profile.get(name) or {}
        config = by_config.get(name) or {}
        is_ready = bool(row.get("ready"))
        bio = str(profile.get("bio") or "")
        origin = config.get("origin") if config.get("origin") in origins else ORIGIN_EVIDENCE
        agent = {
            "name": name,
            "ready": is_ready,
            "kind": "organisation" if profile.get("gender") == "other" else ("person" if profile else None),
            "profession": profile.get("profession") or None,
            "bio": bio[:BIO_CHARS] + ("…" if len(bio) > BIO_CHARS else "") if bio else None,
            "stance": config.get("stance"),
            "activity_level": config.get("activity_level"),
            "origin": origin,
            "anchor": config.get("anchor_name") or None,
            "relation": config.get("relation") or None,
            "why": config.get("why") or None,
            "joined_round": config.get("joined_round") or 0,
            "type_label": type_label(etype),
            "circle": [],
        }
        agents[name] = agent
        placed.append((etype, agent))
        origins[origin] += 1
        total += 1
        ready += is_ready

    def top_anchor(agent: Dict[str, Any]):
        """The actor this account hangs off. One level only: a chain resolves to its first link."""
        seen = {agent["name"]}
        current = agents.get(agent["anchor"] or "")
        while current is not None and current["name"] not in seen:
            seen.add(current["name"])
            parent = agents.get(current["anchor"] or "")
            if parent is None or parent["name"] in seen:
                return current
            current = parent
        return None

    groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for etype, agent in placed:
        anchor = top_anchor(agent)
        if anchor is not None:
            anchor["circle"].append(agent)
        else:
            groups.setdefault(group_for(etype), {}).setdefault(etype, []).append(agent)
    for agent in agents.values():
        agent["circle"].sort(key=lambda a: (a["joined_round"], a["name"].lower()))

    def count(items: List[Dict[str, Any]], key=None) -> int:
        return sum((1 if key is None else bool(a[key])) + count(a["circle"], key) for a in items)

    out = []
    for key in GROUP_ORDER:
        if key not in groups:
            continue
        types = [
            {"type": t, "label": type_label(t), "agents": sorted(members, key=lambda a: a["name"].lower())}
            for t, members in sorted(groups[key].items())
        ]
        out.append({
            "key": key,
            "label": GROUP_LABEL[key],
            "count": sum(count(t["agents"]) for t in types),
            "ready": sum(count(t["agents"], "ready") for t in types),
            "types": types,
        })
    return {
        "total": total, "ready": ready, "complete": total > 0 and ready == total,
        "origins": origins, "groups": out,
    }


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
    run = _read(os.path.join(sim_dir, "run_state.json")) or {}
    report = _read(os.path.join(sim_dir, GROWTH_FILE)) or {}
    tree.update({
        # While a platform is still playing rounds, more accounts can join.
        "growing": bool(run.get("twitter_running") or run.get("reddit_running")),
        "growth": report.get("settings"),
        "simulation_id": simulation_id,
        "question": config.get("simulation_requirement") or "",
        "status": state.get("status"),
    })
    return tree
