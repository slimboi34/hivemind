"""
Hivemind briefing: what a run means, in plain language.

"What happened" (run_recap) tells the story of a run in time order. The
briefing answers the questions a decision-maker asks next:

- What is the bottom line?
- Where do the simulated voices agree, and where do they split?
- How did each kind of actor react (companies, government, investors, media,
  the public), and what would they likely do next?
- How would each company react?
- What should I watch?

Like the recap it has two layers:

1. Facts (deterministic). Every simulated person is placed in a group using
   the entity type the run already gave them. Each group gets counts, how
   warmly its posts were received, and verbatim posts.
2. Reading (prose). An LLM interprets those facts only. A template writes the
   same shape without an LLM, so a briefing always exists.

Read-only over the run's outputs: it never feeds back into the simulation,
the graph or the report agent, so it cannot change what Hivemind predicts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .run_recap import _duration_label, _lock_for, _read_json, _snippet, _tone
from .simulation_analytics import EXCLUDED_ACTIONS, OPPOSE, PASSIVE, POST, REPLY, SUPPORT, TARGET_FIELD, categorize

BRIEFING_FILE = "briefing.json"
BRIEFING_VERSION = 1

SAID_PER_GROUP = 6
VOICES_PER_GROUP = 5
COMPANIES_SHOWN = 12
SAID_PER_COMPANY = 2
BACKED_POSTS_SHOWN = 6
PAIRS_SHOWN = 8

PLATFORM_NAMES = {"twitter": "Info Plaza", "reddit": "Topic Community"}
STANCES = ("supportive", "critical", "cautious", "divided", "neutral", "quiet")
STRENGTHS = ("strong", "moderate", "weak")

# Broad groups a reader recognises. A run's entity types are designed per
# project by the ontology step, so they are matched by keyword, first hit wins.
# Order matters: "InvestmentAnalystFirm" is an investor, "LegalFirm" an expert,
# "RegulatoryAgency" government, before the generic company words are tried.
GROUPS: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("media", "Media", ("media", "news", "press", "journal", "outlet", "reporter", "broadcast", "publication")),
    ("investors", "Investors and analysts", ("invest", "analyst", "fund", "bank", "trader", "shareholder", "broker", "venture")),
    ("government", "Government and regulators", (
        # Not a bare "official": a RugbyOfficial or MatchOfficial is not the government.
        "government", "politic", "legislat", "committee", "regulat", "agency", "ministry",
        "court", "senat", "congress", "parliament", "authority", "department", "military",
    )),
    ("experts", "Experts and institutions", (
        "legal", "law", "universit", "professor", "expert", "research", "academ", "scien", "ngo",
        "nonprofit", "thinktank", "institut", "union", "association", "advocacy",
    )),
    ("companies", "Companies and executives", (
        "company", "corporat", "business", "brand", "firm", "enterprise", "startup", "executive",
        "ceo", "founder", "manufactur", "vendor", "supplier", "competitor", "retailer", "platform",
    )),
    ("public", "Public voices", (
        "person", "people", "citizen", "student", "consumer", "customer", "user", "public", "resident",
        "fan", "employee", "worker", "individual", "influencer", "creator", "parent", "voter",
    )),
    ("organizations", "Organisations", ("organization", "organisation", "group", "community")),
]
GROUP_LABEL = {key: label for key, label, _ in GROUPS}
GROUP_LABEL["other"] = "Other voices"
GROUP_ORDER = [key for key, _, _ in GROUPS] + ["other"]


def group_for(entity_type: Optional[str]) -> str:
    """Broad group key for a run's entity type name (e.g. "PublicCompany")."""
    t = (entity_type or "").lower()
    if not t:
        return "other"
    for key, _, words in GROUPS:
        if any(w in t for w in words):
            return key
    return "other"


