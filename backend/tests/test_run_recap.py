"""Tests for the "What happened" recap: chapters, facts, stories and caching."""

from pathlib import Path

import pytest

from app.services import run_recap
from app.services.consensus_report import _latin1, build_consensus_pdf
from app.services.run_recap import (
    _merge_story,
    build_recap_facts,
    plan_chapters,
    template_story,
)


def act(round_num, name, action_type, platform="twitter", ts=None, **args):
    return {
        "round_num": round_num,
        "timestamp": ts or f"2026-11-13T00:{round_num:02d}:00",
        "platform": platform,
        "agent_id": abs(hash(name)) % 1000,
        "agent_name": name,
        "action_type": action_type,
        "action_args": args,
    }


SEED = "Huang has resigned. The board is weighing interim leadership."
SCOTT = "The Senate wants testimony on 3 December."


def sample_actions():
    return [
        # Seeding round: same seed on both platforms is one opening post.
        act(0, "White House", "CREATE_POST", content=SEED),
        act(0, "White House", "CREATE_POST", platform="reddit", content=SEED),
        act(0, "Wedbush", "CREATE_POST", content="Exit could cost 20% of value."),
        # Stretch 1
        act(1, "Tim Scott", "CREATE_POST", content=SCOTT),
        act(1, "Ann", "LIKE_POST", post_author_name="Tim Scott", post_content=SCOTT),
        act(1, "Bo", "REPOST", original_author_name="Tim Scott", original_content=SCOTT),
        act(1, "Cy", "DISLIKE_POST", post_author_name="White House", post_content=SEED),
        act(1, "Ann", "DO_NOTHING"),
        # Stretch 2: a quote post stores its own text under "content".
        act(2, "Dee", "QUOTE_POST", content="This changes everything.",
            original_author_name="Tim Scott", original_content=SCOTT),
        act(2, "Ann", "LIKE_POST", post_author_name="Wedbush", post_content="Exit could cost 20% of value."),
        act(2, "Eve", "CREATE_COMMENT", platform="reddit", content="Wait for a filing.",
            post_author_name="White House", post_content=SEED),
        act(2, "Ann", "LIKE_COMMENT", platform="reddit", comment_author_name="Eve",
            comment_content="Wait for a filing."),
        act(2, "Zed", "INTERVIEW", prompt="ignored"),
    ]


def test_plan_chapters_short_run_groups_rounds():
    ch = plan_chapters(10, 60)
    assert [(c["first_round"], c["last_round"]) for c in ch] == [(1, 3), (4, 6), (7, 8), (9, 10)]
    assert ch[0]["time"] == "Day 1, 00:00–02:59"
    assert ch[-1]["label"] == "Rounds 9–10"


def test_plan_chapters_one_per_round_when_few():
    ch = plan_chapters(3, 30)
    assert [c["label"] for c in ch] == ["Round 1", "Round 2", "Round 3"]
    assert ch[1]["time"] == "Day 1, 00:30–00:59"


def test_plan_chapters_by_day_for_multi_day_runs():
    ch = plan_chapters(72, 60)
    assert [c["label"] for c in ch] == ["Day 1", "Day 2", "Day 3"]
    assert (ch[1]["first_round"], ch[1]["last_round"]) == (25, 48)


def test_plan_chapters_empty():
    assert plan_chapters(0, 60) == []


def test_facts_opening_chapters_and_highlights():
    facts = build_recap_facts(
        sample_actions(), requirement="How will Nvidia react?", minutes_per_round=60,
        run={"status": "completed", "total_rounds": 2}, roster_size=10,
    )
    assert facts["run"]["finished"] is True
    assert facts["run"]["duration"] == "2 simulated hours"
    # Opening: three seed actions, two distinct posts, the shared one on both platforms.
    assert facts["opening"]["seed_count"] == 2
    assert facts["opening"]["seed_posts"][0]["platforms"] == ["twitter", "reddit"]
    assert facts["totals"]["posts"] == 4  # 3 seed actions + Tim Scott

    ch1, ch2 = facts["chapters"]
    assert ch1["standout_posts"][0]["author"] == "Tim Scott"
    assert ch1["standout_posts"][0]["reactions_in_chapter"] == 2
    assert ch1["approving"] == 2 and ch1["disapproving"] == 1
    assert ch1["tone"] == pytest.approx(0.667, abs=0.001)
    assert ch1["pushback"]["author"] == "White House"
    assert {v["name"] for v in ch1["new_voices"]} == {"Tim Scott", "Ann", "Bo", "Cy"}

    # The quote post's own words are captured as something said.
    assert any(p["text"] == "This changes everything." for p in ch2["posts_said"])
    # Tim Scott led stretch 1, so stretch 2 leads with a different post.
    assert ch2["standout_posts"][0]["author"] != "Tim Scott"
    assert ch2["top_replies"][0] == {
        "author": "Eve", "replying_to": "White House", "platform": "reddit",
        "text": "Wait for a filing.", "likes": 1, "dislikes": 0,
    }
    assert {v["name"] for v in ch2["new_voices"]} == {"Dee", "Eve"}
    assert "Zed" not in {v["name"] for v in ch2["loudest"]}  # interviews are not part of the story

    assert facts["highlights"]["biggest_post"]["author"] == "Tim Scott"
    assert facts["cast"] == {"people_active": 8, "roster": 10, "silent": 2}


