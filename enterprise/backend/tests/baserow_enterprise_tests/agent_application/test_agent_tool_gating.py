import asyncio

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ApprovalRequired
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage

from baserow_enterprise.agent_application.deps import AgentRunDeps
from baserow_enterprise.agent_application.tools.catalog import (
    list_workspace_tools,
    to_catalog_name,
)
from baserow_enterprise.agent_application.tools.classification import is_write_tool
from baserow_enterprise.agent_application.tools.gating import (
    RuleToolset,
    wrap_workspace_toolset,
)
from baserow_enterprise.agent_application.tools.rules import (
    ACCESS_CUSTOM,
    ACCESS_EVERYTHING,
    ACCESS_READ_ONLY,
    RULE_ALLOW,
    RULE_ASK,
    RULE_OFF,
    allowed_row_operations,
    materialize_tool_rules,
    normalize_workspace_config,
    rule_for,
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


def test_to_catalog_name_maps_dynamic_row_tools():
    assert to_catalog_name("create_rows_in_table_12") == "create_rows"
    assert to_catalog_name("update_rows_in_table_7") == "update_rows"
    assert to_catalog_name("delete_rows_in_table_7") == "delete_rows"
    assert to_catalog_name("list_rows") == "list_rows"
    assert to_catalog_name("create_tables") == "create_tables"


def _config(**kwargs):
    return normalize_workspace_config(kwargs)


def test_normalize_defaults_and_legacy_keys():
    assert _config() == {
        "access": ACCESS_EVERYTHING,
        "require_write_approval": True,
        "tool_rules": {},
    }
    assert _config(mode="read_only")["access"] == ACCESS_READ_ONLY
    assert _config(require_write_approval=False)["require_write_approval"] is False
    assert _config(access="custom", tool_rules={"create_tables": "bogus"}) == {
        "access": ACCESS_CUSTOM,
        "require_write_approval": True,
        "tool_rules": {},
    }

    legacy = _config(enabled_tools=["list_rows", "load_row_tools"])
    assert legacy["access"] == ACCESS_CUSTOM
    assert legacy["tool_rules"]["create_tables"] == RULE_OFF
    assert "list_rows" not in legacy["tool_rules"]
    # Enabling the loader in the old model enabled every row operation.
    assert "create_rows" not in legacy["tool_rules"]


def test_rule_for_defaults_per_access_level():
    everything = _config()
    assert rule_for(everything, "list_rows") == RULE_ALLOW
    assert rule_for(everything, "create_tables") == RULE_ASK
    assert rule_for(everything, "create_rows_in_table_5") == RULE_ASK
    assert rule_for(everything, "load_row_tools") == RULE_ALLOW

    trusted = _config(require_write_approval=False)
    assert rule_for(trusted, "create_tables") == RULE_ALLOW

    read_only = _config(access="read_only")
    assert rule_for(read_only, "list_rows") == RULE_ALLOW
    assert rule_for(read_only, "create_tables") == RULE_OFF
    assert rule_for(read_only, "delete_rows_in_table_5") == RULE_OFF
    assert rule_for(read_only, "load_row_tools") == RULE_OFF
    assert allowed_row_operations(read_only) == set()


def test_rule_for_custom_rules_and_read_tools_never_ask():
    custom = _config(
        access="custom",
        tool_rules={
            "create_tables": RULE_OFF,
            "update_rows": RULE_ALLOW,
            "delete_rows": RULE_OFF,
            "list_rows": RULE_ASK,
        },
    )
    assert rule_for(custom, "create_tables") == RULE_OFF
    assert rule_for(custom, "update_rows_in_table_5") == RULE_ALLOW
    assert rule_for(custom, "delete_rows_in_table_5") == RULE_OFF
    # Unlisted tools keep the defaults of the approval switch.
    assert rule_for(custom, "create_fields") == RULE_ASK
    assert rule_for(custom, "list_rows") == RULE_ALLOW
    assert allowed_row_operations(custom) == {"create", "update"}
    assert rule_for(custom, "load_row_tools") == RULE_ALLOW

    no_rows = _config(
        access="custom",
        tool_rules={
            "create_rows": RULE_OFF,
            "update_rows": RULE_OFF,
            "delete_rows": RULE_OFF,
        },
    )
    assert rule_for(no_rows, "load_row_tools") == RULE_OFF


def test_materialize_tool_rules_covers_the_catalog():
    rules = materialize_tool_rules(_config())
    assert set(rules) == {tool["name"] for tool in list_workspace_tools()}
    assert rules["list_rows"] == RULE_ALLOW
    assert rules["create_rows"] == RULE_ASK
    assert "load_row_tools" not in rules


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

    def load_row_tools(operations: list[str]) -> str:
        """Loads row tools."""

        return ",".join(operations)

    return FunctionToolset([list_rows, create_tables, load_row_tools])


def _run_ctx(deps, approved=False):
    return RunContext(
        deps=deps, model=None, usage=RunUsage(), tool_call_approved=approved
    )


async def _call(wrapped, name, args, ctx):
    tools = await wrapped.wrapped.get_tools(ctx)
    return await wrapped.call_tool(name, args, ctx, tools[name])


def test_wrap_workspace_toolset_read_only_hides_and_blocks_write_tools():
    deps = _make_deps(workspace_tool_config={"access": "read_only"})
    wrapped = wrap_workspace_toolset(_make_toolset(), deps)
    assert isinstance(wrapped, RuleToolset)

    tools = asyncio.run(wrapped.get_tools(_run_ctx(deps)))
    assert set(tools) == {"list_rows"}

    result = asyncio.run(_call(wrapped, "create_tables", {}, _run_ctx(deps)))
    assert "disabled" in result["error"]


def test_rule_toolset_asks_for_writes_until_approved():
    deps = _make_deps()
    wrapped = wrap_workspace_toolset(_make_toolset(), deps)

    assert asyncio.run(_call(wrapped, "list_rows", {}, _run_ctx(deps))) == "rows"
    with pytest.raises(ApprovalRequired):
        asyncio.run(_call(wrapped, "create_tables", {}, _run_ctx(deps)))
    assert (
        asyncio.run(_call(wrapped, "create_tables", {}, _run_ctx(deps, approved=True)))
        == "created"
    )


def test_rule_toolset_filters_row_loader_operations():
    deps = _make_deps(
        workspace_tool_config={
            "access": "custom",
            "tool_rules": {"delete_rows": "off"},
        }
    )
    wrapped = wrap_workspace_toolset(_make_toolset(), deps)

    result = asyncio.run(
        _call(
            wrapped,
            "load_row_tools",
            {"operations": ["create", "delete"]},
            _run_ctx(deps),
        )
    )
    assert result == "create"

    result = asyncio.run(
        _call(wrapped, "load_row_tools", {"operations": ["delete"]}, _run_ctx(deps))
    )
    assert "disabled" in result["error"]


def test_rule_toolset_governs_dynamic_row_tools_by_base_rule():
    def create_rows_in_table_5() -> str:
        return "created"

    def update_rows_in_table_5() -> str:
        return "updated"

    deps = _make_deps(
        workspace_tool_config={
            "access": "custom",
            "tool_rules": {"create_rows": "off", "update_rows": "allow"},
        }
    )
    wrapped = wrap_workspace_toolset(
        FunctionToolset([create_rows_in_table_5, update_rows_in_table_5]), deps
    )
    tools = asyncio.run(wrapped.get_tools(_run_ctx(deps)))
    assert set(tools) == {"update_rows_in_table_5"}
    assert (
        asyncio.run(_call(wrapped, "update_rows_in_table_5", {}, _run_ctx(deps)))
        == "updated"
    )


def test_list_workspace_tools_has_labels_and_synthetic_row_tools():
    tools = {tool["name"]: tool for tool in list_workspace_tools()}
    assert tools["list_rows"]["is_write"] is False
    assert tools["list_rows"]["group"] == "database"
    assert tools["list_rows"]["group_label"] == "Databases"
    assert tools["list_rows"]["label"] == "Read rows"
    assert tools["create_tables"]["is_write"] is True
    for name in ("create_rows", "update_rows", "delete_rows"):
        assert tools[name]["group"] == "database"
        assert tools[name]["is_write"] is True
    assert "load_row_tools" not in tools
    # Assistant-only tools are not part of the agent's universe.
    assert "navigate" not in tools
    assert "switch_mode" not in tools
    for tool in tools.values():
        assert tool["label"] and tool["description"], tool["name"]


@pytest.mark.django_db
def test_workspace_tool_type_sets_deps_config(data_fixture):
    from baserow_enterprise.agent_application.models import AgentTool
    from baserow_enterprise.agent_application.tools.workspace import (
        BaserowWorkspaceAgentToolType,
    )

    tool = AgentTool(type="workspace", config={"access": "read_only"})
    deps = _make_deps()
    BaserowWorkspaceAgentToolType().build_toolsets(tool, deps)
    assert deps.workspace_tool_config["access"] == ACCESS_READ_ONLY
    assert deps.workspace_tool_config["require_write_approval"] is True

    tool = AgentTool(type="workspace", config={"require_write_approval": False})
    deps = _make_deps()
    BaserowWorkspaceAgentToolType().build_toolsets(tool, deps)
    assert deps.workspace_tool_config["access"] == ACCESS_EVERYTHING
    assert deps.workspace_tool_config["require_write_approval"] is False


def test_describe_workspace_access():
    from baserow_enterprise.agent_application.tools.rules import (
        describe_workspace_access,
    )

    assert "read only" in describe_workspace_access(_config(access="read_only"))
    everything = describe_workspace_access(_config())
    assert "CAN change" in everything
    assert "Every change pauses" in everything
    trusted = describe_workspace_access(_config(require_write_approval=False))
    assert "pauses" not in trusted
    custom = describe_workspace_access(
        _config(
            access="custom",
            tool_rules={"delete_rows": "off", "create_rows": "allow"},
        )
    )
    assert "disabled: delete_rows" in custom
    no_rows = describe_workspace_access(
        _config(
            access="custom",
            tool_rules={
                "create_rows": "off",
                "update_rows": "off",
                "delete_rows": "off",
                "create_fields": "allow",
            },
        )
    )
    # The row loader is hidden when every row tool is off, so the note must
    # not send the model to it.
    assert "load_row_tools" not in no_rows
    assert "CAN change" in no_rows
    assert "pause until a person approves them: " in custom
    assert "create_rows" not in custom.split("approves them: ")[1].split(".")[0]


@pytest.mark.django_db
def test_workspace_tool_type_adds_access_note(data_fixture):
    from baserow_enterprise.agent_application.models import AgentTool
    from baserow_enterprise.agent_application.tools.workspace import (
        BaserowWorkspaceAgentToolType,
    )

    deps = _make_deps()
    BaserowWorkspaceAgentToolType().build_toolsets(
        AgentTool(type="workspace", config={"access": "read_only"}), deps
    )
    assert any("read only" in note for note in deps.system_notes)
