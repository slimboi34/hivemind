"""
Hivemind simulation analytics.

Read-only aggregation over the action logs a simulation already writes
(uploads/simulations/<id>/{twitter,reddit}/actions.jsonl). Nothing here feeds
back into the simulation, the knowledge graph or the report agent, so it cannot
change what Hivemind predicts. It only reshapes existing results for the
Analytics view: activity per round, an agent interaction network, influence
rankings and the most-engaged posts.
"""

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

# How each OASIS action type is grouped. Interactions (support/reply/oppose)
# point from the acting agent to the author of the content they acted on.
POST = "post"
SUPPORT = "support"
REPLY = "reply"
OPPOSE = "oppose"
PASSIVE = "passive"

CATEGORIES = [SUPPORT, OPPOSE, REPLY, POST, PASSIVE]
INTERACTION_KINDS = [SUPPORT, OPPOSE, REPLY]

ACTION_CATEGORY = {
    "CREATE_POST": POST,
    "LIKE_POST": SUPPORT,
    "REPOST": SUPPORT,
    "QUOTE_POST": SUPPORT,
    "LIKE_COMMENT": SUPPORT,
    "FOLLOW": SUPPORT,
    "CREATE_COMMENT": REPLY,
    "DISLIKE_POST": OPPOSE,
    "DISLIKE_COMMENT": OPPOSE,
    "MUTE": OPPOSE,
}

# Actions that are logged but are not part of the simulated social activity.
EXCLUDED_ACTIONS = {"INTERVIEW"}

# Which action_args field names the agent whose content was acted on.
TARGET_FIELD = {
    "LIKE_POST": "post_author_name",
    "DISLIKE_POST": "post_author_name",
    "CREATE_COMMENT": "post_author_name",
    "REPOST": "original_author_name",
    "QUOTE_POST": "original_author_name",
    "LIKE_COMMENT": "comment_author_name",
    "DISLIKE_COMMENT": "comment_author_name",
    "FOLLOW": "target_user_name",
    "MUTE": "target_user_name",
}

# Engagement on a post, by action type -> counter name in the post record.
POST_ENGAGEMENT = {
    "LIKE_POST": "likes",
    "DISLIKE_POST": "dislikes",
    "REPOST": "reposts",
    "QUOTE_POST": "quotes",
    "CREATE_COMMENT": "comments",
}

TOP_POSTS_LIMIT = 15


def categorize(action_type: str) -> str:
    return ACTION_CATEGORY.get(action_type, PASSIVE)


def _zero_counts(keys: Iterable[str]) -> Dict[str, int]:
    return {k: 0 for k in keys}


def _post_target(action_type: str, args: Dict[str, Any]) -> Tuple[Optional[Any], str, str]:
    """Return (post_id, author, content) of the post an engagement action points at."""
    if action_type in ("REPOST", "QUOTE_POST"):
        return (
            args.get("quoted_id") if action_type == "QUOTE_POST" else None,
            args.get("original_author_name") or "",
            args.get("original_content") or "",
        )
    return args.get("post_id"), args.get("post_author_name") or "", args.get("post_content") or ""


