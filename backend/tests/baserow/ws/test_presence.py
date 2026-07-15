import json
import uuid
from unittest.mock import AsyncMock, Mock, patch

from django.test import override_settings

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.core.async_redis import get_async_redis
from baserow.ws.auth import ANONYMOUS_USER_TOKEN
from baserow.ws.presence import (
    ANONYMOUS_USER_ID,
    PresenceHandler,
    PresenceSpace,
    make_page_key,
)

VALID_ONE_SEAT_ENTERPRISE_LICENSE = (
    # id: "1", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjUzODczYmVkLWJlNTQtNDEwZS04N2EzLTE2OTM2ODY2YjBiNiIsICJ2YWxpZF9mcm9tIjogIjIwMjItMTAtMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDY5LTA4LTA5VDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJlbnRlcnByaXNlIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIyLTEwLTI2VDE0OjQ4OjU0LjI1OTQyMyIsICJpc3N1ZWRfdG9fZW1haWwiOiAidGVzdEB0ZXN0LmNvbSIsICJpc3N1ZWRfdG9fbmFtZSI6ICJ0ZXN0QHRlc3QuY29tIiwgImluc3RhbmNlX2lkIjogIjEifQ==.B7aPXR0R4Fxr28AL7B5oopa2Yiz_MmEBZGdzSEHHLt4wECpnzjd_SF440KNLEZYA6WL1rhNkZ5znbjYIp6KdCqLdcm1XqNYOIKQvNTOtl9tUAYj_Qvhq1jhqSja-n3HFBjIh9Ve7a6T1PuaPLF1DoxSRGFZFXliMeJRBSzfTsiHiO22xRQ4GwafscYfUIWvIJJHGHtYEd9rk0tG6mfGEaQGB4e6KOsN-zw-bgLDBOKmKTGrVOkZnaGHBVVhUdpBn25r3CFWqHIApzUCo81zAA96fECHPlx_fBHhvIJXLsN5i3LdeJlwysg5SBO15Vt-tsdPmdcsec-fOzik-k3ib0A== "
)


def _enable_enterprise():
    from baserow.core.cache import local_cache
    from baserow.core.models import Settings
    from baserow_premium.license.models import License

    Settings.objects.update_or_create(defaults={"instance_id": "1"})
    License.objects.get_or_create(
        cached_untrusted_instance_wide=True,
        defaults={"license": VALID_ONE_SEAT_ENTERPRISE_LICENSE.decode()},
    )
    local_cache.clear()


SPACE_NAME = "test-space-1"
PRESENCE_KEY = f"presence:{SPACE_NAME}"


async def _connect(token):
    ws_id = str(uuid.uuid4())
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id={ws_id}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()  # auth message
    return communicator, ws_id


async def _connect_anonymous():
    ws_id = str(uuid.uuid4())
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={ANONYMOUS_USER_TOKEN}&web_socket_id={ws_id}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()  # auth message
    return communicator, ws_id


async def _subscribe(communicator, page="test_presence_page", test_param=1):
    await communicator.send_json_to({"page": page, "test_param": test_param})
    return await communicator.receive_json_from(timeout=0.5)


async def _drain(communicator, timeout=0.1):
    frames = []
    while not await communicator.receive_nothing(timeout=timeout):
        frames.append(await communicator.receive_json_from())
    return frames


async def _subscribe_and_get_members(
    communicator, page="test_presence_page", test_param=1
):
    """Subscribe and return (page_add, members_msg) tuple."""
    page_add = await _subscribe(communicator, page=page, test_param=test_param)
    assert page_add["type"] == "page_add"
    members_msg = await communicator.receive_json_from(timeout=0.5)
    assert members_msg["type"] == "presence.members"
    return page_add, members_msg


async def _presence_ids_in_redis(redis_key):
    """Return set of presence_id keys stored in a Redis presence hash."""
    redis = await get_async_redis()
    return set(await redis.hkeys(redis_key))


def _make_mock_handler(user_id=7):
    """Build a PresenceHandler wired to a fully mocked consumer."""
    consumer = Mock()
    consumer.channel_layer = AsyncMock()
    consumer.channel_name = "chan-test"
    consumer.send_json = AsyncMock()
    handler = PresenceHandler(
        consumer=consumer, web_socket_id="ws-test", user_id=user_id
    )
    return handler, consumer


