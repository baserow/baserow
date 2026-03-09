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

from .toolset import (
    InlineRefsToolset,
    ModeAwareToolset,
    generate_tool_manifest_compact,
)

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
        deps: "AssistantDeps",
    ) -> tuple[AbstractToolset, str, str, str, str]:
        """
        Assemble the combined assistant toolset, filtering by ``can_use()``.

        :param user: The requesting user.
        :param workspace: The current workspace.
        :param model: The pydantic-ai model string.
        :param deps: The assistant deps (used for mode-aware filtering).
        :return: ``(toolset, database_manifest, application_manifest,
            automation_manifest, explain_manifest)``.
        """

        toolsets: list[AbstractToolset] = []
        module_groups: list[tuple[str, list[Callable]]] = []

        for tool_type in self.get_all():
            if not tool_type.can_use(user, workspace):
                continue
            toolsets.append(tool_type.get_toolset())
            module_groups.append((tool_type.type, tool_type.get_tool_functions()))

        combined = CombinedToolset(toolsets)
        mode_aware = ModeAwareToolset(combined, deps)

        from baserow_enterprise.assistant.prompts import (
            TOOL_ROUTING_RULES_APPLICATION,
            TOOL_ROUTING_RULES_AUTOMATION,
            TOOL_ROUTING_RULES_DATABASE,
        )

        from .toolset import (
            _APPLICATION_TOOLS,
            _AUTOMATION_TOOLS,
            _DATABASE_TOOLS,
            _EXPLAIN_INCLUDE,
        )

        manifests = {}
        for mode_key, allowed, rules in [
            ("database", _DATABASE_TOOLS, TOOL_ROUTING_RULES_DATABASE),
            ("application", _APPLICATION_TOOLS, TOOL_ROUTING_RULES_APPLICATION),
            ("automation", _AUTOMATION_TOOLS, TOOL_ROUTING_RULES_AUTOMATION),
        ]:
            groups = [
                (label, [f for f in funcs if f.__name__ in allowed])
                for label, funcs in module_groups
            ]
            manifests[mode_key] = generate_tool_manifest_compact(
                groups, routing_rules=rules
            )

        explain_groups = [
            (label, [f for f in funcs if f.__name__ in _EXPLAIN_INCLUDE])
            for label, funcs in module_groups
        ]
        manifests["explain"] = generate_tool_manifest_compact(explain_groups)

        return (
            InlineRefsToolset(mode_aware, model=model),
            manifests["database"],
            manifests["application"],
            manifests["automation"],
            manifests["explain"],
        )


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
