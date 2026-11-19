"""
The Hivemind briefing PDF: the one document to read after a run.

It leads with what the run means (run_briefing): the bottom line, where the
simulated voices agree and split, how each group and each company reacted and
what they would likely do next. The story of the run (run_recap) follows, and
the technical run diagnostics (run_dynamics) close it as an appendix.

Everything is read-only over the run's outputs. Uses PyMuPDF (already a
dependency for seed-doc parsing).
"""

from __future__ import annotations

import io
import os
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from .run_dynamics import build_dynamics


PAGE_W, PAGE_H = 595, 842  # A4
MARGIN = 52
CONTENT_W = PAGE_W - 2 * MARGIN
BOTTOM = PAGE_H - 56

# Brand kit (docs/BRAND.md)
INK = (0.086, 0.078, 0.059)
INK_3 = (0.333, 0.314, 0.282)
MUTED = (0.451, 0.427, 0.388)
LINE = (0.894, 0.867, 0.824)
SURFACE = (0.973, 0.965, 0.945)
SIGNAL = (0.831, 0.537, 0.039)
ON_INK = (0.941, 0.659, 0.094)
PAPER = (0.953, 0.941, 0.910)
GREEN = (0.12, 0.50, 0.36)
AMBER = (0.72, 0.46, 0.02)
RED = (0.72, 0.22, 0.16)

SANS, BOLD, ITALIC, MONO = "helv", "hebo", "heit", "cour"

PLATFORM_NAMES = {"twitter": "Info Plaza", "reddit": "Topic Community"}

STANCE_STYLE = {
    "supportive": ("Supportive", GREEN),
    "critical": ("Critical", RED),
    "cautious": ("Cautious", AMBER),
    "divided": ("Divided", AMBER),
    "neutral": ("Neutral", MUTED),
    "quiet": ("Silent in this run", MUTED),
}
STRENGTH_STYLE = {
    "strong": ("Strong agreement", GREEN),
    "moderate": ("Moderate agreement", AMBER),
    "weak": ("Weak agreement", MUTED),
}
CONFIDENCE_COLOR = {"high": GREEN, "medium": AMBER, "low": RED}


def _color(level: str) -> Tuple[float, float, float]:
    return {"green": GREEN, "amber": AMBER, "red": RED}.get(level, MUTED)


# The base-14 Helvetica used here only encodes Latin-1, so typographic
# punctuation would otherwise print as a stray glyph.
_PUNCT = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",
    "\u2026": "...", "\u2022": "\u00b7", "\u00a0": " ", "\u2009": " ", "\u202f": " ",
})


def _latin1(text: str) -> str:
    out = []
    for ch in (text or "").translate(_PUNCT):
        if ord(ch) < 256:
            out.append(ch)
        elif unicodedata.category(ch).startswith("S"):
            continue  # emoji and other symbols: drop rather than print "?"
        else:
            out.append("?")
    return "".join(out)


def _insert(page, point, text: str, **kwargs) -> None:
    page.insert_text(point, _latin1(text), **kwargs)


def _wrap(text: str, fontname: str, size: float, width: float) -> List[str]:
    """Greedy word wrap by measured width. Paragraph breaks are kept."""
    lines: List[str] = []
    for para in _latin1(text or "").split("\n"):
        words = para.split()
        if not words:
            continue
        cur = words[0]
        for w in words[1:]:
            if fitz.get_text_length(cur + " " + w, fontname=fontname, fontsize=size) <= width:
                cur += " " + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines or [""]


def _pct(x: Optional[float]) -> str:
    return "-" if x is None else f"{round(x * 100)}%"