def test_template_story_has_one_entry_per_chapter():
    facts = build_recap_facts(sample_actions(), run={"status": "running"})
    story = template_story(facts)
    assert facts["run"]["finished"] is False
    assert [c["index"] for c in story["chapters"]] == [0, 1]
    assert "Tim Scott" in story["headline"]
    assert story["takeaways"]


def test_template_story_for_empty_run():
    facts = build_recap_facts([], run={"status": "idle"})
    story = template_story(facts)
    assert facts["chapters"] == []
    assert story["headline"] == "Nothing has happened in this run yet."


def test_merge_story_fills_gaps_from_template():
    facts = build_recap_facts(sample_actions())
    fallback = template_story(facts)
    merged = _merge_story(
        {"headline": "  A short story.  ", "summary": 42,
         "chapters": [{"index": "1", "title": "Second", "story": "It went on."}, "junk"],
         "takeaways": ["", "One point"]},
        fallback, facts,
    )
    assert merged["headline"] == "A short story."
    assert merged["summary"] == fallback["summary"]
    assert merged["chapters"][0] == fallback["chapters"][0]
    assert merged["chapters"][1] == {"index": 1, "title": "Second", "story": "It went on."}
    assert merged["takeaways"] == ["One point"]


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def chat_json(self, messages, **kwargs):
        self.calls += 1
        assert "FACTS:" in messages[-1]["content"]
        return {"headline": f"Story {self.calls}", "chapters": []}


def test_write_recap_caches_and_reuses(monkeypatch, tmp_path):
    facts = build_recap_facts(sample_actions(), run={"status": "completed"})
    state = {"fp": "fp-1"}
    monkeypatch.setattr(run_recap, "_sim_dir", lambda sid: str(tmp_path))
    monkeypatch.setattr(run_recap, "_load_inputs", lambda sid, dynamics=None: (facts, state["fp"]))
    llm = FakeLLM()

    first = run_recap.write_recap("sim_x", llm_client=llm)
    assert first["story_source"] == "llm" and first["story"]["headline"] == "Story 1"
    assert (tmp_path / "recap.json").is_file()

    again = run_recap.write_recap("sim_x", llm_client=llm)
    assert llm.calls == 1 and again["story"]["headline"] == "Story 1"

    shown = run_recap.get_recap("sim_x")
    assert shown["story_source"] == "llm" and shown["story_stale"] is False

    forced = run_recap.write_recap("sim_x", force=True, llm_client=llm)
    assert llm.calls == 2 and forced["story"]["headline"] == "Story 2"

    # New data: the cached story no longer matches, so the template is shown.
    state["fp"] = "fp-2"
    stale = run_recap.get_recap("sim_x")
    assert stale["story_source"] == "template" and stale["story_stale"] is True


def test_pdf_text_is_latin1_safe():
    assert _latin1("“Hi” – it’s done… \U0001f680") == "\"Hi\" - it's done... "
    assert _latin1("café · ok") == "café · ok"


EXAMPLE_SIM = "sim_168d7ecb477b"
UPLOADS = Path(__file__).resolve().parents[1] / "uploads" / "simulations" / EXAMPLE_SIM


@pytest.mark.skipif(not UPLOADS.is_dir(), reason="example simulation not on disk")
def test_recap_on_example_run_and_pdf_section():
    recap = run_recap.get_recap(EXAMPLE_SIM)
    facts = recap["facts"]
    assert facts["run"]["rounds_done"] == 10
    assert len(facts["chapters"]) == 4
    assert facts["opening"]["seed_count"] > 0
    assert len(recap["story"]["chapters"]) == 4

    pdf = build_consensus_pdf(EXAMPLE_SIM)
    import fitz

    text = fitz.open(stream=pdf)[0].get_text()
    assert "1. What happened" in text
    assert "How it started" in text
