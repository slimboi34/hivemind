"""
Hivemind "What happened" recap.

A plain-language account of one simulation run: how it opened, who spoke up,
which posts drew the crowd, how the tone of reactions moved and where it ended.
It is built in two layers:

1. Facts (deterministic). The run's rounds are grouped into chapters, each with
   counts, new voices, standout posts and replies, and every quote is copied
   verbatim from the action logs.
2. Story (prose). An LLM narrates from those facts only. A template writes the
   same shape without an LLM, so a recap always exists, including while a run
   is still going or when no model is reachable.

Like the rest of the Analytics layer this is read-only over the run's outputs:
it never feeds back into the simulation, the graph or the report agent, so it
cannot change what Hivemind predicts.
"""

from __future__ import annotations

import json
import math
import os
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .simulation_analytics import EXCLUDED_ACTIONS, OPPOSE, PASSIVE, POST, REPLY, SUPPORT, categorize

RECAP_FILE = "recap.json"
RECAP_VERSION = 1

SNIPPET_CHARS = 280
SAID_PER_CHAPTER = 8
STANDOUTS_PER_CHAPTER = 3
REPLIES_PER_CHAPTER = 3
NEW_VOICES_PER_CHAPTER = 8
SEED_POSTS_SHOWN = 8

# Engagement on a post or comment, by action type -> counter name.
POST_COUNTERS = {
    "LIKE_POST": "likes",
    "DISLIKE_POST": "dislikes",
    "REPOST": "reposts",
    "QUOTE_POST": "quotes",
    "CREATE_COMMENT": "comments",
}
COMMENT_COUNTERS = {"LIKE_COMMENT": "likes", "DISLIKE_COMMENT": "dislikes"}

FINISHED_STATUSES = {"completed", "stopped"}


# --------------------------------------------------------------------------- #
# Time and chapters
# --------------------------------------------------------------------------- #

def _round_start_minutes(round_num: int, minutes_per_round: int) -> int:
    """Simulated minutes elapsed when a logged round starts.

    Logged round 0 is the seeding round (initial posts). Logged round N >= 1 is
    loop iteration N - 1 in the runner, which starts at (N - 1) * minutes_per_round.
    """
    return max(round_num - 1, 0) * minutes_per_round


def _clock(minutes: int) -> Tuple[int, str]:
    day = minutes // 1440 + 1
    rem = minutes % 1440
    return day, f"{rem // 60:02d}:{rem % 60:02d}"


def _span_label(first_round: int, last_round: int, minutes_per_round: int) -> str:
    start = _round_start_minutes(first_round, minutes_per_round)
    end = _round_start_minutes(last_round, minutes_per_round) + minutes_per_round - 1
    d1, t1 = _clock(start)
    d2, t2 = _clock(end)
    if d1 == d2:
        return f"Day {d1}, {t1}–{t2}"
    return f"Day {d1} {t1} – Day {d2} {t2}"


def _duration_label(minutes: int) -> str:
    if minutes <= 0:
        return "no simulated time"
    hours = minutes / 60
    if hours < 48:
        h = round(hours, 1)
        h = int(h) if float(h).is_integer() else h
        return f"{h} simulated hour{'s' if h != 1 else ''}"
    days = round(hours / 24, 1)
    days = int(days) if float(days).is_integer() else days
    return f"{days} simulated days"


def plan_chapters(last_round: int, minutes_per_round: int) -> List[Dict[str, Any]]:
    """Group rounds 1..last_round into chapters a reader can follow.

    Runs spanning 2-10 simulated days get one chapter per day. Shorter runs get
    one chapter per round when there are six rounds or fewer, otherwise four
    chapters of near-equal length; very long runs get six.
    """
    if last_round < 1:
        return []
    minutes_per_round = max(int(minutes_per_round or 60), 1)
    span = last_round * minutes_per_round
    days = math.ceil(span / 1440)

    groups: List[Tuple[int, int]] = []
    by_day = 2 <= days <= 10 and minutes_per_round <= 1440
    if by_day:
        current_day, start = None, 1
        for r in range(1, last_round + 1):
            day = _round_start_minutes(r, minutes_per_round) // 1440
            if current_day is None:
                current_day = day
            elif day != current_day:
                groups.append((start, r - 1))
                start, current_day = r, day
        groups.append((start, last_round))
    else:
        k = last_round if last_round <= 6 else (4 if days < 2 else 6)
        base, extra = divmod(last_round, k)
        start = 1
        for i in range(k):
            size = base + (1 if i < extra else 0)
            groups.append((start, start + size - 1))
            start += size

    chapters = []
    for i, (a, b) in enumerate(groups):
        if by_day:
            label = f"Day {_clock(_round_start_minutes(a, minutes_per_round))[0]}"
        elif a == b:
            label = f"Round {a}"
        else:
            label = f"Rounds {a}–{b}"
        chapters.append({
            "index": i,
            "label": label,
            "first_round": a,
            "last_round": b,
            "time": _span_label(a, b, minutes_per_round),
        })
    return chapters


