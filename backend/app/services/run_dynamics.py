"""
Run dynamics: health card + cascade/orphan/branching summary for a simulation.

Combines sqlite trace reconstruction (trace_reader) with the JSONL action
analytics already used by the Analytics page. Read-only; never feeds back into
the prediction pipeline.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set

from .simulation_analytics import build_analytics
from .simulation_runner import SimulationRunner
from .trace_reader import read_simulation_traces


def _sim_dir(simulation_id: str) -> str:
    return os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)


def _load_configured_agents(simulation_id: str) -> List[str]:
    """Agent names from profiles / config, used to spot silent (orphan) agents."""
    names: Set[str] = set()
    sim_dir = _sim_dir(simulation_id)
    reddit = os.path.join(sim_dir, "reddit_profiles.json")
    if os.path.isfile(reddit):
        try:
            data = json.loads(open(reddit, encoding="utf-8").read())
            if isinstance(data, list):
                for row in data:
                    n = row.get("name") or row.get("username")
                    if n:
                        names.add(str(n))
        except (OSError, json.JSONDecodeError):
            pass
    twitter_csv = os.path.join(sim_dir, "twitter_profiles.csv")
    if os.path.isfile(twitter_csv):
        try:
            import csv

            with open(twitter_csv, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    n = row.get("name") or row.get("username") or row.get("user_name")
                    if n:
                        names.add(str(n))
        except OSError:
            pass
    return sorted(names)


def _level(ok: bool, warn: bool = False) -> str:
    if not ok:
        return "red"
    if warn:
        return "amber"
    return "green"


def _count_feed_errors(simulation_id: Optional[str]) -> int:
    """Lines the OASIS patch layer printed when building a feed failed."""
    if not simulation_id:
        return 0
    try:
        with open(os.path.join(_sim_dir(simulation_id), "simulation.log"), encoding="utf-8", errors="replace") as f:
            return sum(1 for line in f if "[feed-error]" in line)
    except OSError:
        return 0


def _health_checks(
    platforms: Dict[str, Any],
    analytics: Dict[str, Any],
    configured: List[str],
    run_state: Any,
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    reasons: List[str] = []

    feed_errors = _count_feed_errors(getattr(run_state, "simulation_id", None))

    # Blind activations (any platform)
    blind = sum(p.get("blind_activations", 0) for p in platforms.values())
    acts = sum(p.get("activations", 0) for p in platforms.values())
    blind_share = (blind / acts) if acts else 0.0
    level = _level(blind_share < 0.15, warn=blind_share >= 0.05)
    checks.append(
        {
            "id": "blind_activations",
            "label": "Feed visibility",
            "level": level,
            "value": round(blind_share, 3),
            "detail": (
                f"{blind} of {acts} agent turns had no feed to read"
                + (f"; {feed_errors} feed errors in simulation.log" if feed_errors else "")
                if acts
                else "No activations logged yet"
            ),
        }
    )
    if level == "red":
        reasons.append(
            f"In {round(blind_share * 100)}% of turns the agent was shown no feed, so it could only post "
            "or do nothing. Treat how posts spread as unreliable."
        )
    elif level == "amber":
        reasons.append(
            f"In {round(blind_share * 100)}% of turns the agent was shown no feed."
        )

    # Participation
    totals = analytics.get("totals") or {}
    active = totals.get("agents_active") or 0
    known = len(configured) or totals.get("agents_total") or active
    part = (active / known) if known else 0.0
    silent = sorted(set(configured) - {a["name"] for a in analytics.get("agents") or [] if a.get("actions")})
    # Three bands: red under 30%, amber under 50%, green from 50%.
    level = _level(part >= 0.3, warn=part < 0.5)
    checks.append(
        {
            "id": "participation",
            "label": "Effective participation",
            "level": level,
            "value": round(part, 3),
            "detail": f"{active} of {known} agents acted; {len(silent)} stayed silent",
            "silent_agents": silent[:40],
        }
    )
    if level != "green":
        reasons.append(
            f"Only {active} of {known} agents posted or engaged — "
            "the crowd is thinner than the roster suggests."
        )

    # Action mix: likes vs posts (Twitter-heavy runs with 0 likes are a red flag)
    support = totals.get("support") or 0
    posts = totals.get("post") or 0
    like_ratio = (support / posts) if posts else None
    level = _level(
        like_ratio is None or like_ratio >= 0.2,
        warn=like_ratio is not None and like_ratio < 0.5,
    )
    checks.append(
        {
            "id": "action_mix",
            "label": "Action mix",
            "level": level if posts else "amber",
            "value": round(like_ratio, 3) if like_ratio is not None else None,
            "detail": (
                f"{support} support actions vs {posts} posts"
                if posts
                else "No posts yet"
            ),
        }
    )
    if posts and (like_ratio or 0) < 0.2:
        reasons.append(
            "Almost no likes/reposts relative to new posts — conversation looks like broadcasting."
        )

    # Feed degeneracy from top slot share
    top_shares = [p.get("top_slot_share", 0) for p in platforms.values() if p.get("top_slot_share")]
    top = max(top_shares) if top_shares else 0.0
    # Red from 50%, amber from 35%.
    level = _level(top < 0.5, warn=top >= 0.35)
    checks.append(
        {
            "id": "feed_degeneracy",
            "label": "Feed concentration",
            "level": level if top_shares else "amber",
            "value": top,
            "detail": (
                f"Top post filled {round(top * 100)}% of recommendation slots"
                if top_shares
                else "No refresh traces yet"
            ),
        }
    )
    if top >= 0.5:
        reasons.append(
            f"One post dominated {round(top * 100)}% of feed slots — spread is recommender-driven, not word-of-mouth."
        )

    # Branching / orphan cascades
    roots = sum(p.get("roots", 0) for p in platforms.values())
    orphans = sum(p.get("orphan_cascades", 0) for p in platforms.values())
    branching = None
    derived = sum(p.get("derived_posts", 0) for p in platforms.values())
    n_posts = sum(p.get("posts", 0) for p in platforms.values())
    if n_posts:
        branching = round(derived / n_posts, 3)
    orphan_share = (orphans / roots) if roots else 0.0
    # Red under 0.2, amber under 0.4. Most real posts draw no follow-on either, so only
    # near-zero spread is treated as a fault.
    level = _level(branching is None or branching >= 0.2, warn=branching is not None and branching < 0.4)
    checks.append(
        {
            "id": "branching",
            "label": "Cascade branching",
            "level": level if n_posts else "amber",
            "value": branching,
            "detail": (
                f"Branching factor {branching}; {orphans}/{roots} cascades never left the seed (orphans)"
                if n_posts
                else "No cascade data yet"
            ),
        }
    )
    if branching is not None and branching < 0.4:
        reasons.append(
            f"Each post produces about {branching} follow-on posts — threads mostly fizzle; "
            f"{round(orphan_share * 100)}% of cascades are orphans (seed alone)."
        )

    # Horizon coverage if we know planned rounds
    total_rounds = getattr(run_state, "total_rounds", None) or 0
    current = getattr(run_state, "current_round", None)
    if current is None:
        current = max((r.get("round", 0) for r in analytics.get("rounds") or []), default=0)
    if total_rounds and total_rounds > 0:
        cover = min(1.0, (current + 1) / total_rounds)
        # Red under 15% of the planned rounds, amber under 50%.
        level = _level(cover >= 0.15, warn=cover < 0.5)
        checks.append(
            {
                "id": "horizon",
                "label": "Horizon coverage",
                "level": level,
                "value": round(cover, 3),
                "detail": f"Round {current} of {total_rounds} planned",
            }
        )
        if cover < 0.5:
            reasons.append(
                f"Only {round(cover * 100)}% of the planned horizon has been simulated — "
                "do not read the report as a full-period forecast."
            )

    # Overall badge = worst check
    order = {"green": 0, "amber": 1, "red": 2}
    overall = "green"
    for c in checks:
        if order[c["level"]] > order[overall]:
            overall = c["level"]

    plain = {
        "green": "This run looks healthy enough to read as a simulated public.",
        "amber": "This run has warnings — use the forecast carefully.",
        "red": "This run has serious validity problems — treat conclusions as provisional.",
    }[overall]

    return {
        "overall": overall,
        "headline": plain,
        "reasons": reasons,
        "checks": checks,
        "orphan_agents": silent[:40],
        "orphan_agent_count": len(silent),
    }


def _consensus_from_analytics(analytics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lightweight 'consensus' view from support/oppose without a stance LLM.

    Approval share across agents who received any support or opposition, plus
    who the crowd amplified vs ignored.
    """
    agents = analytics.get("agents") or []
    with_signal = [a for a in agents if a.get("approval") is not None]
    if with_signal:
        mean_approval = round(
            sum(a["approval"] for a in with_signal) / len(with_signal), 3
        )
    else:
        mean_approval = None
    totals = analytics.get("totals") or {}
    support = totals.get("support") or 0
    oppose = totals.get("oppose") or 0
    denom = support + oppose
    crowd_support = round(support / denom, 3) if denom else None

    amplified = [
        {"name": a["name"], "engagement": a["engagement_received"], "approval": a["approval"]}
        for a in agents
        if a.get("engagement_received", 0) > 0
    ][:10]
    ignored = [
        {"name": a["name"], "actions": a.get("actions", 0)}
        for a in agents
        if a.get("engagement_received", 0) == 0 and a.get("actions", 0) > 0
    ][:15]

    verdict = "insufficient_signal"
    if crowd_support is None:
        verdict = "no_engagement"
    elif crowd_support >= 0.65:
        verdict = "supportive"
    elif crowd_support <= 0.35:
        verdict = "opposed"
    else:
        verdict = "split"

    plain = {
        "no_engagement": "Agents posted, but almost nobody engaged — there is no crowd consensus to read.",
        "insufficient_signal": "Not enough support/oppose actions to call a consensus.",
        "supportive": "Engagement leans supportive: likes, reposts and follows outweigh opposition.",
        "opposed": "Engagement leans opposed: dislikes and mutes outweigh support.",
        "split": "The crowd is split — support and opposition are both material.",
    }[verdict]

    return {
        "verdict": verdict,
        "plain": plain,
        "crowd_support_share": crowd_support,
        "mean_agent_approval": mean_approval,
        "support_actions": support,
        "oppose_actions": oppose,
        "amplified_agents": amplified,
        "ignored_posters": ignored,
    }


