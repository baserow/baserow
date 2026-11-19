import json
import threading
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.shortcuts import reverse
from django.test import override_settings

import anyio
import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.api.sessions import set_untrusted_client_session_id
from baserow.contrib.database.fields.actions import CreateFieldActionType
from baserow.contrib.database.rows.actions import CreateRowsActionType
from baserow.core.action.context import undo_redo_session
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.exceptions import LockConflict
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.groups import GROUP_WORKSPACE_UNDO
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.registries import mcp_tool_registry

User = get_user_model()
TOOLS = ["create_rows", "create_fields", "undo", "redo"]


def _call(endpoint, name, arguments=None, expect_error=False):
    async def inner():
        server = BaserowMCPServer()
        token = current_key.set(endpoint.key)
        try:
            async with client_session(server._mcp_server) as client:
                return await client.call_tool(name, arguments or {})
        finally:
            current_key.reset(token)

    with transaction.atomic():
        result = async_to_sync(inner)()
    assert result.isError is expect_error, result.content[0].text
    text = result.content[0].text
    return text if expect_error else json.loads(text)


@pytest.fixture
def setup(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=TOOLS
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    return endpoint, table


def _names(table):
    return [row.name for row in table.get_model(attribute_names=True).objects.all()]


@pytest.mark.django_db
def test_undo_and_redo_a_tool_call(setup):
    endpoint, table = setup

    _call(endpoint, "create_rows", {"table_id": table.id, "rows": [{"Name": "A"}]})
    assert _names(table) == ["A"]

    undone = _call(endpoint, "undo")
    assert undone == [{"action": "Create rows", "failed": False}]
    assert _names(table) == []

    redone = _call(endpoint, "redo")
    assert redone == [{"action": "Create rows", "failed": False}]
    assert _names(table) == ["A"]


@pytest.mark.django_db
def test_undo_with_nothing_to_undo(setup):
    endpoint, _ = setup

    assert _call(endpoint, "undo") == []
    assert _call(endpoint, "redo") == []


@pytest.mark.django_db
def test_undo_takes_back_everything_one_call_changed(setup):
    endpoint, table = setup

    _call(
        endpoint,
        "create_fields",
        {
            "table_id": table.id,
            "fields": [{"name": "X", "type": "text"}, {"name": "Y", "type": "text"}],
        },
    )
    _call(
        endpoint,
        "create_fields",
        {"table_id": table.id, "fields": [{"name": "Z", "type": "text"}]},
    )
    assert {f.name for f in table.field_set.all()} == {"Name", "X", "Y", "Z"}

    assert len(_call(endpoint, "undo")) == 1
    assert {f.name for f in table.field_set.all()} == {"Name", "X", "Y"}

    assert len(_call(endpoint, "undo")) == 2
    assert {f.name for f in table.field_set.all()} == {"Name"}


@pytest.mark.django_db
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_undo_takes_back_a_call_with_more_actions_than_a_group_limit(setup):
    endpoint, table = setup
    _call(endpoint, "create_rows", {"table_id": table.id, "rows": [{"Name": "A"}]})
    _call(
        endpoint,
        "create_fields",
        {
            "table_id": table.id,
            "fields": [{"name": "X", "type": "text"}, {"name": "Y", "type": "text"}],
        },
    )

    assert len(_call(endpoint, "undo")) == 2
    assert {f.name for f in table.field_set.all()} == {"Name"}
    assert _names(table) == ["A"]

    assert len(_call(endpoint, "redo")) == 2
    assert {f.name for f in table.field_set.all()} == {"Name", "X", "Y"}


@pytest.mark.django_db
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_a_change_made_while_a_call_is_undone_leaves_the_rest_for_the_next_undo(
    data_fixture, setup
):
    endpoint, table = setup
    other_table = data_fixture.create_database_table(database=table.database)
    name = data_fixture.create_text_field(table=other_table, name="Name", primary=True)
    _call(
        endpoint,
        "create_fields",
        {
            "table_id": table.id,
            "fields": [{"name": "X", "type": "text"}, {"name": "Y", "type": "text"}],
        },
    )

    # Another call of the same endpoint adds a row right after the first part of
    # the undo, the way a write from another chat on the same key would.
    undo = ActionHandler.undo

    def first_part_then_another_change(*args):
        actions = undo(*args)
        if not Action.objects.filter(action_group=other_group).exists():
            with undo_redo_session(
                endpoint.user, endpoint.undo_session_id, other_group
            ):
                CreateRowsActionType.do(
                    endpoint.user, other_table, rows_values=[{name.db_column: "A"}]
                )
        return actions

    other_group = str(uuid4())
    with patch.object(
        ActionHandler, "undo", side_effect=first_part_then_another_change
    ):
        assert len(_call(endpoint, "undo")) == 1
    assert {f.name for f in table.field_set.all()} == {"Name", "X"}

    assert _call(endpoint, "undo") == [{"action": "Create rows", "failed": False}]
    assert _names(other_table) == []
    assert _call(endpoint, "undo") == [{"action": "Create field", "failed": False}]
    assert {f.name for f in table.field_set.all()} == {"Name"}


@pytest.mark.django_db
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_undo_stops_at_a_part_of_the_call_that_failed(setup):
    endpoint, table = setup
    _call(
        endpoint,
        "create_fields",
        {
            "table_id": table.id,
            "fields": [{"name": "X", "type": "text"}, {"name": "Y", "type": "text"}],
        },
    )

    with patch.object(CreateFieldActionType, "undo", side_effect=Exception("boom")):
        undone = _call(endpoint, "undo")

    assert undone == [{"action": "Create field", "failed": True}]
    assert {f.name for f in table.field_set.all()} == {"Name", "X", "Y"}


@pytest.mark.django_db
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_undo_refuses_to_go_on_into_a_call_that_was_partly_undone(setup):
    endpoint, table = setup
    _call(
        endpoint,
        "create_fields",
        {
            "table_id": table.id,
            "fields": [
                {"name": "X", "type": "text"},
                {"name": "Y", "type": "text"},
                {"name": "Z", "type": "text"},
            ],
        },
    )
    undo_field = CreateFieldActionType.undo
    calls = []

    def fail_on_the_middle_field(*args):
        calls.append(args)
        if len(calls) == 2:
            raise Exception("boom")
        return undo_field(*args)

    with patch.object(
        CreateFieldActionType, "undo", side_effect=fail_on_the_middle_field
    ):
        undone = _call(endpoint, "undo")
        text = _call(endpoint, "undo", expect_error=True)

    assert undone == [
        {"action": "Create field", "failed": False},
        {"action": "Create field", "failed": True},
    ]
    assert "partly undone" in text
    assert {f.name for f in table.field_set.all()} == {"Name", "X", "Y"}


@pytest.mark.django_db
def test_undo_reports_a_lock_conflict(setup):
    endpoint, _ = setup

    with patch.object(ActionHandler, "undo", side_effect=LockConflict()):
        text = _call(endpoint, "undo", expect_error=True)

    assert "Try again" in text


@pytest.mark.django_db
def test_undo_only_reaches_changes_of_the_same_endpoint(data_fixture, setup):
    endpoint, table = setup
    other_endpoint = data_fixture.create_mcp_endpoint(
        user=endpoint.user, workspace=endpoint.workspace, allowed_tools=TOOLS
    )

    _call(endpoint, "create_rows", {"table_id": table.id, "rows": [{"Name": "A"}]})

    assert _call(other_endpoint, "undo") == []
    with transaction.atomic():
        assert ActionHandler.undo(endpoint.user, [], "browser-session") == []
    assert _names(table) == ["A"]


@pytest.mark.django_db
def test_browser_changes_are_not_undone_by_the_undo_tool(setup):
    endpoint, table = setup
    user = User.objects.get(id=endpoint.user_id)
    set_untrusted_client_session_id(user, "browser-session")
    CreateFieldActionType.do(user, table, "text", name="Browser")

    assert _call(endpoint, "undo") == []
    assert table.field_set.filter(name="Browser").exists()


@pytest.mark.django_db
def test_mcp_changes_can_be_undone_through_the_undo_api(
    api_client, data_fixture, setup
):
    endpoint, table = setup
    token = data_fixture.generate_token(endpoint.user)

    _call(endpoint, "create_rows", {"table_id": table.id, "rows": [{"Name": "A"}]})
    action = Action.objects.get(type="create_rows")
    assert action.session == f"mcp-{endpoint.id}"
    assert action.action_group is not None

    response = api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"table": table.id}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=f"mcp-{endpoint.id}",
    )
    assert response.status_code == 200, response.json()
    assert [a["action_type"] for a in response.json()["actions"]] == ["create_rows"]
    assert _names(table) == []