class _Doc:
    def __init__(self, footer: str) -> None:
        self.doc = fitz.open()
        self.footer = footer
        self.page = None
        self.y = MARGIN
        self._new_page()

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = MARGIN

    def ensure(self, need: float = 24) -> None:
        if self.y + need > BOTTOM:
            self._new_page()

    def text(self, text: str, *, font: str = SANS, size: float = 10, color=INK_3, indent: float = 0,
             width: Optional[float] = None, leading: float = 1.42, after: float = 0) -> None:
        width = width if width is not None else CONTENT_W - indent
        step = size * leading
        for line in _wrap(text, font, size, width):
            self.ensure(step)
            self.page.insert_text((MARGIN + indent, self.y + size), line, fontsize=size, fontname=font, color=color)
            self.y += step
        self.y += after

    def label(self, text: str, color=SIGNAL) -> None:
        """Small spaced caps label above a block."""
        self.ensure(16)
        self.page.insert_text(
            (MARGIN, self.y + 7.5), _latin1(" ".join(text.upper())), fontsize=7.5, fontname=BOLD, color=color,
        )
        self.y += 15

    def section(self, label: str, title: str, note: str = "") -> None:
        self.ensure(90)
        self.y += 10
        self.page.draw_line(fitz.Point(MARGIN, self.y), fitz.Point(PAGE_W - MARGIN, self.y), color=LINE, width=0.8)
        self.y += 14
        self.label(label)
        self.text(title, font=BOLD, size=15, color=INK, leading=1.25, after=4)
        if note:
            self.text(note, size=8.5, color=MUTED, after=6)

    def bullet(self, text: str, size: float = 10, color=INK_3) -> None:
        self.ensure(size * 1.42)
        self.page.draw_circle(fitz.Point(MARGIN + 4, self.y + size * 0.62), 1.6, color=SIGNAL, fill=SIGNAL)
        self.text(text, size=size, color=color, indent=14, after=3)

    def pill(self, text: str, color, x: Optional[float] = None, right: bool = False, y: Optional[float] = None) -> float:
        """A small outlined tag. Returns its width. Does not move the cursor."""
        text = _latin1(text)
        size = 7.5
        w = fitz.get_text_length(text, fontname=BOLD, fontsize=size) + 12
        x0 = (PAGE_W - MARGIN - w) if right else (MARGIN if x is None else x)
        y0 = self.y if y is None else y
        self.page.draw_rect(fitz.Rect(x0, y0, x0 + w, y0 + 13), color=color, width=0.8, radius=0.3)
        self.page.insert_text((x0 + 6, y0 + 9.3), text, fontsize=size, fontname=BOLD, color=color)
        return w

    def labelled(self, lead: str, text: str, size: float = 9.5) -> None:
        """"Likely next:" in bold, then the text, wrapped under it with a hanging indent."""
        if not text:
            return
        lead_w = fitz.get_text_length(_latin1(lead) + " ", fontname=BOLD, fontsize=size)
        self.ensure(size * 1.42)
        self.page.insert_text((MARGIN, self.y + size), _latin1(lead), fontsize=size, fontname=BOLD, color=INK)
        self.text(text, size=size, color=INK_3, indent=lead_w, after=3)

    def quote(self, text: str, attribution: str) -> None:
        self.ensure(34)
        top = self.y
        self.text(f"\u201c{text}\u201d", font=ITALIC, size=9, color=INK_3, indent=12)
        self.text(attribution, size=8, color=MUTED, indent=12)
        if self.y > top:  # no rule across a page break
            self.page.draw_line(fitz.Point(MARGIN + 3, top + 2), fitz.Point(MARGIN + 3, self.y - 2), color=SIGNAL, width=1.6)
        self.y += 6

    def bar(self, share: Optional[float], x: float, y: float, w: float = 60) -> None:
        self.page.draw_rect(fitz.Rect(x, y, x + w, y + 4), color=None, fill=LINE)
        if share is not None and share > 0:
            self.page.draw_rect(fitz.Rect(x, y, x + w * min(share, 1), y + 4), color=None, fill=GREEN)

    def stats(self, items: List[Tuple[str, str]]) -> None:
        """A row of headline numbers."""
        self.ensure(52)
        gap = 8
        w = (CONTENT_W - gap * (len(items) - 1)) / len(items)
        for i, (value, caption) in enumerate(items):
            x = MARGIN + i * (w + gap)
            self.page.draw_rect(fitz.Rect(x, self.y, x + w, self.y + 44), color=LINE, fill=SURFACE, width=0.6)
            self.page.insert_text((x + 9, self.y + 20), _latin1(value), fontsize=15, fontname=BOLD, color=INK)
            self.page.insert_text((x + 9, self.y + 34), _latin1(caption), fontsize=7.5, fontname=SANS, color=MUTED)
        self.y += 54

    def kv(self, key: str, value: str) -> None:
        self.ensure(14)
        self.page.insert_text((MARGIN, self.y + 9), _latin1(key), fontsize=8.5, fontname=SANS, color=MUTED)
        self.text(value, size=9, color=INK, indent=150, after=1)

    def finish(self) -> bytes:
        total = len(self.doc)
        for i, page in enumerate(self.doc, 1):
            page.draw_line(fitz.Point(MARGIN, PAGE_H - 40), fitz.Point(PAGE_W - MARGIN, PAGE_H - 40), color=LINE, width=0.6)
            page.insert_text((MARGIN, PAGE_H - 27), _latin1(self.footer), fontsize=7.5, fontname=SANS, color=MUTED)
            num = f"{i} / {total}"
            page.insert_text(
                (PAGE_W - MARGIN - fitz.get_text_length(num, fontname=SANS, fontsize=7.5), PAGE_H - 27),
                num, fontsize=7.5, fontname=SANS, color=MUTED,
            )
        buf = io.BytesIO()
        self.doc.save(buf, deflate=True)
        self.doc.close()
        return buf.getvalue()


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


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #

