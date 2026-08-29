from typing import TYPE_CHECKING, Optional

from loguru import logger

from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from ..deps import AgentRunDeps
    from ..models import AgentDefinition, AgentTool


class AgentToolType(Instance):
    """
    A kind of tool that can be enabled for an agent. Simple tool types are
    toggled on/off (one `AgentTool` row without configuration); configurable
    ones carry a config and optionally a backing service that is dispatched
    when the model calls the tool.
    """

    # Whether users can add multiple configured instances of this tool type
    # (e.g. services as tools) instead of a single on/off toggle.
    is_configurable = False

    def can_enable(self, agent: "AgentDefinition") -> tuple[bool, Optional[str]]:
        """
        Whether this tool type can currently be enabled for the agent, and a
        human readable reason when it can't (e.g. workspace tools require an
        agent identity to act as).
        """

        return True, None

    def build_toolsets(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        """
        Returns the pydantic-ai toolsets this tool contributes to a run.
        """

        return []

    def get_builtin_tools(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        """
        Returns provider-native builtin tools (e.g. web search) that must be
        passed to the pydantic-ai agent directly instead of as a toolset.
        """

        return []


class AgentToolTypeRegistry(Registry[AgentToolType]):
    name = "agent_tool_type"

    def build_toolsets(self, agent: "AgentDefinition", deps: "AgentRunDeps") -> list:
        toolsets = []
        for tool in agent.tools.all():
            toolset = self._build_for_tool(tool, deps)
            if toolset:
                toolsets.extend(toolset)
        return toolsets

    def build_builtin_tools(
        self, agent: "AgentDefinition", deps: "AgentRunDeps"
    ) -> list:
        builtin_tools = []
        for tool in agent.tools.all():
            tool_type = self._get_type(tool)
            if tool_type and tool_type.can_enable(agent)[0]:
                builtin_tools.extend(tool_type.get_builtin_tools(tool, deps))
        return builtin_tools

    def _build_for_tool(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        tool_type = self._get_type(tool)
        if tool_type is None:
            return []
        enabled, reason = tool_type.can_enable(tool.agent)
        if not enabled:
            logger.debug(
                "Skipping agent tool {} for agent {}: {}",
                tool.type,
                tool.agent_id,
                reason,
            )
            return []
        try:
            return tool_type.build_toolsets(tool, deps)
        except Exception:
            # One broken tool (e.g. a missing optional dependency) must not
            # take down every run of the agent; the rest of the tools still
            # work and the model is told what is missing.
            logger.exception(
                "Failed to build agent tool {} for agent {}",
                tool.type,
                tool.agent_id,
            )
            deps.system_notes.append(
                f"The tool '{tool.name or tool.type}' could not be loaded "
                "and is unavailable in this conversation."
            )
            return []

    def _get_type(self, tool: "AgentTool") -> Optional[AgentToolType]:
        try:
            return self.get(tool.type)
        except self.does_not_exist_exception_class:
            logger.warning("Unknown agent tool type {}", tool.type)
            return None


agent_tool_type_registry = AgentToolTypeRegistry()