async def _create_enterprise_table_with_restricted_view(data_fixture):
    setup = await database_sync_to_async(
        lambda: (
            _enable_enterprise(),
            data_fixture.create_user_and_token(),
            data_fixture.create_user_and_token(),
        )
    )()
    _, (user_a, token_a), (user_b, token_b) = setup

    _, _, table, restricted_view = await database_sync_to_async(
        lambda: (
            (w := data_fixture.create_workspace(user=user_a, members=[user_b])),
            (db := data_fixture.create_database_application(workspace=w)),
            (t := data_fixture.create_database_table(database=db)),
            data_fixture.create_grid_view(table=t, ownership_type="restricted"),
        )
    )()
    return user_a, token_a, user_b, token_b, table, restricted_view


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_broadcasts_join_and_returns_members(
    data_fixture, presence_types
):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    page_add_a, active_a = await _subscribe_and_get_members(comm_a)
    assert "presence_members" not in page_add_a
    assert active_a["entries"] == []
    assert active_a["space"] == SPACE_NAME

    comm_b, ws_b = await _connect(token_b)
    page_add_b, active_b = await _subscribe_and_get_members(comm_b)
    assert "presence_members" not in page_add_b
    assert len(active_b["entries"]) == 1
    assert active_b["entries"][0]["user_id"] == user_a.id
    pid_a = active_b["entries"][0]["presence_id"]

    join = await comm_a.receive_json_from(timeout=0.5)
    assert join["type"] == "presence.join"
    assert join["space"] == SPACE_NAME
    assert join["user_id"] == user_b.id
    assert "presence_id" in join
    assert "web_socket_id" not in join

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@override_settings(PRESENCE_VISIBLE_USERS=0)
async def test_circuit_breaker_setting_disables_presence(data_fixture, presence_types):
    user, token = data_fixture.create_user_and_token()

    comm, _ = await _connect(token)
    page_add = await _subscribe(comm)
    assert page_add["type"] == "page_add"

    frames = await _drain(comm)
    assert [f for f in frames if f["type"].startswith("presence.")] == []
    assert await _presence_ids_in_redis(PRESENCE_KEY) == set()

    await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscriber_does_not_receive_own_join(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    assert await comm_a.receive_nothing(timeout=0.3)
    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_unsubscribe_broadcasts_leave_not_to_self(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    comm_b, ws_b = await _connect(token_b)
    _, active_b = await _subscribe_and_get_members(comm_b)
    pid_a = active_b["entries"][0]["presence_id"]
    await _drain(comm_a)  # consume B's join

    await comm_b.send_json_to({"remove_page": "test_presence_page", "test_param": 1})
    b_frames = await _drain(comm_b, timeout=0.3)
    assert any(f["type"] == "presence.space_discard" for f in b_frames)
    assert any(f["type"] == "page_discard" for f in b_frames)
    assert not any(f["type"] == "presence.leave" for f in b_frames)

    leave = await comm_a.receive_json_from(timeout=0.5)
    assert leave["type"] == "presence.leave"
    assert leave["space"] == SPACE_NAME
    assert leave["user_id"] == user_b.id
    assert "presence_id" in leave
    assert "web_socket_id" not in leave

    pids = await _presence_ids_in_redis(PRESENCE_KEY)
    assert pid_a in pids
    assert leave["presence_id"] not in pids

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_disconnect_broadcasts_leave(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)
    comm_b, ws_b = await _connect(token_b)
    _, active_b = await _subscribe_and_get_members(comm_b)
    pid_a = active_b["entries"][0]["presence_id"]
    await _drain(comm_a)  # consume B's join

    await comm_b.disconnect()

    frames = await _drain(comm_a, timeout=0.3)
    assert frames, "expected a presence.leave for the disconnected session"
    assert all(
        f["type"] == "presence.leave"
        and f["user_id"] == user_b.id
        and "presence_id" in f
        for f in frames
    )

    pids = await _presence_ids_in_redis(PRESENCE_KEY)
    assert pid_a in pids

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_non_presence_page_omits_members(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    page_add_a = await _subscribe(comm_a, page="test_non_presence_page")
    assert page_add_a["type"] == "page_add"
    assert "presence_members" not in page_add_a
    assert await comm_a.receive_nothing(timeout=0.3)

    comm_b, ws_b = await _connect(token_b)
    page_add_b = await _subscribe(comm_b, page="test_non_presence_page")
    assert "presence_members" not in page_add_b
    assert await comm_b.receive_nothing(timeout=0.3)

    assert await comm_a.receive_nothing(timeout=0.3)
    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_channel_isolation_no_cross_delivery(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a, test_param=1)

    comm_b, ws_b = await _connect(token_b)
    await _subscribe_and_get_members(comm_b, test_param=2)

    assert await comm_a.receive_nothing(timeout=0.3)

    pids_1 = await _presence_ids_in_redis("presence:test-space-1")
    pids_2 = await _presence_ids_in_redis("presence:test-space-2")
    assert len(pids_1) == 1
    assert len(pids_2) == 1
    assert pids_1.isdisjoint(pids_2)

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
    await _subscribe_and_get_members(comm_a, test_param=1)
    await _subscribe_and_get_members(comm_a, test_param=2)

    comm_b, ws_b = await _connect(token_b)
    _, active_b = await _subscribe_and_get_members(comm_b, test_param=1)
    pid_a = active_b["entries"][0]["presence_id"]
    await _drain(comm_b)

    await comm_a.disconnect()

    leave = await comm_b.receive_json_from(timeout=0.5)
    assert leave["type"] == "presence.leave"
    assert leave["presence_id"] == pid_a

    assert len(await _presence_ids_in_redis("presence:test-space-1")) == 1  # only B
    assert len(await _presence_ids_in_redis("presence:test-space-2")) == 0

    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_multi_tab_same_user_separate_entries(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()

    comm_1, ws_1 = await _connect(token_a)
    _, active_1 = await _subscribe_and_get_members(comm_1)
    assert active_1["entries"] == []

    comm_2, ws_2 = await _connect(token_a)
    _, active_2 = await _subscribe_and_get_members(comm_2)
    assert len(active_2["entries"]) == 1
    assert active_2["entries"][0]["user_id"] == user_a.id
    pid_1 = active_2["entries"][0]["presence_id"]

    join = await comm_1.receive_json_from(timeout=0.5)
    assert join["type"] == "presence.join"
    assert join["user_id"] == user_a.id
    pid_2 = join["presence_id"]

    pids = await _presence_ids_in_redis(PRESENCE_KEY)
    assert pid_1 in pids
    assert pid_2 in pids
    assert pid_1 != pid_2

    await comm_1.disconnect()
    await comm_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_corrupt_entry_cleaned_on_new_subscribe(data_fixture, presence_types):
    redis = await get_async_redis()
    await redis.hset(PRESENCE_KEY, "corrupt-pid", "not-json")

    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)
    _, members_resp = await _subscribe_and_get_members(comm_a)

    assert members_resp["entries"] == []
    assert not await redis.hexists(PRESENCE_KEY, "corrupt-pid")
    assert len(await _presence_ids_in_redis(PRESENCE_KEY)) == 1

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
    await _subscribe_and_get_members(comm_a)

    comm_b, ws_b = await _connect(token_b)
    await _subscribe_and_get_members(comm_b)
    await _drain(comm_a)

    # second subscribe — already in space, no members or join broadcast
    await comm_b.send_json_to({"page": "test_presence_page", "test_param": 1})
    page_add_2 = await comm_b.receive_json_from(timeout=0.5)
    assert page_add_2["type"] == "page_add"
    assert await comm_b.receive_nothing(timeout=0.3)
    assert await comm_a.receive_nothing(timeout=0.3)

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_redis_key_has_sliding_ttl(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)

    redis = await get_async_redis()
    ttl = await redis.ttl(PRESENCE_KEY)
    assert 0 < ttl <= 43200

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_presence_space_and_handler_members_self_exclusion():
    space = PresenceSpace("g")
    mock_ctx_1 = Mock()
    mock_ctx_1.channel_layer = Mock()
    mock_ctx_1.channel_name = "chan-1"
    mock_ctx_2 = Mock()
    mock_ctx_2.channel_layer = Mock()
    mock_ctx_2.channel_name = "chan-2"
    h1 = PresenceHandler(consumer=mock_ctx_1, web_socket_id="ws-1", user_id=7)
    h2 = PresenceHandler(consumer=mock_ctx_2, web_socket_id="ws-2", user_id=9)

    assert await h1._join(space) == []
    active = await h2._join(space)
    assert len(active) == 1
    assert active[0]["user_id"] == 7
    assert active[0]["presence_id"] == h1.presence_id

    await h1._leave(space)
    active = await space.get_members(exclude_presence_id=h2.presence_id)
    assert active == []


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_presence_space_cleanup_removes_corrupt_entries():
    redis = await get_async_redis()
    space = PresenceSpace("g2")
    await redis.hset(space.redis_key, "valid", json.dumps({"user_id": 1}))
    await redis.hset(space.redis_key, "corrupt", "not-json")

    active = await space.get_members()
    assert len(active) == 1
    assert active[0]["user_id"] == 1
    assert active[0]["presence_id"] == "valid"
    assert await redis.hexists(space.redis_key, "valid") is True
    assert await redis.hexists(space.redis_key, "corrupt") is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_permission_revocation_removes_presence_and_broadcasts_leave(
    data_fixture, presence_types
):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a, page="test_presence_perm_page")

    comm_b, ws_b = await _connect(token_b)
    _, active_b = await _subscribe_and_get_members(
        comm_b, page="test_presence_perm_page"
    )
    pid_a = active_b["entries"][0]["presence_id"]
    await _drain(comm_a)

    pres_key = "presence:test-perm-space-1"
    pids_before = await _presence_ids_in_redis(pres_key)
    assert pid_a in pids_before
    assert len(pids_before) == 2

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
    pid_b = leaves[0]["presence_id"]

    pids_after = await _presence_ids_in_redis(pres_key)
    assert pid_b not in pids_after
    assert pid_a in pids_after

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_table_page_subscribe_returns_members(data_fixture):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a, members=[user_b])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    page_add_a = await comm_a.receive_json_from(timeout=1)
    assert page_add_a["type"] == "page_add"
    active_a = await comm_a.receive_json_from(timeout=1)
    assert active_a["type"] == "presence.members"
    assert active_a["space"] == f"table-{table.id}"
    assert active_a["entries"] == []

    comm_b, ws_b = await _connect(token_b)
    await comm_b.send_json_to({"page": "table", "table_id": table.id})
    page_add_b = await comm_b.receive_json_from(timeout=1)
    assert page_add_b["type"] == "page_add"
    active_b = await comm_b.receive_json_from(timeout=1)
    assert active_b["type"] == "presence.members"
    assert len(active_b["entries"]) == 1
    assert active_b["entries"][0]["user_id"] == user_a.id
    assert "presence_id" in active_b["entries"][0]

    join = await comm_a.receive_json_from(timeout=1)
    assert join["type"] == "presence.join"
    assert join["user_id"] == user_b.id

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_restricted_view_excluded_from_presence(data_fixture):
    """Restricted views return None for presence — no join/members events."""

    (
        user_a,
        token_a,
        user_b,
        token_b,
        table,
        restricted_view,
    ) = await _create_enterprise_table_with_restricted_view(data_fixture)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await comm_a.receive_json_from(timeout=1)  # page_add
    active_a = await comm_a.receive_json_from(timeout=1)
    assert active_a["space"] == f"table-{table.id}"

    comm_b, ws_b = await _connect(token_b)
    await comm_b.send_json_to(
        {
            "page": "restricted_view",
            "restricted_view_id": restricted_view.id,
        }
    )
    page_add_b = await comm_b.receive_json_from(timeout=1)
    assert page_add_b["type"] == "page_add"
    # No presence.members expected — restricted views opt out
    assert await comm_b.receive_nothing(timeout=0.5)
    # Table subscriber should NOT see a join from the restricted view user
    assert await comm_a.receive_nothing(timeout=0.5)

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_public_view_joins_table_presence_space(data_fixture):
    user_a, token_a = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "view", "slug": view.slug})
    page_add = await comm_a.receive_json_from(timeout=1)
    assert page_add["type"] == "page_add"
    members = await comm_a.receive_json_from(timeout=1)
    assert members["type"] == "presence.members"
    assert members["space"] == f"table-{table.id}"
    assert members["entries"] == []

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_restricted_view_no_presence_entries_in_redis(data_fixture):
    """Restricted view subscription creates no Redis presence entries."""

    (
        user_a,
        token_a,
        user_b,
        token_b,
        table,
        restricted_view,
    ) = await _create_enterprise_table_with_restricted_view(data_fixture)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to(
        {
            "page": "restricted_view",
            "restricted_view_id": restricted_view.id,
        }
    )
    await comm_a.receive_json_from(timeout=1)  # page_add
    assert await comm_a.receive_nothing(timeout=0.5)

    pids = await _presence_ids_in_redis(f"presence:table-{table.id}")
    assert len(pids) == 0

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_independent_space_isolation_on_partial_unsubscribe(
    data_fixture, presence_types
):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()

    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a, test_param=1)

    comm_b, ws_b = await _connect(token_b)
    _, active_b = await _subscribe_and_get_members(comm_b, test_param=1)
    # Also subscribe to perm page with same param (different space)
    await _subscribe_and_get_members(
        comm_b, page="test_presence_perm_page", test_param=1
    )
    await _drain(comm_a)

    await comm_b.send_json_to({"remove_page": "test_presence_page", "test_param": 1})
    b_frames = await _drain(comm_b, timeout=0.5)
    assert any(f["type"] == "page_discard" for f in b_frames)

    a_frames = await _drain(comm_a, timeout=0.5)
    leaves = [f for f in a_frames if f["type"] == "presence.leave"]
    assert len(leaves) == 1

    # But the perm page (different space) should still have B's presence
    assert len(await _presence_ids_in_redis("presence:test-perm-space-1")) == 1
    assert len(await _presence_ids_in_redis("presence:test-space-1")) == 1  # only A

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_permission_revocation_no_presence_leave_for_restricted_view(
    data_fixture,
):
    """Restricted view has no presence, so permission revocation produces
    no presence.leave event on the table subscriber side."""

    (
        user_a,
        token_a,
        user_b,
        token_b,
        table,
        restricted_view,
    ) = await _create_enterprise_table_with_restricted_view(data_fixture)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await _drain(comm_a, timeout=0.5)

    comm_b, ws_b = await _connect(token_b)
    await comm_b.send_json_to(
        {
            "page": "restricted_view",
            "restricted_view_id": restricted_view.id,
        }
    )
    await _drain(comm_b, timeout=0.5)
    await _drain(comm_a, timeout=0.5)

    perm_group = f"permissions-restricted-view-{restricted_view.id}"
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        perm_group,
        {
            "type": "users_removed_from_permission_group",
            "user_ids_to_remove": [user_b.id],
            "permission_group_name": perm_group,
        },
    )

    b_frames = await _drain(comm_b, timeout=0.5)
    assert any(f["type"] == "page_discard" for f in b_frames)

    # No presence.leave on table side — restricted view had no presence
    a_frames = await _drain(comm_a, timeout=0.5)
    leaves = [f for f in a_frames if f["type"] == "presence.leave"]
    assert len(leaves) == 0

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_invalid_shape_entries_cleaned_from_redis():
    """Wrong-shape JSON entries are treated as corrupt and removed (R20)."""

    redis = await get_async_redis()
    space = PresenceSpace("g3")
    await redis.hset(space.redis_key, "valid", json.dumps({"user_id": 42}))
    await redis.hset(space.redis_key, "list", json.dumps([1, 2, 3]))
    await redis.hset(space.redis_key, "empty", json.dumps({}))
    await redis.hset(space.redis_key, "null-uid", json.dumps({"user_id": None}))
    await redis.hset(space.redis_key, "str-uid", json.dumps({"user_id": "abc"}))

    active = await space.get_members()
    assert len(active) == 1
    assert active[0]["user_id"] == 42
    assert active[0]["presence_id"] == "valid"

    assert await redis.hexists(space.redis_key, "valid") is True
    for bad_key in ("list", "empty", "null-uid", "str-uid"):
        assert await redis.hexists(space.redis_key, bad_key) is False


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_unsubscribe_failure_keeps_state_for_disconnect_retry(presence_types):
    handler, consumer = _make_mock_handler()
    params = {"test_param": 1}
    await handler.handle_page_subscribed("test_presence_page", params)
    assert await _presence_ids_in_redis(PRESENCE_KEY) == {handler.presence_id}
    consumer.send_json.reset_mock()
    consumer.channel_layer.group_discard.reset_mock()

    with patch.object(handler, "_leave", side_effect=Exception("redis down")):
        await handler.handle_page_unsubscribed("test_presence_page", params)

    # Failure keeps the maps and Redis entry intact and skips every later
    # side effect, so disconnect cleanup can retry the whole sequence.
    page_key = make_page_key("test_presence_page", params)
    assert handler._page_to_space == {page_key: SPACE_NAME}
    assert page_key in handler._space_pages[SPACE_NAME]
    assert handler.presence_id in await _presence_ids_in_redis(PRESENCE_KEY)
    consumer.send_json.assert_not_called()
    consumer.channel_layer.group_discard.assert_not_called()

    await handler.leave_all_spaces()

    assert handler._page_to_space == {}
    assert handler._space_pages == {}
    assert await _presence_ids_in_redis(PRESENCE_KEY) == set()
    consumer.channel_layer.group_discard.assert_awaited_once_with(
        f"presence.{SPACE_NAME}", "chan-test"
    )


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_unsubscribe_broadcast_failure_after_leave_still_commits_maps(
    presence_types,
):
    handler, consumer = _make_mock_handler()
    params = {"test_param": 1}
    await handler.handle_page_subscribed("test_presence_page", params)
    assert await _presence_ids_in_redis(PRESENCE_KEY) == {handler.presence_id}
    consumer.send_json.reset_mock()

    with patch.object(
        handler, "_broadcast_leave", side_effect=Exception("channel layer down")
    ):
        await handler.handle_page_unsubscribed("test_presence_page", params)

    # The Redis removal succeeded, so the maps must be committed even though a
    # later side effect failed; keeping them would make a re-subscribe
    # early-return on a page key with no Redis entry behind it.
    assert handler._page_to_space == {}
    assert handler._space_pages == {}
    assert await _presence_ids_in_redis(PRESENCE_KEY) == set()
    # The side effects after the failed broadcast still ran.
    space_discard_msg = consumer.send_json.await_args_list[0].args[0]
    assert space_discard_msg["type"] == "presence.space_discard"
    assert space_discard_msg["space"] == SPACE_NAME
    consumer.channel_layer.group_discard.assert_awaited_once_with(
        f"presence.{SPACE_NAME}", "chan-test"
    )

    consumer.send_json.reset_mock()
    await handler.handle_page_subscribed("test_presence_page", params)

    page_key = make_page_key("test_presence_page", params)
    assert handler._page_to_space == {page_key: SPACE_NAME}
    assert handler.presence_id in await _presence_ids_in_redis(PRESENCE_KEY)
    members_msg = consumer.send_json.await_args_list[0].args[0]
    assert members_msg["type"] == "presence.members"
    assert members_msg["space"] == SPACE_NAME

    await handler.leave_all_spaces()


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_subscribe_failure_rolls_back_state_so_resubscribe_works(
    presence_types,
):
    handler, consumer = _make_mock_handler()
    params = {"test_param": 1}
    consumer.send_json.side_effect = Exception("send failed")

    await handler.handle_page_subscribed("test_presence_page", params)

    assert handler._page_to_space == {}
    assert handler._space_pages == {}
    assert await _presence_ids_in_redis(PRESENCE_KEY) == set()
    consumer.channel_layer.group_discard.assert_awaited_once_with(
        f"presence.{SPACE_NAME}", "chan-test"
    )

    consumer.send_json = AsyncMock()
    await handler.handle_page_subscribed("test_presence_page", params)

    page_key = make_page_key("test_presence_page", params)
    assert handler._page_to_space == {page_key: SPACE_NAME}
    assert handler.presence_id in await _presence_ids_in_redis(PRESENCE_KEY)
    members_msg = consumer.send_json.await_args_list[0].args[0]
    assert members_msg["type"] == "presence.members"
    assert members_msg["space"] == SPACE_NAME


