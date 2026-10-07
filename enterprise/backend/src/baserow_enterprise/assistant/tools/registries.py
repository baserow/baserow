"""
Baserow registry for assistant tool types.

Each tool module (navigation, database, etc.) registers an
``AssistantToolType`` instance.  The registry assembles the combined
toolset at runtime, filtering by ``can_use(user, workspace)`` so
individual tool groups can be gated on permissions or feature flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from pydantic_ai.toolsets import AbstractToolset, CombinedToolset

from baserow.core.registry import Instance, Registry

from .routing import ModeAwareToolset, build_tool_catalog
from .toolset import InlineRefsToolset

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace
    from baserow_enterprise.assistant.deps import AssistantDeps
    from baserow_enterprise.assistant.model_profiles import (
        ResolvedAssistantModelProfile,
    )


class AssistantToolType(Instance):
    """
    Base class for assistant tool groups.

    Each subclass represents a logical group of tools (e.g. "database",
    "navigation").  Override ``can_use`` to gate availability on user
    permissions or feature flags.
    """

    type: str = ""

    def can_use(self, user: "AbstractUser", workspace: "Workspace") -> bool:
        """
        Permission gate.  Override in subclasses for conditional availability.

        :param user: The requesting user.
        :param workspace: The current workspace.
        :return: ``True`` if this tool group should be included.
        """

        return True

    def get_tool_functions(self) -> list[Callable]:
        """
        Return the raw tool functions for catalog generation.

        :return: The tool functions this group exposes.
        :raises NotImplementedError: Subclasses must implement this.
        """

        raise NotImplementedError

    def get_toolset(self) -> AbstractToolset:
        """Return the pydantic-ai ``FunctionToolset`` for this group."""

        raise NotImplementedError

    def remembered_result(self, tool_name: str, result: Any) -> Any:
        """
        Choose what action memory keeps of a result of one of this group's tools.

        :param tool_name: The name of the tool that ran.
        :param result: The tool's result.
        :return: The result to remember for later turns, by default all of it.
        """

        return result


class AssistantToolRegistry(Registry[AssistantToolType]):
    name = "assistant_tool"

    def get_by_tool_name(self, tool_name: str) -> AssistantToolType | None:
        """
        Find the tool group that owns a tool.

        :param tool_name: The tool function's name.
        :return: The group whose tool functions include it, or None when no group
            has a tool of that name.
        """

        return next(
            (
                tool_type
                for tool_type in self.get_all()
                if any(
                    function.__name__ == tool_name
                    for function in tool_type.get_tool_functions()
                )
            ),
            None,
        )

    def build_toolset(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        model: Any,
        model_profile: "ResolvedAssistantModelProfile",
        deps: "AssistantDeps",
    ) -> tuple[AbstractToolset, str]:
        """
        Build the permitted, routed toolset and its compact catalog.

        :param user: The requesting user.
        :param workspace: The current workspace.
        :param model: The pydantic-ai model already created for this request.
        :param model_profile: The frozen model resolution the request runs on.
        :param deps: The assistant deps (used for mode-aware routing).
        :return: ``(toolset, tool_catalog)``.
        """

        toolsets: list[AbstractToolset] = []
        tool_names: set[str] = set()

        for tool_type in self.get_all():
            if not tool_type.can_use(user, workspace):
                continue
            toolsets.append(tool_type.get_toolset())
            tool_names.update(
                function.__name__ for function in tool_type.get_tool_functions()
            )

        combined = CombinedToolset(toolsets)
        inlined = InlineRefsToolset(combined, model=model, model_profile=model_profile)
        routed = ModeAwareToolset(inlined, deps)
        return routed, build_tool_catalog(tool_names)


assistant_tool_registry = AssistantToolRegistry()
