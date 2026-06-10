import json
import uuid
from unittest.mock import Mock

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django_redis import get_redis_connection

from baserow.config.asgi import application
from baserow.ws.presence import (
    PresenceHandler,
    PresenceSpace,
)
from baserow.ws.registries import PageType, page_registry

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


GROUP = "test-presence-page-1"
SPACE_NAME = "test-space-1"
PRESENCE_KEY = f"presence:{SPACE_NAME}"


class PresenceTestPageType(PageType):
    type = "test_presence_page"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-presence-page-{test_param}"

    def get_presence_space_name(self, test_param, **kwargs):
        return f"test-space-{test_param}"

    def filter_focus_for_recipient(self, page_parameters, focus, focus_type):
        return True


class NonPresencePageType(PageType):
    type = "test_non_presence_page"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-non-presence-page-{test_param}"


class PresenceWithPermGroupPageType(PageType):
    type = "test_presence_perm_page"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-presence-perm-page-{test_param}"

    def get_permission_channel_group_name(self, test_param, **kwargs):
        return f"test-perm-group-{test_param}"

    def get_presence_space_name(self, test_param, **kwargs):
        return f"test-perm-space-{test_param}"

    def filter_focus_for_recipient(self, page_parameters, focus, focus_type):
        return True


@pytest.fixture
def presence_types():
    page_registry.register(PresenceTestPageType())
    page_registry.register(NonPresencePageType())
    page_registry.register(PresenceWithPermGroupPageType())
    yield
    page_registry.unregister(PresenceTestPageType.type)
    page_registry.unregister(NonPresencePageType.type)
    page_registry.unregister(PresenceWithPermGroupPageType.type)


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


def _presence_ids_in_redis(redis_key):
    """Return set of presence_id keys stored in a Redis presence hash."""
    redis = get_redis_connection("default")
    return {(k.decode() if isinstance(k, bytes) else k) for k in redis.hkeys(redis_key)}


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

    pids = _presence_ids_in_redis(PRESENCE_KEY)
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

    pids = _presence_ids_in_redis(PRESENCE_KEY)
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

    pids_1 = _presence_ids_in_redis("presence:test-space-1")
    pids_2 = _presence_ids_in_redis("presence:test-space-2")
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

    assert len(_presence_ids_in_redis("presence:test-space-1")) == 1  # only B
    assert len(_presence_ids_in_redis("presence:test-space-2")) == 0

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

    pids = _presence_ids_in_redis(PRESENCE_KEY)
    assert pid_1 in pids
    assert pid_2 in pids
    assert pid_1 != pid_2

    await comm_1.disconnect()
    await comm_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_corrupt_entry_cleaned_on_new_subscribe(data_fixture, presence_types):
    redis = get_redis_connection("default")
    redis.hset(PRESENCE_KEY, "corrupt-pid", "not-json")

    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)
    _, members_resp = await _subscribe_and_get_members(comm_a)

    assert members_resp["entries"] == []
    assert not redis.hexists(PRESENCE_KEY, "corrupt-pid")
    assert len(_presence_ids_in_redis(PRESENCE_KEY)) == 1

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
async def test_redis_key_has_no_ttl(data_fixture, presence_types):
    user_a, token_a = data_fixture.create_user_and_token()
    comm_a, ws_a = await _connect(token_a)
    await _subscribe_and_get_members(comm_a)

    redis = get_redis_connection("default")
    ttl = redis.ttl(PRESENCE_KEY)
    assert ttl == -1

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
    redis = get_redis_connection("default")
    space = PresenceSpace("g2")
    redis.hset(
        space.redis_key,
        "valid",
        json.dumps({"user_id": 1}),
    )
    redis.hset(space.redis_key, "corrupt", "not-json")

    active = await space.get_members()
    assert len(active) == 1
    assert active[0]["user_id"] == 1
    assert active[0]["presence_id"] == "valid"
    assert redis.hexists(space.redis_key, "valid") is True
    assert redis.hexists(space.redis_key, "corrupt") is False


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

    redis = get_redis_connection("default")
    pres_key = "presence:test-perm-space-1"
    pids_before = _presence_ids_in_redis(pres_key)
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

    pids_after = _presence_ids_in_redis(pres_key)
    assert pid_b not in pids_after
    assert pid_a in pids_after

    await comm_a.disconnect()
    await comm_b.disconnect()


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