# --- Anonymous presence tests ---


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_anonymous_entry_valid_in_presence_space():
    from baserow.ws.presence import _is_valid_entry

    assert _is_valid_entry({"user_id": ANONYMOUS_USER_ID}) is True
    assert _is_valid_entry({"user_id": ANONYMOUS_USER_ID, "focus": None}) is True

    space = PresenceSpace("anon-test")
    pid = "anon-pid-1"
    await space.join(pid, ANONYMOUS_USER_ID)
    members = await space.get_members()
    assert len(members) == 1
    assert members[0]["user_id"] == ANONYMOUS_USER_ID
    assert members[0]["presence_id"] == pid

    await space.remove_entry(pid)
    assert await space.get_members() == []


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_multiple_anonymous_entries_coexist():
    space = PresenceSpace("anon-multi")
    await space.join("anon-1", ANONYMOUS_USER_ID)
    await space.join("anon-2", ANONYMOUS_USER_ID)
    await space.join("auth-1", 42)

    members = await space.get_members()
    assert len(members) == 3
    anon_members = [m for m in members if m["user_id"] == ANONYMOUS_USER_ID]
    assert len(anon_members) == 2
    assert {m["presence_id"] for m in anon_members} == {"anon-1", "anon-2"}


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_anonymous_handler_suppresses_members_snapshot(presence_types):
    handler, consumer = _make_mock_handler(user_id=ANONYMOUS_USER_ID)
    params = {"test_param": 1}
    await handler.handle_page_subscribed("test_presence_page", params)

    assert handler.presence_id in await _presence_ids_in_redis(PRESENCE_KEY)
    send_calls = consumer.send_json.await_args_list
    assert not any(
        call.args[0].get("type") == "presence.members" for call in send_calls
    )
    consumer.channel_layer.group_send.assert_awaited()

    await handler.leave_all_spaces()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_anonymous_join_broadcasts_to_authenticated_editor(data_fixture):
    user_a, token_a = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await comm_a.receive_json_from(timeout=1)  # page_add
    await comm_a.receive_json_from(timeout=1)  # presence.members

    comm_anon, ws_anon = await _connect_anonymous()
    await comm_anon.send_json_to({"page": "view", "slug": view.slug})
    page_add = await comm_anon.receive_json_from(timeout=1)
    assert page_add["type"] == "page_add"

    ea = await comm_anon.receive_json_from(timeout=1)
    assert ea["type"] == "presence.editors_active"
    assert ea["active"] is True
    assert await comm_anon.receive_nothing(timeout=0.5)

    join = await comm_a.receive_json_from(timeout=1)
    assert join["type"] == "presence.join"
    assert join["user_id"] == ANONYMOUS_USER_ID
    assert "presence_id" in join

    await comm_anon.disconnect()

    leave = await comm_a.receive_json_from(timeout=1)
    assert leave["type"] == "presence.leave"
    assert leave["user_id"] == ANONYMOUS_USER_ID

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_anonymous_receives_no_join_leave_broadcasts(data_fixture):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a, members=[user_b])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await comm_a.receive_json_from(timeout=1)  # page_add
    await comm_a.receive_json_from(timeout=1)  # presence.members

    comm_anon, ws_anon = await _connect_anonymous()
    await comm_anon.send_json_to({"page": "view", "slug": view.slug})
    await comm_anon.receive_json_from(timeout=1)  # page_add
    await _drain(comm_anon, timeout=0.5)  # consume editors_active

    comm_b, ws_b = await _connect(token_b)
    await comm_b.send_json_to({"page": "table", "table_id": table.id})
    await comm_b.receive_json_from(timeout=1)  # page_add
    await comm_b.receive_json_from(timeout=1)  # presence.members
    await _drain(comm_a, timeout=0.5)  # consume join on editor A

    anon_frames = await _drain(comm_anon, timeout=0.5)
    join_or_leave = [
        f for f in anon_frames if f.get("type") in ("presence.join", "presence.leave")
    ]
    assert join_or_leave == []

    await comm_b.disconnect()
    await _drain(comm_a, timeout=0.5)  # consume leave on editor A

    anon_frames = await _drain(comm_anon, timeout=0.5)
    join_or_leave = [
        f for f in anon_frames if f.get("type") in ("presence.join", "presence.leave")
    ]
    assert join_or_leave == []

    await comm_anon.disconnect()
    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_anonymous_receives_no_focus_broadcasts(data_fixture):
    user_a, token_a = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await comm_a.receive_json_from(timeout=1)  # page_add
    await comm_a.receive_json_from(timeout=1)  # presence.members

    comm_anon, ws_anon = await _connect_anonymous()
    await comm_anon.send_json_to({"page": "view", "slug": view.slug})
    await comm_anon.receive_json_from(timeout=1)  # page_add
    await _drain(comm_anon, timeout=0.5)  # consume editors_active
    await _drain(comm_a, timeout=0.5)  # consume join

    await comm_a.send_json_to(
        {
            "type": "presence.focus",
            "page": "table",
            "table_id": table.id,
            "focus": {"type": "cell", "row_id": 1, "field_id": 1, "editing": False},
        }
    )

    assert await comm_anon.receive_nothing(timeout=0.5)

    await comm_anon.disconnect()
    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_public_view_page_resolves_to_table_space(data_fixture):
    from baserow.ws.registries import page_registry

    user_a, token_a = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    view_page = page_registry.get("view")

    space_name = view_page.get_presence_space_name(slug=view.slug)
    assert space_name == f"table-{table.id}"

    assert view_page.get_presence_space_name(slug="non-existent") is None
    assert view_page.get_presence_space_name(slug=None) is None
    assert view_page.get_presence_space_name() is None


