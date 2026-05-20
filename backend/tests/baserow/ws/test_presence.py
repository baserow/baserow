import json
import time
from unittest.mock import Mock

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django_redis import get_redis_connection

from baserow.config.asgi import application
from baserow.ws.presence import PRESENCE_STALE_AFTER_SECONDS, PresenceHandler
from baserow.ws.presence_focus_types import (
    InvalidPresenceFocus,
    PresenceFocusType,
    presence_focus_type_registry,
)
from baserow.ws.registries import PageType, page_registry

GROUP = "test-presence-page-1"
PRESENCE_KEY = f"presence:{GROUP}"


class PresenceTestPageType(PageType):
    type = "test_presence_page"
    parameters = ["test_param"]
    presence_enabled = True

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-presence-page-{test_param}"


class NonPresencePageType(PageType):
    type = "test_non_presence_page"
    parameters = ["test_param"]
    presence_enabled = False

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-non-presence-page-{test_param}"


class PresenceWithPermGroupPageType(PageType):
    type = "test_presence_perm_page"
    parameters = ["test_param"]
    presence_enabled = True

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-presence-perm-page-{test_param}"

    def get_permission_channel_group_name(self, test_param, **kwargs):
        return f"test-perm-group-{test_param}"


class PresenceTestFocusType(PresenceFocusType):
    type = "test_focus"
    declared_keys = ("type", "cell")


@pytest.fixture
def presence_types():
    page_registry.register(PresenceTestPageType())
    page_registry.register(NonPresencePageType())
    page_registry.register(PresenceWithPermGroupPageType())
    presence_focus_type_registry.register(PresenceTestFocusType())
    yield
    page_registry.unregister(PresenceTestPageType.type)
    page_registry.unregister(NonPresencePageType.type)
    page_registry.unregister(PresenceWithPermGroupPageType.type)
    presence_focus_type_registry.unregister(PresenceTestFocusType.type)


async def _connect(token):
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    auth = await communicator.receive_json_from()
    return communicator, auth["web_socket_id"]


async def _subscribe(communicator, page="test_presence_page", test_param=1):
    await communicator.send_json_to({"page": page, "test_param": test_param})
    return await communicator.receive_json_from(timeout=0.5)