def test_undo_tools_are_off_for_new_keys_and_destructive():
    for name in ["undo", "redo"]:
        tool = mcp_tool_registry.get(name)
        assert tool.group == GROUP_WORKSPACE_UNDO
        assert tool.destructive is True
        assert tool.read_only is False
        assert name not in MCPEndpointHandler().get_default_tools()


@pytest.mark.django_db
def test_another_user_cannot_undo_mcp_changes_with_the_session_header(
    api_client, data_fixture, setup
):
    endpoint, table = setup
    other = data_fixture.create_user()
    data_fixture.create_user_workspace(
        user=other, workspace=endpoint.workspace, permissions="ADMIN"
    )
    token = data_fixture.generate_token(other)

    _call(endpoint, "create_rows", {"table_id": table.id, "rows": [{"Name": "A"}]})

    response = api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"table": table.id}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=endpoint.undo_session_id,
    )
    assert response.status_code == 200, response.json()
    assert response.json()["actions"] == []
    assert _names(table) == ["A"]


def _create_xyz_and_fail_on_y(endpoint, table):
    _call(
        endpoint,
        "create_fields",
        {
            "table_id": table.id,
            "fields": [
                {"name": "X", "type": "text"},
                {"name": "Y", "type": "text"},
                {"name": "Z", "type": "text"},
            ],
        },
    )
    undo_field = CreateFieldActionType.undo
    calls = []

    def fail_on_the_middle_field(*args):
        calls.append(args)
        if len(calls) == 2:
            raise Exception("boom")
        return undo_field(*args)

    with patch.object(
        CreateFieldActionType, "undo", side_effect=fail_on_the_middle_field
    ):
        _call(endpoint, "undo")
    assert {f.name for f in table.field_set.all()} == {"Name", "X", "Y"}


