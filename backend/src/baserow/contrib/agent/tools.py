from typing import Annotated

from pydantic import StringConstraints
from pydantic_ai import Tool
from pydantic_ai.exceptions import CallDeferred

from .constants import (
    ASK_PERSON_DESCRIPTION,
    ASK_PERSON_QUESTION_MAX_LENGTH,
    ASK_PERSON_TOOL_NAME,
)


async def ask_person(
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
    Hold the question until a person answers or dismisses it. The resumed run
    gets the answer as the call's result without running this again, so a
    question already asked is answered even when asking is turned off.

    :param question: The question, with the context needed to answer it.
    :raises CallDeferred: Always.
    """

    raise CallDeferred()


def ask_person_tool() -> Tool[None]:
    """
    :return: The question tool offered to an unattended reply.
    """

    return Tool(
        ask_person,
        name=ASK_PERSON_TOOL_NAME,
        description=ASK_PERSON_DESCRIPTION,
    )
