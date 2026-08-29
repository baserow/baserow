import asyncio

from pydantic_ai.toolsets import ApprovalRequiredToolset

from baserow_enterprise.agent_application.deps import AgentRunDeps
from baserow_enterprise.agent_application.models import AgentTool
from baserow_enterprise.agent_application.tools.mcp import (
    FailsafeMCPToolset,
    McpServerAgentToolType,
    get_mcp_tool_prefix,
)


def _make_deps():
    return AgentRunDeps(
        user=None, workspace=None, agent=None, chat=None, tool_helpers=None
    )


def test_get_mcp_tool_prefix():
    assert get_mcp_tool_prefix(AgentTool(name="My GitHub Server")) == "my_github_server"
    assert get_mcp_tool_prefix(AgentTool(id=7, name="")) == "mcp_7"


def test_build_toolsets_without_url_returns_nothing():
    tool = AgentTool(type="mcp", config={})
    assert McpServerAgentToolType().build_toolsets(tool, _make_deps()) == []


def test_build_toolsets_requires_approval_by_default():
    tool = AgentTool(
        id=1,
        type="mcp",
        name="Test",
        config={"url": "http://localhost:9/mcp"},
    )
    toolsets = McpServerAgentToolType().build_toolsets(tool, _make_deps())
    assert len(toolsets) == 1
    assert isinstance(toolsets[0], ApprovalRequiredToolset)
    # Every MCP tool call requires approval, not just some.
    assert toolsets[0].approval_required_func(None, None, {})


def test_build_toolsets_approval_can_be_disabled():
    tool = AgentTool(
        id=1,
        type="mcp",
        name="Test",
        config={"url": "http://localhost:9/mcp", "require_approval": False},
    )
    toolsets = McpServerAgentToolType().build_toolsets(tool, _make_deps())
    assert len(toolsets) == 1
    assert isinstance(toolsets[0], FailsafeMCPToolset)


def test_failsafe_toolset_degrades_when_server_unreachable():
    tool = AgentTool(
        id=1,
        type="mcp",
        name="Dead server",
        # Port 9 (discard) refuses connections immediately.
        config={"url": "http://127.0.0.1:9/mcp", "require_approval": False},
    )
    deps = _make_deps()
    toolset = McpServerAgentToolType().build_toolsets(tool, deps)[0]

    async def run():
        async with toolset:
            return await toolset.get_tools(None)

    tools = asyncio.run(run())
    assert tools == {}
    assert any("Dead server" in note for note in deps.system_notes)
