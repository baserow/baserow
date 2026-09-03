"""
Baserow registry for assistant tool types.

Each tool module (navigation, database, etc.) registers an
``AssistantToolType`` instance.  The registry assembles the combined
toolset at runtime, filtering by ``can_use(user, workspace)`` so
individual tool groups can be gated on permissions or feature flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from pydantic_ai.toolsets import AbstractToolset, CombinedToolset

from baserow.core.registry import Instance, Registry

from .routing import ModeAwareToolset, build_tool_catalog
from .toolset import InlineRefsToolset

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace
    from baserow_enterprise.assistant.deps import AssistantDeps


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


class AssistantToolRegistry(Registry[AssistantToolType]):
    name = "assistant_tool"

    def build_toolset(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        model: str,
        deps: "AssistantDeps",
    ) -> tuple[AbstractToolset, str]:
        """
        Build the permitted, routed toolset and its compact catalog.

        :param user: The requesting user.
        :param workspace: The current workspace.
        :param model: The pydantic-ai model string.
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
        inlined = InlineRefsToolset(combined, model=model)
        routed = ModeAwareToolset(inlined, deps)
        return routed, build_tool_catalog(tool_names)


assistant_tool_registry = AssistantToolRegistry()