def _cover(d: _Doc, simulation_id: str, question: str, run: Dict[str, Any]) -> None:
    band = 118
    d.page.draw_rect(fitz.Rect(0, 0, PAGE_W, band), color=None, fill=INK)
    d.page.insert_text((MARGIN, 44), "H I V E M I N D", fontsize=8, fontname=BOLD, color=ON_INK)
    d.page.insert_text((MARGIN, 78), "Briefing", fontsize=28, fontname=BOLD, color=PAPER)
    status = "finished run" if run.get("finished") else "run still in progress"
    d.page.insert_text(
        (MARGIN, 98),
        _latin1(f"{datetime.now(timezone.utc).strftime('%d %B %Y')}  ·  {status}  ·  {simulation_id}"),
        fontsize=8.5, fontname=SANS, color=(0.72, 0.69, 0.65),
    )
    d.y = band + 22
    if question:
        d.label("The question")
        q = question if len(question) <= 700 else question[:700].rsplit(" ", 1)[0] + "..."
        d.text(q, size=10, color=INK, after=6)


def _briefing(d: _Doc, briefing: Dict[str, Any]) -> None:
    facts, reading, conf = briefing["facts"], briefing["reading"], briefing["confidence"]
    run = facts["run"]
    fact_groups = {g["key"]: g for g in facts["groups"]}
    fact_companies = {c["name"]: c for c in facts["companies"]}

    d.y += 4
    d.label("The bottom line")
    d.text(reading.get("bottom_line") or "", font=BOLD, size=13, color=INK, leading=1.35, after=8)

    c = CONFIDENCE_COLOR.get(conf["level"], MUTED)
    d.ensure(30)
    w = d.pill(f"How far to trust this: {conf['label']}", c)
    d.y += 1
    d.text(conf["why"], size=8.5, color=MUTED, indent=w + 8, after=8)

    d.stats([
        (f"{run['people_active']} of {run['people_total']}", "simulated people took part"),
        (str(run["posts"] + run["replies"]), "posts and replies written"),
        (str(run["approving"] + run["disapproving"]), "reactions to posts"),
        (_pct(run["reception"]), "of reactions were approving"),
    ])
    if (run.get("cast") or {}).get("note"):
        d.text(run["cast"]["note"], size=8.5, color=MUTED, after=8)

    if reading.get("what_it_means"):
        d.label("What it means")
        for point in reading["what_it_means"]:
            d.bullet(point, color=INK)

    d.section("Consensus", "Where the simulated voices agree",
              "Agreement means several groups made the same point, or one group's point was backed by others.")
    if not reading.get("consensus"):
        d.text("No point drew clear agreement across groups in this run.")
    for item in reading.get("consensus") or []:
        label, colour = STRENGTH_STYLE.get(item.get("strength"), STRENGTH_STYLE["moderate"])
        d.ensure(50)
        d.pill(label, colour)
        d.y += 18
        d.text(item["point"], size=10.5, color=INK)
        if item.get("held_by"):
            d.text("Held by: " + ", ".join(item["held_by"]), size=8.5, color=MUTED)
        d.y += 8

    d.section("Disagreement", "Where they split")
    if not reading.get("splits"):
        d.text("No clear disagreement showed up in what people wrote or how they reacted.")
    for item in reading.get("splits") or []:
        d.ensure(60)
        d.text(item["issue"], font=BOLD, size=10.5, color=INK, after=2)
        d.labelled("One side:", item["side_a"])
        d.labelled("Other side:", item["side_b"])
        d.y += 6

    d.section("Reactions", "How each group reacted",
              "Groups come from the roles the simulation gave each participant. "
              "The bar shows how warmly a group's posts were received, not its opinion.")
    for g in reading.get("groups") or []:
        fg = fact_groups.get(g["key"])
        if not fg:
            continue
        d.ensure(86)
        label, colour = STANCE_STYLE.get(g.get("stance"), STANCE_STYLE["neutral"])
        d.pill(label, colour, right=True, y=d.y + 1)
        d.text(fg["label"], font=BOLD, size=11.5, color=INK, leading=1.3)
        reactions = fg["approving_received"] + fg["disapproving_received"]
        meta = (
            f"{fg['active']} of {fg['members']} took part  ·  {fg['posts']} posts, {fg['replies']} replies  ·  "
            + (f"{_pct(fg['reception'])} of the {reactions} reaction{'s' if reactions != 1 else ''} to their posts approving"
               if reactions else "no reactions to their posts")
        )
        y_meta = d.y
        d.text(meta, size=8, color=MUTED, width=CONTENT_W - 72, after=4)
        if reactions:
            d.bar(fg["reception"], PAGE_W - MARGIN - 60, y_meta + 4)
        d.text(g["reaction"], size=10, color=INK_3, after=3)
        d.labelled("Likely next:", g.get("likely_next") or "")
        if fg["said"]:
            s = fg["said"][0]
            d.quote(s["text"], f"{s['author']} on {PLATFORM_NAMES.get(s['platform'], s['platform'])}")
        d.y += 8

    if reading.get("companies"):
        d.section("Companies", "How each company reacted, and its likely move",
                  "Companies and executives that wrote at least one post or reply in this run.")
        for co in reading["companies"]:
            fc = fact_companies.get(co["name"]) or {}
            d.ensure(54)
            d.text(co["name"], font=BOLD, size=10.5, color=INK, leading=1.3)
            if fc.get("kind"):
                d.text(f"{fc['kind']}  ·  {fc.get('posts', 0)} posts, {fc.get('replies', 0)} replies", size=8, color=MUTED, after=2)
            d.labelled("Position:", co.get("position") or "")
            d.labelled("Likely move:", co.get("likely_move") or "")
            d.y += 6

    if reading.get("watch"):
        d.section("Next", "What to watch")
        for w_ in reading["watch"]:
            d.bullet(w_, color=INK)

    d.y += 4
    d.text(
        ("Reading written by Hivemind's AI from this run's posts and reactions only. "
         if briefing.get("reading_source") == "llm" else
         "Quick reading generated from this run's counts; open Analytics to have the full reading written. ")
        + "Every participant is simulated. \"Likely next\" and \"Likely move\" are inferences from what the "
          "simulated participants wrote, not statements by the real organisations.",
        size=8, color=MUTED,
    )