# --------------------------------------------------------------------------- #
# Facts
# --------------------------------------------------------------------------- #

def _snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _tone(support: int, oppose: int) -> Optional[float]:
    return round(support / (support + oppose), 3) if (support + oppose) else None


def _post_target(action_type: str, args: Dict[str, Any]) -> Tuple[str, str]:
    """(author, content) of the post an engagement action points at."""
    if action_type in ("REPOST", "QUOTE_POST"):
        return args.get("original_author_name") or "", args.get("original_content") or ""
    return args.get("post_author_name") or "", args.get("post_content") or ""


def _new_chapter_stats() -> Dict[str, Any]:
    return {
        "counts": {POST: 0, REPLY: 0, SUPPORT: 0, OPPOSE: 0, PASSIVE: 0},
        "platforms": defaultdict(int),
        "agent_moves": defaultdict(int),
        "agent_writes": defaultdict(int),
        "post_engagement": defaultdict(lambda: defaultdict(int)),
        "comment_engagement": defaultdict(lambda: defaultdict(int)),
        "posts_created": [],
        "comments_created": [],
    }


def build_recap_facts(
    actions: List[Dict[str, Any]],
    *,
    requirement: str = "",
    minutes_per_round: int = 60,
    run: Optional[Dict[str, Any]] = None,
    dynamics: Optional[Dict[str, Any]] = None,
    roster_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Turn raw action dicts (AgentAction.to_dict() shape) into story facts.

    Pure function: no disk or network access, so it is easy to test.
    """
    run = dict(run or {})
    minutes_per_round = max(int(minutes_per_round or 60), 1)
    actions = [a for a in actions if a.get("action_type") not in EXCLUDED_ACTIONS]
    actions.sort(key=lambda a: (int(a.get("round_num", 0) or 0), a.get("timestamp", "")))

    rounds_with_moves = [
        int(a.get("round_num", 0) or 0) for a in actions
        if categorize(a.get("action_type", "")) != PASSIVE
    ]
    last_round = max(rounds_with_moves, default=0)
    chapters = plan_chapters(last_round, minutes_per_round)
    round_chapter = {
        r: ch["index"] for ch in chapters for r in range(ch["first_round"], ch["last_round"] + 1)
    }

    # Global registries so a post's total engagement is known in every chapter.
    posts: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    comments: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    first_move: Dict[str, int] = {}
    total_moves: Dict[str, int] = defaultdict(int)
    stats = [_new_chapter_stats() for _ in chapters]
    seed_posts: List[Dict[str, Any]] = []
    seen_seed: set = set()
    seed_actions = 0

    def post_rec(platform: str, author: str, content: str, round_num: int) -> Optional[Dict[str, Any]]:
        content = " ".join((content or "").split())
        if not author or not content:
            return None
        key = (platform, author, content)
        rec = posts.get(key)
        if rec is None:
            rec = posts[key] = {
                "key": key, "platform": platform, "author": author, "content": content,
                "round": round_num, "likes": 0, "dislikes": 0, "reposts": 0, "quotes": 0, "comments": 0,
            }
        return rec

    def comment_rec(platform: str, author: str, content: str, round_num: int,
                    replying_to: str = "") -> Optional[Dict[str, Any]]:
        content = " ".join((content or "").split())
        if not author or not content:
            return None
        key = (platform, author, content)
        rec = comments.get(key)
        if rec is None:
            rec = comments[key] = {
                "key": key, "platform": platform, "author": author, "content": content,
                "replying_to": replying_to, "round": round_num, "likes": 0, "dislikes": 0,
            }
        elif replying_to and not rec["replying_to"]:
            rec["replying_to"] = replying_to
        return rec

    for a in actions:
        action_type = a.get("action_type", "")
        category = categorize(action_type)
        name = a.get("agent_name") or f"Agent_{a.get('agent_id', '?')}"
        platform = a.get("platform") or ""
        round_num = int(a.get("round_num", 0) or 0)
        args = a.get("action_args") or {}

        if category != PASSIVE:
            total_moves[name] += 1
            first_move.setdefault(name, round_num)

        if action_type in ("CREATE_POST", "QUOTE_POST"):
            content = args.get("content") or args.get("quote_content") or ""
            created = post_rec(platform, name, content, round_num)
        else:
            created = None

        if round_num == 0:
            if action_type == "CREATE_POST":
                seed_actions += 1
            if created is not None and action_type == "CREATE_POST":
                dedupe = (name, created["content"])
                if dedupe not in seen_seed:
                    seen_seed.add(dedupe)
                    seed_posts.append({
                        "author": name,
                        "platforms": [platform],
                        "text": _snippet(created["content"]),
                    })
                else:
                    for s in seed_posts:
                        if s["author"] == name and platform not in s["platforms"]:
                            s["platforms"].append(platform)
            # Seeding-round reactions still count toward post totals below.

        ci = round_chapter.get(round_num)
        st = stats[ci] if ci is not None else None
        if st is not None:
            st["counts"][category] += 1
            if category != PASSIVE:
                st["platforms"][platform] += 1
                st["agent_moves"][name] += 1
            if action_type in ("CREATE_POST", "QUOTE_POST", "CREATE_COMMENT"):
                st["agent_writes"][name] += 1
            if created is not None:
                st["posts_created"].append(created["key"])

        if action_type in POST_COUNTERS:
            author, content = _post_target(action_type, args)
            target = post_rec(platform, author, content, round_num)
            if target is not None:
                target[POST_COUNTERS[action_type]] += 1
                if st is not None:
                    st["post_engagement"][target["key"]][POST_COUNTERS[action_type]] += 1

        if action_type == "CREATE_COMMENT":
            c = comment_rec(platform, name, args.get("content") or "", round_num,
                            args.get("post_author_name") or "")
            if c is not None and st is not None:
                st["comments_created"].append(c["key"])

        if action_type in COMMENT_COUNTERS:
            c = comment_rec(platform, args.get("comment_author_name") or "",
                            args.get("comment_content") or "", round_num)
            if c is not None:
                c[COMMENT_COUNTERS[action_type]] += 1
                if st is not None:
                    st["comment_engagement"][c["key"]][COMMENT_COUNTERS[action_type]] += 1

    def engagement(rec: Dict[str, Any]) -> int:
        return rec["likes"] + rec["dislikes"] + rec["reposts"] + rec["quotes"] + rec["comments"]

    def post_view(rec: Dict[str, Any], in_chapter: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        view = {
            "author": rec["author"],
            "platform": rec["platform"],
            "round": rec["round"],
            "text": _snippet(rec["content"]),
            "reactions_total": engagement(rec),
            "likes": rec["likes"], "reposts": rec["reposts"], "quotes": rec["quotes"],
            "comments": rec["comments"], "dislikes": rec["dislikes"],
        }
        if in_chapter is not None:
            view["reactions_in_chapter"] = sum(in_chapter.values())
        return view

    out_chapters = []
    prev_active: set = set()
    featured: set = set()  # posts already leading an earlier chapter
    for ch, st in zip(chapters, stats):
        counts = st["counts"]
        movers = st["agent_moves"]
        active = set(movers)

        ranked = sorted(
            st["post_engagement"].items(),
            key=lambda kv: (sum(kv[1].values()), engagement(posts[kv[0]])),
            reverse=True,
        )
        ranked = [(k, e) for k, e in ranked if sum(e.values()) > 0]
        # Lead with a post no earlier chapter featured, so each stretch shows something new.
        lead = next((i for i, (k, _) in enumerate(ranked) if k not in featured), 0)
        if ranked:
            ranked.insert(0, ranked.pop(lead))
            featured.add(ranked[0][0])
        standouts = [post_view(posts[k], dict(e)) for k, e in ranked[:STANDOUTS_PER_CHAPTER]]
        for sp in standouts:
            sp["written_in_this_stretch"] = ch["first_round"] <= sp["round"] <= ch["last_round"]

        created_keys = list(dict.fromkeys(st["posts_created"]))
        created_keys.sort(key=lambda k: (engagement(posts[k]), total_moves.get(posts[k]["author"], 0)), reverse=True)
        said = [post_view(posts[k]) for k in created_keys[:SAID_PER_CHAPTER]]

        comment_keys = list(dict.fromkeys(st["comments_created"]))
        comment_keys.sort(key=lambda k: (comments[k]["likes"] - comments[k]["dislikes"], len(comments[k]["content"])),
                          reverse=True)
        replies = [{
            "author": comments[k]["author"],
            "replying_to": comments[k]["replying_to"],
            "platform": comments[k]["platform"],
            "text": _snippet(comments[k]["content"], 220),
            "likes": comments[k]["likes"],
            "dislikes": comments[k]["dislikes"],
        } for k in comment_keys[:REPLIES_PER_CHAPTER]]

        pushback = None
        disliked = [(k, e.get("dislikes", 0), "post") for k, e in st["post_engagement"].items()]
        disliked += [(k, e.get("dislikes", 0), "comment") for k, e in st["comment_engagement"].items()]
        disliked = [d for d in disliked if d[1] > 0]
        if disliked:
            k, n, kind = max(disliked, key=lambda d: d[1])
            rec = posts[k] if kind == "post" else comments[k]
            pushback = {"kind": kind, "author": rec["author"], "platform": rec["platform"],
                        "text": _snippet(rec["content"], 220), "dislikes": n}

        new_voices = sorted(
            (n for n in active if first_move.get(n) is not None
             and ch["first_round"] <= first_move[n] <= ch["last_round"]),
            key=lambda n: movers[n], reverse=True,
        )
        loudest = sorted(movers.items(), key=lambda kv: kv[1], reverse=True)[:3]

        out_chapters.append({
            **ch,
            "posts": counts[POST],
            "replies": counts[REPLY],
            "approving": counts[SUPPORT],
            "disapproving": counts[OPPOSE],
            "activity": counts[POST] + counts[REPLY] + counts[SUPPORT] + counts[OPPOSE],
            "people_active": len(active),
            "returning": len(active & prev_active),
            "platforms": dict(st["platforms"]),
            "tone": _tone(counts[SUPPORT], counts[OPPOSE]),
            "loudest": [{"name": n, "moves": m, "posts_and_replies": st["agent_writes"][n]} for n, m in loudest],
            "new_voices": [{"name": n, "moves": movers[n]} for n in new_voices[:NEW_VOICES_PER_CHAPTER]],
            "new_voice_count": len(new_voices),
            "standout_posts": standouts,
            "posts_said": said,
            "top_replies": replies,
            "pushback": pushback,
            "quiet": counts[POST] + counts[REPLY] + counts[SUPPORT] + counts[OPPOSE] == 0,
        })
        prev_active = active

    all_posts = sorted(posts.values(), key=lambda r: (engagement(r), -r["round"]), reverse=True)
    biggest_post = post_view(all_posts[0]) if all_posts and engagement(all_posts[0]) > 0 else None
    most_disliked = max(
        list(posts.values()) + list(comments.values()), key=lambda r: r["dislikes"], default=None,
    )
    if most_disliked is not None and most_disliked["dislikes"] == 0:
        most_disliked = None

    busiest = max(out_chapters, key=lambda c: c["activity"], default=None)
    signal = [c for c in out_chapters if c["tone"] is not None]
    total_support = sum(c["approving"] for c in out_chapters)
    total_oppose = sum(c["disapproving"] for c in out_chapters)

    dyn = dynamics or {}
    consensus = dyn.get("consensus") or {}
    health = dyn.get("health") or {}
    top_cascade = ((dyn.get("cascades") or {}).get("top") or [None])[0]
    received: Dict[str, int] = defaultdict(int)
    for p in posts.values():
        received[p["author"]] += engagement(p)
    for c in comments.values():
        received[c["author"]] += c["likes"] + c["dislikes"]
    most_engaged = sorted(received.items(), key=lambda kv: kv[1], reverse=True)

    planned = run.get("total_rounds") or 0
    return {
        "version": RECAP_VERSION,
        "question": _snippet(requirement, 700),
        "run": {
            "status": run.get("status"),
            "finished": run.get("status") in FINISHED_STATUSES or bool(run.get("ready_for_report")),
            "rounds_done": last_round,
            "rounds_planned": planned,
            "minutes_per_round": minutes_per_round,
            "duration": _duration_label(last_round * minutes_per_round),
            "platforms": sorted({a.get("platform") for a in actions if a.get("platform")}),
        },
        "cast": {
            "people_active": len(total_moves),
            "roster": roster_size,
            "silent": max((roster_size or 0) - len(total_moves), 0) if roster_size else None,
        },
        "totals": {
            "posts": sum(c["posts"] for c in out_chapters) + seed_actions,
            "replies": sum(c["replies"] for c in out_chapters),
            "approving": total_support,
            "disapproving": total_oppose,
            "tone": _tone(total_support, total_oppose),
        },
        "opening": {
            "seed_posts": seed_posts[:SEED_POSTS_SHOWN],
            "seed_count": len(seed_posts),
            "seed_authors": list(dict.fromkeys(s["author"] for s in seed_posts)),
        },
        "chapters": out_chapters,
        "highlights": {
            "busiest_chapter": busiest["index"] if busiest and busiest["activity"] else None,
            "biggest_post": biggest_post,
            "most_engaged_people": [{"name": n, "reactions": v} for n, v in most_engaged[:5] if v > 0],
            "most_disliked": ({
                "author": most_disliked["author"], "platform": most_disliked["platform"],
                "text": _snippet(most_disliked["content"], 220), "dislikes": most_disliked["dislikes"],
            } if most_disliked else None),
            "tone_first": signal[0]["tone"] if signal else None,
            "tone_last": signal[-1]["tone"] if signal else None,
            "largest_thread": ({
                "author": top_cascade.get("root_author"),
                "platform": top_cascade.get("platform"),
                "size": top_cascade.get("size"),
                "shape": top_cascade.get("shape"),
                "text": _snippet(top_cascade.get("root_content") or "", 220),
            } if top_cascade else None),
        },
        "ending": {
            "consensus": consensus.get("verdict"),
            "consensus_plain": consensus.get("plain"),
        },
        "caveats": {
            "level": health.get("overall"),
            "headline": health.get("headline"),
            "reasons": (health.get("reasons") or [])[:3],
        },
    }


def facts_fingerprint(facts: Dict[str, Any], actions_count: int, last_timestamp: str) -> str:
    run = facts.get("run") or {}
    # Status is left out on purpose: a run marked ready_for_report that later
    # closes as "completed" has the same story.
    return f"v{RECAP_VERSION}|{actions_count}|{last_timestamp}|{bool(run.get('finished'))}"


# --------------------------------------------------------------------------- #
# Story: template (no LLM)
# --------------------------------------------------------------------------- #

def _pct(x: Optional[float]) -> str:
    return "–" if x is None else f"{round(x * 100)}%"


def _tone_word(x: Optional[float]) -> str:
    if x is None:
        return "too thin to read"
    if x >= 0.75:
        return "warm"
    if x >= 0.6:
        return "mostly approving"
    if x >= 0.4:
        return "mixed"
    if x >= 0.25:
        return "mostly disapproving"
    return "hostile"


def _names(items: List[str], limit: int = 3) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    shown = items[:limit]
    rest = len(items) - len(shown)
    if rest > 0:
        return ", ".join(shown) + f" and {rest} other{'s' if rest != 1 else ''}"
    if len(shown) == 1:
        return shown[0]
    return ", ".join(shown[:-1]) + " and " + shown[-1]


def _tone_shift(prev: Optional[float], cur: Optional[float]) -> str:
    if prev is None or cur is None:
        return ""
    delta = cur - prev
    if abs(delta) < 0.08:
        return "about the same as before"
    return "warmer than before" if delta > 0 else "cooler than before"


def template_story(facts: Dict[str, Any]) -> Dict[str, Any]:
    chapters = facts.get("chapters") or []
    totals = facts.get("totals") or {}
    cast = facts.get("cast") or {}
    run = facts.get("run") or {}
    opening = facts.get("opening") or {}
    hl = facts.get("highlights") or {}
    ending = facts.get("ending") or {}
    caveats = facts.get("caveats") or {}

    biggest = hl.get("biggest_post")
    people = cast.get("people_active") or 0
    busiest = chapters[hl["busiest_chapter"]] if hl.get("busiest_chapter") is not None else None

    if biggest:
        headline = (f"{people} simulated voices posted and reacted over {run.get('duration')}; "
                    f"{biggest['author']}'s post drew the biggest response.")
    elif people:
        headline = f"{people} simulated voices posted over {run.get('duration')}, but almost nobody reacted."
    else:
        headline = "Nothing has happened in this run yet."

    seeds = opening.get("seed_posts") or []
    summary_parts = []
    if seeds:
        summary_parts.append(
            f"The run opened with {opening.get('seed_count')} starting posts from "
            f"{_names([s['author'] for s in seeds])}."
        )
    if busiest and busiest["activity"]:
        summary_parts.append(
            f"Activity peaked during {busiest['time']}, "
            f"with {busiest['posts']} posts, {busiest['replies']} replies and "
            f"{busiest['approving'] + busiest['disapproving']} reactions."
        )
    if totals.get("tone") is not None:
        trend = _tone_shift(hl.get("tone_first"), hl.get("tone_last"))
        summary_parts.append(
            f"Reactions were {_tone_word(totals['tone'])} overall ({_pct(totals['tone'])} approving)"
            + (f", ending {trend}." if trend else ".")
        )
    if ending.get("consensus_plain"):
        summary_parts.append(ending["consensus_plain"])
    summary = " ".join(summary_parts) or "There is not enough activity to tell a story yet."

    if seeds:
        first = seeds[0]
        opening_text = (
            f"It started with {opening.get('seed_count')} posts that set the scene. "
            f"{first['author']} went first: “{_snippet(first['text'], 160)}”"
        )
    else:
        opening_text = "The run started without seed posts."

    stories = []
    prev_tone = None
    for ch in chapters:
        if ch["quiet"]:
            stories.append({"index": ch["index"], "title": "A quiet stretch",
                            "story": "Nobody posted or reacted in this stretch."})
            continue
        bits = []
        if ch["loudest"]:
            bits.append(f"{ch['loudest'][0]['name']} was the most active.")
        if ch["new_voice_count"]:
            bits.append(
                f"{ch['new_voice_count']} new voice{'s' if ch['new_voice_count'] != 1 else ''} joined, "
                f"including {_names([v['name'] for v in ch['new_voices']])}."
            )
        if ch["standout_posts"]:
            sp = ch["standout_posts"][0]
            bits.append(f"The post that drew the most reactions was by {sp['author']} "
                        f"({sp['reactions_in_chapter']} in this stretch).")
        if ch["tone"] is not None:
            shift = _tone_shift(prev_tone, ch["tone"])
            bits.append(f"Reactions were {_tone_word(ch['tone'])} ({_pct(ch['tone'])} approving)"
                        + (f", {shift}." if shift else "."))
            prev_tone = ch["tone"]
        if ch["pushback"]:
            pb = ch["pushback"]
            bits.append(f"The strongest pushback hit a {pb['kind']} by {pb['author']} "
                        f"({pb['dislikes']} dislike{'s' if pb['dislikes'] != 1 else ''}).")
        title = (f"{ch['standout_posts'][0]['author']} takes the spotlight" if ch["standout_posts"]
                 else f"{ch['posts']} posts, few reactions")
        stories.append({"index": ch["index"], "title": title, "story": " ".join(bits)})

    end_bits = []
    last = next((c for c in reversed(chapters) if not c["quiet"]), None)
    if last and last["standout_posts"]:
        end_bits.append(f"In the final stretch the conversation centred on {last['standout_posts'][0]['author']}'s post.")
    if hl.get("tone_last") is not None:
        end_bits.append(f"The last reactions were {_tone_word(hl['tone_last'])} ({_pct(hl['tone_last'])} approving).")
    if ending.get("consensus_plain"):
        end_bits.append(ending["consensus_plain"])
    ending_text = " ".join(end_bits) or "The run has not reached an ending yet."

    takeaways = []
    if hl.get("most_engaged_people"):
        top = hl["most_engaged_people"][0]
        takeaways.append(f"{top['name']} drew the most reactions ({top['reactions']}).")
    if busiest and busiest["activity"]:
        takeaways.append(f"The busiest stretch was {busiest['time']}.")
    if cast.get("silent"):
        takeaways.append(f"{cast['silent']} of {cast['roster']} rostered voices never spoke up.")
    if caveats.get("level") in ("amber", "red") and caveats.get("headline"):
        takeaways.append(caveats["headline"])

    return {
        "headline": headline,
        "summary": summary,
        "opening": opening_text,
        "chapters": stories,
        "ending": ending_text,
        "takeaways": takeaways,
    }


# --------------------------------------------------------------------------- #
# Story: LLM
# --------------------------------------------------------------------------- #

STORY_SYSTEM_PROMPT = """You write the "What happened" recap for Hivemind, a product that simulates how a crowd of people reacts online to a situation. Readers are ordinary people, not data scientists. They want to know, plainly, what happened in this simulated run.

You get FACTS as JSON. Write only from them.

Rules:
- Use only names, numbers and events that appear in FACTS. Never invent people, posts, numbers, dates or outcomes.
- "question" is what the person asked Hivemind to simulate. The run itself only covered run.duration, shown as simulated clock times in each chapter's "time". Never say the run covered the dates or period named in the question.
- Do not put quotation marks around anything unless it is copied word for word from a "text" field. Prefer describing what people argued in your own words.
- Describe what people actually said and argued about, using the post and reply texts: the themes, the disagreements, who answered whom.
- Each chapter's story covers only that chapter. Use only its own posts_said, standout_posts, top_replies, pushback, loudest and new_voices, and never borrow posts or statements from other chapters. If a chapter has 0 posts and 0 replies, nobody wrote anything new then: say it was quiet and describe only the reactions.
- A standout post with written_in_this_stretch false was written earlier and kept drawing reactions; say so instead of presenting it as new. "loudest" counts every move (posts, replies and reactions); posts_and_replies says how much of that was writing.
- "tone" is the share of reactions that were approving (likes, reposts, quotes, follows) versus disapproving (dislikes, mutes). It measures how warmly the crowd treated posts, not people's opinion on the question. Say "reactions were warmer/cooler", never "opinion shifted".
- Hivemind calls the platforms "Info Plaza" (platform "twitter", a short-post feed) and "Topic Community" (platform "reddit", threaded discussion). Use those names if you mention a platform; never say Twitter or Reddit.
- Avoid jargon: no "cascade", "branching factor", "agent", "round", "engagement". Say "people", "voices", "posts", "reactions", "stretch".
- These are simulated people. Do not present anything as a real-world event or a forecast; the separate prediction report does that.
- If caveats.level is amber or red, mention the main caveat once, briefly, in the ending.
- Be concrete and brief. Short sentences. No hype.

Return JSON with exactly these keys:
{
  "headline": "one sentence, at most 25 words, saying what happened",
  "summary": "2-4 sentences: the arc of the whole run",
  "opening": "1-3 sentences: how it started (the seed posts)",
  "chapters": [{"index": <chapter index from FACTS>, "title": "3-7 word title", "story": "2-4 sentences"}],
  "ending": "2-3 sentences: where it ended up",
  "takeaways": ["3 to 4 short plain-language points a reader should remember"]
}
Write one chapters entry for every chapter in FACTS, in order, with the same index."""


def _facts_for_llm(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Trim facts to what the narrator needs (keeps the prompt small)."""
    slim = json.loads(json.dumps(facts, ensure_ascii=False))
    for ch in slim.get("chapters") or []:
        for p in ch.get("standout_posts") or []:
            for k in ("likes", "reposts", "quotes", "comments", "dislikes", "round"):
                p.pop(k, None)
        ch["posts_said"] = [
            {"author": p["author"], "platform": p["platform"], "text": p["text"], "reactions_total": p["reactions_total"]}
            for p in (ch.get("posts_said") or [])
        ]
        ch.pop("first_round", None)
        ch.pop("last_round", None)
    return slim


def _merge_story(llm: Dict[str, Any], fallback: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the LLM's JSON and fill any gap from the template story."""
    def text(key: str) -> str:
        v = llm.get(key)
        return v.strip() if isinstance(v, str) and v.strip() else fallback[key]

    by_index: Dict[int, Dict[str, Any]] = {}
    for item in llm.get("chapters") or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        title, story = item.get("title"), item.get("story")
        if isinstance(title, str) and isinstance(story, str) and story.strip():
            by_index[idx] = {"index": idx, "title": title.strip() or "", "story": story.strip()}

    fb_chapters = {c["index"]: c for c in fallback["chapters"]}
    chapters = [by_index.get(ch["index"]) or fb_chapters[ch["index"]] for ch in facts.get("chapters") or []]

    takeaways = [t.strip() for t in (llm.get("takeaways") or []) if isinstance(t, str) and t.strip()]
    return {
        "headline": text("headline"),
        "summary": text("summary"),
        "opening": text("opening"),
        "chapters": chapters,
        "ending": text("ending"),
        "takeaways": takeaways[:5] or fallback["takeaways"],
    }


def llm_story(facts: Dict[str, Any], llm_client: Any = None) -> Dict[str, Any]:
    from ..utils.llm_client import LLMClient
    from ..utils.locale import get_language_instruction

    client = llm_client or LLMClient()
    messages = [
        {"role": "system", "content": f"{STORY_SYSTEM_PROMPT}\n\n{get_language_instruction()}"},
        {"role": "user", "content": "FACTS:\n" + json.dumps(_facts_for_llm(facts), ensure_ascii=False)},
    ]
    raw = client.chat_json(messages, temperature=0.4, max_tokens=4096, max_attempts=2)
    return _merge_story(raw, template_story(facts), facts)


# --------------------------------------------------------------------------- #
# Disk: load inputs, cache stories
# --------------------------------------------------------------------------- #

_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


def _lock_for(simulation_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks[simulation_id]


def _sim_dir(simulation_id: str) -> str:
    from .simulation_runner import SimulationRunner

    return os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _load_inputs(simulation_id: str, dynamics: Optional[Dict[str, Any]] = None):
    from .run_dynamics import _load_configured_agents, build_dynamics
    from .simulation_runner import SimulationRunner

    actions = [a.to_dict() for a in SimulationRunner.get_all_actions(simulation_id)]
    run_state = SimulationRunner.get_run_state(simulation_id)
    config = _read_json(os.path.join(_sim_dir(simulation_id), "simulation_config.json")) or {}
    time_config = config.get("time_config") or {}
    if dynamics is None:
        dynamics = build_dynamics(simulation_id)
    run = {
        "status": run_state.runner_status.value if run_state else None,
        "total_rounds": run_state.total_rounds if run_state else 0,
        "ready_for_report": bool(getattr(run_state, "ready_for_report", False)) if run_state else False,
    }
    roster = len(_load_configured_agents(simulation_id)) or None
    facts = build_recap_facts(
        actions,
        requirement=config.get("simulation_requirement") or "",
        minutes_per_round=time_config.get("minutes_per_round") or 60,
        run=run,
        dynamics=dynamics,
        roster_size=roster,
    )
    # Report-time agent interviews are logged too; they must not stale the story.
    story_actions = [a for a in actions if a.get("action_type") not in EXCLUDED_ACTIONS]
    last_ts = max((a.get("timestamp") or "" for a in story_actions), default="")
    return facts, facts_fingerprint(facts, len(story_actions), last_ts)


def _load_cache(simulation_id: str) -> Optional[Dict[str, Any]]:
    data = _read_json(os.path.join(_sim_dir(simulation_id), RECAP_FILE))
    if not data or data.get("version") != RECAP_VERSION or not isinstance(data.get("story"), dict):
        return None
    return data


def _save_cache(simulation_id: str, fingerprint: str, story: Dict[str, Any], model: Optional[str]) -> str:
    path = os.path.join(_sim_dir(simulation_id), RECAP_FILE)
    payload = {
        "version": RECAP_VERSION,
        "fingerprint": fingerprint,
        "story": story,
        "source": "llm",
        "model": model,
        "written_at": datetime.now().isoformat(timespec="seconds"),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return payload["written_at"]


def _assemble(simulation_id: str, facts: Dict[str, Any], fingerprint: str,
              story: Dict[str, Any], source: str, written_at: Optional[str] = None,
              stale: bool = False) -> Dict[str, Any]:
    from ..config import Config

    return {
        "simulation_id": simulation_id,
        "facts": facts,
        "story": story,
        "story_source": source,            # "llm" | "template"
        "story_stale": stale,              # an older LLM story exists for earlier data
        "written_at": written_at,
        "fingerprint": fingerprint,
        "can_write": bool(Config.LLM_API_KEY) and bool((facts.get("chapters") or [])),
    }


def get_recap(simulation_id: str, dynamics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Current facts plus the best story available without calling an LLM."""
    facts, fingerprint = _load_inputs(simulation_id, dynamics)
    cached = _load_cache(simulation_id)
    if cached and cached.get("fingerprint") == fingerprint:
        return _assemble(simulation_id, facts, fingerprint, cached["story"], "llm", cached.get("written_at"))
    return _assemble(simulation_id, facts, fingerprint, template_story(facts), "template", stale=bool(cached))


def write_recap(simulation_id: str, force: bool = False, llm_client: Any = None) -> Dict[str, Any]:
    """Have the LLM narrate the current facts and cache the story.

    Serialised per simulation so an automatic request and a manual rewrite
    never pay for two stories at once. Without force, a cached story for the
    same data is reused.
    """
    from ..config import Config

    with _lock_for(simulation_id):
        facts, fingerprint = _load_inputs(simulation_id)
        cached = _load_cache(simulation_id)
        if not force and cached and cached.get("fingerprint") == fingerprint:
            return _assemble(simulation_id, facts, fingerprint, cached["story"], "llm", cached.get("written_at"))
        if not facts.get("chapters"):
            return _assemble(simulation_id, facts, fingerprint, template_story(facts), "template")
        story = llm_story(facts, llm_client=llm_client)
        written_at = _save_cache(simulation_id, fingerprint, story, Config.LLM_MODEL_NAME)
        return _assemble(simulation_id, facts, fingerprint, story, "llm", written_at)
