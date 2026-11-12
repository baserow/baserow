"""
Tools shared by the clients that act for a user: the MCP server, Kuma and the
Agent Builder.

A shared tool is a plain function. Its first argument is a ``ToolContext`` and
the others are annotated with ``typing.Annotated`` and ``pydantic.Field``, so
every client can build its input schema from the signature. The docstring
describes the tool to any client, and must not mention a client's own tools.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    # Not at runtime: ``baserow.core.mcp`` imports this package through
    # ``core.tools.errors`` before Django is set up, from ``config/asgi.py``.
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace


def _ignore_status(message: str) -> None:
    pass


def _never_cancelled() -> bool:
    return False


@dataclass
class ToolContext:
    """Who a shared tool acts for, and where it reports its progress."""

    user: "AbstractUser"
    workspace: "Workspace"
    update_status: Callable[[str], None] = field(default=_ignore_status)
    timezone: str | None = None
    """The timezone date values are in, UTC when None. Not read from ``user``,
    because an actor such as an Agent has no profile."""
    is_cancelled: Callable[[], bool] = field(default=_never_cancelled)
    """Whether a batch should stop before its next item, preserving finished work."""