def _what_happened(d: _Doc, recap: Dict[str, Any]) -> None:
    """The plain-language story of the run, in time order (see run_recap)."""
    facts = recap.get("facts") or {}
    story = recap.get("story") or {}
    chapters = {c["index"]: c for c in facts.get("chapters") or []}

    d.section("The story", "What happened")
    d.text(story.get("headline") or "", font=BOLD, size=11.5, color=INK, leading=1.35, after=3)
    d.text(story.get("summary") or "", color=INK, after=6)

    if story.get("opening"):
        d.text("How it started", font=BOLD, color=INK)
        d.text(story["opening"], after=6)

    for item in story.get("chapters") or []:
        ch = chapters.get(item.get("index"))
        if not ch:
            continue
        d.ensure(60)
        d.text(f"{ch['time']}  ·  {item.get('title') or ''}", font=BOLD, color=INK)
        d.text(item.get("story") or "")
        tone = ch.get("tone")
        d.text(
            f"{ch.get('posts', 0)} posts · {ch.get('replies', 0)} replies · "
            f"{ch.get('approving', 0) + ch.get('disapproving', 0)} reactions"
            f" ({round(tone * 100)}% approving)" if tone is not None else
            f"{ch.get('posts', 0)} posts · {ch.get('replies', 0)} replies · no reactions",
            size=8, color=MUTED, after=3,
        )
        standouts = ch.get("standout_posts") or []
        if standouts:
            sp = standouts[0]
            d.quote(
                sp["text"],
                f"{sp['author']} on {PLATFORM_NAMES.get(sp['platform'], sp['platform'])} · "
                f"{sp.get('reactions_in_chapter', 0)} reactions in this stretch",
            )
        d.y += 4

    if story.get("ending"):
        d.text("Where it ended up", font=BOLD, color=INK)
        d.text(story["ending"], color=INK, after=4)
    for t in story.get("takeaways") or []:
        d.bullet(t)
    d.text(
        ("Story written by Hivemind's AI from this run's posts and reactions only."
         if recap.get("story_source") == "llm"
         else "Quick summary generated from this run's data. Open Analytics to have the full story written.")
        + " Quotes are real posts from the simulation.",
        size=8, color=MUTED,
    )


