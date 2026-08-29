import asyncio

import pytest
from pydantic_ai import RunContext
from pydantic_ai.toolsets import ApprovalRequiredToolset, FunctionToolset
from pydantic_ai.usage import RunUsage

from baserow_enterprise.agent_application.deps import AgentRunDeps
from baserow_enterprise.agent_application.tools.classification import is_write_tool
from baserow_enterprise.agent_application.tools.gating import (
    ReadOnlyToolset,
    wrap_workspace_toolset,
)


def test_is_write_tool_classification():
    for name in [
        "list_tables",
        "get_tables_schema",
        "list_rows",
        "generate_formula",
        "search_user_docs",
        "list_builders",
        "list_elements",
    ]:
        assert not is_write_tool(name), name

    for name in [
        "create_tables",
        "update_fields",
        "delete_fields",
        "create_builders",
        "setup_page",
        "set_theme",
        "load_row_tools",
        "create_rows_in_table_42",
        "update_rows_in_table_42",
        "delete_rows_in_table_42",
    ]:
        assert is_write_tool(name), name


def test_unknown_tools_fail_closed_as_writes():
    assert is_write_tool("some_future_tool")
    assert not is_write_tool("list_something_new")
    assert not is_write_tool("get_something_new")


def _make_deps(**kwargs):
    return AgentRunDeps(
        user=None,
        workspace=None,
        agent=None,
        chat=None,
        tool_helpers=None,
        **kwargs,
    )


def _make_toolset():
    def list_rows() -> str:
        """Reads rows."""

        return "rows"

    def create_tables() -> str:
        """Writes tables."""

        return "created"

    return FunctionToolset([list_rows, create_tables])


def _run_ctx(deps):
    return RunContext(deps=deps, model=None, usage=RunUsage())


def test_wrap_workspace_toolset_read_only_hides_write_tools():
    deps = _make_deps(workspace_tools_read_only=True)
    wrapped = wrap_workspace_toolset(_make_toolset(), deps)
    assert isinstance(wrapped, ReadOnlyToolset)

    tools = asyncio.run(wrapped.get_tools(_run_ctx(deps)))
    assert "list_rows" in tools
    assert "create_tables" not in tools


def test_read_only_toolset_blocks_write_calls_defensively():
    deps = _make_deps(workspace_tools_read_only=True)
    wrapped = wrap_workspace_toolset(_make_toolset(), deps)

    async def call():
        ctx = _run_ctx(deps)
        tools = await wrapped.wrapped.get_tools(ctx)
        return await wrapped.call_tool("create_tables", {}, ctx, tools["create_tables"])

    result = asyncio.run(call())
    assert "read only" in result["error"]


def test_wrap_workspace_toolset_write_approval():
    deps = _make_deps(workspace_write_approval=True)
    wrapped = wrap_workspace_toolset(_make_toolset(), deps)
    assert isinstance(wrapped, ApprovalRequiredToolset)

    ctx = _run_ctx(deps)
    tools = asyncio.run(wrapped.get_tools(ctx))
    # Reads are auto-approved, writes require approval.
    assert not wrapped.approval_required_func(ctx, tools["list_rows"].tool_def, {})
    assert wrapped.approval_required_func(ctx, tools["create_tables"].tool_def, {})


def test_load_row_tools_is_write_but_approval_exempt():
    from pydantic_ai.tools import ToolDefinition

    from baserow_enterprise.agent_application.tools.classification import (
        APPROVAL_EXEMPT_TOOLS,
    )

    assert is_write_tool("load_row_tools")
    assert "load_row_tools" in APPROVAL_EXEMPT_TOOLS

    deps = _make_deps(workspace_write_approval=True)
    wrapped = wrap_workspace_toolset(_make_toolset(), deps)
    # It only unlocks the (approval-gated) row write tools, so pausing on it
    # would be approval noise.
    tool_def = ToolDefinition(name="load_row_tools")
    assert not wrapped.approval_required_func(None, tool_def, {})
    assert wrapped.approval_required_func(
        None, ToolDefinition(name="update_rows_in_table_5"), {}
    )


def test_allowlist_toolset_only_exposes_enabled_tools():
    from baserow_enterprise.agent_application.tools.gating import AllowlistToolset

    deps = _make_deps()
    wrapped = AllowlistToolset(_make_toolset(), {"list_rows"})

    tools = asyncio.run(wrapped.get_tools(_run_ctx(deps)))
    assert "list_rows" in tools
    assert "create_tables" not in tools

    async def call_blocked():
        ctx = _run_ctx(deps)
        all_tools = await wrapped.wrapped.get_tools(ctx)
        return await wrapped.call_tool(
            "create_tables", {}, ctx, all_tools["create_tables"]
        )

    result = asyncio.run(call_blocked())
    assert "not been enabled" in result["error"]


def test_list_workspace_tools_classifies_and_excludes():
    from baserow_enterprise.agent_application.tools.workspace import (
        list_workspace_tools,
    )

    tools = {tool["name"]: tool for tool in list_workspace_tools()}
    assert tools["list_rows"]["is_write"] is False
    assert tools["list_rows"]["group"] == "database"
    assert tools["create_tables"]["is_write"] is True
    # Assistant-only tools are not part of the agent's universe.
    assert "navigate" not in tools
    assert "switch_mode" not in tools


def test_wrap_workspace_toolset_no_gating():
    deps = _make_deps(workspace_write_approval=False)
    toolset = _make_toolset()
    assert wrap_workspace_toolset(toolset, deps) is toolset


@pytest.mark.django_db
def test_workspace_tool_type_sets_deps_flags(data_fixture):
    from baserow_enterprise.agent_application.models import AgentTool
    from baserow_enterprise.agent_application.tools.workspace import (
        BaserowWorkspaceAgentToolType,
    )

    tool = AgentTool(type="workspace", config={"mode": "read_only"})
    deps = _make_deps()
    BaserowWorkspaceAgentToolType().build_toolsets(tool, deps)
    assert deps.workspace_tools_read_only is True
    assert deps.workspace_write_approval is True

    tool = AgentTool(
        type="workspace",
        config={"mode": "read_write", "require_write_approval": False},
    )
    deps = _make_deps()
    BaserowWorkspaceAgentToolType().build_toolsets(tool, deps)
    assert deps.workspace_tools_read_only is False
    assert deps.workspace_write_approval is False