def build_dynamics(simulation_id: str) -> Dict[str, Any]:
    actions = [a.to_dict() for a in SimulationRunner.get_all_actions(simulation_id)]
    run_state = SimulationRunner.get_run_state(simulation_id)
    total_rounds = run_state.total_rounds if run_state else 0
    analytics = build_analytics(actions, total_rounds=total_rounds)
    traces = read_simulation_traces(simulation_id)
    platforms = traces.get("platforms") or {}
    configured = _load_configured_agents(simulation_id)
    health = _health_checks(platforms, analytics, configured, run_state)
    consensus = _consensus_from_analytics(analytics)

    # Cross-platform cascade rollup for the UI gauges
    rollup = {
        "roots": sum(p.get("roots", 0) for p in platforms.values()),
        "orphan_cascades": sum(p.get("orphan_cascades", 0) for p in platforms.values()),
        "derived_posts": sum(p.get("derived_posts", 0) for p in platforms.values()),
        "posts": sum(p.get("posts", 0) for p in platforms.values()),
        "branching_factor": None,
        "max_depth": max((p.get("max_depth", 0) for p in platforms.values()), default=0),
        "max_size": max((p.get("max_size", 0) for p in platforms.values()), default=0),
        "mean_virality": None,
    }
    if rollup["posts"]:
        rollup["branching_factor"] = round(rollup["derived_posts"] / rollup["posts"], 3)
    viralities = [
        p.get("mean_virality")
        for p in platforms.values()
        if p.get("mean_virality") is not None
    ]
    if viralities:
        rollup["mean_virality"] = round(sum(viralities) / len(viralities), 3)
    rollup["orphan_share"] = (
        round(rollup["orphan_cascades"] / rollup["roots"], 3) if rollup["roots"] else 0.0
    )

    # Top cascades across platforms for the forest view
    top_cascades: List[Dict[str, Any]] = []
    for p in platforms.values():
        for c in p.get("cascades") or []:
            top_cascades.append({**c, "platform": p["platform"]})
    top_cascades.sort(key=lambda c: (c["size"], c["depth"], c["virality"]), reverse=True)

    return {
        "simulation_id": simulation_id,
        "run": {
            "status": run_state.runner_status.value if run_state else None,
            "current_round": run_state.current_round if run_state else None,
            "total_rounds": total_rounds,
        },
        "health": health,
        "cascades": {
            "summary": rollup,
            "top": top_cascades[:20],
            "platforms": platforms,
        },
        "orphans": {
            "cascade_orphans": rollup["orphan_cascades"],
            "cascade_orphan_share": rollup["orphan_share"],
            "silent_agents": health.get("orphan_agents") or [],
            "silent_agent_count": health.get("orphan_agent_count") or 0,
            "plain": (
                f"{rollup['orphan_cascades']} cascades never branched (orphans). "
                f"{health.get('orphan_agent_count') or 0} rostered agents stayed silent."
            ),
        },
        "consensus": consensus,
        "analytics_totals": analytics.get("totals") or {},
    }
