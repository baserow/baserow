"""Payload guard shared by every collection-creating tool."""

from typing import Any

from pydantic_ai import ModelRetry


def require_payload(tool_name: str, arg_name: str, items: Any) -> None:
    """Reject a call that named a target but carried nothing to act on.

    An empty success result would let a dropped payload read as done work.

    :param tool_name: The collection-creating tool receiving the call.
    :param arg_name: The argument containing the items to create.
    :param items: The collection supplied for that argument.
    :return: None when the collection is nonempty.
    :raises ModelRetry: When the payload is empty and must be supplied again.
    """

    if not items:
        raise ModelRetry(
            f"{tool_name} received an empty `{arg_name}`. `{arg_name}` is "
            f"required and must contain at least one item: an ID argument "
            f"only says where to act, it never says what to create. Nothing "
            f"was changed. Resend the call with the target ID and the full "
            f"`{arg_name}` list together."
        )