# ---------------------------------------------------------------------------
# Integration tests with real page types
# ---------------------------------------------------------------------------


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
async def test_restricted_view_joins_table_presence_space(data_fixture):
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
            "table_id": table.id,
        }
    )
    page_add_b = await comm_b.receive_json_from(timeout=1)
    assert page_add_b["type"] == "page_add"
    active_b = await comm_b.receive_json_from(timeout=1)
    assert active_b["type"] == "presence.members"
    assert active_b["space"] == f"table-{table.id}"
    assert len(active_b["entries"]) == 1
    assert active_b["entries"][0]["user_id"] == user_a.id

    join = await comm_a.receive_json_from(timeout=1)
    assert join["type"] == "presence.join"
    assert join["user_id"] == user_b.id

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_restricted_view_disconnect_broadcasts_leave_to_table_subscribers(
    data_fixture,
):
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
            "table_id": table.id,
        }
    )
    await _drain(comm_b, timeout=0.5)
    await _drain(comm_a, timeout=0.5)  # consume B's join

    await comm_b.disconnect()

    frames = await _drain(comm_a, timeout=0.5)
    leaves = [f for f in frames if f["type"] == "presence.leave"]
    assert len(leaves) == 1
    assert leaves[0]["user_id"] == user_b.id

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_public_view_has_no_presence(data_fixture):
    user_a, token_a = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user_a)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, public=True)

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to({"page": "view", "slug": view.slug})
    page_add = await comm_a.receive_json_from(timeout=1)
    assert page_add["type"] == "page_add"
    assert await comm_a.receive_nothing(timeout=0.5)

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_restricted_view_rejects_spoofed_table_id(data_fixture):
    (
        user_a,
        token_a,
        user_b,
        token_b,
        table,
        restricted_view,
    ) = await _create_enterprise_table_with_restricted_view(data_fixture)

    other_table = await database_sync_to_async(
        lambda: data_fixture.create_database_table(
            database=table.database,
        )
    )()

    comm_a, ws_a = await _connect(token_a)
    await comm_a.send_json_to(
        {
            "page": "restricted_view",
            "restricted_view_id": restricted_view.id,
            "table_id": other_table.id,
        }
    )
    # Spoofed table_id — subscription should be silently rejected (no page_add)
    assert await comm_a.receive_nothing(timeout=0.5)

    # Verify no presence entry was created for the spoofed table
    pids = _presence_ids_in_redis(f"presence:table-{other_table.id}")
    assert len(pids) == 0

    await comm_a.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_independent_space_isolation_on_partial_unsubscribe(
    data_fixture, presence_types
):
    """Removing one page leaves its space; other spaces remain unaffected."""
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
    assert len(_presence_ids_in_redis("presence:test-perm-space-1")) == 1
    assert len(_presence_ids_in_redis("presence:test-space-1")) == 1  # only A

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_permission_revocation_triggers_presence_leave_for_restricted_view(
    data_fixture,
):
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
            "table_id": table.id,
        }
    )
    await _drain(comm_b, timeout=0.5)
    await _drain(comm_a, timeout=0.5)  # consume B's join

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

    a_frames = await _drain(comm_a, timeout=0.5)
    leaves = [f for f in a_frames if f["type"] == "presence.leave"]
    assert len(leaves) == 1
    assert leaves[0]["user_id"] == user_b.id

    pres_key = f"presence:table-{table.id}"
    pids = _presence_ids_in_redis(pres_key)
    assert len(pids) == 1  # only A remains

    await comm_a.disconnect()
    await comm_b.disconnect()
