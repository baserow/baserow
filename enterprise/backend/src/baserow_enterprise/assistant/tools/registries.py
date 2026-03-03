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

from .toolset import InlineRefsToolset, generate_tool_manifest_compact

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace


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
        """Return the raw tool functions for manifest generation."""

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
    ) -> tuple[AbstractToolset, str]:
        """
        Assemble the combined assistant toolset, filtering by ``can_use()``.

        :param user: The requesting user.
        :param workspace: The current workspace.
        :param model: The pydantic-ai model string.
        :return: A tuple of (toolset, manifest_string).
        """

        toolsets: list[AbstractToolset] = []
        func_lists: list[list[Callable]] = []

        for tool_type in self.get_all():
            if not tool_type.can_use(user, workspace):
                continue
            toolsets.append(tool_type.get_toolset())
            func_lists.append(tool_type.get_tool_functions())

        combined = CombinedToolset(toolsets)

        from baserow_enterprise.assistant.prompts import TOOL_ROUTING_RULES

        manifest = generate_tool_manifest_compact(
            func_lists, routing_rules=TOOL_ROUTING_RULES
        )
        return InlineRefsToolset(combined, model=model), manifest


assistant_tool_registry = AssistantToolRegistry()


def get_shared_read_funcs() -> list[Callable]:
    """
    Return read-only tool functions shared across sub-agents.

    Uses deferred imports to avoid circular dependencies.
    """

    from baserow_enterprise.assistant.tools.database.tools import (
        get_tables_schema,
        list_rows,
        list_tables,
    )

    return [list_tables, get_tables_schema, list_rows]