# --- editors_active signal tests ---


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_anonymous_receives_editors_active_on_editor_join(data_fixture):
    user_a, token_a = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_anon, ws_anon = await _connect_anonymous()
    await comm_anon.send_json_to({"page": "view", "slug": view.slug})
    await comm_anon.receive_json_from(timeout=1)  # page_add
    assert await comm_anon.receive_nothing(timeout=0.5)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await comm_a.receive_json_from(timeout=1)  # page_add
    await comm_a.receive_json_from(timeout=1)  # presence.members

    anon_frames = await _drain(comm_anon, timeout=0.5)
    editors_active_msgs = [
        f for f in anon_frames if f.get("type") == "presence.editors_active"
    ]
    assert len(editors_active_msgs) == 1
    assert editors_active_msgs[0]["active"] is True
    assert editors_active_msgs[0]["space"] == f"table-{table.id}"

    await comm_anon.disconnect()
    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_anonymous_receives_editors_active_false_on_last_editor_leave(
    data_fixture,
):
    user_a, token_a = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await comm_a.receive_json_from(timeout=1)  # page_add
    await comm_a.receive_json_from(timeout=1)  # presence.members

    comm_anon, ws_anon = await _connect_anonymous()
    await comm_anon.send_json_to({"page": "view", "slug": view.slug})
    await comm_anon.receive_json_from(timeout=1)  # page_add
    ea_init = await comm_anon.receive_json_from(timeout=1)
    assert ea_init["type"] == "presence.editors_active"
    assert ea_init["active"] is True
    await _drain(comm_a, timeout=0.5)  # consume anon join

    await comm_a.disconnect()

    anon_frames = await _drain(comm_anon, timeout=1)
    editors_active_msgs = [
        f for f in anon_frames if f.get("type") == "presence.editors_active"
    ]
    assert len(editors_active_msgs) == 1
    assert editors_active_msgs[0]["active"] is False

    await comm_anon.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_no_editors_active_signal_when_second_editor_joins(data_fixture):
    user_a, token_a = data_fixture.create_user_and_token()
    user_b, token_b = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a, members=[user_b])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await comm_a.receive_json_from(timeout=1)  # page_add
    await comm_a.receive_json_from(timeout=1)  # presence.members

    comm_anon, ws_anon = await _connect_anonymous()
    await comm_anon.send_json_to({"page": "view", "slug": view.slug})
    await comm_anon.receive_json_from(timeout=1)  # page_add
    await comm_anon.receive_json_from(timeout=1)  # editors_active: true (initial)
    await _drain(comm_a, timeout=0.5)  # consume anon join

    comm_b, ws_b = await _connect(token_b)
    await comm_b.send_json_to({"page": "table", "table_id": table.id})
    await comm_b.receive_json_from(timeout=1)  # page_add
    await comm_b.receive_json_from(timeout=1)  # presence.members

    anon_frames = await _drain(comm_anon, timeout=0.5)
    editors_active_msgs = [
        f for f in anon_frames if f.get("type") == "presence.editors_active"
    ]
    assert len(editors_active_msgs) == 0

    await comm_anon.disconnect()
    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_anonymous_focus_emission_blocked_server_side(data_fixture):
    """Anonymous connections cannot emit focus even if a custom client tries."""
    user_a, token_a = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "table", "table_id": table.id})
    await comm_a.receive_json_from(timeout=1)  # page_add
    await comm_a.receive_json_from(timeout=1)  # presence.members

    comm_anon, ws_anon = await _connect_anonymous()
    await comm_anon.send_json_to({"page": "view", "slug": view.slug})
    await comm_anon.receive_json_from(timeout=1)  # page_add
    await _drain(comm_anon, timeout=0.5)  # consume editors_active
    await _drain(comm_a, timeout=0.5)  # consume join

    await comm_anon.send_json_to(
        {
            "type": "presence.focus",
            "page": "view",
            "slug": view.slug,
            "focus": {"type": "cell", "row_id": 1, "field_id": 1, "editing": False},
        }
    )

    assert await comm_a.receive_nothing(timeout=0.5)

    await comm_anon.disconnect()
    await comm_a.disconnect()