async def _drain(communicator, timeout=0.1):
    frames = []
    while not await communicator.receive_nothing(timeout=timeout):
        frames.append(await communicator.receive_json_from())
    return frames


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_broadcasts_join_and_returns_snapshot(
    data_fixture, presence_types
):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    page_add_a = await _subscribe(comm_a)
    assert page_add_a["type"] == "page_add"
    assert page_add_a["presence_snapshot"] == []

    comm_b, ws_b = await _connect(token_b)
    page_add_b = await _subscribe(comm_b)
    assert page_add_b["presence_snapshot"] == [
        {"user_id": user_a.id, "web_socket_id": ws_a, "focus": None}
    ]

    join = await comm_a.receive_json_from(timeout=0.5)
    assert join == {
        "type": "presence.join",
        "channel": GROUP,
        "user_id": user_b.id,
        "web_socket_id": ws_b,
    }

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscriber_does_not_receive_own_join(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a)
    assert await comm_a.receive_nothing(timeout=0.3)
    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_unsubscribe_broadcasts_leave_not_to_self(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b)
    await _drain(comm_a)  # consume B's join

    await comm_b.send_json_to({"remove_page": "test_presence_page", "test_param": 1})
    discard = await comm_b.receive_json_from(timeout=0.5)
    assert discard["type"] == "page_discard"
    assert await comm_b.receive_nothing(timeout=0.3)  # no self leave

    leave = await comm_a.receive_json_from(timeout=0.5)
    assert leave == {
        "type": "presence.leave",
        "channel": GROUP,
        "user_id": user_b.id,
        "web_socket_id": ws_b,
    }

    redis = get_redis_connection("default")
    assert redis.hexists(PRESENCE_KEY, ws_b) is False
    assert redis.hexists(PRESENCE_KEY, ws_a) is True

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_disconnect_broadcasts_leave(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b)
    await _drain(comm_a)  # consume B's join

    await comm_b.disconnect()

    frames = await _drain(comm_a, timeout=0.3)
    assert frames, "expected a presence.leave for the disconnected session"
    assert all(
        f["type"] == "presence.leave"
        and f["user_id"] == user_b.id
        and f["web_socket_id"] == ws_b
        for f in frames
    )

    redis = get_redis_connection("default")
    assert redis.hexists(PRESENCE_KEY, ws_b) is False
    assert redis.hexists(PRESENCE_KEY, ws_a) is True

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_valid_focus_broadcast_to_others_not_sender(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b)
    await _drain(comm_a)

    focus = {"type": "test_focus", "cell": "A1"}
    await comm_a.send_json_to(
        {
            "type": "presence.focus",
            "page": "test_presence_page",
            "test_param": 1,
            "focus": focus,
        }
    )

    received = await comm_b.receive_json_from(timeout=0.5)
    assert received == {
        "type": "presence.focus",
        "channel": GROUP,
        "user_id": user_a.id,
        "web_socket_id": ws_a,
        "focus": focus,
    }
    assert await comm_a.receive_nothing(timeout=0.3)

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@pytest.mark.parametrize(
    "bad_focus",
    [
        {"type": "test_focus", "blob": "x" * 5000},  # too large
        "not-an-object",  # not a dict
        {"type": "unregistered_focus_type"},  # unknown type
        {"no_type": True},  # missing type
    ],
)
async def test_invalid_focus_silently_dropped(data_fixture, presence_types, bad_focus):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b)
    await _drain(comm_a)

    await comm_a.send_json_to(
        {
            "type": "presence.focus",
            "page": "test_presence_page",
            "test_param": 1,
            "focus": bad_focus,
        }
    )

    assert await comm_b.receive_nothing(timeout=0.3)
    assert await comm_a.receive_nothing(timeout=0.3)

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_null_focus_accepted_and_broadcast(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a)
    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b)
    await _drain(comm_a)

    await comm_a.send_json_to(
        {
            "type": "presence.focus",
            "page": "test_presence_page",
            "test_param": 1,
            "focus": None,
        }
    )

    received = await comm_b.receive_json_from(timeout=0.5)
    assert received == {
        "type": "presence.focus",
        "channel": GROUP,
        "user_id": user_a.id,
        "web_socket_id": ws_a,
        "focus": None,
    }

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_focus_rejected_when_not_subscribed(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)

    await comm_a.send_json_to(
        {
            "type": "presence.focus",
            "page": "test_presence_page",
            "test_param": 1,
            "focus": {"type": "test_focus", "cell": "A1"},
        }
    )
    assert await comm_a.receive_nothing(timeout=0.3)
    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_non_presence_page_omits_snapshot_key(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    page_add_a = await _subscribe(comm_a, page="test_non_presence_page")
    assert "presence_snapshot" not in page_add_a

    comm_b, ws_b = await _connect(token_b)
    page_add_b = await _subscribe(comm_b, page="test_non_presence_page")
    assert "presence_snapshot" not in page_add_b

    assert await comm_a.receive_nothing(timeout=0.3)
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

    await comm_a.send_json_to(
        {
            "type": "presence.focus",
            "page": "test_non_presence_page",
            "test_param": 1,
            "focus": {"type": "test_focus", "cell": "A1"},
        }
    )

    assert await comm_b.receive_nothing(timeout=0.3)
    assert await comm_a.receive_nothing(timeout=0.3)

    redis = get_redis_connection("default")
    assert not list(redis.scan_iter(match="presence:*"))

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_channel_isolation_no_cross_delivery(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a, test_param=1)

    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b, test_param=2)

    assert await comm_a.receive_nothing(timeout=0.3)

    await comm_b.send_json_to(
        {
            "type": "presence.focus",
            "page": "test_presence_page",
            "test_param": 2,
            "focus": {"type": "test_focus", "cell": "X9"},
        }
    )

    assert await comm_a.receive_nothing(timeout=0.3)

    redis = get_redis_connection("default")
    key_1 = "presence:test-presence-page-1"
    key_2 = "presence:test-presence-page-2"
    assert redis.hexists(key_1, ws_a) is True
    assert redis.hexists(key_2, ws_b) is True
    assert redis.hexists(key_1, ws_b) is False
    assert redis.hexists(key_2, ws_a) is False

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_disconnect_removes_from_all_subscribed_channels(
    data_fixture, presence_types
):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a, test_param=1)
    await _subscribe(comm_a, test_param=2)

    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b, test_param=1)
    await _drain(comm_b)

    await comm_a.disconnect()

    leave = await comm_b.receive_json_from(timeout=0.5)
    assert leave["type"] == "presence.leave"
    assert leave["web_socket_id"] == ws_a

    redis = get_redis_connection("default")
    assert redis.hexists("presence:test-presence-page-1", ws_a) is False
    assert redis.hexists("presence:test-presence-page-2", ws_a) is False

    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_multi_tab_same_user_separate_entries(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()

    comm_1, ws_1 = await _connect(token_a)
    page_add_1 = await _subscribe(comm_1)
    assert page_add_1["presence_snapshot"] == []

    comm_2, ws_2 = await _connect(token_a)
    page_add_2 = await _subscribe(comm_2)
    assert len(page_add_2["presence_snapshot"]) == 1
    assert page_add_2["presence_snapshot"][0]["user_id"] == user_a.id
    assert page_add_2["presence_snapshot"][0]["web_socket_id"] == ws_1

    join = await comm_1.receive_json_from(timeout=0.5)
    assert join["type"] == "presence.join"
    assert join["user_id"] == user_a.id
    assert join["web_socket_id"] == ws_2

    redis = get_redis_connection("default")
    assert redis.hexists(PRESENCE_KEY, ws_1) is True
    assert redis.hexists(PRESENCE_KEY, ws_2) is True

    await comm_1.disconnect()
    await comm_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_stale_entry_cleaned_on_new_subscribe(data_fixture, presence_types):
    redis = get_redis_connection("default")
    stale = json.dumps(
        {"user_id": 999, "focus": None, "last_seen": int(time.time()) - 99999}
    )
    redis.hset(PRESENCE_KEY, "ghost-ws-id", stale)

    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)
    page_add = await _subscribe(comm_a)

    assert page_add["presence_snapshot"] == []
    assert redis.hexists(PRESENCE_KEY, "ghost-ws-id") is False
    assert redis.hexists(PRESENCE_KEY, ws_a) is True

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_double_subscribe_does_not_broadcast_duplicate_join(
    data_fixture, presence_types
):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a)

    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b)
    await _drain(comm_a)

    page_add_2 = await _subscribe(comm_b)
    assert page_add_2["type"] == "page_add"
    assert len(page_add_2["presence_snapshot"]) == 1

    assert await comm_a.receive_nothing(timeout=0.3)

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_previous_web_socket_id_purges_ghost_entry(data_fixture, presence_types):
    redis = get_redis_connection("default")
    ghost_ws_id = "old-ws-id-that-didnt-disconnect"
    ghost_entry = json.dumps(
        {"user_id": 42, "focus": None, "last_seen": int(time.time())}
    )
    redis.hset(PRESENCE_KEY, ghost_ws_id, ghost_entry)

    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)

    await comm_a.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": None,
            "last_seen_id": None,
            "previous_web_socket_id": ghost_ws_id,
        }
    )
    await comm_a.receive_json_from(timeout=0.5)  # realtime_subscribe_result

    page_add = await _subscribe(comm_a)

    assert redis.hexists(PRESENCE_KEY, ghost_ws_id) is False
    assert redis.hexists(PRESENCE_KEY, ws_a) is True
    snapshot_ws_ids = [e["web_socket_id"] for e in page_add["presence_snapshot"]]
    assert ghost_ws_id not in snapshot_ws_ids

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_redis_key_ttl_set_on_presence_operations(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a)

    redis = get_redis_connection("default")
    ttl = redis.ttl(PRESENCE_KEY)
    expected_ttl = PRESENCE_STALE_AFTER_SECONDS * 4
    assert 0 < ttl <= expected_ttl

    await comm_a.send_json_to(
        {
            "type": "presence.focus",
            "page": "test_presence_page",
            "test_param": 1,
            "focus": {"type": "test_focus", "cell": "B2"},
        }
    )
    await _drain(comm_a, timeout=0.3)

    ttl_after_focus = redis.ttl(PRESENCE_KEY)
    assert 0 < ttl_after_focus <= expected_ttl

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_presence_handler_snapshot_self_exclusion_and_focus():
    h1 = PresenceHandler(Mock(), "chan-1", "ws-1", user_id=7)
    h2 = PresenceHandler(Mock(), "chan-2", "ws-2", user_id=9)

    assert await h1.add_presence("g") == []
    assert await h2.add_presence("g") == [
        {"user_id": 7, "web_socket_id": "ws-1", "focus": None}
    ]

    await h1.update_focus("g", {"type": "test_focus", "cell": "B2"})
    snapshot = await h2.get_snapshot("g", exclude_web_socket_id="ws-2")
    assert snapshot == [
        {
            "user_id": 7,
            "web_socket_id": "ws-1",
            "focus": {"type": "test_focus", "cell": "B2"},
        }
    ]

    await h1.remove_presence("g")
    assert await h2.get_snapshot("g", exclude_web_socket_id="ws-2") == []


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_presence_handler_cleanup_prunes_stale_and_corrupt():
    redis = get_redis_connection("default")
    key = "presence:g2"
    now = int(time.time())
    redis.hset(
        key,
        "fresh",
        json.dumps({"user_id": 1, "focus": None, "last_seen": now}),
    )
    redis.hset(
        key,
        "stale",
        json.dumps({"user_id": 2, "focus": None, "last_seen": now - 99999}),
    )
    redis.hset(key, "corrupt", "not-json")

    h = PresenceHandler(Mock(), "chan", "ws-x", user_id=42)
    entries, corrupt = await h._read_all_entries("g2")
    survivors = await h._prune_stale("g2", entries, corrupt)

    assert "fresh" in survivors
    assert survivors["fresh"]["user_id"] == 1
    assert "stale" not in survivors
    assert "corrupt" not in survivors
    assert redis.hexists(key, "fresh") is True
    assert redis.hexists(key, "stale") is False
    assert redis.hexists(key, "corrupt") is False


