"""Interview answers are parsed in the English format and in the older Chinese format.

The interview prompt asks each answer to start with "Question X:". Answers stored before
the backend strings were translated start with "问题X：", and must still parse.
"""
import pytest

from app.services.simulation_runner import SimulationRunner
from app.services.zep_tools import (
    AgentInterview,
    InterviewResult,
    ZepToolsService,
    contains_numbered_answer_label,
    starts_with_answer_label,
    strip_answer_prefixes,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Question 1: I support it.", "I support it."),
        ("question 2 : Not really.", "Not really."),
        ("Question1:Yes", "Yes"),
        ("Question 1: A\n\nQuestion 2: B", "A\n\nB"),
        ("问题1：我支持。", "我支持。"),
        ("问题2:不太同意", "不太同意"),
        ("问题1：甲\n\n问题2：乙", "甲\n\n乙"),
    ],
)
def test_strip_answer_prefixes_accepts_english_and_chinese(text, expected):
    assert strip_answer_prefixes(text) == expected


def test_answer_label_detection_accepts_english_and_chinese():
    assert starts_with_answer_label("Question 3: something")
    assert starts_with_answer_label("问题3：内容")
    assert not starts_with_answer_label("Questions remain about the policy")

    assert contains_numbered_answer_label("as I said in Question 2, it matters")
    assert contains_numbered_answer_label("见问题2的回答")
    assert not contains_numbered_answer_label("No numbered label here")


def _service_with_answers(monkeypatch, twitter_answer, reddit_answer):
    service = ZepToolsService.__new__(ZepToolsService)
    profiles = [{"realname": "Alice", "profession": "Student", "bio": "A student."}]
    monkeypatch.setattr(service, "_load_agent_profiles", lambda simulation_id: profiles)
    monkeypatch.setattr(
        service,
        "_select_agents_for_interview",
        lambda **kwargs: (profiles, [0], "Alice is directly affected."),
    )
    monkeypatch.setattr(service, "_generate_interview_summary", lambda **kwargs: "Summary.")
    monkeypatch.setattr(
        SimulationRunner,
        "interview_agents_batch",
        lambda **kwargs: {
            "success": True,
            "interviews_count": 1,
            "result": {
                "results": {
                    "twitter_0": {"response": twitter_answer},
                    "reddit_0": {"response": reddit_answer},
                }
            },
        },
    )
    return service


def test_interview_parses_english_answer_prefix(monkeypatch):
    service = _service_with_answers(
        monkeypatch, "Question 1: The new policy will hurt students who rely on campus housing", ""
    )

    result = service.interview_agents("sim-1", "housing policy", custom_questions=["What do you think?"])

    interview = result.interviews[0]
    assert interview.key_quotes == ["The new policy will hurt students who rely on campus housing"]
    assert interview.response.startswith("[Twitter answer]\nQuestion 1: The new policy")
    assert interview.response.endswith("[Reddit answer]\n(no reply on this platform)")


def test_interview_parses_legacy_chinese_answer_prefix(monkeypatch):
    service = _service_with_answers(monkeypatch, "", "问题1：我认为这项新政策会严重影响依赖校内住宿的学生群体。")

    result = service.interview_agents("sim-1", "住房政策", custom_questions=["您怎么看？"])

    interview = result.interviews[0]
    assert interview.key_quotes == ["我认为这项新政策会严重影响依赖校内住宿的学生群体。"]
    assert interview.response.startswith("[Twitter answer]\n(no reply on this platform)")


def test_agent_interview_text_skips_quotes_with_answer_labels():
    interview = AgentInterview(
        agent_name="Alice",
        agent_role="Student",
        agent_bio="Bio",
        question="1. What do you think?",
        response="Answer",
        key_quotes=[
            "This quote still mentions Question 2 and is noise",
            "问题2的内容混在这里了，应该被过滤掉",  # the same noise behind the older Chinese "Question 2" label
            "A clean and meaningful quote from Alice",
        ],
    )

    text = interview.to_text()

    quotes = text.split("**Key quotes:**\n")[1]
    assert quotes == '> "A clean and meaningful quote from Alice"\n'
    assert "_Bio: Bio_" in text


def test_interview_result_text_is_english():
    result = InterviewResult(
        interview_topic="housing",
        interview_questions=["What do you think?"],
        total_agents=3,
        interviewed_count=0,
    )

    text = result.to_text()

    assert text.startswith("## In-depth Interview Report")
    assert "**Interview topic:** housing" in text
    assert "**Agents interviewed:** 0 / 3 simulated agents" in text
    assert "### Why these interviewees were chosen\n(selected automatically)" in text
    assert "(no interview records)" in text
    assert text.endswith("### Interview summary and key viewpoints\n(no summary)")


def test_key_quotes_come_from_english_sentences(monkeypatch):
    answer = (
        "Question 1: I bought at the $111.50 open and I am not selling yet. "
        "The real test is whether the lock-up schedule is published before employees can sell! "
        "Short one. "
        "Question 2: Governance worries me more than the price, because public holders get almost no vote."
    )
    service = _service_with_answers(monkeypatch, answer, "")

    quotes = service.interview_agents("sim-1", "IPO", custom_questions=["Q1?", "Q2?"]).interviews[0].key_quotes

    assert "I bought at the $111.50 open and I am not selling yet." in quotes  # decimals don't split sentences
    assert any(q.startswith("The real test is whether the lock-up schedule") for q in quotes)
    assert "Short one." not in quotes                                        # too short to be a quote
    assert all(not q.startswith("Question") for q in quotes)
