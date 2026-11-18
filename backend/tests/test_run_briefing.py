"""Tests for the briefing: groups, facts, readings, caching and the PDF."""

from pathlib import Path

import pytest

from app.services import run_briefing
from app.services.run_briefing import (
    _facts_for_llm,
    _merge_reading,
    build_briefing_facts,
    confidence_for,
    group_for,
    template_reading,
    type_label,
)


def act(round_num, name, action_type, platform="twitter", **args):
    return {
        "round_num": round_num,
        "timestamp": f"2026-11-13T00:{round_num:02d}:00",
        "platform": platform,
        "agent_name": name,
        "action_type": action_type,
        "action_args": args,
    }


ROSTER = [
    {"entity_name": "Acme", "entity_type": "PublicCompany", "stance": "supportive"},
    {"entity_name": "Rival Corp", "entity_type": "TechCompany", "stance": "neutral"},
    {"entity_name": "The Ledger", "entity_type": "MediaOutlet", "stance": "neutral"},
    {"entity_name": "Trade Board", "entity_type": "RegulatoryAgency", "stance": "opposing"},
    {"entity_name": "Northbank", "entity_type": "InvestmentAnalystFirm", "stance": "neutral"},
    {"entity_name": "Sam", "entity_type": "Person", "stance": "observer"},
]
ACME = "We are raising prices by 10% from January."
BOARD = "We will review whether the increase is justified."


def sample_actions():
    return [
        act(0, "Acme", "CREATE_POST", content=ACME),
        act(0, "Acme", "CREATE_POST", platform="reddit", content=ACME),
        act(1, "Trade Board", "CREATE_POST", content=BOARD),
        act(1, "The Ledger", "LIKE_POST", post_content=BOARD, post_author_name="Trade Board"),
        act(1, "Northbank", "LIKE_POST", post_content=BOARD, post_author_name="Trade Board"),
        act(2, "Northbank", "DISLIKE_POST", post_content=ACME, post_author_name="Acme"),
        act(2, "The Ledger", "CREATE_COMMENT", platform="reddit", content="How will customers respond?",
            post_content=ACME, post_author_name="Acme"),
        act(2, "Sam", "DO_NOTHING"),
        act(3, "Acme", "INTERVIEW", prompt="ignored"),
    ]


def facts(**kw):
    return build_briefing_facts(sample_actions(), ROSTER, requirement="How will people react?",
                                run={"status": "completed"}, **kw)


def test_entity_types_map_to_reader_groups():
    assert group_for("PublicCompany") == "companies"
    assert group_for("NvidiaExecutive") == "companies"
    assert group_for("InvestmentAnalystFirm") == "investors"   # not "companies" via "firm"
    assert group_for("LegalFirm") == "experts"
    assert group_for("RegulatoryAgency") == "government"
    assert group_for("FinancialMediaOutlet") == "media"
    assert group_for("Person") == "public"
    assert group_for("Widget") == "other"
    assert group_for(None) == "other"
    assert type_label("InvestmentAnalystFirm") == "Investment analyst firm"


def test_facts_group_people_and_count_reception():
    f = facts()
    groups = {g["key"]: g for g in f["groups"]}
    assert set(groups) == {"media", "investors", "government", "companies", "public"}

    gov = groups["government"]
    assert (gov["posts"], gov["approving_received"], gov["disapproving_received"]) == (1, 2, 0)
    assert gov["reception"] == 1.0
    assert gov["said"][0]["text"] == BOARD

    co = groups["companies"]
    assert co["members"] == 2 and co["active"] == 1
    assert co["posts"] == 2            # the seed went out on both platforms...
    assert len(co["said"]) == 1        # ...but is one distinct post
    assert co["disapproving_received"] == 1 and co["replies_received"] == 1
    assert co["silent"] == ["Rival Corp"]

    assert groups["public"]["posts"] == 0 and groups["public"]["active"] == 0
    assert f["run"]["people_total"] == 6 and f["run"]["people_active"] == 4
    assert f["run"]["finished"] is True
    assert [c["name"] for c in f["companies"]] == ["Acme"]      # silent companies are left out
    assert f["most_backed_posts"][0]["author"] == "Trade Board"
    assert f["most_disputed_posts"][0]["author"] == "Acme"
    assert {"from": "Media", "to": "Government and regulators", "approving": 1, "disapproving": 0} in f["who_backed_whom"]


def test_template_reading_has_every_group_and_marks_silence():
    f = facts()
    reading = template_reading(f)
    assert [g["key"] for g in reading["groups"]] == [g["key"] for g in f["groups"]]
    assert {g["key"]: g["stance"] for g in reading["groups"]}["public"] == "quiet"
    assert reading["bottom_line"]
    assert reading["companies"][0]["position"] == ACME


