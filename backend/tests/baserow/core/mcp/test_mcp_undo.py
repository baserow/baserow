import asyncio
import json
import threading
import time
from asyncio import sleep as asyncio_sleep
from unittest.mock import patch

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
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.exceptions import LockConflict
from baserow.core.mcp import BaserowMCPServer, current_key, registries
from baserow.core.mcp.constants import ENDPOINT_CHANGES_LOCK_NAMESPACE
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


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("tool", ["undo", "redo"])
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_another_call_retries_until_a_call_is_fully_undone_or_redone(
    data_fixture, setup, tool
):
    endpoint, table = setup
    # Another table, so the other call isn't held up by the fields being replayed.
    other_table = data_fixture.create_database_table(database=table.database)
    data_fixture.create_text_field(table=other_table, name="Name", primary=True)
    _call(
        endpoint,
        "create_fields",
        {
            "table_id": table.id,
            "fields": [{"name": "X", "type": "text"}, {"name": "Y", "type": "text"}],
        },
    )
    if tool == "redo":
        _call(endpoint, "undo")

    def other_call():
        try:
            _call(
                endpoint,
                "create_rows",
                {"table_id": other_table.id, "rows": [{"Name": "A"}]},
            )
        finally:
            connection.close()

    # Another call of the same endpoint starts right after the first part is
    # replayed, and the next part runs once that call found the lock taken. The
    # call keeps trying, and gets the lock once the whole call is replayed.
    replay = getattr(ActionHandler, tool)
    other = threading.Thread(target=other_call)
    found_it_locked = threading.Event()
    other_call_was_held_back = []

    async def note_the_retry(seconds):
        found_it_locked.set()
        await asyncio_sleep(seconds)

    def first_part_then_other_call(*args):
        actions = replay(*args)
        if other.ident is None:
            other.start()
            other_call_was_held_back.append(found_it_locked.wait(timeout=10))
        return actions

    with (
        patch(f"{registries.__name__}.sleep", side_effect=note_the_retry),
        patch(f"{registries.__name__}.ENDPOINT_CHANGES_LOCK_WAIT_SECONDS", 20),
        patch.object(ActionHandler, tool, side_effect=first_part_then_other_call),
    ):
        replayed = _call(endpoint, tool)
        other.join(timeout=20)

    assert other_call_was_held_back == [True], "The other call never found it locked."
    assert len(replayed) == 2
    expected = {"Name"} if tool == "undo" else {"Name", "X", "Y"}
    assert {f.name for f in table.field_set.all()} == expected
    assert _names(other_table) == ["A"]


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


@pytest.mark.django_db(transaction=True)
def test_a_call_gives_up_when_the_endpoint_stays_locked(setup):
    endpoint, table = setup
    result = {}

    def call():
        try:
            started = time.monotonic()
            result["text"] = _call(
                endpoint,
                "create_rows",
                {"table_id": table.id, "rows": [{"Name": "A"}]},
                expect_error=True,
            )
            result["seconds"] = time.monotonic() - started
        finally:
            connection.close()

    key = [ENDPOINT_CHANGES_LOCK_NAMESPACE, endpoint.id]
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s, %s)", key)
    other = threading.Thread(target=call)
    try:
        with patch(f"{registries.__name__}.ENDPOINT_CHANGES_LOCK_WAIT_SECONDS", 0.5):
            other.start()
            other.join(timeout=5)
            still_waiting = other.is_alive()
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", key)
        other.join(timeout=10)

    assert not still_waiting, "The call kept waiting for the lock."
    assert "Try again" in result["text"]
    assert result["seconds"] < 3
    assert _names(table) == []


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


@pytest.mark.django_db(transaction=True)
def test_a_call_waiting_for_the_lock_doesnt_hold_up_other_calls(setup):
    endpoint, table = setup
    endpoint.allowed_tools = [*TOOLS, "list_databases"]
    endpoint.save()
    result = {}

    async def timed(name, arguments):
        server = BaserowMCPServer()
        current_key.set(endpoint.key)
        started = time.monotonic()
        async with client_session(server._mcp_server) as client:
            response = await client.call_tool(name, arguments)
        return response, time.monotonic() - started

    async def both():
        waiting = asyncio.ensure_future(
            timed(
                "create_rows",
                {"table_id": table.id, "rows": [{"Name": "A"}]},
            )
        )
        await asyncio.sleep(0.2)
        result["read"] = await timed("list_databases", {})
        result["write"] = await waiting

    def run():
        try:
            async_to_sync(both)()
        finally:
            connection.close()

    key = [ENDPOINT_CHANGES_LOCK_NAMESPACE, endpoint.id]
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s, %s)", key)
    other = threading.Thread(target=run)
    try:
        with patch(f"{registries.__name__}.ENDPOINT_CHANGES_LOCK_WAIT_SECONDS", 2):
            other.start()
            other.join(timeout=10)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", key)
        other.join(timeout=10)

    read, read_seconds = result["read"]
    write, _ = result["write"]
    assert not read.isError, read.content[0].text
    assert read_seconds < 1
    assert write.isError and "Try again" in write.content[0].text


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


def _advisory_locks_of(endpoint):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
            "AND database = (SELECT oid FROM pg_database "
            "WHERE datname = current_database()) "
            "AND classid = %s AND objid = %s AND objsubid = 2",
            [ENDPOINT_CHANGES_LOCK_NAMESPACE, endpoint.id],
        )
        return cursor.fetchone()[0]


def _cancel_a_call_after(endpoint, table, seconds, release=None):
    """
    Runs a `create_rows` call on another thread and cancels it after `seconds`
    the way the MCP SDK does, with an anyio cancel scope. Returns the number of
    advisory locks with the endpoint's key once the thread is done, counted
    before its connection closes, because closing it would release them.
    """

    tool = mcp_tool_registry.get("create_rows")
    args = tool.input_schema(table_id=table.id, rows=[{"Name": "A"}])
    result = {}

    async def cancelled_call():
        with anyio.move_on_after(seconds) as scope:
            await tool.call(endpoint, args.model_dump())
        result["cancelled"] = scope.cancelled_caught
        if release is not None:
            release.set()

    def run():
        try:
            async_to_sync(cancelled_call)()
            result["locks"] = _advisory_locks_of(endpoint)
        finally:
            connection.close()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=20)
    assert not thread.is_alive(), "The cancelled call never finished."
    return result


@pytest.mark.django_db(transaction=True)
def test_a_call_cancelled_while_it_runs_releases_the_endpoint_lock(setup):
    endpoint, table = setup
    release = threading.Event()
    body_ran = []

    def slow_body(*args):
        body_ran.append(True)
        release.wait(timeout=10)
        return []

    with patch.object(
        type(mcp_tool_registry.get("create_rows")),
        "_sync_call",
        side_effect=slow_body,
    ):
        result = _cancel_a_call_after(endpoint, table, 0.3, release=release)

    assert body_ran == [True]
    assert result["cancelled"] is True
    assert result["locks"] == 0


@pytest.mark.django_db(transaction=True)
def test_a_call_cancelled_while_it_waits_for_the_lock_leaves_no_lock(setup):
    endpoint, table = setup
    key = [ENDPOINT_CHANGES_LOCK_NAMESPACE, endpoint.id]
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s, %s)", key)
    try:
        with patch(f"{registries.__name__}.ENDPOINT_CHANGES_LOCK_WAIT_SECONDS", 20):
            result = _cancel_a_call_after(endpoint, table, 0.35)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", key)

    assert result["cancelled"] is True
    assert result["locks"] == 1  # Only the one this test holds.
    assert _names(table) == []


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
