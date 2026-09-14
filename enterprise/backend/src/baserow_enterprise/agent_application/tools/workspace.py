import asyncio
from typing import TYPE_CHECKING, Any, Callable, Optional

from loguru import logger
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from typing_extensions import Self

from baserow_enterprise.assistant.tools.registries import assistant_tool_registry

from .catalog import (  # noqa: F401
    EXCLUDED_GROUPS,
    EXCLUDED_TOOLS,
    list_workspace_tools,
)
from .registries import AgentToolType

if TYPE_CHECKING:
    from ..deps import AgentRunDeps
    from ..models import AgentDefinition, AgentTool


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

    def owns_tool_name(self, tool: "AgentTool", tool_name: str) -> bool:
        from .catalog import SYNTHETIC_ROW_TOOLS, catalog_tool_names, to_catalog_name

        # The synthetic row entries only exist in the catalog; at run time the
        # row tools carry the table id, so a bare `create_rows` is some other
        # tool (e.g. an action tool named that way).
        if tool_name in SYNTHETIC_ROW_TOOLS:
            return False
        return to_catalog_name(tool_name) in catalog_tool_names()

    def apply_dont_ask_again(self, tool: "AgentTool", tool_name: str) -> dict:
        from .catalog import to_catalog_name
        from .rules import (
            ACCESS_CUSTOM,
            RULE_ALLOW,
            materialize_tool_rules,
            normalize_workspace_config,
        )

        config = normalize_workspace_config(tool.config)
        if config["access"] != ACCESS_CUSTOM:
            # Switching to custom keeps every other tool exactly as it is.
            config["tool_rules"] = materialize_tool_rules(config)
            config["access"] = ACCESS_CUSTOM
        config["tool_rules"][to_catalog_name(tool_name)] = RULE_ALLOW
        return config

    def build_toolsets(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        from .gating import wrap_workspace_toolset
        from .rules import describe_workspace_access, normalize_workspace_config

        deps.workspace_tool_config = normalize_workspace_config(tool.config)
        # The model must reason from the current permissions, not from what
        # it concluded earlier in the conversation when they may have differed.
        deps.system_notes.append(describe_workspace_access(deps.workspace_tool_config))

        toolsets = []
        for tool_type in assistant_tool_registry.get_all():
            if tool_type.type in EXCLUDED_GROUPS:
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

        # The rules wrapper sits outside the error handler so that the
        # deferred-approval control flow is never swallowed.
        toolset = ErrorHandlingToolset(CombinedToolset(toolsets))
        return [wrap_workspace_toolset(toolset, deps)]