@pytest.mark.django_db
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_one_redo_restores_a_call_that_was_partly_undone(setup):
    endpoint, table = setup
    _create_xyz_and_fail_on_y(endpoint, table)

    redone = _call(endpoint, "redo")

    assert redone == [
        {"action": "Create field", "failed": True},
        {"action": "Create field", "failed": False},
    ]
    assert {f.name for f in table.field_set.all()} == {"Name", "X", "Y", "Z"}
    assert _call(endpoint, "redo") == []


@pytest.mark.django_db
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_undo_goes_on_into_a_partly_undone_call_once_redo_cant_restore_it(setup):
    endpoint, table = setup
    _call(endpoint, "create_rows", {"table_id": table.id, "rows": [{"Name": "OLD"}]})
    _create_xyz_and_fail_on_y(endpoint, table)
    _call(endpoint, "create_rows", {"table_id": table.id, "rows": [{"Name": "NEW"}]})
    assert _call(endpoint, "redo") == []

    assert _call(endpoint, "undo") == [{"action": "Create rows", "failed": False}]
    assert _names(table) == ["OLD"]

    assert _call(endpoint, "undo") == [{"action": "Create field", "failed": False}]
    assert {f.name for f in table.field_set.all()} == {"Name", "Y"}
    assert _call(endpoint, "undo") == [{"action": "Create rows", "failed": False}]
    assert _names(table) == []


@pytest.mark.django_db
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=2)
def test_redo_restores_every_part_when_the_failed_part_is_a_short_batch(setup):
    endpoint, table = setup
    _call(
        endpoint,
        "create_fields",
        {
            "table_id": table.id,
            "fields": [
                {"name": "X", "type": "text"},
                {"name": "Y", "type": "text"},
                {"name": "Z", "type": "text"},
            ],
        },
    )
    undo_field = CreateFieldActionType.undo
    calls = []

    def fail_on_x(*args):
        calls.append(args)
        if len(calls) == 3:
            raise Exception("boom")
        return undo_field(*args)

    # Undone newest first, two at a time: Z and Y, then X, which fails.
    with patch.object(CreateFieldActionType, "undo", side_effect=fail_on_x):
        assert _call(endpoint, "undo") == [
            {"action": "Create field", "failed": False},
            {"action": "Create field", "failed": False},
            {"action": "Create field", "failed": True},
        ]
    assert {f.name for f in table.field_set.all()} == {"Name", "X"}

    redone = _call(endpoint, "redo")

    assert redone == [
        {"action": "Create field", "failed": True},
        {"action": "Create field", "failed": False},
        {"action": "Create field", "failed": False},
    ]
    assert {f.name for f in table.field_set.all()} == {"Name", "X", "Y", "Z"}
    assert _call(endpoint, "redo") == []


@pytest.mark.django_db(transaction=True)
def test_a_cancelled_call_keeps_its_undo_session_until_its_body_ends(setup):
    endpoint, table = setup
    tool_class = type(mcp_tool_registry.get("create_fields"))
    original = tool_class._sync_call
    cancelled = threading.Event()
    first_done = threading.Event()

    def body(endpoint, args):
        first = args.model_copy(update={"fields": args.fields[:1]})
        rest = args.model_copy(update={"fields": args.fields[1:]})
        original(mcp_tool_registry.get("create_fields"), endpoint, first)
        first_done.set()
        # The client gives up here and the server stops waiting, but this
        # body still runs to the end on the thread.
        cancelled.wait(timeout=10)
        return original(mcp_tool_registry.get("create_fields"), endpoint, rest)

    arguments = {
        "table_id": table.id,
        "fields": [{"name": "X", "type": "text"}, {"name": "Y", "type": "text"}],
    }

    async def cancelled_call():
        token = current_key.set(endpoint.key)
        try:
            async with anyio.create_task_group() as group:

                async def cancel_after_first_field():
                    while not first_done.is_set():
                        await anyio.sleep(0.01)
                    group.cancel_scope.cancel()

                group.start_soon(cancel_after_first_field)
                await BaserowMCPServer().call_tool("create_fields", arguments)
        finally:
            current_key.reset(token)
            cancelled.set()

    def run():
        try:
            async_to_sync(cancelled_call)()
        finally:
            connection.close()

    with patch.object(tool_class, "_sync_call", side_effect=body):
        thread = threading.Thread(target=run)
        thread.start()
        thread.join(timeout=20)
    assert not thread.is_alive(), "The cancelled call never finished."

    actions = list(Action.objects.filter(user=endpoint.user).order_by("id"))
    assert len(actions) == 2
    assert {a.session for a in actions} == {endpoint.undo_session_id}
    groups = {a.action_group for a in actions}
    assert len(groups) == 1 and None not in groups

    assert len(_call(endpoint, "undo")) == 2
    assert {f.name for f in table.field_set.all()} == {"Name"}