def test_confidence_is_low_for_thin_or_unfinished_runs():
    assert confidence_for(facts(health={"overall": "green"}))["level"] == "low"      # 4 posts is thin
    f = facts(health={"overall": "green"})
    f["run"].update(posts=80, replies=40, people_active=6)
    assert confidence_for(f)["level"] == "high"
    f["caveats"]["level"] = "red"
    assert confidence_for(f)["level"] == "low"
    f["caveats"]["level"] = "green"
    f["run"]["finished"] = False
    assert confidence_for(f)["level"] == "low"


def test_merge_reading_validates_and_falls_back():
    f = facts()
    fallback = template_reading(f)
    merged = _merge_reading({
        "bottom_line": "  Regulators pushed back.  ",
        "what_it_means": ["Expect a review.", 7, ""],
        "consensus": [
            {"point": "A review is warranted.", "held_by": ["Media", "Martians"], "strength": "overwhelming"},
            {"point": ""},
        ],
        "splits": [{"issue": "Price", "side_a": "Acme", "side_b": ""}],
        "groups": [
            {"key": "government", "stance": "critical", "reaction": "They announced a review.", "likely_next": "Open a review."},
            {"key": "public", "stance": "supportive", "reaction": "They cheered."},
            {"key": "nonsense", "reaction": "x"},
        ],
        "companies": [{"name": "Acme", "position": "Defended the rise.", "likely_move": "Hold the line."}],
        "watch": ["The review's timing."],
    }, fallback, f)

    assert merged["bottom_line"] == "Regulators pushed back."
    assert merged["what_it_means"] == ["Expect a review."]
    assert merged["consensus"] == [{"point": "A review is warranted.", "held_by": ["Media"], "strength": "moderate"}]
    assert merged["splits"] == []                       # incomplete split dropped
    groups = {g["key"]: g for g in merged["groups"]}
    assert groups["government"]["likely_next"] == "Open a review."
    assert groups["public"]["stance"] == "quiet"        # wrote nothing, whatever the model says
    assert groups["media"] == {g["key"]: g for g in fallback["groups"]}["media"]
    assert merged["companies"][0]["likely_move"] == "Hold the line."

    # An explicit empty list means "no real agreement" and is kept; a missing key falls back.
    assert _merge_reading({"consensus": []}, fallback, f)["consensus"] == []
    assert _merge_reading({}, fallback, f)["consensus"] == fallback["consensus"]


def test_llm_never_sees_raw_platform_names():
    import json

    blob = json.dumps(_facts_for_llm(facts()))
    assert "twitter" not in blob and "reddit" not in blob
    assert "Info Plaza" in blob


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def chat_json(self, messages, **kwargs):
        self.calls += 1
        return {"bottom_line": f"Reading {self.calls}.", "consensus": [], "splits": []}


def test_write_briefing_caches_and_reuses(monkeypatch, tmp_path):
    f = facts()
    state = {"fp": "a"}
    monkeypatch.setattr(run_briefing, "_sim_dir", lambda sid: str(tmp_path))
    monkeypatch.setattr(run_briefing, "_load_inputs", lambda sid, dynamics=None: (f, state["fp"]))
    llm = FakeLLM()

    first = run_briefing.write_briefing("sim_x", llm_client=llm)
    assert first["reading_source"] == "llm" and first["reading"]["bottom_line"] == "Reading 1."
    assert (tmp_path / "briefing.json").is_file()

    run_briefing.write_briefing("sim_x", llm_client=llm)
    assert llm.calls == 1
    assert run_briefing.get_briefing("sim_x")["reading"]["bottom_line"] == "Reading 1."

    assert run_briefing.write_briefing("sim_x", force=True, llm_client=llm)["reading"]["bottom_line"] == "Reading 2."

    state["fp"] = "b"   # the run moved on: the cached reading no longer applies
    stale = run_briefing.get_briefing("sim_x")
    assert stale["reading_source"] == "template" and stale["reading_stale"] is True


EXAMPLE_SIM = "sim_168d7ecb477b"
UPLOADS = Path(__file__).resolve().parents[1] / "uploads" / "simulations" / EXAMPLE_SIM


@pytest.mark.skipif(not UPLOADS.is_dir(), reason="example simulation not on disk")
def test_briefing_pdf_on_example_run(monkeypatch):
    import fitz

    from app.services.consensus_report import build_consensus_pdf

    monkeypatch.setattr(run_briefing, "_load_cache", lambda sid: None)   # template path, no model
    briefing = run_briefing.get_briefing(EXAMPLE_SIM)
    assert {g["key"] for g in briefing["facts"]["groups"]} >= {"companies", "government", "media", "investors"}
    assert briefing["facts"]["companies"]

    doc = fitz.open(stream=build_consensus_pdf(EXAMPLE_SIM))
    text = "".join(page.get_text() for page in doc)
    for heading in ("Briefing", "Where the simulated voices agree", "Where they split",
                    "How each group reacted", "How each company reacted", "What happened", "Run diagnostics"):
        assert heading in text
