"""
Utilities for compacting and trimming pydantic-ai message histories.

The assistant persists the full message history (including intermediate tool
calls) across turns.  Before feeding it back into the agent we compact each
turn down to (user prompt, final answer) and trim to a fixed window so the
context doesn't grow unboundedly.
"""

from loguru import logger
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from baserow_enterprise.assistant.action_memory import (
    _has_user_prompt,
    carry_verified_actions,
)

MAX_HISTORY_MESSAGES = 20
UNFINISHED_ANSWER = (
    "I couldn't finish my answer, but some changes may already have been made. "
    "Please check them, then tell me how to continue."
)
NOT_STARTED_ANSWER = "I couldn't start working on this message, so nothing changed."


def _get_final_text_response(turn: list[ModelMessage]) -> ModelResponse | None:
    """
    Return the last ModelResponse in the turn that contains a TextPart,
    or None if no such response exists.
    """

    for msg in reversed(turn):
        if isinstance(msg, ModelResponse) and any(
            isinstance(p, TextPart) for p in msg.parts
        ):
            return msg
    return None


def _split_into_turns(
    messages: list[ModelMessage],
) -> list[list[ModelMessage]]:
    """
    Split a flat message list into turns. Each turn starts at a ModelRequest
    that contains a UserPromptPart.

    Messages before the first UserPromptPart (e.g. initial system instructions)
    are grouped into a leading "turn 0".
    """

    turns: list[list[ModelMessage]] = []
    current: list[ModelMessage] = []

    for msg in messages:
        if _has_user_prompt(msg) and current:
            turns.append(current)
            current = []
        current.append(msg)

    if current:
        turns.append(current)

    return turns


def _compact_turn(turn: list[ModelMessage]) -> list[ModelMessage]:
    """
    Compact a single turn. If the turn has more than 2 messages (user prompt
    + final answer), strip intermediate tool call/return messages and keep
    only the user prompt request and the final text response.

    Returns the turn unchanged if it has no tool calls or no final text
    response.
    """

    if len(turn) <= 2:
        return turn

    # Find the user prompt request (first message) and final text response
    user_request = turn[0] if _has_user_prompt(turn[0]) else None
    final_response = _get_final_text_response(turn)

    if user_request and final_response:
        return [user_request, final_response]

    # Cannot compact -- return as-is
    return turn


def compact_message_history(
    messages: list[ModelMessage],
    max_messages: int = MAX_HISTORY_MESSAGES,
) -> list[ModelMessage]:
    """
    Compact and trim a pydantic-ai message history for multi-turn context.

    1. Splits messages into turns (delimited by UserPromptPart).
    2. For each turn with intermediate tool calls, collapses to just the
       user prompt and final text answer.
    3. Trims to the last ``max_messages`` messages if still too long.
    4. Carries verified tool outcomes into the compacted history metadata.

    :param messages: The full message history to compact.
    :param max_messages: The maximum number of messages to keep.
    :return: The compacted history with verified outcomes attached.
    """

    turns = _split_into_turns(messages)

    compacted: list[ModelMessage] = []
    for turn in turns:
        compacted.extend(_compact_turn(turn))

    if len(compacted) > max_messages:
        compacted = compacted[-max_messages:]

    return carry_verified_actions(messages, compacted)


def unfinished_answer(text: str) -> str:
    """
    :param text: What the user saw of the answer when the run stopped.
    :return: That text followed by the note that tells the model the turn is
        unfinished.
    """

    return f"{text}\n\n{UNFINISHED_ANSWER}" if text else UNFINISHED_ANSWER


def count_user_prompts(messages: list[ModelMessage]) -> int:
    """
    Counts user prompt parts. pydantic-ai's history cleaning can merge messages
    but keeps every part, so comparing counts tells whether the agent added its
    prompt.

    :param messages: A message history.
    :return: The number of user prompt parts.
    """

    return sum(
        isinstance(part, UserPromptPart)
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
    )


def append_turn(history: bytes | memoryview | None, prompt: str, answer: str) -> bytes:
    """
    Adds a prompt and its answer to a saved history, for a message whose run didn't
    record its own turn. A history that can't be read is replaced, as loading it
    would discard it anyway.

    :param history: The chat's saved history, if any.
    :param prompt: The human message.
    :param answer: The answer to record for it.
    :return: The new history, serialized.
    """

    messages: list[ModelMessage] = []
    if history:
        try:
            messages = ModelMessagesTypeAdapter.validate_json(bytes(history))
        except ValueError:
            logger.warning("Replacing an assistant message history that can't be read")
    messages += [
        ModelRequest(parts=[UserPromptPart(content=prompt)]),
        ModelResponse(parts=[TextPart(content=answer)]),
    ]
    return ModelMessagesTypeAdapter.dump_json(messages)
