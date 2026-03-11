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
from baserow_enterprise.assistant.deps import AgentMode

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

    def get_routing_rules(self) -> str:
        """Return routing rules text for this tool group's manifest.

        Override in subclasses that define mode-specific routing rules.
        Returns empty string by default (no rules).
        """

        return ""


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

        from .toolset import _get_mode_tool_map

        # Build a routing-rules lookup from registered tool types so each
        # module owns its own rules (no hardcoded imports here).
        routing_rules_by_type: dict[str, str] = {
            tt.type: tt.get_routing_rules()
            for tt in self.get_all()
            if tt.get_routing_rules()
        }

        mode_map = _get_mode_tool_map()
        shared = mode_map[AgentMode.DATABASE] & mode_map[AgentMode.APPLICATION]

        _mode_config: list[tuple[str, AgentMode, str]] = [
            ("database", AgentMode.DATABASE, routing_rules_by_type.get("database", "")),
            (
                "application",
                AgentMode.APPLICATION,
                routing_rules_by_type.get("builder", ""),
            ),
            (
                "automation",
                AgentMode.AUTOMATION,
                routing_rules_by_type.get("automation", ""),
            ),
        ]

        manifests = {}
        for mode_key, mode, rules in _mode_config:
            allowed = mode_map[mode]
            groups = [
                (label, [f for f in funcs if f.__name__ in allowed])
                for label, funcs in module_groups
            ]
            manifest = generate_tool_manifest_compact(groups, routing_rules=rules)

            # Append a compact cross-mode summary so the agent knows what
            # capabilities exist in other modes (and can switch_mode to use them).
            other_lines = []
            for other_key, other_mode, _ in _mode_config:
                if other_key == mode_key:
                    continue
                specific = mode_map[other_mode] - shared
                other_lines.append(f"- {other_key}: {', '.join(sorted(specific))}")
            if other_lines:
                manifest += "\n\n## Other modes (switch_mode to access)\n" + "\n".join(
                    other_lines
                )

            manifests[mode_key] = manifest

        explain_allowed = mode_map[AgentMode.EXPLAIN]
        explain_groups = [
            (label, [f for f in funcs if f.__name__ in explain_allowed])
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
