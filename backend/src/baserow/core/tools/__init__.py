"""
Tools shared by the clients that act for a user: the MCP server, Kuma and the
Agent Builder.

A shared tool is a plain function. Its first argument is a ``ToolContext`` and
the others are annotated with ``typing.Annotated`` and ``pydantic.Field``, so
every client can build its input schema from the signature. The docstring
describes the tool to any client, and must not mention a client's own tools.

Public tool entry points use ``tool_execution`` so permission caches live for
one invocation, even when the caller reuses a context. Internal helpers share
that invocation's caches and must not start another execution boundary.
"""

from dataclasses import dataclass, field, replace
from functools import wraps
from typing import TYPE_CHECKING, Callable, Concatenate, ParamSpec, TypeVar

if TYPE_CHECKING:
    # Not at runtime: ``baserow.core.mcp`` imports this package through
    # ``core.tools.errors`` before Django is set up, from ``config/asgi.py``.
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace


def _ignore_status(message: str) -> None:
    pass


@dataclass
class ToolContext:
    """Who a shared tool acts for, and where it reports its progress."""

    user: "AbstractUser"
    workspace: "Workspace"
    update_status: Callable[[str], None] = field(default=_ignore_status)
    timezone: str | None = None
    """The timezone date values are in, UTC when None. Set by the caller so
    tools use the execution timezone for either a user or an identity."""


ToolParams = ParamSpec("ToolParams")
ToolResult = TypeVar("ToolResult")


def tool_execution(
    function: Callable[Concatenate[ToolContext, ToolParams], ToolResult],
) -> Callable[Concatenate[ToolContext, ToolParams], ToolResult]:
    """Start a fresh permission cache lifetime for one public shared tool call."""

    @wraps(function)
    def wrapped(
        ctx: ToolContext, *args: ToolParams.args, **kwargs: ToolParams.kwargs
    ) -> ToolResult:
        # Imported here: this package loads before Django is set up.
        from baserow.core.cache import local_cache
        from baserow.core.subjects import without_prefetched_memberships

        ctx = replace(ctx, workspace=without_prefetched_memberships(ctx.workspace))
        with local_cache.isolated():
            return function(ctx, *args, **kwargs)

    wrapped.is_tool_execution = True
    return wrapped
