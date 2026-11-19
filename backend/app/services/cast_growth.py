"""
Growing the cast beyond the names in the evidence.

The cast a run starts with is whoever the knowledge graph names. Two things
are missing from it, and this module supplies both:

1. The circle. The people immediately around the key actors: staff, customers,
   members, rivals, the reporter on the beat. They are added when the cast is
   set up, each tied to the actor they surround (their "anchor").
2. Joiners. Accounts that arrive while the run is under way, because a thread
   took off or a niche angle came up that nobody in the cast speaks for.

Both kinds are invented by the model, so they are named by role ("Season-ticket
holder, Leinster"), never given a made-up personal name, and every one carries
its origin so the product can always tell the reader which voices came from
the evidence and which were added.

This file has no imports from the rest of the app on purpose: the simulation
subprocess loads it by path (scripts/agent_spawner.py) and the backend imports
it normally (services/cast_circle.py).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

ORIGIN_EVIDENCE = "evidence"
ORIGIN_CIRCLE = "circle"
ORIGIN_JOINED = "joined"

GROWTH_FILE = "cast_growth.json"

# Defaults. A run's simulation_config.json may override them under "growth_config",
# and the environment overrides both (HIVEMIND_CIRCLE=0 switches the circle off).
DEFAULTS: Dict[str, Any] = {
    "circle": True,
    "circle_anchors": 6,       # how many key actors get a circle
    "circle_per_anchor": 2,    # people around each of them
    "join": True,
    "join_first_round": 2,     # nothing has happened before this
    "join_every": 2,           # look for newcomers every N rounds
    "join_per_wave": 3,
    "join_max": 12,            # hard cap for the whole run
}
_ENV = {
    "circle": "HIVEMIND_CIRCLE",
    "circle_anchors": "HIVEMIND_CIRCLE_ANCHORS",
    "circle_per_anchor": "HIVEMIND_CIRCLE_PER_ANCHOR",
    "join": "HIVEMIND_JOIN",
    "join_first_round": "HIVEMIND_JOIN_FIRST_ROUND",
    "join_every": "HIVEMIND_JOIN_EVERY",
    "join_per_wave": "HIVEMIND_JOIN_PER_WAVE",
    "join_max": "HIVEMIND_JOIN_MAX",
}

# Role types the model may choose from. Each is spelled so the briefing's
# keyword grouping (run_briefing.GROUPS) files it under the right group.
ROLE_TYPES = [
    "Employee", "Customer", "Fan", "Resident", "Voter", "Student", "Parent", "Worker",
    "Supplier", "Competitor", "Reporter", "Analyst", "Shareholder", "Regulator",
    "LegalAdviser", "Researcher", "UnionRep", "AdvocacyGroup", "CommunityGroup",
]
DEFAULT_ROLE_TYPE = "Person"
STANCES = ("supportive", "opposing", "neutral", "observer")

NAME_MAX = 60
BIO_MAX = 240
PERSONA_MAX = 900


def settings(config: Optional[Dict[str, Any]] = None, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Defaults, then the run's growth_config, then the environment."""
    out = dict(DEFAULTS)
    for key, value in ((config or {}).get("growth_config") or {}).items():
        if key in out and value is not None:
            out[key] = value
    env = os.environ if env is None else env
    for key, name in _ENV.items():
        raw = env.get(name)
        if raw is None or raw == "":
            continue
        if isinstance(DEFAULTS[key], bool):
            out[key] = raw.strip().lower() not in ("0", "false", "no", "off")
        else:
            try:
                out[key] = max(0, int(raw))
            except ValueError:
                pass
    for key, default in DEFAULTS.items():
        if isinstance(default, bool):
            out[key] = bool(out[key])
        else:
            try:
                out[key] = max(0, int(out[key]))
            except (TypeError, ValueError):
                out[key] = default
    out["join_every"] = max(1, out["join_every"])
    return out


ADDED_SHARE = 4  # the circle, and the joiners, may each be at most a quarter of the evidence cast