def type_label(entity_type: Optional[str]) -> str:
    """"InvestmentAnalystFirm" -> "Investment analyst firm"."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", entity_type or "").replace("_", " ").split()
    return " ".join(words).capitalize() if words else "Unspecified"


# --------------------------------------------------------------------------- #
# Facts
# --------------------------------------------------------------------------- #

def cast_note(mix: Dict[str, Any]) -> str:
    """One plain sentence on who was added to the cast. Empty when nobody was."""
    circle, joined = mix.get("circle") or 0, mix.get("joined") or 0
    if not circle + joined:
        return ""
    parts = []
    if circle:
        parts.append(f"{circle} {'person' if circle == 1 else 'people'} around the key actors")
    if joined:
        parts.append(f"{joined} who {'was' if joined == 1 else 'were'} drawn in as the conversation grew")
    share = round((mix.get("added_share_of_posts") or 0) * 100)
    return (
        f"{mix.get('evidence') or 0} of these voices are named in the evidence. Hivemind added "
        f"{' and '.join(parts)}, described by role. Together the added voices wrote {share}% of the posts and replies."
    )


def build_briefing_facts(
    actions: List[Dict[str, Any]],
    roster: List[Dict[str, Any]],
    *,
    requirement: str = "",
    minutes_per_round: int = 60,
    run: Optional[Dict[str, Any]] = None,
    health: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Group the run's people and summarise what each group said and received.

    actions: AgentAction.to_dict() rows. roster: simulation_config agent_configs
    rows (entity_name, entity_type, stance). Pure function, no disk or network.
    """
    run = dict(run or {})
    actions = [a for a in actions if a.get("action_type") not in EXCLUDED_ACTIONS]
    actions.sort(key=lambda a: (int(a.get("round_num", 0) or 0), a.get("timestamp", "")))

    etype: Dict[str, str] = {}
    configured_stance: Dict[str, str] = {}
    origin: Dict[str, str] = {}
    for row in roster or []:
        name = str(row.get("entity_name") or "").strip()
        if not name:
            continue
        origin[name] = row.get("origin") if row.get("origin") in ("circle", "joined") else "evidence"
        etype[name] = str(row.get("entity_type") or "")
        if row.get("stance"):
            configured_stance[name] = str(row["stance"])

    def group_of(name: str) -> str:
        return group_for(etype.get(name))

    people: Dict[str, Dict[str, Any]] = {}

    def person(name: str) -> Dict[str, Any]:
        if name not in people:
            people[name] = {
                "name": name, "type": etype.get(name, ""), "group": group_of(name),
                "posts": 0, "replies": 0, "gave_support": 0, "gave_oppose": 0,
                "got_support": 0, "got_oppose": 0, "got_replies": 0, "texts": [],
            }
        return people[name]

    for name in etype:
        person(name)

    # One record per distinct post text per author (seeds are posted on both platforms).
    posts: Dict[Tuple[str, str], Dict[str, Any]] = {}
    pair_support: Dict[Tuple[str, str], int] = defaultdict(int)
    pair_oppose: Dict[Tuple[str, str], int] = defaultdict(int)
    last_round = 0
    support_total = oppose_total = 0

    for a in actions:
        name = str(a.get("agent_name") or "").strip()
        kind = categorize(a.get("action_type", ""))
        if not name or kind == PASSIVE:
            continue
        args = a.get("action_args") or {}
        rnd = int(a.get("round_num", 0) or 0)
        last_round = max(last_round, rnd)
        p = person(name)
        atype = a.get("action_type", "")

        text = ""
        if atype == "CREATE_POST":
            text = args.get("content") or ""
        elif atype == "QUOTE_POST":
            text = args.get("quote_content") or ""
        elif atype == "CREATE_COMMENT":
            text = args.get("content") or ""
        text = str(text).strip()

        if kind == POST or (atype == "QUOTE_POST" and text):
            p["posts"] += 1
        elif kind == REPLY:
            p["replies"] += 1
        if text:
            key = (name, text)
            if key not in posts:
                posts[key] = {
                    "author": name, "group": p["group"], "platform": a.get("platform") or "",
                    "text": _snippet(text), "round": rnd, "support": 0, "oppose": 0, "replies": 0,
                    "is_reply": kind == REPLY,
                }
                p["texts"].append(posts[key])

        target = str(args.get(TARGET_FIELD.get(atype, "")) or "").strip()
        if not target or target == name:
            continue
        tp = person(target)
        target_text = str(
            args.get("post_content") or args.get("original_content") or args.get("comment_content") or ""
        ).strip()
        rec = posts.get((target, target_text)) if target_text else None
        if kind == SUPPORT:
            p["gave_support"] += 1
            tp["got_support"] += 1
            support_total += 1
            pair_support[(p["group"], tp["group"])] += 1
            if rec:
                rec["support"] += 1
        elif kind == OPPOSE:
            p["gave_oppose"] += 1
            tp["got_oppose"] += 1
            oppose_total += 1
            pair_oppose[(p["group"], tp["group"])] += 1
            if rec:
                rec["oppose"] += 1
        elif kind == REPLY:
            tp["got_replies"] += 1
            if rec:
                rec["replies"] += 1

    def reach(rec: Dict[str, Any]) -> int:
        return rec["support"] + rec["oppose"] + rec["replies"]

    def said_view(rec: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "author": rec["author"], "platform": rec["platform"], "text": rec["text"],
            "approving": rec["support"], "disapproving": rec["oppose"], "replies": rec["replies"],
        }

    def pick_said(members: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """Most-reacted-to posts first, then one post each from other members, so a
        group is not represented only by its loudest voice."""
        pool = sorted(
            (t for m in members for t in m["texts"]),
            key=lambda r: (-reach(r), r["is_reply"], r["round"]),
        )
        chosen: List[Dict[str, Any]] = []
        seen_authors: Dict[str, int] = defaultdict(int)
        for rec in pool:
            if len(chosen) >= limit:
                break
            if seen_authors[rec["author"]] >= 2:
                continue
            chosen.append(rec)
            seen_authors[rec["author"]] += 1
        return [said_view(r) for r in chosen]

    groups: List[Dict[str, Any]] = []
    for key in GROUP_ORDER:
        members = [p for p in people.values() if p["group"] == key]
        if not members:
            continue
        active = [m for m in members if m["posts"] + m["replies"] + m["gave_support"] + m["gave_oppose"] > 0]
        got_s = sum(m["got_support"] for m in members)
        got_o = sum(m["got_oppose"] for m in members)
        stances: Dict[str, int] = defaultdict(int)
        for m in members:
            if m["name"] in configured_stance:
                stances[configured_stance[m["name"]]] += 1
        voices = sorted(
            (m for m in members if m["posts"] + m["replies"] > 0),
            key=lambda m: (-(m["got_support"] + m["got_oppose"] + m["got_replies"]), -(m["posts"] + m["replies"]), m["name"]),
        )
        groups.append({
            "key": key,
            "label": GROUP_LABEL[key],
            "kinds": sorted({type_label(m["type"]) for m in members if m["type"]}),
            "members": len(members),
            "active": len(active),
            "posts": sum(m["posts"] for m in members),
            "replies": sum(m["replies"] for m in members),
            "approving_received": got_s,
            "disapproving_received": got_o,
            "replies_received": sum(m["got_replies"] for m in members),
            "reception": _tone(got_s, got_o),
            "approving_given": sum(m["gave_support"] for m in members),
            "disapproving_given": sum(m["gave_oppose"] for m in members),
            "starting_stances": dict(sorted(stances.items())),
            "voices": [
                {"name": m["name"], "kind": type_label(m["type"]), "posts": m["posts"], "replies": m["replies"],
                 "reactions_received": m["got_support"] + m["got_oppose"] + m["got_replies"]}
                for m in voices[:VOICES_PER_GROUP]
            ],
            "silent": sorted(m["name"] for m in members if m not in active)[:8],
            "said": pick_said(members, SAID_PER_GROUP),
        })

    company_people = sorted(
        (p for p in people.values() if p["group"] == "companies" and p["texts"]),
        key=lambda m: (-(m["got_support"] + m["got_oppose"] + m["got_replies"]), -(m["posts"] + m["replies"]), m["name"]),
    )
    companies = [
        {
            "name": m["name"],
            "kind": type_label(m["type"]),
            "posts": m["posts"],
            "replies": m["replies"],
            "approving_received": m["got_support"],
            "disapproving_received": m["got_oppose"],
            "reception": _tone(m["got_support"], m["got_oppose"]),
            "starting_stance": configured_stance.get(m["name"]),
            "said": pick_said([m], SAID_PER_COMPANY),
        }
        for m in company_people[:COMPANIES_SHOWN]
    ]

    backed = sorted(
        (r for r in posts.values() if r["support"] > 0),
        key=lambda r: (-r["support"], r["round"], r["author"]),
    )[:BACKED_POSTS_SHOWN]
    pushed_back = sorted(
        (r for r in posts.values() if r["oppose"] > 0),
        key=lambda r: (-r["oppose"], r["round"], r["author"]),
    )[:3]

    pairs = []
    for (src, dst), n in sorted(pair_support.items(), key=lambda kv: (-kv[1], kv[0])):
        pairs.append({
            "from": GROUP_LABEL[src], "to": GROUP_LABEL[dst],
            "approving": n, "disapproving": pair_oppose.get((src, dst), 0),
        })
    for (src, dst), n in sorted(pair_oppose.items(), key=lambda kv: (-kv[1], kv[0])):
        if (src, dst) not in pair_support:
            pairs.append({"from": GROUP_LABEL[src], "to": GROUP_LABEL[dst], "approving": 0, "disapproving": n})

    # Accounts Hivemind added (the circle around key actors, and mid-run joiners) are
    # invented, so the reader is always told how many there were and how loud they were.
    written = {n: p["posts"] + p["replies"] for n, p in people.items()}
    added_written = sum(v for n, v in written.items() if origin.get(n, "evidence") != "evidence")
    cast_mix = {
        "evidence": sum(1 for o in origin.values() if o == "evidence"),
        "circle": sum(1 for o in origin.values() if o == "circle"),
        "joined": sum(1 for o in origin.values() if o == "joined"),
        "added_share_of_posts": round(added_written / sum(written.values()), 2) if sum(written.values()) else 0.0,
        "added_names": sorted(n for n, o in origin.items() if o != "evidence"),
    }
    cast_mix["note"] = cast_note(cast_mix)

    active_people = sum(g["active"] for g in groups)
    roster_size = len(etype) or len(people)
    status = run.get("status")
    finished = status in ("completed", "stopped") or bool(run.get("ready_for_report"))
    health = health or {}
    return {
        "question": (requirement or "").strip(),
        "run": {
            "status": status,
            "finished": finished,
            "duration": _duration_label(last_round * max(int(minutes_per_round or 60), 1)),
            "people_total": roster_size,
            "people_active": active_people,
            "cast": cast_mix,
            "posts": sum(g["posts"] for g in groups),
            "replies": sum(g["replies"] for g in groups),
            "approving": support_total,
            "disapproving": oppose_total,
            "reception": _tone(support_total, oppose_total),
        },
        "groups": groups,
        "companies": companies,
        "most_backed_posts": [dict(said_view(r), group=GROUP_LABEL[r["group"]]) for r in backed],
        "most_disputed_posts": [dict(said_view(r), group=GROUP_LABEL[r["group"]]) for r in pushed_back],
        "who_backed_whom": pairs[:PAIRS_SHOWN],
        "caveats": {
            "level": health.get("overall") or "unknown",
            "headline": health.get("headline") or "",
            "reasons": list(health.get("reasons") or [])[:4],
        },
    }


def facts_fingerprint(facts: Dict[str, Any]) -> str:
    slim = dict(facts, run={k: v for k, v in facts["run"].items() if k != "status"})
    return hashlib.sha1(json.dumps(slim, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Confidence (deterministic)
# --------------------------------------------------------------------------- #

def confidence_for(facts: Dict[str, Any]) -> Dict[str, str]:
    """How much weight this run can bear, from the run's own health checks."""
    run, caveats = facts["run"], facts["caveats"]
    total, active = run.get("people_total") or 0, run.get("people_active") or 0
    share = active / total if total else 0
    writing = (run.get("posts") or 0) + (run.get("replies") or 0)
    level = {"green": "high", "amber": "medium", "red": "low"}.get(caveats.get("level"), "medium")
    if writing < 20 or share < 0.3:
        level = "low"
    elif level == "high" and share < 0.6:
        level = "medium"
    if not run.get("finished"):
        level = "low"
    why = []
    if not run.get("finished"):
        why.append("The run has not finished, so this reading can still change.")
    why.append(f"{active} of {total} simulated people took part, writing {writing} posts and replies.")
    if caveats.get("headline") and caveats.get("level") in ("amber", "red"):
        why.append(caveats["headline"].rstrip(".") + ".")
    label = {"high": "Solid", "medium": "Directional", "low": "Thin"}[level]
    return {"level": level, "label": label, "why": " ".join(why)}


# --------------------------------------------------------------------------- #
# Template reading (no LLM)
# --------------------------------------------------------------------------- #

def _pct(x: Optional[float]) -> str:
    return "–" if x is None else f"{round(x * 100)}%"


def _stance_from_reception(g: Dict[str, Any]) -> str:
    if g["posts"] + g["replies"] == 0:
        return "quiet"
    stances = g.get("starting_stances") or {}
    if stances:
        top = max(stances.items(), key=lambda kv: kv[1])[0].lower()
        if "support" in top:
            return "supportive"
        if "oppos" in top or "critic" in top:
            return "critical"
        if "observ" in top or "caut" in top:
            return "cautious"
    return "neutral"


def template_reading(facts: Dict[str, Any]) -> Dict[str, Any]:
    run = facts["run"]
    groups = facts["groups"]
    writing = [g for g in groups if g["posts"] + g["replies"] > 0]
    loudest = max(writing, key=lambda g: g["posts"] + g["replies"], default=None)
    warmest = max(
        (g for g in writing if g["reception"] is not None),
        key=lambda g: (g["reception"], g["approving_received"]), default=None,
    )

    if not writing:
        bottom = "Nobody has written anything in this run yet, so there is nothing to read."
    else:
        bottom = (
            f"Across {run['duration']}, {run['people_active']} of {run['people_total']} simulated people took part. "
            f"{loudest['label']} wrote the most"
            + (f", and reactions to posts were {_pct(run['reception'])} approving." if run["reception"] is not None
               else ", and posts drew almost no reactions.")
        )

    means = []
    if warmest:
        means.append(
            f"{warmest['label']} were received most warmly: {_pct(warmest['reception'])} of reactions to their posts were approving."
        )
    quiet = [g["label"] for g in groups if g["posts"] + g["replies"] == 0]
    if quiet:
        means.append(f"{', '.join(quiet)} stayed silent, so this run says nothing about how they would react.")
    if facts["most_backed_posts"]:
        top = facts["most_backed_posts"][0]
        means.append(f"The most-backed post came from {top['author']} ({top['group']}), with {top['approving']} approving reactions.")

    consensus = []
    for post in facts["most_backed_posts"][:3]:
        consensus.append({
            "point": f"{post['author']}'s post drew {post['approving']} approving reactions: {post['text']}",
            "held_by": [post["group"]],
            "strength": "moderate" if post["approving"] >= 3 else "weak",
        })
    splits = [
        {
            "issue": f"{post['author']}'s post drew {post['disapproving']} disapproving reactions: {post['text']}",
            "side_a": f"{post['approving']} approving", "side_b": f"{post['disapproving']} disapproving",
        }
        for post in facts["most_disputed_posts"][:2]
    ]

    group_readings = []
    for g in groups:
        if g["posts"] + g["replies"] == 0:
            reaction = f"None of the {g['members']} {g['label'].lower()} in this run wrote anything."
        else:
            names = ", ".join(v["name"] for v in g["voices"][:3])
            reaction = (
                f"{g['active']} of {g['members']} took part, writing {g['posts']} posts and {g['replies']} replies. "
                f"The most-heard voices were {names}."
                + (f" Reactions to their posts were {_pct(g['reception'])} approving." if g["reception"] is not None else "")
            )
        group_readings.append({
            "key": g["key"], "stance": _stance_from_reception(g), "reaction": reaction, "likely_next": "",
        })

    companies = [
        {
            "name": c["name"],
            "position": c["said"][0]["text"] if c["said"] else "",
            "likely_move": "",
        }
        for c in facts["companies"]
    ]
    return {
        "bottom_line": bottom,
        "what_it_means": means,
        "consensus": consensus,
        "splits": splits,
        "groups": group_readings,
        "companies": companies,
        "watch": [],
    }


# --------------------------------------------------------------------------- #
# LLM reading
# --------------------------------------------------------------------------- #

READING_SYSTEM_PROMPT = """You write the briefing for Hivemind, a product that simulates how a crowd of people and organisations reacts online to a situation. The reader is a busy decision-maker, not a data scientist. They asked a question, Hivemind ran a simulation, and they now want to know what it means and what each kind of actor would do.

You get FACTS as JSON: the question, the run's totals, and for each group of simulated actors what they wrote (verbatim "text"), how many approving and disapproving reactions they received, and who backed whom. "companies" lists individual companies and executives with their own posts.

Rules:
- Use only names, numbers and positions that appear in FACTS. Never invent actors, posts, numbers, dates or outcomes. Do not bring in outside knowledge about these actors.
- This is a simulation. Phrase findings as what the simulated actors did and what that suggests: "In this run, analysts held their ratings", "This suggests regulators would...". Never state a real-world outcome as fact.
- Agreement means several groups arguing the same point, or one group's point drawing approving reactions from other groups (see who_backed_whom and most_backed_posts). If only one actor said something and nobody reacted, it is not consensus. If there is no real agreement, return an empty consensus list rather than stretching.
- A split is a real disagreement visible in the texts or in disapproving reactions. Return an empty list if there is none.
- "reception" is the share of reactions to a group's posts that were approving. It measures how warmly their posts were received, not their opinion.
- "likely_next" and "likely_move" are your inference of what that actor would do next, given what they said in the run. Start them with a verb. Keep each tied to something the actor actually said. If a group or company wrote nothing, set stance to "quiet" and say the run gives no basis for a prediction.
- "starting_stances" is how the simulation cast the actors before the run; use it only as background.
- run.cast.added_names lists voices Hivemind added to the cast: the people around the key actors, and people drawn in as the conversation grew. They are described by role and were not named in the evidence. Use them as evidence of how ordinary affected people react. Never present an added voice's view as the position of a named actor, and do not build a consensus or a company's likely move on added voices alone.
- Avoid jargon: no "cascade", "branching", "agent", "round", "engagement", "entity". Say "people", "voices", "posts", "reactions".
- The two simulated platforms are "Info Plaza" (a short-post feed) and "Topic Community" (threaded discussion). Never say Twitter or Reddit.
- Do not use quotation marks unless the words are copied exactly from a "text" field.
- Be concrete and brief. Short sentences. No hype. No hedging filler.

Return JSON with exactly these keys:
{
  "bottom_line": "1-2 sentences answering the question as far as this run can",
  "what_it_means": ["3-4 short points: the implications for someone who has to decide or respond"],
  "consensus": [{"point": "one sentence stating what was agreed", "held_by": ["group labels from FACTS"], "strength": "strong|moderate|weak"}],
  "splits": [{"issue": "what they disagree about", "side_a": "one side and who holds it", "side_b": "the other side and who holds it"}],
  "groups": [{"key": "<group key from FACTS>", "stance": "supportive|critical|cautious|divided|neutral|quiet", "reaction": "2-3 sentences on how this group reacted", "likely_next": "one sentence"}],
  "companies": [{"name": "<name from FACTS companies>", "position": "one sentence on the line they took", "likely_move": "one sentence"}],
  "watch": ["3-4 concrete signals that would confirm or break this reading"]
}
"stance" describes the group's attitude to the situation in the question. Write one groups entry per group in FACTS and one companies entry per company in FACTS, in the same order. Up to 4 consensus points and 3 splits."""


def _facts_for_llm(facts: Dict[str, Any]) -> Dict[str, Any]:
    slim = json.loads(json.dumps(facts, ensure_ascii=False))
    for g in slim["groups"]:
        g.pop("silent", None)

    def rename(node: Any) -> None:  # the model must never see "twitter" / "reddit"
        if isinstance(node, dict):
            if node.get("platform") in PLATFORM_NAMES:
                node["platform"] = PLATFORM_NAMES[node["platform"]]
            for v in node.values():
                rename(v)
        elif isinstance(node, list):
            for v in node:
                rename(v)

    rename(slim)
    return slim


def _clean(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _str_list(v: Any, limit: int) -> List[str]:
    return [s.strip() for s in (v or []) if isinstance(s, str) and s.strip()][:limit] if isinstance(v, list) else []


def _merge_reading(llm: Dict[str, Any], fallback: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the LLM's JSON and fill any gap from the template reading."""
    labels = {g["label"] for g in facts["groups"]}

    consensus = []
    for item in llm.get("consensus") or []:
        if not isinstance(item, dict) or not _clean(item.get("point")):
            continue
        strength = _clean(item.get("strength")).lower()
        consensus.append({
            "point": _clean(item["point"]),
            "held_by": [h for h in _str_list(item.get("held_by"), 8) if h in labels],
            "strength": strength if strength in STRENGTHS else "moderate",
        })

    splits = [
        {"issue": _clean(s.get("issue")), "side_a": _clean(s.get("side_a")), "side_b": _clean(s.get("side_b"))}
        for s in (llm.get("splits") or [])
        if isinstance(s, dict) and _clean(s.get("issue")) and _clean(s.get("side_a")) and _clean(s.get("side_b"))
    ]

    by_key = {
        _clean(g.get("key")): g for g in (llm.get("groups") or [])
        if isinstance(g, dict) and _clean(g.get("reaction"))
    }
    fb_groups = {g["key"]: g for g in fallback["groups"]}
    groups = []
    for g in facts["groups"]:
        got = by_key.get(g["key"])
        if not got:
            groups.append(fb_groups[g["key"]])
            continue
        stance = _clean(got.get("stance")).lower()
        if g["posts"] + g["replies"] == 0:
            stance = "quiet"
        groups.append({
            "key": g["key"],
            "stance": stance if stance in STANCES else fb_groups[g["key"]]["stance"],
            "reaction": _clean(got["reaction"]),
            "likely_next": _clean(got.get("likely_next")),
        })

    by_name = {
        _clean(c.get("name")): c for c in (llm.get("companies") or [])
        if isinstance(c, dict) and _clean(c.get("position"))
    }
    fb_companies = {c["name"]: c for c in fallback["companies"]}
    companies = []
    for c in facts["companies"]:
        got = by_name.get(c["name"])
        companies.append(
            {"name": c["name"], "position": _clean(got["position"]), "likely_move": _clean(got.get("likely_move"))}
            if got else fb_companies[c["name"]]
        )

    return {
        "bottom_line": _clean(llm.get("bottom_line")) or fallback["bottom_line"],
        "what_it_means": _str_list(llm.get("what_it_means"), 5) or fallback["what_it_means"],
        # An empty list from the model is a finding ("no real agreement"), so keep it.
        "consensus": consensus[:4] if isinstance(llm.get("consensus"), list) else fallback["consensus"],
        "splits": splits[:3] if isinstance(llm.get("splits"), list) else fallback["splits"],
        "groups": groups,
        "companies": companies,
        "watch": _str_list(llm.get("watch"), 5),
    }


def llm_reading(facts: Dict[str, Any], llm_client: Any = None) -> Dict[str, Any]:
    from ..utils.llm_client import LLMClient
    from ..utils.locale import get_language_instruction

    client = llm_client or LLMClient()
    messages = [
        {"role": "system", "content": f"{READING_SYSTEM_PROMPT}\n\n{get_language_instruction()}"},
        {"role": "user", "content": "FACTS:\n" + json.dumps(_facts_for_llm(facts), ensure_ascii=False)},
    ]
    raw = client.chat_json(messages, temperature=0.3, max_tokens=8192, max_attempts=2)
    return _merge_reading(raw, template_reading(facts), facts)


# --------------------------------------------------------------------------- #
# Disk: load inputs, cache readings
# --------------------------------------------------------------------------- #

def _sim_dir(simulation_id: str) -> str:
    from .simulation_runner import SimulationRunner

    return os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)


def _load_inputs(simulation_id: str, dynamics: Optional[Dict[str, Any]] = None):
    from .run_dynamics import build_dynamics
    from .simulation_runner import SimulationRunner

    actions = [a.to_dict() for a in SimulationRunner.get_all_actions(simulation_id)]
    run_state = SimulationRunner.get_run_state(simulation_id)
    config = _read_json(os.path.join(_sim_dir(simulation_id), "simulation_config.json")) or {}
    if dynamics is None:
        dynamics = build_dynamics(simulation_id)
    facts = build_briefing_facts(
        actions,
        config.get("agent_configs") or [],
        requirement=config.get("simulation_requirement") or "",
        minutes_per_round=(config.get("time_config") or {}).get("minutes_per_round") or 60,
        run={
            "status": run_state.runner_status.value if run_state else None,
            # Every round has been played once all platforms logged simulation_end. The
            # run can stay "running" long after that while agents are kept alive for
            # interviews or graph-memory writes are still draining; neither changes
            # what happened, so the write-up does not wait for them.
            "ready_for_report": bool(run_state) and (
                bool(getattr(run_state, "ready_for_report", False))
                or SimulationRunner._check_all_platforms_completed(run_state)
            ),
        },
        health=dynamics.get("health"),
    )
    return facts, facts_fingerprint(facts)


def _load_cache(simulation_id: str) -> Optional[Dict[str, Any]]:
    data = _read_json(os.path.join(_sim_dir(simulation_id), BRIEFING_FILE))
    if not data or data.get("version") != BRIEFING_VERSION or not isinstance(data.get("reading"), dict):
        return None
    return data


def _save_cache(simulation_id: str, fingerprint: str, reading: Dict[str, Any], model: Optional[str]) -> str:
    path = os.path.join(_sim_dir(simulation_id), BRIEFING_FILE)
    payload = {
        "version": BRIEFING_VERSION,
        "fingerprint": fingerprint,
        "reading": reading,
        "source": "llm",
        "model": model,
        "written_at": datetime.now().isoformat(timespec="seconds"),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return payload["written_at"]


def _has_writing(facts: Dict[str, Any]) -> bool:
    return (facts["run"]["posts"] + facts["run"]["replies"]) > 0


def _assemble(simulation_id: str, facts: Dict[str, Any], fingerprint: str, reading: Dict[str, Any],
              source: str, written_at: Optional[str] = None, stale: bool = False) -> Dict[str, Any]:
    from ..config import Config

    return {
        "simulation_id": simulation_id,
        "facts": facts,
        "reading": reading,
        "confidence": confidence_for(facts),
        "reading_source": source,          # "llm" | "template"
        "reading_stale": stale,            # an older LLM reading exists for earlier data
        "written_at": written_at,
        "fingerprint": fingerprint,
        "can_write": bool(Config.LLM_API_KEY) and _has_writing(facts),
    }


def get_briefing(simulation_id: str, dynamics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Current facts plus the best reading available without calling an LLM."""
    facts, fingerprint = _load_inputs(simulation_id, dynamics)
    cached = _load_cache(simulation_id)
    if cached and cached.get("fingerprint") == fingerprint:
        return _assemble(simulation_id, facts, fingerprint, cached["reading"], "llm", cached.get("written_at"))
    return _assemble(simulation_id, facts, fingerprint, template_reading(facts), "template", stale=bool(cached))


def write_briefing(simulation_id: str, force: bool = False, llm_client: Any = None) -> Dict[str, Any]:
    """Have the LLM interpret the current facts and cache the reading.

    Serialised per simulation so the page and the PDF never pay for two
    readings at once. Without force, a cached reading for the same data is reused.
    """
    from ..config import Config

    with _lock_for("briefing:" + simulation_id):
        facts, fingerprint = _load_inputs(simulation_id)
        cached = _load_cache(simulation_id)
        if not force and cached and cached.get("fingerprint") == fingerprint:
            return _assemble(simulation_id, facts, fingerprint, cached["reading"], "llm", cached.get("written_at"))
        if not _has_writing(facts):
            return _assemble(simulation_id, facts, fingerprint, template_reading(facts), "template")
        reading = llm_reading(facts, llm_client=llm_client)
        written_at = _save_cache(simulation_id, fingerprint, reading, Config.LLM_MODEL_NAME)
        return _assemble(simulation_id, facts, fingerprint, reading, "llm", written_at)
