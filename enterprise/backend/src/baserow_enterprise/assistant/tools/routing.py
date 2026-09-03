"""Tool ownership, mode visibility, and routing for the assistant."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cache
from typing import TYPE_CHECKING, Any, Callable, Iterable

from loguru import logger
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import AgentDepsT, ToolsetTool
from typing_extensions import Self

from baserow.core.exceptions import PermissionException, UserNotInWorkspace
from baserow_enterprise.assistant.deps import AgentMode

from .shared.errors import ToolInputError, permission_denied_result
from .toolset import LENIENT_ARGS_VALIDATOR

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import AssistantDeps


MODE_ROUTER_METADATA_KEY = "assistant_mode"


@dataclass(frozen=True)
class _ToolRoute:
    home: AgentMode
    active_modes: frozenset[AgentMode]


def _routes_for(
    functions: Iterable[Callable], home: AgentMode, active_modes: frozenset[AgentMode]
) -> dict[str, _ToolRoute]:
    route = _ToolRoute(home, active_modes)
    return {function.__name__: route for function in functions}


@cache
def _tool_routes() -> dict[str, _ToolRoute]:
    from .automation.tools import TOOL_FUNCTIONS as automation_tools
    from .builder.tools import TOOL_FUNCTIONS as application_tools
    from .core.tools import (
        ask_user,
        create_builders,
        list_builders,
        switch_mode,
        update_builder,
    )
    from .database.tools import TOOL_FUNCTIONS as database_tools
    from .navigation.tools import navigate
    from .search_user_docs.tools import search_user_docs

    all_modes = frozenset(AgentMode)
    domain_modes = all_modes - {AgentMode.EXPLAIN}
    database_mode = frozenset({AgentMode.DATABASE})
    application_mode = frozenset({AgentMode.APPLICATION})
    automation_mode = frozenset({AgentMode.AUTOMATION})
    explain_mode = frozenset({AgentMode.EXPLAIN})

    database_reads = [
        tool for tool in database_tools if tool.__name__.startswith(("list_", "get_"))
    ]
    application_reads = [
        tool for tool in application_tools if tool.__name__.startswith("list_")
    ]
    automation_reads = [
        tool for tool in automation_tools if tool.__name__.startswith("list_")
    ]

    return {
        **_routes_for(database_tools, AgentMode.DATABASE, database_mode),
        **_routes_for(database_reads, AgentMode.DATABASE, all_modes),
        **_routes_for(application_tools, AgentMode.APPLICATION, application_mode),
        **_routes_for(
            application_reads,
            AgentMode.APPLICATION,
            application_mode | explain_mode,
        ),
        **_routes_for(automation_tools, AgentMode.AUTOMATION, automation_mode),
        **_routes_for(
            automation_reads,
            AgentMode.AUTOMATION,
            automation_mode | explain_mode,
        ),
        **_routes_for(
            (navigate, switch_mode, list_builders, ask_user),
            AgentMode.DATABASE,
            all_modes,
        ),
        **_routes_for(
            (create_builders, update_builder), AgentMode.DATABASE, domain_modes
        ),
        **_routes_for((search_user_docs,), AgentMode.EXPLAIN, explain_mode),
    }


def is_tool_active(name: str, mode: AgentMode) -> bool:
    """
    Whether a tool's full schema is active in a mode.

    :param name: The tool function name.
    :param mode: The agent mode to check against.
    :return: True when the tool is routed and active in the given mode.
    """

    route = _tool_routes().get(name)
    return route is not None and mode in route.active_modes


def tool_home(name: str) -> AgentMode | None:
    """
    Return a tool's canonical mode.

    :param name: The tool function name.
    :return: The mode that owns the tool, or None for unrouted tools.
    """

    route = _tool_routes().get(name)
    return route.home if route else None


def build_tool_catalog(tool_names: Iterable[str]) -> str:
    """
    Group permitted tool names by their canonical mode.

    :param tool_names: The permitted tool function names.
    :return: One line per mode listing its tools, ready for the system prompt.
    """

    names_by_mode = {mode: [] for mode in AgentMode}
    for name in sorted(set(tool_names)):
        home = tool_home(name)
        if home is not None:
            names_by_mode[home].append(name)

    return "\n".join(
        f"- {mode.value}: {', '.join(names)}"
        for mode, names in names_by_mode.items()
        if names
    )


def _defer_tool(
    tool: ToolsetTool[AgentDepsT], target_mode: AgentMode
) -> ToolsetTool[AgentDepsT]:
    metadata = {
        **(tool.tool_def.metadata or {}),
        MODE_ROUTER_METADATA_KEY: target_mode.value,
    }
    definition = replace(
        tool.tool_def,
        defer_loading=True,
        sequential=True,
        metadata=metadata,
    )
    return replace(
        tool,
        tool_def=definition,
        args_validator=LENIENT_ARGS_VALIDATOR,
        args_validator_func=None,
    )


def _routed_mode(tool: ToolsetTool[AgentDepsT]) -> AgentMode | None:
    value = (tool.tool_def.metadata or {}).get(MODE_ROUTER_METADATA_KEY)
    return AgentMode(value) if value is not None else None


class ModeAwareToolset(AbstractToolset[AgentDepsT]):
    """Expose active tools and defer permitted tools owned by other modes."""

    def __init__(self, inner: AbstractToolset[AgentDepsT], deps: "AssistantDeps"):
        self._inner = inner
        self._deps = deps

    @property
    def id(self) -> str:
        return self._inner.id

    async def __aenter__(self) -> Self:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        return await self._inner.__aexit__(*args)

    def apply(self, visitor: Callable[[AbstractToolset[AgentDepsT]], None]) -> None:
        self._inner.apply(visitor)

    def visit_and_replace(
        self,
        visitor: Callable[[AbstractToolset[AgentDepsT]], AbstractToolset[AgentDepsT]],
    ) -> AbstractToolset[AgentDepsT]:
        inner = self._inner.visit_and_replace(visitor)
        return ModeAwareToolset(inner, self._deps)

    async def get_tools(self, ctx) -> dict[str, ToolsetTool[AgentDepsT]]:
        """
        Return the mode-filtered view of the inner toolset.

        :param ctx: The agent run context.
        :return: Active tools as-is; permitted tools owned by another mode are
            included with deferred schemas so calling them triggers a switch.
        """

        tools: dict[str, ToolsetTool[AgentDepsT]] = {}
        for name, tool in (await self._inner.get_tools(ctx)).items():
            if is_tool_active(name, self._deps.mode):
                tools[name] = tool
                continue

            home = tool_home(name)
            if home is not None:
                tools[name] = _defer_tool(tool, home)
        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        """
        Call a tool, switching modes first when it was deferred.

        :param name: The tool name.
        :param tool_args: The raw tool arguments.
        :param ctx: The agent run context.
        :param tool: The toolset tool being called.
        :return: The inner tool result, or an error dict for contained
            failures such as invalid input or missing resources.
        :raises ModelRetry: When the call routed a mode switch and the tool
            must be re-issued with its full schema.
        """

        routed_mode = _routed_mode(tool)
        if routed_mode is not None:
            self._deps.mode = routed_mode
            raise ModelRetry(
                f"Switched to {routed_mode.value} mode. {name} was not executed yet. "
                f"Call {name} again now using the full schema shown in this mode."
            )

        try:
            return await self._inner.call_tool(name, tool_args, ctx, tool)
        except ToolInputError as exc:
            return {"error": str(exc)}
        except UserNotInWorkspace:
            return {
                "error": (
                    "One or more IDs reference a resource outside the current "
                    "workspace. Use the appropriate list_* tool to find "
                    "the correct IDs and retry."
                )
            }
        except PermissionException:
            return permission_denied_result(name)
        except Exception as exc:
            if not type(exc).__name__.endswith("DoesNotExist"):
                raise
            logger.warning(
                "[assistant] Tool '{}' referenced a missing resource: {}: {}",
                name,
                type(exc).__name__,
                exc,
            )
            return {
                "error": (
                    f"{name} referenced something that does not exist or is not "
                    f"accessible: {exc}"
                ),
                "next_steps": (
                    "Every id and type value must come from a previous tool "
                    "result, never from a guess or a placeholder. Re-read it "
                    "from the latest list_*/get_*/create_* result, or call the "
                    f"matching list_*/get_* tool to look it up, then retry {name}."
                ),
            }
