"""The action, page setup, user source and theme tools, over MCP."""

import json

import pytest

from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.user_sources.models import UserSource
from tests.baserow.contrib.builder.mcp.test_mcp_builder_read_tools import (
    READ_TOOLS,
    _endpoint,
    _session,
)

WRITE_TOOLS = [
    "create_element_actions",
    "update_element_action",
    "setup_page",
    "setup_user_source",
    "set_theme",
]


def _load(result):
    assert result.isError is False, result.content[0].text
    return json.loads(result.content[0].text)


@pytest.fixture
def users_table(data_fixture, builder_ctx):
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )
    table = data_fixture.create_database_table(database=database, name="People")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_email_field(table=table, name="Email")
    return table


def _row_action(builder_ctx, row_id):
    table = builder_ctx["data_source"].service.specific.table
    return {
        "type": "update_row",
        "element": builder_ctx["button"].id,
        "table_id": table.id,
        "row_id": row_id,
        "field_values": [{"field_id": str(table.field_set.first().id), "value": "'x'"}],
    }


def _call(data_fixture, builder_ctx, name, arguments, allowed=None):
    endpoint = _endpoint(
        data_fixture, builder_ctx, allowed or [*READ_TOOLS, *WRITE_TOOLS]
    )

    async def callback(client):
        return await client.call_tool(name, arguments)

    return _session(endpoint, callback)


def _calls(builder_ctx, users_table):
    return {
        "create_element_actions": {
            "page_id": builder_ctx["page"].id,
            "actions": [
                {
                    "type": "notification",
                    "element": builder_ctx["button"].id,
                    "title": "Hi",
                }
            ],
        },
        "update_element_action": {
            "action_id": builder_ctx["action"].id,
            "changes": {"title": "Hello"},
        },
        "setup_page": {
            "page_id": builder_ctx["page"].id,
            "elements": [{"ref": "h", "type": "heading", "value": "Hi"}],
        },
        "setup_user_source": {
            "builder_id": builder_ctx["builder"].id,
            "setup": {"name": "People", "table_id": users_table.id},
        },
        "set_theme": {"builder_id": builder_ctx["builder"].id, "theme": "eclipse"},
    }


@pytest.mark.django_db
def test_write_tools_with_builder_edit_turned_on(
    data_fixture, builder_ctx, users_table
):
    endpoint = _endpoint(data_fixture, builder_ctx, [*READ_TOOLS, *WRITE_TOOLS])
    calls = _calls(builder_ctx, users_table)

    async def callback(client):
        listed = await client.list_tools()
        results = {
            name: await client.call_tool(name, arguments)
            for name, arguments in calls.items()
        }
        return listed, results

    listed, results = _session(endpoint, callback)

    tools = {tool.name: tool for tool in listed.tools}
    assert set(WRITE_TOOLS) <= set(tools)
    # update_element_action sets one field of a row action and keeps the others.
    assert "add_element_action_field_mapping" not in tools
    for name in WRITE_TOOLS:
        assert tools[name].annotations.readOnlyHint is False
        assert tools[name].annotations.destructiveHint is (
            name in ("set_theme", "update_element_action")
        )
    assert set(tools["create_element_actions"].inputSchema["properties"]) == {
        "page_id",
        "actions",
    }
    assert set(tools["update_element_action"].inputSchema["properties"]) == {
        "action_id",
        "changes",
    }
    assert set(tools["setup_page"].inputSchema["properties"]) == {
        "page_id",
        "data_sources",
        "elements",
        "actions",
    }
    assert set(tools["setup_user_source"].inputSchema["properties"]) == {
        "builder_id",
        "setup",
    }
    assert set(tools["set_theme"].inputSchema["properties"]) == {"builder_id", "theme"}
    for name in WRITE_TOOLS:
        for word in ("navigate", "thought", "load_", "ask_user", "get_tables_schema"):
            assert word not in tools[name].description, (name, word)

    assert _load(results["create_element_actions"])["created_actions"][0]["type"] == (
        "notification"
    )
    assert _load(results["update_element_action"])["updated_action"]["id"] == (
        builder_ctx["action"].id
    )
    assert _load(results["setup_page"])["created_elements"][0]["ref"] == "h"
    created = _load(results["setup_user_source"])
    assert created["created_user_source"]["table_id"] == users_table.id
    assert created["created_pages"][0]["path"] == "/login"
    assert _load(results["set_theme"]) == {"updated_theme": "eclipse"}


@pytest.mark.django_db
def test_write_tools_with_only_builder_read_turned_on_are_refused(
    data_fixture, builder_ctx, users_table
):
    endpoint = _endpoint(data_fixture, builder_ctx, READ_TOOLS)
    calls = _calls(builder_ctx, users_table)
    actions_before = BuilderWorkflowAction.objects.count()

    async def callback(client):
        return {
            name: await client.call_tool(name, arguments)
            for name, arguments in calls.items()
        }

    results = _session(endpoint, callback)

    assert set(results) == set(WRITE_TOOLS)
    for result in results.values():
        assert result.isError is True
    assert BuilderWorkflowAction.objects.count() == actions_before
    assert not UserSource.objects.exists()


@pytest.mark.django_db
def test_other_workspaces_are_not_found_over_mcp(data_fixture, builder_ctx):
    other = data_fixture.create_workspace(user=builder_ctx["user"])
    builder = data_fixture.create_builder_application(workspace=other)
    page = data_fixture.create_builder_page(builder=builder)
    calls = {
        "create_element_actions": {
            "page_id": page.id,
            "actions": [{"type": "logout", "element": 1}],
        },
        "setup_page": {
            "page_id": page.id,
            "elements": [{"ref": "h", "type": "heading", "value": "Hi"}],
        },
        "setup_user_source": {
            "builder_id": builder.id,
            "setup": {"name": "P", "table_id": 1},
        },
        "set_theme": {"builder_id": builder.id, "theme": "eclipse"},
    }
    endpoint = _endpoint(data_fixture, builder_ctx, WRITE_TOOLS)

    async def callback(client):
        return {
            name: await client.call_tool(name, arguments)
            for name, arguments in calls.items()
        }

    results = _session(endpoint, callback)

    for result in results.values():
        assert result.isError is True
        assert result.content[0].text == "Not found in this workspace."
