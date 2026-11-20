from typing import Annotated

from pydantic import StringConstraints
from pydantic_ai import RunContext, Tool
from pydantic_ai.exceptions import ApprovalRequired
from pydantic_ai.toolsets import FunctionToolset

from .constants import (
    ASK_PERSON_ANSWER_METADATA_KEY,
    ASK_PERSON_DESCRIPTION,
    ASK_PERSON_QUESTION_MAX_LENGTH,
    ASK_PERSON_TOOL_NAME,
)


async def ask_person(
    ctx: RunContext[None],
    question: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=ASK_PERSON_QUESTION_MAX_LENGTH,
        ),
    ],
) -> str:
    """
    Hold the question until a person answers it, then return the answer.

    :param ctx: The run, with the answer in the call's metadata once approved.
    :param question: The question, with the context needed to answer it.
    :raises ApprovalRequired: Until a person answered the question.
    :return: The person's answer.
    """

    if not ctx.tool_call_approved:
        raise ApprovalRequired()
    return (ctx.tool_call_metadata or {})[ASK_PERSON_ANSWER_METADATA_KEY]


def ask_person_toolset() -> FunctionToolset[None]:
    """
    :return: The toolset offering the question tool to an unattended reply.
    """

    return FunctionToolset(
        [
            Tool(
                ask_person,
                name=ASK_PERSON_TOOL_NAME,
                description=ASK_PERSON_DESCRIPTION,
            )
        ]
    )