@pytest.mark.websockets
def test_presence_focus_type_default_validation():
    focus_type = PresenceTestFocusType()

    result = focus_type.validate({"type": "test_focus", "cell": "A1"})
    assert result == {"type": "test_focus", "cell": "A1"}

    with pytest.raises(InvalidPresenceFocus):
        focus_type.validate("not-a-dict")
    with pytest.raises(InvalidPresenceFocus):
        focus_type.validate({"type": "test_focus", "blob": "x" * 5000})
    with pytest.raises(InvalidPresenceFocus):
        focus_type.validate({"type": "test_focus", "nan": float("nan")})
    with pytest.raises(InvalidPresenceFocus, match="type mismatch"):
        focus_type.validate({"type": "wrong_type", "cell": "A1"})


@pytest.mark.websockets
def test_presence_focus_type_strips_undeclared_keys():
    focus_type = PresenceTestFocusType()

    result = focus_type.validate(
        {"type": "test_focus", "cell": "A1", "extra_key": "should_be_stripped"}
    )
    assert result == {"type": "test_focus", "cell": "A1"}
    assert "extra_key" not in result


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_permission_revocation_removes_presence_and_broadcasts_leave(
    data_fixture, presence_types
):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe(comm_a, page="test_presence_perm_page")

    comm_b, ws_b = await _connect(token_b)
    await _subscribe(comm_b, page="test_presence_perm_page")
    await _drain(comm_a)

    redis = get_redis_connection("default")
    pres_key = "presence:test-presence-perm-page-1"
    assert redis.hexists(pres_key, ws_a) is True
    assert redis.hexists(pres_key, ws_b) is True

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "test-perm-group-1",
        {
            "type": "users_removed_from_permission_group",
            "user_ids_to_remove": [user_b.id],
            "permission_group_name": "test-perm-group-1",
        },
    )

    b_frames = await _drain(comm_b, timeout=0.5)
    assert any(f["type"] == "page_discard" for f in b_frames)

    a_frames = await _drain(comm_a, timeout=0.5)
    leaves = [f for f in a_frames if f["type"] == "presence.leave"]
    assert len(leaves) == 1
    assert leaves[0]["user_id"] == user_b.id
    assert leaves[0]["web_socket_id"] == ws_b

    assert redis.hexists(pres_key, ws_b) is False
    assert redis.hexists(pres_key, ws_a) is True

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.websockets
def test_filter_for_recipient_default_identity():
    focus_type = PresenceTestFocusType()
    focus = {"type": "test_focus", "cell": "A1"}
    assert focus_type.filter_for_recipient(focus, {}) == focus
