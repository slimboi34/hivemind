"""
Seed brief: start a run from a question alone.

A run normally starts from uploaded documents. When the user gives only a
question, the LLM writes a short background brief from what it already knows
(the situation, the actors with a stake in it and their known positions), and
that brief becomes the seed document. The rest of the pipeline is unchanged.

The brief comes from the model's general knowledge, so it can be out of date
or wrong about recent events. It says so at the top, and the UI repeats it.
"""

from __future__ import annotations

from datetime import date
from typing import Any

BRIEF_FILENAME = "hivemind-brief.md"
PASTED_FILENAME = "pasted-notes.txt"

BRIEF_SYSTEM_PROMPT = """You prepare the background brief for Hivemind, a product that simulates how people and organisations react online to a situation. The user has given only a question. Your brief is the only source the simulation will have: every person and organisation you name can become a simulated participant, so name the ones who would really speak up.

Write the brief in Markdown with exactly these sections:

## Situation
What is happening or proposed, in 1-2 short paragraphs. If the question describes a hypothetical or future event, state it plainly as the scenario premise and treat it as having happened.

## Who has a stake
15 to 25 named actors, grouped under these sub-headings (skip one only if it truly does not apply):
### Companies and executives
### Government and regulators
### Investors and analysts
### Media
### Experts and institutions
### Public voices
For each actor write one line: **Name** (what they are): their role in this situation and the position they have taken or would be expected to take, and why. Use real, specific names (the company, the regulator, the outlet, the named executive or commentator). For public voices, name the kinds of people affected (for example "Small-business owners who rely on the service") and what they care about.

## How they relate
5-10 short lines on the relationships that matter: who competes with, regulates, funds, supplies, covers or criticises whom.

## Timeline
The dated events that led here and the ones coming up, as a short list. Only include dates you are confident of.

## Open questions
4-6 things that are undecided and that people would argue about.

Rules:
- Use what you know. Where you are unsure whether something is true or current, say "reportedly" or "as of my last information" rather than stating it flatly. Never invent quotes, figures or dates.
- Keep the scenario premise separate from established fact.
- Plain language. No preamble, no closing remarks, no advice to the reader. Start with "## Situation".
- 600 to 1,000 words."""


def write_seed_brief(question: str, llm_client: Any = None) -> str:
    """Return a Markdown background brief for a question-only run."""
    from ..utils.llm_client import LLMClient
    from ..utils.locale import get_language_instruction

    client = llm_client or LLMClient()
    body = client.chat(
        [
            {"role": "system", "content": f"{BRIEF_SYSTEM_PROMPT}\n\n{get_language_instruction()}"},
            {"role": "user", "content": f"Today's date: {date.today().isoformat()}\n\nQUESTION:\n{question.strip()}"},
        ],
        temperature=0.4,
        max_tokens=4096,
    ).strip()
    if len(body) < 200:
        raise ValueError("The model returned too little to build a background brief from")
    return (
        "# Background brief\n\n"
        f"Question: {question.strip()}\n\n"
        "Note: Hivemind's AI wrote this brief from the question alone, using the model's general "
        "knowledge. It may be out of date or wrong about recent events. Upload your own documents "
        "for anything recent or confidential.\n\n"
        f"{body}\n"
    )