def build_analytics(actions: List[Dict[str, Any]], total_rounds: int = 0) -> Dict[str, Any]:
    """
    Aggregate raw action dicts (AgentAction.to_dict() shape) into analytics.

    Args:
        actions: every logged action of one simulation, any order.
        total_rounds: planned rounds from the run state, so the round axis
            covers the whole run even before late rounds have actions.
    """
    actions = [a for a in actions if a.get("action_type") not in EXCLUDED_ACTIONS]
    actions.sort(key=lambda a: (a.get("round_num", 0), a.get("timestamp", "")))

    max_round = max([a.get("round_num", 0) for a in actions] + [max(total_rounds - 1, 0)])
    rounds = [
        {"round": r, **_zero_counts(CATEGORIES), "total": 0, "twitter": 0, "reddit": 0, "active_agents": 0}
        for r in range(max_round + 1)
    ]
    active_by_round: Dict[int, set] = defaultdict(set)

    agents: Dict[str, Dict[str, Any]] = {}

    def agent(name: str, agent_id: Optional[int] = None) -> Dict[str, Any]:
        rec = agents.get(name)
        if rec is None:
            rec = agents[name] = {
                "name": name,
                "agent_id": agent_id,
                "actions": 0,
                "twitter": 0,
                "reddit": 0,
                "first_round": None,
                "given": _zero_counts(CATEGORIES),
                "received": _zero_counts(INTERACTION_KINDS),
                "_engagers": set(),
            }
        if rec["agent_id"] is None and agent_id is not None:
            rec["agent_id"] = agent_id
        return rec

    edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    self_interactions = 0
    action_types: Dict[str, int] = defaultdict(int)

    posts: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    post_ids: Dict[Tuple[str, Any], Tuple[str, str, str]] = {}

    def post(platform: str, author: str, content: str, round_num: int,
             post_id: Any = None) -> Optional[Dict[str, Any]]:
        if post_id is not None and (platform, post_id) in post_ids:
            return posts[post_ids[(platform, post_id)]]
        content = (content or "").strip()
        if not author or not content:
            return None
        key = (platform, author, content)
        rec = posts.get(key)
        if rec is None:
            rec = posts[key] = {
                "platform": platform,
                "author": author,
                "content": content,
                "round": round_num,
                "likes": 0,
                "dislikes": 0,
                "reposts": 0,
                "quotes": 0,
                "comments": 0,
            }
        if post_id is not None:
            post_ids[(platform, post_id)] = key
        return rec

    for a in actions:
        action_type = a.get("action_type", "")
        name = a.get("agent_name") or f"Agent_{a.get('agent_id', '?')}"
        platform = a.get("platform") or ""
        round_num = int(a.get("round_num", 0) or 0)
        args = a.get("action_args") or {}
        category = categorize(action_type)

        action_types[action_type] += 1

        row = rounds[round_num]
        row[category] += 1
        row["total"] += 1
        if platform in ("twitter", "reddit"):
            row[platform] += 1
        active_by_round[round_num].add(name)

        src = agent(name, a.get("agent_id"))
        src["actions"] += 1
        if platform in ("twitter", "reddit"):
            src[platform] += 1
        if src["first_round"] is None:
            src["first_round"] = round_num
        src["given"][category] += 1

        if action_type == "CREATE_POST":
            post(platform, name, args.get("content", ""), round_num, args.get("post_id"))

        if action_type in POST_ENGAGEMENT:
            pid, author, content = _post_target(action_type, args)
            target_post = post(platform, author, content, round_num, pid)
            if target_post is not None:
                target_post[POST_ENGAGEMENT[action_type]] += 1

        target_name = args.get(TARGET_FIELD.get(action_type, ""), "") if category in INTERACTION_KINDS else ""
        if not target_name:
            continue
        if target_name == name:
            self_interactions += 1
            continue

        tgt = agent(target_name)
        tgt["received"][category] += 1
        tgt["_engagers"].add(name)

        edge = edges.get((name, target_name, category))
        if edge is None:
            edge = edges[(name, target_name, category)] = {
                "source": name,
                "target": target_name,
                "kind": category,
                "weight": 0,
                "first_round": round_num,
                "by_round": defaultdict(int),
            }
        edge["weight"] += 1
        edge["by_round"][round_num] += 1

    for r, names in active_by_round.items():
        rounds[r]["active_agents"] = len(names)

    agent_list = []
    for rec in agents.values():
        received = rec["received"]
        support, oppose = received[SUPPORT], received[OPPOSE]
        rec["reach"] = len(rec.pop("_engagers"))
        rec["engagement_received"] = sum(received.values())
        # Share of support among support + opposition received; None when neither.
        rec["approval"] = round(support / (support + oppose), 3) if (support + oppose) else None
        agent_list.append(rec)
    agent_list.sort(key=lambda r: (r["engagement_received"], r["reach"], r["actions"]), reverse=True)

    edge_list = []
    for e in edges.values():
        e["by_round"] = {str(k): v for k, v in sorted(e["by_round"].items())}
        edge_list.append(e)
    edge_list.sort(key=lambda e: (e["first_round"], e["source"], e["target"], e["kind"]))

    post_list = []
    for p in posts.values():
        p["engagement"] = p["likes"] + p["dislikes"] + p["reposts"] + p["quotes"] + p["comments"]
        post_list.append(p)
    post_list.sort(key=lambda p: (p["engagement"], -p["round"]), reverse=True)

    totals = {
        "actions": len(actions),
        "agents_active": sum(1 for r in agent_list if r["actions"] > 0),
        "agents_total": len(agent_list),
        "rounds": max_round + 1 if (actions or total_rounds) else 0,
        "posts": len(posts),
        "interactions": sum(e["weight"] for e in edge_list),
        "self_interactions": self_interactions,
        "twitter": sum(r["twitter"] for r in rounds),
        "reddit": sum(r["reddit"] for r in rounds),
        **{c: sum(r[c] for r in rounds) for c in CATEGORIES},
    }

    return {
        "categories": CATEGORIES,
        "interaction_kinds": INTERACTION_KINDS,
        "totals": totals,
        "rounds": rounds,
        "agents": agent_list,
        "edges": edge_list,
        "top_posts": [p for p in post_list if p["engagement"] > 0][:TOP_POSTS_LIMIT],
        "action_types": dict(sorted(action_types.items(), key=lambda kv: kv[1], reverse=True)),
    }
