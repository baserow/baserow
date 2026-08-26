"""LLM-as-judge for kuma-docs answers.

``docs_answer_judge`` grades an assistant answer to a Baserow end-user
documentation question against the sources it cited and the topic keywords a
good answer should touch.
"""

from __future__ import annotations

import os

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field
from pydantic_ai import Agent

DEFAULT_JUDGE_MODEL = "groq:openai/gpt-oss-120b"

JUDGE_INSTRUCTIONS = """\
You are grading an AI assistant's answer to a Baserow end-user documentation
question. You are given the question, the assistant's answer, the
documentation sources it cited, topic keywords a good answer should touch,
and — when available — a reference answer.

Score from 0.0 to 1.0 for factual correctness, helpfulness, and groundedness
in the cited sources. Penalize confident claims that are not supported by
the sources.

When a reference answer is given, weigh factual agreement with it heavily:
it is the ideal answer, not the only acceptable phrasing, so score down only
for real factual or completeness gaps against it, not wording differences.

Write a 1-3 sentence explanation naming what's wrong or missing, or why the
answer is good.
"""


class JudgeVerdict(PydanticBaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Overall answer quality score.")
    explanation: str = Field(
        description="1-3 sentences on what's wrong, missing, or good."
    )


docs_answer_judge: Agent[None, JudgeVerdict] = Agent(
    output_type=JudgeVerdict,
    instructions=JUDGE_INSTRUCTIONS,
    name="docs_answer_judge",
)


def get_judge_model() -> str:
    """Return the pydantic-ai model string to use for judge agents."""

    return os.environ.get("BASEROW_EVAL_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL


def judge_docs_answer(
    question: str,
    answer: str,
    sources: list[str],
    keywords: list[str],
    reference_answer: str | None = None,
) -> JudgeVerdict:
    """Score a kuma-docs answer for correctness, helpfulness, and groundedness.

    Raises whatever the underlying agent run raises; handling a judge
    failure is the caller's problem.
    """

    prompt = (
        f"Question: {question}\n\n"
        f"Answer: {answer}\n\n"
        f"Cited sources: {sources}\n\n"
        f"Topic keywords a good answer should touch: {keywords}"
    )
    if reference_answer:
        prompt += f"\n\nReference answer (ideal, not the only correct phrasing):\n{reference_answer}"
    result = docs_answer_judge.run_sync(prompt, model=get_judge_model())
    return result.output
