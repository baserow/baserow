"""The action, page setup, user source and theme tools, over MCP."""

import json

import pytest

from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.user_sources.models import UserSource

from .test_mcp_builder_read_tools import READ_TOOLS, _endpoint, _session

WRITE_TOOLS = [
    "create_actions",
    "add_action_field_mapping",
    "update_action",
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


def _calls(builder_ctx, users_table, mapping_action):
    table = builder_ctx["data_source"].service.specific.table
    return {
        "create_actions": {
            "page_id": builder_ctx["page"].id,
            "actions": [
                {
                    "type": "notification",
                    "element": builder_ctx["button"].id,
                    "title": "Hi",
                }
            ],
        },
        "add_action_field_mapping": {
            "action_id": mapping_action.id,
            "field_id": table.field_set.first().id,
            "value_formula": "'x'",
        },
        "update_action": {
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


@pytest.fixture
def mapping_action(data_fixture, builder_ctx):
    table = builder_ctx["data_source"].service.specific.table
    return data_fixture.create_local_baserow_create_row_workflow_action(
        page=builder_ctx["page"],
        element=builder_ctx["button"],
        event="click",
        service=data_fixture.create_local_baserow_upsert_row_service(table=table),
    )


@pytest.mark.django_db
def test_write_tools_with_builder_edit_turned_on(
    data_fixture, builder_ctx, users_table, mapping_action
):
    endpoint = _endpoint(data_fixture, builder_ctx, [*READ_TOOLS, *WRITE_TOOLS])
    calls = _calls(builder_ctx, users_table, mapping_action)

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
    for name in WRITE_TOOLS:
        assert tools[name].annotations.readOnlyHint is False
        assert tools[name].annotations.destructiveHint is (
            name in ("set_theme", "update_action")
        )
    assert set(tools["create_actions"].inputSchema["properties"]) == {
        "page_id",
        "actions",
    }
    assert set(tools["add_action_field_mapping"].inputSchema["properties"]) == {
        "action_id",
        "field_id",
        "value_formula",
    }
    assert set(tools["update_action"].inputSchema["properties"]) == {
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

    assert _load(results["create_actions"])["created_actions"][0]["type"] == (
        "notification"
    )
    assert _load(results["add_action_field_mapping"])["updated_action"]["id"] == (
        mapping_action.id
    )
    assert _load(results["update_action"])["updated_action"]["id"] == (
        builder_ctx["action"].id
    )
    assert _load(results["setup_page"])["created_elements"][0]["ref"] == "h"
    created = _load(results["setup_user_source"])
    assert created["created_user_source"]["table_id"] == users_table.id
    assert created["created_pages"][0]["path"] == "/login"
    assert _load(results["set_theme"]) == {"updated_theme": "eclipse"}


@pytest.mark.django_db
def test_write_tools_with_only_builder_read_turned_on_are_refused(
    data_fixture, builder_ctx, users_table, mapping_action
):
    endpoint = _endpoint(data_fixture, builder_ctx, READ_TOOLS)
    calls = _calls(builder_ctx, users_table, mapping_action)
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
@pytest.mark.parametrize(
    "name,email,password,message",
    [
        ("text", "email", "text", "field named 'Password'"),
        ("text", "number", "password", "missing required fields: email"),
        ("date", "email", "password", "missing required fields: name"),
    ],
    ids=["password", "email", "name"],
)
def test_setup_user_source_names_a_field_of_the_wrong_type_over_mcp(
    data_fixture, builder_ctx, name, email, password, message
):
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )
    table = data_fixture.create_database_table(database=database, name="People")
    getattr(data_fixture, f"create_{name}_field")(
        table=table, name="Name", primary=True
    )
    getattr(data_fixture, f"create_{email}_field")(table=table, name="Email")
    getattr(data_fixture, f"create_{password}_field")(table=table, name="Password")

    result = _call(
        data_fixture,
        builder_ctx,
        "setup_user_source",
        {
            "builder_id": builder_ctx["builder"].id,
            "setup": {"name": "People", "table_id": table.id},
        },
    )

    assert result.isError is True
    assert message in result.content[0].text
    assert table.field_set.count() == 3
    assert not UserSource.objects.exists()


@pytest.mark.django_db
def test_a_refused_title_is_fixed_with_update_action_over_mcp(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, [*READ_TOOLS, *WRITE_TOOLS])
    formula = f"get('data_source.{builder_ctx['data_source'].id}.0.id')"

    async def callback(client):
        created = _load(
            await client.call_tool(
                "create_actions",
                {
                    "page_id": builder_ctx["page"].id,
                    "actions": [
                        {
                            "type": "notification",
                            "element": builder_ctx["button"].id,
                            "title": "$formula: the product name",
                        }
                    ],
                },
            )
        )
        action_id = created["formula_errors"][0]["action_id"]
        refused = _load(
            await client.call_tool(
                "update_action",
                {"action_id": action_id, "changes": {"title": "get('nope.x')"}},
            )
        )
        fixed = _load(
            await client.call_tool(
                "update_action",
                {"action_id": action_id, "changes": {"title": formula}},
            )
        )
        return action_id, refused, fixed

    action_id, refused, fixed = _session(endpoint, callback)

    assert refused["formula_errors"][0]["field"] == "title"
    assert "formula_errors" not in fixed
    action = BuilderWorkflowAction.objects.get(id=action_id).specific
    assert action.title["formula"] == formula


@pytest.mark.django_db
def test_an_open_page_parameter_is_fixed_with_update_action_over_mcp(
    data_fixture, builder_ctx
):
    detail = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        path="/detail/:id",
        path_params=[{"name": "id", "type": "text"}],
    )
    endpoint = _endpoint(data_fixture, builder_ctx, [*READ_TOOLS, *WRITE_TOOLS])
    formula = f"get('data_source.{builder_ctx['data_source'].id}.0.id')"

    async def callback(client):
        created = _load(
            await client.call_tool(
                "create_actions",
                {
                    "page_id": builder_ctx["page"].id,
                    "actions": [
                        {
                            "type": "open_page",
                            "element": builder_ctx["button"].id,
                            "navigate_to_page_id": detail.id,
                            "page_parameters": [
                                {"name": "id", "value": "$formula: the row id"}
                            ],
                        }
                    ],
                },
            )
        )
        action_id = created["formula_errors"][0]["action_id"]
        fixed = _load(
            await client.call_tool(
                "update_action",
                {
                    "action_id": action_id,
                    "changes": {"page_parameters": [{"name": "id", "value": formula}]},
                },
            )
        )
        return action_id, fixed

    action_id, fixed = _session(endpoint, callback)

    assert "formula_errors" not in fixed
    action = BuilderWorkflowAction.objects.get(id=action_id).specific
    assert action.page_parameters[0]["value"]["formula"] == formula


@pytest.mark.django_db
def test_update_action_outside_the_workspace_is_refused_over_mcp(
    data_fixture, builder_ctx
):
    other = data_fixture.create_workspace(user=builder_ctx["user"])
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=other)
    )
    action = data_fixture.create_notification_workflow_action(
        page=page,
        element=data_fixture.create_builder_button_element(page=page),
        event="click",
    )

    result = _call(
        data_fixture,
        builder_ctx,
        "update_action",
        {"action_id": action.id, "changes": {"title": "Taken"}},
    )

    assert result.isError is True
    assert "not found in this workspace" in result.content[0].text


