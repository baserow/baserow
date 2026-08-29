"""
Toolset wrappers gating what an agent may change: a read-only filter for the
workspace tools and approval wrappers pausing the run on write tool calls so
the user can approve them in the approval queue first.
"""

from typing import Any, Callable

from pydantic_ai.toolsets import AbstractToolset, ApprovalRequiredToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.toolsets.wrapper import WrapperToolset

from .classification import APPROVAL_EXEMPT_TOOLS, is_write_tool

# Config keys on the workspace AgentTool row.
WORKSPACE_MODE_READ_ONLY = "read_only"
WORKSPACE_MODE_READ_WRITE = "read_write"


class AllowlistToolset(WrapperToolset):
    """
    Only exposes the workspace tools the user explicitly enabled. The
    per-table row tools loaded dynamically are governed by whether
    `load_row_tools` itself is enabled, so they are not listed here.
    """

    def __init__(self, wrapped, enabled_tools: set[str]):
        super().__init__(wrapped)
        self._enabled_tools = enabled_tools

    async def get_tools(self, ctx) -> dict[str, ToolsetTool]:
        all_tools = await super().get_tools(ctx)
        return {k: v for k, v in all_tools.items() if k in self._enabled_tools}

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: Any, tool: ToolsetTool
    ) -> Any:
        if name not in self._enabled_tools:
            return {
                "error": (
                    "This tool has not been enabled for the agent by the "
                    "user; only use the tools that are available."
                )
            }
        return await super().call_tool(name, tool_args, ctx, tool)


class ReadOnlyToolset(WrapperToolset):
    """
    Hides every write tool, so a read-only agent cannot even see them. The
    call guard is defense in depth for a model calling a hidden tool anyway.
    """

    async def get_tools(self, ctx) -> dict[str, ToolsetTool]:
        all_tools = await super().get_tools(ctx)
        return {k: v for k, v in all_tools.items() if not is_write_tool(k)}

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: Any, tool: ToolsetTool
    ) -> Any:
        if is_write_tool(name):
            return {
                "error": (
                    "The Baserow workspace tools are configured as read only; "
                    "this agent can never create, update or delete anything."
                )
            }
        return await super().call_tool(name, tool_args, ctx, tool)


def wrap_workspace_toolset(toolset: AbstractToolset, deps) -> AbstractToolset:
    """
    Applies the workspace tool config (read-only mode and write approval) to
    a toolset of workspace tools. Also used for the dynamically loaded
    per-table row tools, which are workspace tools too.
    """

    if deps.workspace_tools_read_only:
        return ReadOnlyToolset(toolset)

    if deps.workspace_write_approval:
        return ApprovalRequiredToolset(
            toolset,
            approval_required_func=lambda ctx, tool_def, args: (
                is_write_tool(tool_def.name)
                and tool_def.name not in APPROVAL_EXEMPT_TOOLS
            ),
        )

    return toolset


def wrap_approval_required(
    toolset: AbstractToolset,
    predicate: Callable[..., bool] | None = None,
) -> AbstractToolset:
    """
    Requires approval for every call of the given toolset (e.g. action
    service tools and MCP tools, which are assumed to write).
    """

    if predicate is None:
        return ApprovalRequiredToolset(toolset)
    return ApprovalRequiredToolset(toolset, approval_required_func=predicate)
