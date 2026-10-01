"""
Toolset wrappers gating what an agent may change: the workspace tool rules
(allow / ask / off) and approval wrappers pausing the run on tool calls so
the user can approve them in the chat first.
"""

import re
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from pydantic_ai.exceptions import ApprovalRequired
from pydantic_ai.toolsets import AbstractToolset, ApprovalRequiredToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.toolsets.wrapper import WrapperToolset

from .catalog import ROW_TOOL_LOADER, to_catalog_name
from .rules import (
    RULE_ASK,
    RULE_OFF,
    allowed_row_operations,
    normalize_workspace_config,
    rule_for,
)


@dataclass
class RuleToolset(WrapperToolset):
    """
    Applies the workspace tool rules: `off` tools are hidden (and blocked as
    defense in depth), `ask` tools raise `ApprovalRequired` until approved.
    The row loader only unlocks the row operations that are not `off`.
    """

    config: dict = field(default_factory=lambda: normalize_workspace_config(None))
    # Catalog tool name -> workspace agent the call runs as instead of the
    # application's identity.
    identities: dict = field(default_factory=dict)

    async def get_tools(self, ctx) -> dict[str, ToolsetTool]:
        all_tools = await super().get_tools(ctx)
        return {
            name: tool
            for name, tool in all_tools.items()
            if rule_for(self.config, name) != RULE_OFF
        }

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: Any, tool: ToolsetTool
    ) -> Any:
        rule = rule_for(self.config, name)
        if rule == RULE_OFF:
            return {
                "error": (
                    "This tool is disabled for the agent by its permissions; "
                    "only use the tools that are available."
                )
            }
        if name == ROW_TOOL_LOADER:
            allowed = allowed_row_operations(self.config)
            operations = [
                op for op in tool_args.get("operations") or [] if op in allowed
            ]
            if not operations:
                return {
                    "error": (
                        "The requested row operations are disabled for the "
                        f"agent; allowed operations: {sorted(allowed)}."
                    )
                }
            tool_args = {**tool_args, "operations": operations}
        if rule == RULE_ASK and not ctx.tool_call_approved:
            raise ApprovalRequired
        identity = self.identities.get(to_catalog_name(name))
        if identity is not None and identity != ctx.deps.user:
            # Tool calls can run concurrently, so the run context is copied
            # instead of mutating the shared deps.
            ctx = replace(ctx, deps=replace(ctx.deps, user=identity))
            row_tool = _DYNAMIC_ROW_TOOL_RE.match(name)
            if row_tool:
                # The per-table row tools bind their actor when they are
                # loaded, so the override needs a fresh build.
                return await _call_row_tool_as(
                    identity, row_tool.group(1), int(row_tool.group(2)), tool_args, ctx
                )
        return await super().call_tool(name, tool_args, ctx, tool)


_DYNAMIC_ROW_TOOL_RE = re.compile(r"^(create|update|delete)_rows_in_table_(\d+)$")


async def _call_row_tool_as(identity, operation: str, table_id: int, tool_args, ctx):
    from asgiref.sync import sync_to_async

    from baserow.contrib.database.table.models import Table
    from baserow_enterprise.assistant.tools.database.tools import _build_row_tools

    def build():
        table = Table.objects.select_related("database__workspace").get(id=table_id)
        return _build_row_tools(
            identity,
            ctx.deps.workspace,
            ctx.deps.tool_helpers,
            table,
            resource_changes=ctx.deps.resource_changes,
        )

    tools = await sync_to_async(build)()
    return await tools[operation].function_schema.call(tool_args, ctx)


def wrap_workspace_toolset(toolset: AbstractToolset, deps) -> AbstractToolset:
    """
    Applies the workspace tool config to a toolset of workspace tools. Also
    used for the dynamically loaded per-table row tools, which are workspace
    tools too.
    """

    return RuleToolset(
        toolset,
        normalize_workspace_config(deps.workspace_tool_config),
        identities=getattr(deps, "workspace_tool_identities", None) or {},
    )


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