def _appendix(d: _Doc, dynamics: Dict[str, Any]) -> None:
    health = dynamics["health"]
    cascades = dynamics["cascades"]["summary"]
    orphans = dynamics["orphans"]

    d.section("Appendix", "Run diagnostics",
              "For anyone checking how the simulation behaved. You do not need this to use the briefing.")
    d.ensure(40)
    d.pill(health["overall"].upper(), _color(health["overall"]))
    d.y += 1
    d.text(health["headline"], font=BOLD, size=10, color=INK, indent=60, after=5)
    for reason in health.get("reasons") or []:
        d.bullet(reason, size=9)
    d.y += 4
    for check in health.get("checks") or []:
        d.kv(check["label"], f"{check['level'].upper()} - {check.get('detail') or ''}")

    d.y += 8
    d.text("How posts spread", font=BOLD, color=INK, after=2)
    bf = cascades.get("branching_factor")
    d.kv("Follow-ons per post", f"{bf if bf is not None else '-'} (below 1 means conversations die out)")
    d.kv("Conversation starters", str(cascades.get("roots", 0)))
    d.kv(
        "Posts nobody picked up",
        f"{orphans.get('cascade_orphans', 0)} ({round((orphans.get('cascade_orphan_share') or 0) * 100)}%)",
    )
    d.kv("Longest reply chain", str(cascades.get("max_depth", 0)))
    if orphans.get("plain"):
        d.text(orphans["plain"], size=9, after=2)
    if orphans.get("silent_agents"):
        d.kv("Silent participants", ", ".join(orphans["silent_agents"][:12]))

    top = dynamics["cascades"].get("top") or []
    if top:
        d.y += 8
        d.text("Biggest conversations", font=BOLD, color=INK, after=2)
    for i, c in enumerate(top[:6], 1):
        d.ensure(34)
        d.text(
            f"{i}. {c.get('root_author')} on {PLATFORM_NAMES.get(c.get('platform'), c.get('platform'))}: "
            f"{c.get('size')} posts, {c.get('depth')} deep",
            size=9, color=INK,
        )
        snippet = (c.get("root_content") or "").replace("\n", " ")
        if snippet:
            d.text(f"\u201c{snippet[:170]}{'...' if len(snippet) > 170 else ''}\u201d", font=ITALIC, size=8.5, indent=12, after=2)


def build_consensus_pdf(simulation_id: str, write: bool = False) -> bytes:
    """Build the briefing PDF.

    write=True has the LLM write the reading and the story first when the run
    has finished and they are missing (both are cached, so this costs once per
    run). Otherwise, or if the model call fails, the template versions are used.
    """
    from .run_briefing import get_briefing, write_briefing
    from .run_recap import get_recap, write_recap

    dynamics = build_dynamics(simulation_id)

    briefing = get_briefing(simulation_id, dynamics=dynamics)
    if write and briefing["can_write"] and briefing["facts"]["run"]["finished"] and briefing["reading_source"] != "llm":
        try:
            briefing = write_briefing(simulation_id)
        except Exception:  # the PDF must still download without the model
            pass

    recap = None
    try:
        recap = get_recap(simulation_id, dynamics=dynamics)
        if write and recap["can_write"] and recap["facts"]["run"].get("finished") and recap["story_source"] != "llm":
            recap = write_recap(simulation_id)
    except Exception:  # the story is optional; never block the PDF on it
        pass

    d = _Doc(footer="Hivemind briefing  ·  a simulation of how people might react, not a record of real events")
    _cover(d, simulation_id, briefing["facts"]["question"], briefing["facts"]["run"])
    _briefing(d, briefing)
    if recap and (recap.get("facts") or {}).get("chapters"):
        _what_happened(d, recap)
    _appendix(d, dynamics)

    report_md = _find_report_markdown(simulation_id, dynamics)
    if report_md:
        d.section("Appendix", "Prediction report excerpt", "The opening of the report agent's separate long-form report.")
        lines = [ln.strip() for ln in report_md.splitlines() if ln.strip()]
        for ln in lines[:35]:
            clean = ln.lstrip("#").strip()
            if clean.startswith("|"):
                continue
            d.text(clean[:300], size=9)
    return d.finish()


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