@pytest.mark.django_db
def test_a_form_can_be_wired_in_a_second_call_over_mcp(data_fixture, builder_ctx):
    table = builder_ctx["data_source"].service.specific.table
    field = table.field_set.first()
    endpoint = _endpoint(data_fixture, builder_ctx, [*READ_TOOLS, *WRITE_TOOLS])
    page_id = builder_ctx["page"].id

    async def setup(client):
        return await client.call_tool(
            "setup_page",
            {
                "page_id": page_id,
                "elements": [
                    {"ref": "form", "type": "form_container"},
                    {
                        "ref": "name",
                        "type": "input_text",
                        "label": "Name",
                        "parent_element": "form",
                    },
                ],
            },
        )

    created = {
        item["ref"]: item["id"]
        for item in _load(_session(endpoint, setup))["created_elements"]
    }

    async def wire(client):
        return await client.call_tool(
            "create_actions",
            {
                "page_id": page_id,
                "actions": [
                    {
                        "type": "create_row",
                        "element": created["form"],
                        "event": "submit",
                        "table_id": table.id,
                        "field_values": [
                            {
                                "field_id": str(field.id),
                                "value": f"get('form_data.{created['name']}')",
                            }
                        ],
                    }
                ],
            },
        )

    result = _load(_session(endpoint, wire))

    assert "errors" not in result
    assert "formula_errors" not in result
    action = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][0]["id"]
    ).specific
    mapping = action.service.specific.field_mappings.get()
    assert mapping.value["formula"] == f"get('form_data.{created['name']}')"


@pytest.mark.django_db
def test_other_workspaces_are_not_found_over_mcp(data_fixture, builder_ctx):
    other = data_fixture.create_workspace(user=builder_ctx["user"])
    builder = data_fixture.create_builder_application(workspace=other)
    page = data_fixture.create_builder_page(builder=builder)
    calls = {
        "create_actions": {
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
