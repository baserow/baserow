"""Payload guard shared by every collection-creating tool."""

from typing import Any

from pydantic_ai import ModelRetry


def require_payload(tool_name: str, arg_name: str, items: Any) -> None:
    """
    Reject a call that named a target but carried nothing to act on.

    An empty success result would let a dropped payload read as done work.

    :param tool_name: The tool being called.
    :param arg_name: The payload argument name.
    :param items: The payload value to check.
    :raises ModelRetry: When the payload is empty, so the model re-sends the
        call with the target ID and the payload together.
    """

    if not items:
        raise ModelRetry(
            f"{tool_name} received an empty `{arg_name}`. `{arg_name}` is "
            f"required and must contain at least one item: an ID argument "
            f"only says where to act, it never says what to create. Nothing "
            f"was changed. Resend the call with the target ID and the full "
            f"`{arg_name}` list together."
        )
