import json

import pytest

from baserow.contrib.database.ws.presence_focus_types import CellFocusType, RowFocusType
from baserow.core.async_redis import get_async_redis
from baserow.ws.consumers import MSG_TYPE_PRESENCE_FOCUS
from baserow.ws.presence import PresenceSpace
from tests.baserow.ws.test_presence import (
    SPACE_NAME,
    _connect,
    _drain,
    _subscribe,
    _subscribe_and_get_members,
)


def test_cell_focus_type_validates_valid_payload():
    ft = CellFocusType()
    result = ft.validate({"row_id": 1, "field_id": 2, "editing": True})
    assert result == {"type": "cell", "row_id": 1, "field_id": 2, "editing": True}

    result_defaults = ft.validate({"row_id": 3, "field_id": 4})
    assert result_defaults["editing"] is False


def test_cell_focus_type_rejects_invalid_payload():
    ft = CellFocusType()
    with pytest.raises(ValueError):
        ft.validate({"row_id": "not-int", "field_id": 2})
    with pytest.raises(ValueError):
        ft.validate({"row_id": 1})
    with pytest.raises(ValueError):
        ft.validate({})


def test_row_focus_type_validates_valid_payload():
    ft = RowFocusType()
    result = ft.validate({"row_id": 5, "editing": True})
    assert result == {"type": "row", "row_id": 5, "editing": True}

    result_defaults = ft.validate({"row_id": 7})
    assert result_defaults["editing"] is False


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_focus_stored_in_redis_entry():
    space = PresenceSpace("focus-store-test")
    await space.join("pid-1", user_id=42)
    await space.update_entry_focus(
        "pid-1", {"type": "cell", "row_id": 1, "field_id": 2, "editing": False}
    )

    redis = await get_async_redis()
    raw = await redis.hget(space.redis_key, "pid-1")
    data = json.loads(raw)
    assert data["focus"] == {
        "type": "cell",
        "row_id": 1,
        "field_id": 2,
        "editing": False,
    }
    assert data["user_id"] == 42

    await space.remove_entry("pid-1")


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_members_includes_focus():
    space = PresenceSpace("focus-active-test")
    await space.join("pid-1", user_id=10)
    await space.update_entry_focus(
        "pid-1", {"type": "cell", "row_id": 1, "field_id": 2, "editing": False}
    )
    await space.join("pid-2", user_id=20)

    active = await space.get_members(exclude_presence_id="pid-2")
    assert len(active) == 1
    assert active[0]["user_id"] == 10
    assert active[0]["focus"] == {
        "type": "cell",
        "row_id": 1,
        "field_id": 2,
        "editing": False,
    }

    members_all = await space.get_members()
    pid2_entry = [e for e in members_all if e["presence_id"] == "pid-2"][0]
    assert pid2_entry["focus"] is None

    await space.remove_entry("pid-1")
    await space.remove_entry("pid-2")


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_focus_null_clears_stored_focus():
    space = PresenceSpace("focus-clear-test")
    await space.join("pid-1", user_id=42)
    await space.update_entry_focus(
        "pid-1", {"type": "cell", "row_id": 1, "field_id": 2, "editing": False}
    )
    await space.update_entry_focus("pid-1", None)

    redis = await get_async_redis()
    raw = await redis.hget(space.redis_key, "pid-1")
    data = json.loads(raw)
    assert data["focus"] is None

    await space.remove_entry("pid-1")


async def _send_focus(communicator, page, focus, **params):
    await communicator.send_json_to(
        {"type": MSG_TYPE_PRESENCE_FOCUS, "page": page, "focus": focus, **params}
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_focus_broadcast_reaches_other_user(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe_and_get_members(comm_b)
    await _drain(comm_a)

    await _send_focus(
        comm_a,
        "test_presence_page",
        {"type": "cell", "row_id": 1, "field_id": 2},
        test_param=1,
    )

    msg = await comm_b.receive_json_from(timeout=0.5)
    assert msg["type"] == MSG_TYPE_PRESENCE_FOCUS
    assert msg["space"] == SPACE_NAME
    assert msg["user_id"] == user_a.id
    assert msg["focus"]["type"] == "cell"
    assert msg["focus"]["row_id"] == 1
    assert msg["focus"]["field_id"] == 2
    assert msg["focus"]["editing"] is False

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_focus_broadcast_excludes_sender(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe_and_get_members(comm_b)
    await _drain(comm_a)

    await _send_focus(
        comm_a,
        "test_presence_page",
        {"type": "cell", "row_id": 1, "field_id": 2},
        test_param=1,
    )

    await comm_b.receive_json_from(timeout=0.5)
    assert await comm_a.receive_nothing(timeout=0.3)

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_focus_null_broadcast_reaches_other_user(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe_and_get_members(comm_b)
    await _drain(comm_a)

    await _send_focus(comm_a, "test_presence_page", None, test_param=1)

    msg = await comm_b.receive_json_from(timeout=0.5)
    assert msg["type"] == MSG_TYPE_PRESENCE_FOCUS
    assert msg["focus"] is None

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_invalid_focus_type_silently_dropped(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe_and_get_members(comm_b)
    await _drain(comm_a)

    await _send_focus(
        comm_a,
        "test_presence_page",
        {"type": "nonexistent_type", "row_id": 1},
        test_param=1,
    )

    assert await comm_b.receive_nothing(timeout=0.3)

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_focus_on_non_presence_page_dropped(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a, page="test_non_presence_page")
    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b, page="test_non_presence_page")

    await _send_focus(
        comm_a,
        "test_non_presence_page",
        {"type": "cell", "row_id": 1, "field_id": 2},
        test_param=1,
    )

    assert await comm_b.receive_nothing(timeout=0.3)

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_focus_on_unsubscribed_page_silently_dropped(
    data_fixture, presence_types
):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe_and_get_members(comm_b)
    await _drain(comm_a)

    # A sends focus for a page they never subscribed to
    await _send_focus(
        comm_a,
        "test_presence_page",
        {"type": "cell", "row_id": 1, "field_id": 2},
        test_param=999,
    )

    assert await comm_b.receive_nothing(timeout=0.3)

    # Verify no focus stored in Redis for the non-subscribed space
    space = PresenceSpace("test-space-999")
    members = await space.get_members()
    assert members == []

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_disconnect_clears_focus_from_redis(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    comm_b, ws_b = await _connect(token_b)
    _, active_b = await _subscribe_and_get_members(comm_b)
    pid_a = active_b["entries"][0]["presence_id"]
    await _drain(comm_a)
    await _drain(comm_b)

    await _send_focus(
        comm_a,
        "test_presence_page",
        {"type": "cell", "row_id": 1, "field_id": 2},
        test_param=1,
    )
    await _drain(comm_b)

    # Verify focus is stored
    space = PresenceSpace(SPACE_NAME)
    members = await space.get_members()
    a_entry = [m for m in members if m["presence_id"] == pid_a][0]
    assert a_entry["focus"] is not None

    await comm_a.disconnect()

    # After disconnect, A's entry (including focus) should be removed
    members = await space.get_members()
    pids = [m["presence_id"] for m in members]
    assert pid_a not in pids

    await comm_b.disconnect()
