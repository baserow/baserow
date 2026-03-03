"""
Utilities for compacting and trimming pydantic-ai message histories.

The assistant persists the full message history (including intermediate tool
calls) across turns.  Before feeding it back into the agent we compact each
turn down to (user prompt, final answer) and trim to a fixed window so the
context doesn't grow unboundedly.
"""

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

# The number of messages to keep in the compacted history for context.  This is
# a simple safeguard to prevent excessively long histories from bloating the
# context.
MAX_HISTORY_MESSAGES = 20


def _has_user_prompt(msg: ModelMessage) -> bool:
    """Check if a ModelRequest contains a UserPromptPart."""

    return isinstance(msg, ModelRequest) and any(
        isinstance(p, UserPromptPart) for p in msg.parts
    )


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
    """

    turns = _split_into_turns(messages)

    compacted: list[ModelMessage] = []
    for turn in turns:
        compacted.extend(_compact_turn(turn))

    if len(compacted) > max_messages:
        compacted = compacted[-max_messages:]

    return compacted
