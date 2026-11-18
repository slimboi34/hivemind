"""
Read-only cascade reconstruction from OASIS simulation sqlite traces.

Builds parent→child trees from the `trace` table (reposted_id / quoted_id),
not from `post.original_post_id`, which OASIS rewrites to the cascade root.
Also measures blind activations (actions without a successful refresh) and
exposes per-platform summaries used by run dynamics / the consensus PDF.

Does not write to the DB or change the prediction pipeline.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


PLATFORMS = ("twitter", "reddit")


@dataclass
class CascadeNode:
    post_id: int
    author: str
    content: str
    created_at: str
    kind: str  # original | repost | quote | comment
    children: List["CascadeNode"] = field(default_factory=list)

    def to_dict(self, depth: int = 0) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "author": self.author,
            "content": self.content,
            "created_at": self.created_at,
            "kind": self.kind,
            "depth": depth,
            "children": [c.to_dict(depth + 1) for c in self.children],
        }


def _sim_dir(simulation_id: str) -> str:
    return os.path.join(
        os.path.dirname(__file__),
        "../../uploads/simulations",
        simulation_id,
    )


def db_path(simulation_id: str, platform: str) -> Optional[str]:
    path = os.path.join(_sim_dir(simulation_id), f"{platform}_simulation.db")
    return path if os.path.isfile(path) else None


def _connect_ro(path: str) -> sqlite3.Connection:
    # URI read-only so a live simulation writing the same file cannot lock us out.
    uri = f"file:{os.path.abspath(path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _user_names(conn: sqlite3.Connection) -> Dict[int, str]:
    names: Dict[int, str] = {}
    try:
        for row in conn.execute("SELECT user_id, name, user_name FROM user"):
            names[int(row["user_id"])] = (row["name"] or row["user_name"] or f"user_{row['user_id']}")
    except sqlite3.Error:
        pass
    return names


def _posts(conn: sqlite3.Connection, names: Dict[int, str]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    try:
        for row in conn.execute(
            "SELECT post_id, user_id, original_post_id, content, quote_content, created_at "
            "FROM post"
        ):
            pid = int(row["post_id"])
            uid = int(row["user_id"]) if row["user_id"] is not None else None
            out[pid] = {
                "post_id": pid,
                "user_id": uid,
                "author": names.get(uid, f"user_{uid}") if uid is not None else "unknown",
                "original_post_id": int(row["original_post_id"]) if row["original_post_id"] else None,
                "content": (row["content"] or "").strip(),
                "quote_content": (row["quote_content"] or "").strip() or None,
                "created_at": str(row["created_at"] or ""),
            }
    except sqlite3.Error:
        pass
    return out


def _trace_parents(conn: sqlite3.Connection) -> Dict[int, Tuple[int, str]]:
    """Map child post_id -> (parent_post_id, kind) from trace rows."""
    parents: Dict[int, Tuple[int, str]] = {}
    try:
        rows = conn.execute(
            "SELECT action, info FROM trace WHERE action IN ('quote_post', 'repost')"
        )
    except sqlite3.Error:
        return parents
    for row in rows:
        try:
            info = json.loads(row["info"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        child = info.get("new_post_id")
        if child is None:
            continue
        parent = info.get("quoted_id") if row["action"] == "quote_post" else info.get("reposted_id")
        if parent is None:
            parent = info.get("reposted_id") or info.get("quoted_id")
        if parent is None:
            continue
        kind = "quote" if row["action"] == "quote_post" else "repost"
        parents[int(child)] = (int(parent), kind)
    return parents


def _comment_leaves(
    conn: sqlite3.Connection, names: Dict[int, str]
) -> Dict[int, List[Dict[str, Any]]]:
    """Comments attach to posts only (flat by OASIS design)."""
    by_post: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    try:
        rows = conn.execute(
            "SELECT comment_id, post_id, user_id, content, created_at FROM comment"
        )
    except sqlite3.Error:
        return by_post
    for row in rows:
        uid = int(row["user_id"]) if row["user_id"] is not None else None
        by_post[int(row["post_id"])].append(
            {
                "post_id": -int(row["comment_id"]),  # negative id marks a comment leaf
                "author": names.get(uid, f"user_{uid}") if uid is not None else "unknown",
                "content": (row["content"] or "").strip(),
                "created_at": str(row["created_at"] or ""),
                "kind": "comment",
            }
        )
    return by_post


# Trace rows that are not an agent taking a turn on the platform.
_NOT_A_TURN = ("sign_up", "interview")


def _blind_activations(conn: sqlite3.Connection) -> Tuple[int, int]:
    """
    Return (blind_count, activation_count).

    An activation is one agent acting in one round, after the opening posts.
    It is blind when the agent got no feed that round, either because building
    it failed or because there was nothing to show. OASIS only records a
    refresh that succeeded, so a missing refresh is the signal.

    Rounds are found two ways, because the platforms stamp time differently:
    - a step counter shared by a refresh and the actions after it, or
    - wall-clock times. There, each round writes its refreshes together and
      then its actions, so a refresh that follows an action starts a new round.

    Matching refresh and action on the timestamp alone (the first version of
    this check) counted every wall-clock turn as blind, opening posts included.
    One limit of the wall-clock rule: a round in which every refresh failed
    cannot be told apart from the round before it and is counted as sighted.
    """
    try:
        rows = conn.execute(
            "SELECT rowid AS rid, user_id, created_at, action FROM trace "
            f"WHERE action NOT IN ({','.join('?' * len(_NOT_A_TURN))}) ORDER BY rowid",
            _NOT_A_TURN,
        ).fetchall()
    except sqlite3.Error:
        return 0, 0

    first_refresh = next((r["rid"] for r in rows if r["action"] == "refresh"), None)
    acted: Dict[Any, set] = defaultdict(set)
    refreshed: Dict[Any, set] = defaultdict(set)
    segment = 0
    prev_was_refresh = False
    for r in rows:
        stamp = str(r["created_at"])
        is_refresh = r["action"] == "refresh"
        if is_refresh and not prev_was_refresh:
            segment += 1
        prev_was_refresh = is_refresh
        round_key = ("step", stamp) if stamp.isdigit() else ("segment", segment)
        user = int(r["user_id"])
        if is_refresh:
            refreshed[round_key].add(user)
        # Opening posts are placed by the runner, not chosen by an agent.
        elif stamp != "0" and (first_refresh is None or r["rid"] > first_refresh or stamp.isdigit()):
            acted[round_key].add(user)
    activations = sum(len(users) for users in acted.values())
    blind = sum(len(users - refreshed[key]) for key, users in acted.items())
    return blind, activations


def _exposure_slot_counts(conn: sqlite3.Connection) -> Dict[int, int]:
    """How often each post_id appears in a refresh feed (impression slots)."""
    counts: Dict[int, int] = defaultdict(int)
    try:
        rows = conn.execute("SELECT info FROM trace WHERE action = 'refresh'")
    except sqlite3.Error:
        return counts
    for row in rows:
        try:
            info = json.loads(row["info"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        posts = info.get("posts")
        if isinstance(posts, dict):
            iterable: Iterable[Any] = posts.values()
        elif isinstance(posts, list):
            iterable = posts
        else:
            continue
        for item in iterable:
            if isinstance(item, dict) and item.get("post_id") is not None:
                counts[int(item["post_id"])] += 1
            elif isinstance(item, int):
                counts[item] += 1
    return counts


def _build_trees(
    posts: Dict[int, Dict[str, Any]],
    parents: Dict[int, Tuple[int, str]],
    comments: Dict[int, List[Dict[str, Any]]],
) -> List[CascadeNode]:
    children_map: Dict[int, List[Tuple[int, str]]] = defaultdict(list)
    for child, (parent, kind) in parents.items():
        if child in posts and parent in posts:
            children_map[parent].append((child, kind))

    def make_node(pid: int, kind: str) -> CascadeNode:
        p = posts[pid]
        node = CascadeNode(
            post_id=pid,
            author=p["author"],
            content=(p["quote_content"] or p["content"])[:280],
            created_at=p["created_at"],
            kind=kind,
        )
        for cid, ckind in sorted(children_map.get(pid, []), key=lambda x: x[0]):
            node.children.append(make_node(cid, ckind))
        for leaf in comments.get(pid, []):
            node.children.append(
                CascadeNode(
                    post_id=leaf["post_id"],
                    author=leaf["author"],
                    content=leaf["content"][:280],
                    created_at=leaf["created_at"],
                    kind="comment",
                )
            )
        return node

    child_ids = set(parents.keys())
    roots = [pid for pid in posts if pid not in child_ids]
    # Prefer chronological order of roots
    roots.sort(key=lambda pid: (posts[pid]["created_at"], pid))
    return [make_node(pid, "original") for pid in roots]


def _tree_metrics(node: CascadeNode) -> Dict[str, Any]:
    """Size, depth, breadth, structural virality for one cascade tree."""
    # Collect subtree sizes via post-order for virality W(T).
    sizes: Dict[int, int] = {}
    depths: Dict[int, int] = {}
    breadth: Dict[int, int] = defaultdict(int)
    edges: List[Tuple[int, int]] = []  # (parent, child) for W(T)

    def walk(n: CascadeNode, depth: int) -> int:
        depths[n.post_id] = depth
        breadth[depth] += 1
        total = 1
        for c in n.children:
            edges.append((n.post_id, c.post_id))
            total += walk(c, depth + 1)
        sizes[n.post_id] = total
        return total

    n = walk(node, 0)
    max_depth = max(depths.values()) if depths else 0
    max_breadth = max(breadth.values()) if breadth else 0
    # Structural virality ν = 2W / (n(n-1)); W = Σ_e s_e (n - s_e)
    if n <= 1:
        virality = 0.0
    else:
        w = 0
        for _parent, child in edges:
            s = sizes[child]
            w += s * (n - s)
        virality = round(2 * w / (n * (n - 1)), 3)

    shape = "orphan" if n == 1 else ("broadcast" if virality < 2.2 and max_depth <= 1 else "chain")
    return {
        "root_id": node.post_id,
        "root_author": node.author,
        "root_content": node.content,
        "size": n,
        "depth": max_depth,
        "breadth": max_breadth,
        "virality": virality,
        "shape": shape,
        "derived_posts": 0,  # filled by _annotate_derived
        "tree": node.to_dict(),
    }


def _annotate_derived(metrics: Dict[str, Any], node: CascadeNode) -> None:
    derived = 0

    def count(n: CascadeNode) -> None:
        nonlocal derived
        for c in n.children:
            if c.kind in ("repost", "quote"):
                derived += 1
            count(c)

    count(node)
    metrics["derived_posts"] = derived
    metrics["comment_leaves"] = metrics["size"] - 1 - derived if metrics["size"] else 0


def read_platform_dynamics(simulation_id: str, platform: str) -> Optional[Dict[str, Any]]:
    path = db_path(simulation_id, platform)
    if not path:
        return None
    try:
        conn = _connect_ro(path)
    except sqlite3.Error:
        return None
    try:
        names = _user_names(conn)
        posts = _posts(conn, names)
        parents = _trace_parents(conn)
        comments = _comment_leaves(conn, names)
        trees = _build_trees(posts, parents, comments)
        cascade_metrics = []
        for t in trees:
            m = _tree_metrics(t)
            _annotate_derived(m, t)
            cascade_metrics.append(m)

        cascade_metrics.sort(key=lambda m: (m["size"], m["depth"], m["virality"]), reverse=True)

        n_posts = len(posts)
        n_derived = sum(1 for _ in parents)
        branching = round(n_derived / n_posts, 3) if n_posts else 0.0
        orphans = [m for m in cascade_metrics if m["shape"] == "orphan"]
        blind, activations = _blind_activations(conn)
        slots = _exposure_slot_counts(conn)
        top_slot = max(slots.values()) if slots else 0
        slot_total = sum(slots.values()) or 1
        top_slot_share = round(top_slot / slot_total, 3)

        return {
            "platform": platform,
            "available": True,
            "posts": n_posts,
            "derived_posts": n_derived,
            "roots": len(cascade_metrics),
            "orphan_cascades": len(orphans),
            "orphan_share": round(len(orphans) / len(cascade_metrics), 3) if cascade_metrics else 0.0,
            "branching_factor": branching,
            "mean_tree_size": round(
                sum(m["size"] for m in cascade_metrics) / len(cascade_metrics), 3
            )
            if cascade_metrics
            else 0.0,
            "max_depth": max((m["depth"] for m in cascade_metrics), default=0),
            "max_size": max((m["size"] for m in cascade_metrics), default=0),
            "mean_virality": round(
                sum(m["virality"] for m in cascade_metrics if m["size"] > 1)
                / max(1, sum(1 for m in cascade_metrics if m["size"] > 1)),
                3,
            ),
            "blind_activations": blind,
            "activations": activations,
            "blind_share": round(blind / activations, 3) if activations else 0.0,
            "top_slot_share": top_slot_share,
            "users": len(names),
            "cascades": cascade_metrics[:25],  # top 25 for the UI
            "cascade_count": len(cascade_metrics),
        }
    finally:
        conn.close()


def read_simulation_traces(simulation_id: str) -> Dict[str, Any]:
    platforms = {}
    for p in PLATFORMS:
        data = read_platform_dynamics(simulation_id, p)
        if data is not None:
            platforms[p] = data
    return {
        "simulation_id": simulation_id,
        "platforms": platforms,
    }