def cap_for(evidence_count: int, ceiling: int) -> int:
    """
    How many accounts may be added to a cast of this size.

    Added accounts are invented. If they outnumber the people the evidence names,
    the run is about them. Each kind is held to a quarter of the evidence cast
    (never fewer than two, never more than the configured ceiling).
    """
    return max(0, min(int(ceiling), max(2, int(evidence_count) // ADDED_SHARE)))


def norm(name: Any) -> str:
    return " ".join(str(name or "").lower().split())


def parse_json(text: str) -> Dict[str, Any]:
    """The model's reply as a dict. Tolerates a code fence and text around the object."""
    body = (text or "").strip()
    body = re.sub(r"^```(?:json)?\s*", "", body)
    body = re.sub(r"\s*```$", "", body)
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the model reply")
    data = json.loads(body[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("the model reply is not a JSON object")
    return data


# ---------------------------------------------------------------- the circle

def pick_anchors(cast: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """The actors most connected in the evidence. cast rows: {agent_id, name, degree, ...}."""
    ranked = sorted(cast, key=lambda a: (-int(a.get("degree") or 0), -len(str(a.get("summary") or "")), a["agent_id"]))
    return ranked[:max(0, limit)]


_RULES = """Rules for every account you add:
- It must be someone who would really be online talking about this, with first-hand reasons to care.
- Name it by its role, specific enough to be one voice, for example "Nvidia supply-chain manager", "Season-ticket holder, Leinster", "Local councillor, Ward 4". Do not invent a personal name and do not use the name of a real person.
- No relatives, partners or private friends of real named people.
- Do not repeat anyone already in the cast.
- "type" must be one of: {types}.
- "stance" must be one of: supportive, opposing, neutral, observer (towards the main development in the question).
- "bio" is one sentence, as it would read on their profile.
- "persona" is 60 to 100 words in the second person ("You are ..."): who they are, what they know first hand, what is at stake for them, and how they write online.
- "relation" is a few words saying how they are tied to their anchor, for example "works for", "buys from", "covers", "regulates", "competes with", "is represented by".
Return JSON only, no Markdown."""


def circle_prompt(question: str, anchors: List[Dict[str, Any]], cast_names: Iterable[str],
                  per_anchor: int, language_note: str = "") -> Tuple[str, str]:
    system = (
        "You are casting a social media simulation. The cast so far is only the people and organisations "
        "named in the evidence. Real events also pull in the people immediately around those actors, and "
        "they often decide how a story lands. Add them.\n\n"
        + _RULES.format(types=", ".join(ROLE_TYPES))
        + (f"\n\n{language_note}" if language_note else "")
    )
    lines = []
    for a in anchors:
        near = ", ".join(a.get("near") or []) or "nothing recorded"
        lines.append(
            f'- "{a["name"]}" ({a.get("entity_type") or "Unknown"}): {str(a.get("summary") or "")[:300]}\n'
            f"  Connected in the evidence to: {near}"
        )
    user = (
        f"QUESTION:\n{question.strip()}\n\n"
        f"KEY ACTORS (the anchors):\n" + "\n".join(lines) + "\n\n"
        f"ALREADY IN THE CAST (do not repeat):\n{', '.join(cast_names)}\n\n"
        f"For each anchor, add up to {per_anchor} accounts from the people immediately around it. "
        "Choose the ones whose reaction would differ from the anchor's own, and skip an anchor if no one fits.\n\n"
        'Return: {"accounts": [{"name": "...", "anchor": "<exact anchor name>", "relation": "...", '
        '"type": "...", "stance": "...", "bio": "...", "persona": "...", "profession": "...", '
        '"age": <18-80 or null for an organisation>, "why": "<one sentence: why this voice matters here>"}]}'
    )
    return system, user


# ------------------------------------------------------------------- joiners

def wave_due(round_num: int, first: int, every: int) -> bool:
    """Whether to look for newcomers at the start of this round (rounds count from 1)."""
    return round_num >= first and (round_num - first) % max(1, every) == 0


def hot_threads(actions: List[Dict[str, Any]], top: int = 6) -> List[Dict[str, Any]]:
    """
    What drew attention since the last look: posts ranked by how many reactions
    they pulled, with a sample of what was said back.

    actions: rows as written to actions.jsonl ({agent_name, action_type, action_args}).
    """
    threads: Dict[str, Dict[str, Any]] = {}

    def thread(author: str, text: str) -> Optional[Dict[str, Any]]:
        text = " ".join(str(text or "").split())
        if not text:
            return None
        key = f"{norm(author)}|{text[:120]}"
        return threads.setdefault(key, {"author": author or "someone", "text": text[:400], "reactions": 0, "replies": []})

    for a in actions:
        kind = str(a.get("action_type") or "").upper()
        args = a.get("action_args") or {}
        who = str(a.get("agent_name") or "")
        if kind == "CREATE_POST":
            thread(who, args.get("content"))
            continue
        target_text = args.get("post_content") or args.get("original_content") or args.get("quoted_content")
        target_author = args.get("post_author_name") or args.get("original_author_name") or args.get("quoted_author_name") or ""
        t = thread(target_author, target_text) if target_text else None
        if t is None:
            continue
        t["reactions"] += 1
        said = args.get("content") or args.get("quote_content")
        if said and len(t["replies"]) < 3:
            t["replies"].append({"by": who, "text": " ".join(str(said).split())[:240]})
    ranked = sorted(threads.values(), key=lambda t: (-t["reactions"], -len(t["replies"])))
    return ranked[:top]


def wave_prompt(question: str, cast: List[Dict[str, Any]], hot: List[Dict[str, Any]], limit: int,
                round_num: int, language_note: str = "") -> Tuple[str, str]:
    system = (
        "You are running a social media simulation that is already under way. In a real event the "
        "conversation does not stay among the people who started it: as threads take off, the people "
        "immediately around the actors getting attention are pulled in, and so are people affected by "
        "narrow angles that nobody present speaks for. Decide who would join now.\n\n"
        "Only add an account if something in the recent activity would plausibly bring it in. "
        'If nothing would, return {"accounts": []}. Fewer, well-motivated accounts are better than many.\n\n'
        + _RULES.format(types=", ".join(ROLE_TYPES))
        + '\n- "anchor" is the exact name of the cast member they are closest to, or null if they are '
          "drawn in by a topic and not by a person.\n"
          '- "why" is one sentence naming the post or angle that brings them in now.'
        + (f"\n\n{language_note}" if language_note else "")
    )
    roster = "\n".join(f'- "{c["name"]}" ({c.get("entity_type") or "Unknown"})' for c in cast)
    if hot:
        feed = "\n".join(
            f'- {t["author"]} ({t["reactions"]} reactions): "{t["text"]}"'
            + "".join(f'\n    reply from {r["by"]}: "{r["text"]}"' for r in t["replies"])
            for t in hot
        )
    else:
        feed = "(nothing new was posted)"
    user = (
        f"QUESTION:\n{question.strip()}\n\n"
        f"CAST SO FAR:\n{roster}\n\n"
        f"WHAT DREW ATTENTION SINCE THE LAST CHECK (now starting round {round_num}):\n{feed}\n\n"
        f"Add up to {limit} accounts that would join the conversation now.\n\n"
        'Return: {"accounts": [{"name": "...", "anchor": "<exact cast name or null>", "relation": "...", '
        '"type": "...", "stance": "...", "bio": "...", "persona": "...", "profession": "...", '
        '"age": <18-80 or null for an organisation>, "why": "..."}]}'
    )
    return system, user


# ------------------------------------------------------- validating the reply

def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit].strip()


def parse_accounts(
    result: Dict[str, Any],
    cast: List[Dict[str, Any]],
    limit: int,
    per_anchor: Optional[int] = None,
    require_anchor: bool = False,
) -> List[Dict[str, Any]]:
    """
    Keep only the accounts that are usable: named, not already cast, with a
    persona, tied to a real cast member where an anchor is given.

    cast rows: {agent_id, name}. Returns rows ready for agent_config_row().
    """
    by_name = {norm(c["name"]): c for c in cast}
    taken = set(by_name)
    per: Dict[int, int] = {}
    rows: List[Dict[str, Any]] = []
    accounts = result.get("accounts") if isinstance(result, dict) else None
    for item in accounts if isinstance(accounts, list) else []:
        if len(rows) >= limit:
            break
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"), NAME_MAX)
        persona = _text(item.get("persona"), PERSONA_MAX)
        if not name or not persona or norm(name) in taken:
            continue
        anchor = by_name.get(norm(item.get("anchor"))) if item.get("anchor") else None
        if anchor is None and require_anchor:
            continue
        if anchor is not None and per_anchor is not None:
            if per.get(anchor["agent_id"], 0) >= per_anchor:
                continue
            per[anchor["agent_id"]] = per.get(anchor["agent_id"], 0) + 1
        role = str(item.get("type") or "").strip()
        role = next((t for t in ROLE_TYPES if t.lower() == role.lower()), DEFAULT_ROLE_TYPE)
        stance = str(item.get("stance") or "").strip().lower()
        try:
            age = int(item.get("age")) if item.get("age") is not None else None
        except (TypeError, ValueError):
            age = None
        if age is not None and not 18 <= age <= 90:
            age = None
        rows.append({
            "name": name,
            "entity_type": role,
            "anchor_agent_id": anchor["agent_id"] if anchor else None,
            "anchor_name": anchor["name"] if anchor else None,
            "relation": _text(item.get("relation"), 60),
            "stance": stance if stance in STANCES else "neutral",
            "bio": _text(item.get("bio"), BIO_MAX) or name,
            "persona": persona,
            "profession": _text(item.get("profession"), 80),
            "age": age,
            "why": _text(item.get("why"), 240),
        })
        taken.add(norm(name))
    return rows


# ------------------------------------------------- rows for the run's files

def username_for(name: str, agent_id: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:24] or "account"
    return f"{slug}_{agent_id}"


def agent_config_row(row: Dict[str, Any], agent_id: int, origin: str, joined_round: int = 0,
                     active_hours: Optional[List[int]] = None) -> Dict[str, Any]:
    """One entry for simulation_config.json's agent_configs."""
    person = row.get("age") is not None
    return {
        "agent_id": agent_id,
        "entity_uuid": "",
        "entity_name": row["name"],
        "entity_type": row["entity_type"],
        # Newcomers act in the round they arrive (the runner sees to that); after it they are
        # a little more engaged than the circle, and neither is louder than a named actor.
        "activity_level": 0.6 if origin == ORIGIN_JOINED else (0.5 if person else 0.4),
        "posts_per_hour": 0.5,
        "comments_per_hour": 1.0,
        "active_hours": list(active_hours) if active_hours else list(range(24)),
        "response_delay_min": 5,
        "response_delay_max": 60,
        "sentiment_bias": {"supportive": 0.4, "opposing": -0.4}.get(row.get("stance"), 0.0),
        "stance": row.get("stance") or "neutral",
        "influence_weight": 0.8,
        "origin": origin,
        "anchor_agent_id": row.get("anchor_agent_id"),
        "anchor_name": row.get("anchor_name"),
        "relation": row.get("relation") or "",
        "why": row.get("why") or "",
        "joined_round": joined_round,
    }


def profile_row(row: Dict[str, Any], agent_id: int) -> Dict[str, Any]:
    """One entry for reddit_profiles.json (the profile file every reader uses)."""
    person = row.get("age") is not None
    out = {
        "user_id": agent_id,
        "username": username_for(row["name"], agent_id),
        "name": row["name"],
        "bio": row["bio"],
        "persona": row["persona"],
        "karma": 500,
        "age": row["age"] if person else 30,
        "gender": "unspecified" if person else "other",
        "mbti": "ISTJ",
        "country": "",
    }
    if row.get("profession"):
        out["profession"] = row["profession"]
    return out


def split_original(config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[int]]:
    """
    Remove accounts that joined during an earlier run of the same simulation,
    so a rerun starts from the cast that was set up. Returns the removed ids.
    """
    kept, removed = [], []
    for cfg in config.get("agent_configs") or []:
        if cfg.get("origin") == ORIGIN_JOINED:
            removed.append(cfg.get("agent_id"))
        else:
            kept.append(cfg)
    config["agent_configs"] = kept
    return config, removed


def first_busy_hour(config: Dict[str, Any]) -> int:
    """
    The hour of day a run starts at.

    Round 1 used to be midnight, when almost nobody is scheduled to be awake, so a
    run capped at ten rounds spent seven of them empty. A story starts when people
    are there to see it: the first hour at which at least half the cast is active.
    time_config.start_hour overrides it.
    """
    start = (config.get("time_config") or {}).get("start_hour")
    if isinstance(start, int) and not isinstance(start, bool) and 0 <= start <= 23:
        return start
    agents = config.get("agent_configs") or []
    for hour in range(24):
        awake = sum(1 for a in agents if hour in a.get("active_hours", range(8, 23)))
        if agents and awake * 2 >= len(agents):
            return hour
    return 0


def write_json(path: str, data: Any) -> None:
    """Replace the file in one step, so a reader never sees half of it."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
