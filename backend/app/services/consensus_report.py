"""
Deterministic consensus / dynamics PDF for a finished (or in-progress) run.

Built from run_dynamics + optional ReportAgent markdown. The LLM-written
prediction report stays untouched; this appendix explains branching, orphans,
health and engagement consensus in plain language.

Uses PyMuPDF (already a dependency for seed-doc parsing).
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from .run_dynamics import build_dynamics


PAGE_W, PAGE_H = 595, 842  # A4
MARGIN = 48
INK = (0.04, 0.04, 0.04)
MUTED = (0.35, 0.35, 0.32)
LINE = (0.88, 0.88, 0.86)
GREEN = (0.12, 0.55, 0.38)
AMBER = (0.75, 0.5, 0.05)
RED = (0.75, 0.2, 0.15)


def _color(level: str) -> Tuple[float, float, float]:
    return {"green": GREEN, "amber": AMBER, "red": RED}.get(level, MUTED)


def _wrap(text: str, width: int = 92) -> List[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


class _Doc:
    def __init__(self) -> None:
        self.doc = fitz.open()
        self.page = None
        self.y = MARGIN
        self._new_page()

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = MARGIN

    def _ensure(self, need: float = 24) -> None:
        if self.y + need > PAGE_H - MARGIN:
            self._new_page()

    def heading(self, text: str, size: float = 18) -> None:
        self._ensure(size + 16)
        self.page.insert_text(
            (MARGIN, self.y + size),
            text,
            fontsize=size,
            fontname="helv",
            color=INK,
        )
        self.y += size + 10

    def subheading(self, text: str) -> None:
        self._ensure(28)
        self.page.insert_text(
            (MARGIN, self.y + 12),
            text,
            fontsize=12,
            fontname="helv",
            color=INK,
        )
        self.y += 20

    def body(self, text: str, color=MUTED, size: float = 10) -> None:
        for line in _wrap(text, width=88):
            self._ensure(size + 6)
            self.page.insert_text(
                (MARGIN, self.y + size),
                line,
                fontsize=size,
                fontname="helv",
                color=color,
            )
            self.y += size + 4

    def bullet(self, text: str) -> None:
        for i, line in enumerate(_wrap(text, width=84)):
            self._ensure(14)
            prefix = "•  " if i == 0 else "   "
            self.page.insert_text(
                (MARGIN + 8, self.y + 10),
                prefix + line,
                fontsize=10,
                fontname="helv",
                color=MUTED,
            )
            self.y += 14

    def rule(self) -> None:
        self._ensure(12)
        self.page.draw_line(
            fitz.Point(MARGIN, self.y + 4),
            fitz.Point(PAGE_W - MARGIN, self.y + 4),
            color=LINE,
            width=0.6,
        )
        self.y += 14

    def badge(self, level: str, label: str) -> None:
        self._ensure(28)
        c = _color(level)
        rect = fitz.Rect(MARGIN, self.y, MARGIN + 14, self.y + 14)
        self.page.draw_rect(rect, color=c, fill=c)
        self.page.insert_text(
            (MARGIN + 22, self.y + 11),
            f"{label}  ({level.upper()})",
            fontsize=11,
            fontname="helv",
            color=INK,
        )
        self.y += 22

    def kv(self, key: str, value: str) -> None:
        self._ensure(14)
        self.page.insert_text(
            (MARGIN, self.y + 10),
            key,
            fontsize=9,
            fontname="helv",
            color=MUTED,
        )
        self.page.insert_text(
            (MARGIN + 160, self.y + 10),
            value,
            fontsize=10,
            fontname="helv",
            color=INK,
        )
        self.y += 14


def _find_report_markdown(simulation_id: str, dynamics: Dict[str, Any]) -> Optional[str]:
    """Best-effort: locate a full_report.md linked to this simulation."""
    reports_root = os.path.join(
        os.path.dirname(__file__),
        "../../uploads/reports",
    )
    if not os.path.isdir(reports_root):
        return None
    # Prefer meta.json that mentions this simulation_id
    candidates: List[str] = []
    for name in os.listdir(reports_root):
        folder = os.path.join(reports_root, name)
        meta_path = os.path.join(folder, "meta.json")
        full = os.path.join(folder, "full_report.md")
        if not os.path.isfile(full):
            continue
        if os.path.isfile(meta_path):
            try:
                import json

                meta = json.loads(open(meta_path, encoding="utf-8").read())
                if meta.get("simulation_id") == simulation_id:
                    return open(full, encoding="utf-8").read()
            except (OSError, ValueError):
                pass
        candidates.append(full)
    return None


def build_consensus_pdf(simulation_id: str) -> bytes:
    dynamics = build_dynamics(simulation_id)
    health = dynamics["health"]
    cascades = dynamics["cascades"]["summary"]
    orphans = dynamics["orphans"]
    consensus = dynamics["consensus"]
    run = dynamics["run"]

    d = _Doc()
    d.heading("Hivemind consensus report")
    d.body(
        f"Simulation {simulation_id}  ·  generated "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    d.body(
        f"Run status: {run.get('status') or 'unknown'}  ·  "
        f"round {run.get('current_round') if run.get('current_round') is not None else '–'}"
        f" / {run.get('total_rounds') or '–'}"
    )
    d.rule()

    d.subheading("1. Run health")
    d.badge(health["overall"], health["headline"])
    for reason in health.get("reasons") or []:
        d.bullet(reason)
    d.y += 4
    for check in health.get("checks") or []:
        d.kv(
            check["label"],
            f"{check['level'].upper()} — {check.get('detail') or ''}",
        )

    d.rule()
    d.subheading("2. Branching & orphans")
    bf = cascades.get("branching_factor")
    d.body(
        f"Branching factor: {bf if bf is not None else '–'} "
        f"(each post produces about {bf if bf is not None else 'n/a'} follow-on posts)."
    )
    d.body(
        f"Cascade roots: {cascades.get('roots', 0)}  ·  "
        f"orphan cascades (never branched): {orphans.get('cascade_orphans', 0)} "
        f"({round((orphans.get('cascade_orphan_share') or 0) * 100)}%)  ·  "
        f"max depth: {cascades.get('max_depth', 0)}  ·  "
        f"mean structural virality: {cascades.get('mean_virality') if cascades.get('mean_virality') is not None else '–'}"
    )
    d.body(orphans.get("plain") or "")
    if orphans.get("silent_agents"):
        d.body("Silent rostered agents (sample):")
        d.bullet(", ".join(orphans["silent_agents"][:12]))
    d.body(
        "Shape guide: orphan = seed alone; broadcast = star of depth 1 (feed push); "
        "chain = deeper word-of-mouth."
    )

    d.rule()
    d.subheading("3. Top cascades")
    top = dynamics["cascades"].get("top") or []
    if not top:
        d.body("No cascades reconstructed yet (simulation DB missing or still seeding).")
    for i, c in enumerate(top[:8], 1):
        d.body(
            f"{i}. [{c.get('platform')}] {c.get('root_author')} — "
            f"size {c.get('size')}, depth {c.get('depth')}, "
            f"virality {c.get('virality')}, shape={c.get('shape')}",
            color=INK,
        )
        snippet = (c.get("root_content") or "").replace("\n", " ")
        if snippet:
            d.body(f"   “{snippet[:160]}{'…' if len(snippet) > 160 else ''}”")

    d.rule()
    d.subheading("4. Engagement consensus")
    d.body(consensus.get("plain") or "", color=INK)
    d.kv("Verdict", str(consensus.get("verdict")))
    share = consensus.get("crowd_support_share")
    d.kv(
        "Crowd support share",
        f"{round(share * 100)}%" if share is not None else "–",
    )
    d.kv(
        "Support / oppose actions",
        f"{consensus.get('support_actions', 0)} / {consensus.get('oppose_actions', 0)}",
    )
    if consensus.get("amplified_agents"):
        d.body("Most amplified agents:")
        for a in consensus["amplified_agents"][:6]:
            appr = a.get("approval")
            d.bullet(
                f"{a['name']}: engagement {a.get('engagement', 0)}, "
                f"approval {round(appr * 100) if appr is not None else '–'}%"
            )

    d.rule()
    d.subheading("5. How to read this")
    d.bullet(
        "Branching factor < 1 means conversations die out; near 0 means almost pure broadcasting."
    )
    d.bullet(
        "Structural virality near 2 is a star (one post, many direct reactions); higher values mean chains."
    )
    d.bullet(
        "Orphan cascades are normal online (most real cascades are the seed alone) — "
        "a high orphan share with a red health badge still means the forecast is fragile."
    )
    d.bullet(
        "This PDF is deterministic from the run traces. The narrative Prediction Report "
        "(if generated) is written separately by the Report Agent."
    )

    report_md = _find_report_markdown(simulation_id, dynamics)
    if report_md:
        d.rule()
        d.subheading("6. Prediction report excerpt")
        # First ~40 non-empty lines of the markdown, stripped of headings markers lightly
        lines = [ln.strip() for ln in report_md.splitlines() if ln.strip()]
        for ln in lines[:35]:
            clean = ln.lstrip("#").strip()
            if clean.startswith("|"):
                continue
            d.body(clean[:200])

    buf = io.BytesIO()
    d.doc.save(buf)
    d.doc.close()
    return buf.getvalue()


def write_consensus_pdf(simulation_id: str, dest_path: Optional[str] = None) -> str:
    from .simulation_runner import SimulationRunner

    data = build_consensus_pdf(simulation_id)
    if dest_path is None:
        dest_path = os.path.join(
            SimulationRunner.RUN_STATE_DIR,
            simulation_id,
            "consensus_report.pdf",
        )
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(data)
    return dest_path
