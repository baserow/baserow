import asyncio
from typing import TYPE_CHECKING, Any, Callable, Optional

from loguru import logger
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from typing_extensions import Self

from baserow_enterprise.assistant.tools.registries import assistant_tool_registry

from .registries import AgentToolType

if TYPE_CHECKING:
    from ..deps import AgentRunDeps
    from ..models import AgentDefinition, AgentTool

# Tool groups that only make sense in the interactive assistant.
EXCLUDED_GROUPS = {"navigation"}
# Mode switching only exists for the assistant's mode-filtered toolset.
EXCLUDED_TOOLS = {"switch_mode"}


class ErrorHandlingToolset(AbstractToolset):
    """
    Returns tool input/permission failures to the model as error payloads
    instead of aborting the run, mirroring the assistant's behavior, and
    hides assistant-only tools.
    """

    def __init__(self, inner: AbstractToolset):
        self._inner = inner

    @property
    def id(self) -> str:
        return self._inner.id

    async def __aenter__(self) -> Self:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        return await self._inner.__aexit__(*args)

    def apply(self, visitor: Callable[[AbstractToolset], None]) -> None:
        self._inner.apply(visitor)

    def visit_and_replace(
        self, visitor: Callable[[AbstractToolset], AbstractToolset]
    ) -> AbstractToolset:
        return ErrorHandlingToolset(self._inner.visit_and_replace(visitor))

    async def get_tools(self, ctx) -> dict[str, ToolsetTool]:
        all_tools = await self._inner.get_tools(ctx)
        return {k: v for k, v in all_tools.items() if k not in EXCLUDED_TOOLS}

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: Any, tool: ToolsetTool
    ) -> Any:
        from pydantic_ai import ModelRetry
        from pydantic_ai.exceptions import ApprovalRequired, CallDeferred

        from baserow.core.exceptions import PermissionException, UserNotInWorkspace
        from baserow_enterprise.assistant.tools.builder.helpers import ToolInputError

        try:
            return await self._inner.call_tool(name, tool_args, ctx, tool)
        except (ApprovalRequired, CallDeferred):
            # Deferred tool control flow must reach the framework untouched.
            raise
        except ToolInputError as exc:
            return {"error": str(exc)}
        except PermissionException:
            return {
                "error": (
                    "The agent's workspace role does not allow this operation. "
                    "Only perform actions the agent has been given access to."
                )
            }
        except UserNotInWorkspace:
            return {
                "error": (
                    "One or more IDs reference a resource outside the current "
                    "workspace, or the agent has no access to it. Use the "
                    "appropriate list_* tool to find the correct IDs and retry."
                )
            }
        except (ModelRetry, asyncio.CancelledError):
            raise
        except Exception as exc:
            # A background run has no human to recover from a crashing tool,
            # so any other failure is returned to the model instead of
            # aborting the whole run.
            logger.exception("Agent tool {} failed", name)
            return {"error": f"The tool {name} failed: {exc}"}


def list_workspace_tools() -> list[dict]:
    """
    The universe of workspace tools a user can individually enable for an
    agent, with their group and read/write classification. The per-table row
    tools are dynamic and governed by `load_row_tools`, so they are not
    listed separately.
    """

    from .classification import is_write_tool

    tools = []
    for tool_type in assistant_tool_registry.get_all():
        if tool_type.type in EXCLUDED_GROUPS:
            continue
        for func in tool_type.get_tool_functions():
            name = func.__name__
            if name in EXCLUDED_TOOLS:
                continue
            tools.append(
                {
                    "name": name,
                    "group": tool_type.type,
                    "is_write": is_write_tool(name),
                }
            )
    return tools


class BaserowWorkspaceAgentToolType(AgentToolType):
    """
    Gives the agent the assistant's Baserow tools, executed as the
    application's `core.Agent` identity so RBAC decides what it can touch.
    """

    type = "workspace"

    def can_enable(self, agent: "AgentDefinition") -> tuple[bool, Optional[str]]:
        if agent.application.agent_identity_id is None:
            return (
                False,
                "The application has no agent identity to access the workspace with.",
            )
        return True, None

    def build_toolsets(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        from .gating import WORKSPACE_MODE_READ_ONLY, wrap_workspace_toolset

        deps.workspace_tools_read_only = (
            tool.config.get("mode") == WORKSPACE_MODE_READ_ONLY
        )
        deps.workspace_write_approval = tool.config.get("require_write_approval", True)

        enabled_groups = tool.config.get("groups") or None
        toolsets = []

        for tool_type in assistant_tool_registry.get_all():
            if tool_type.type in EXCLUDED_GROUPS:
                continue
            if enabled_groups is not None and tool_type.type not in enabled_groups:
                continue
            try:
                if not tool_type.can_use(deps.user, deps.workspace):
                    continue
            except Exception:
                logger.exception(
                    "Assistant tool group {} can_use failed for agent actor",
                    tool_type.type,
                )
                continue
            toolsets.append(tool_type.get_toolset())

        if not toolsets:
            return []

        toolset = ErrorHandlingToolset(CombinedToolset(toolsets))

        # An explicit tool selection restricts the agent to exactly those
        # tools; `None` means every tool (subject to the read-only mode).
        enabled_tools = tool.config.get("enabled_tools")
        if isinstance(enabled_tools, list):
            from .gating import AllowlistToolset

            toolset = AllowlistToolset(toolset, set(enabled_tools))

        # The approval/read-only wrapper sits outside the error handler so
        # that the deferred-approval control flow is never swallowed.
        return [wrap_workspace_toolset(toolset, deps)]
