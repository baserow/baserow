from django.conf import settings

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.ws.models import RealtimeEvent
from baserow.ws.realtime_updates import (
    check_realtime_events,
    cleanup_old_realtime_events,
    get_channel_group_names,
    get_replay_events,
    record_realtime_event,
    record_realtime_events_bulk,
)
from baserow.ws.tasks import (
    broadcast_to_channel_group,
    broadcast_to_users,
    broadcast_to_users_individual_payloads,
)


@pytest.mark.django_db
@pytest.mark.websockets
def test_record_creates_row_with_correct_fields():
    payload = {"type": "broadcast_to_group", "payload": {"foo": 1}}
    event_id = record_realtime_event("table-42", payload)

    row = RealtimeEvent.objects.get(id=event_id)
    assert row.channel_group == "table-42"
    assert row.payload == payload


@pytest.mark.django_db
@pytest.mark.websockets
def test_record_returns_monotonically_increasing_ids():
    a = record_realtime_event("g1", {"type": "x"})
    b = record_realtime_event("g1", {"type": "x"})
    c = record_realtime_event("g2", {"type": "x"})
    assert a < b < c


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_baseline_returns_all_false():
    record_realtime_event("table-1", {"type": "broadcast_to_group", "payload": {}})
    updates, latest = check_realtime_events(
        user_id=1,
        channel_group_names=[("table-1", "table"), ("users", "users")],
        last_seen_id=None,
        previous_web_socket_id=None,
    )
    assert updates == {"table": False, "users": False}
    assert latest > 0


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_no_events_returns_zero_latest():
    updates, latest = check_realtime_events(
        user_id=1,
        channel_group_names=[("table-99", "table"), ("users", "users")],
        last_seen_id=None,
        previous_web_socket_id=None,
    )
    assert updates == {"table": False, "users": False}
    assert latest == 0


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_detects_stale_page_group():
    base_id = record_realtime_event(
        "table-5",
        {
            "type": "broadcast_to_group",
            "payload": {"table_id": 5},
            "ignore_web_socket_id": None,
        },
    )
    record_realtime_event(
        "table-5",
        {
            "type": "broadcast_to_group",
            "payload": {"table_id": 5},
            "ignore_web_socket_id": "ws-other",
        },
    )

    updates, _ = check_realtime_events(
        user_id=1,
        channel_group_names=[("table-5", "table"), ("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id="ws-me",
    )
    assert updates["table"] is True
    assert updates["users"] is False


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_excludes_originator():
    base_id = record_realtime_event(
        "table-6", {"type": "x", "ignore_web_socket_id": None}
    )
    record_realtime_event(
        "table-6",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": "ws-me"},
    )

    updates, _ = check_realtime_events(
        user_id=1,
        channel_group_names=[("table-6", "table")],
        last_seen_id=base_id,
        previous_web_socket_id="ws-me",
    )
    assert updates["table"] is False


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_null_originator_counts_as_someone_else():
    base_id = record_realtime_event(
        "table-7", {"type": "x", "ignore_web_socket_id": "ws-me"}
    )
    record_realtime_event(
        "table-7",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    updates, _ = check_realtime_events(
        user_id=1,
        channel_group_names=[("table-7", "table")],
        last_seen_id=base_id,
        previous_web_socket_id="ws-me",
    )
    assert updates["table"] is True


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_users_group_filters_by_user_id():
    base_id = record_realtime_event(
        "users", {"type": "x", "ignore_web_socket_id": None}
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [42],
            "send_to_all_users": False,
            "payload": {"type": "user_data_updated"},
            "ignore_web_socket_id": None,
        },
    )

    updates_target, _ = check_realtime_events(
        user_id=42,
        channel_group_names=[("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert updates_target["users"] is True

    updates_other, _ = check_realtime_events(
        user_id=999,
        channel_group_names=[("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert updates_other["users"] is False


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_users_group_send_to_all_users():
    base_id = record_realtime_event(
        "users", {"type": "x", "ignore_web_socket_id": None}
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [],
            "send_to_all_users": True,
            "payload": {"type": "something"},
            "ignore_web_socket_id": None,
        },
    )

    updates, _ = check_realtime_events(
        user_id=999,
        channel_group_names=[("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert updates["users"] is True


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_users_group_individual_payloads():
    base_id = record_realtime_event(
        "users", {"type": "x", "ignore_web_socket_id": None}
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"7": {"type": "app_created"}},
            "ignore_web_socket_id": None,
        },
    )

    updates_target, _ = check_realtime_events(
        user_id=7,
        channel_group_names=[("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert updates_target["users"] is True

    updates_other, _ = check_realtime_events(
        user_id=8,
        channel_group_names=[("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert updates_other["users"] is False


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_merges_categories():
    base_id = record_realtime_event("x", {"type": "x", "ignore_web_socket_id": None})
    record_realtime_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    updates, _ = check_realtime_events(
        user_id=1,
        channel_group_names=[("table-1", "table"), ("table-2", "table")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert "table" in updates
    assert updates["table"] is True


class FakePageScope:
    def __init__(self, page_type, page_parameters):
        self.page_type = page_type
        self.page_parameters = page_parameters


class FakeSubscribedPages:
    def __init__(self, pages):
        self.pages = pages


@pytest.mark.django_db
@pytest.mark.websockets
def test_get_channel_group_names_includes_users_for_authenticated():
    pages = FakeSubscribedPages(
        [
            FakePageScope("table", {"table_id": 42}),
        ]
    )
    result = get_channel_group_names(pages, authenticated=True)
    assert ("table-42", "table") in result
    assert ("users", "users") in result


@pytest.mark.django_db
@pytest.mark.websockets
def test_get_channel_group_names_excludes_users_for_unauthenticated():
    pages = FakeSubscribedPages(
        [
            FakePageScope("table", {"table_id": 42}),
        ]
    )
    result = get_channel_group_names(pages, authenticated=False)
    assert ("table-42", "table") in result
    assert ("users", "users") not in result


@pytest.mark.django_db
@pytest.mark.websockets
def test_get_channel_group_names_skips_unknown_page_types():
    pages = FakeSubscribedPages(
        [
            FakePageScope("nonexistent_type", {}),
        ]
    )
    result = get_channel_group_names(pages, authenticated=False)
    assert result == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_returns_events_in_id_order():
    base_id = record_realtime_event("x", {"type": "x"})
    record_realtime_event(
        "table-1",
        {
            "type": "broadcast_to_group",
            "payload": {"a": 1},
            "ignore_web_socket_id": None,
        },
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "user_updated"},
            "ignore_web_socket_id": None,
        },
    )

    events = get_replay_events(
        user_id=1,
        channel_group_names=[("table-1", "table"), ("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert events is not None
    assert len(events) == 2
    assert events[0].id < events[1].id


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_returns_none_when_over_threshold():
    base_id = record_realtime_event("x", {"type": "x"})
    for i in range(settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 1):
        record_realtime_event(
            "table-1",
            {
                "type": "broadcast_to_group",
                "payload": {"i": i},
                "ignore_web_socket_id": None,
            },
        )

    result = get_replay_events(
        user_id=1,
        channel_group_names=[("table-1", "table")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert result is None


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_returns_none_when_last_seen_id_not_in_table():
    record_realtime_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    result = get_replay_events(
        user_id=1,
        channel_group_names=[("table-1", "table")],
        last_seen_id=999999,
        previous_web_socket_id=None,
    )
    assert result is None


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_excludes_previous_web_socket_id():
    base_id = record_realtime_event("x", {"type": "x"})
    record_realtime_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": "ws-me"},
    )
    record_realtime_event(
        "table-1",
        {
            "type": "broadcast_to_group",
            "payload": {},
            "ignore_web_socket_id": "ws-other",
        },
    )

    events = get_replay_events(
        user_id=1,
        channel_group_names=[("table-1", "table")],
        last_seen_id=base_id,
        previous_web_socket_id="ws-me",
    )
    assert events is not None
    assert len(events) == 1
    assert events[0].payload["ignore_web_socket_id"] == "ws-other"


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_returns_empty_list_when_no_new_events():
    base_id = record_realtime_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    events = get_replay_events(
        user_id=1,
        channel_group_names=[("table-1", "table")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert events is not None
    assert len(events) == 0


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_includes_events_from_all_subscribed_groups():
    base_id = record_realtime_event("x", {"type": "x"})
    record_realtime_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )
    record_realtime_event(
        "dashboard-2",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )
    record_realtime_event(
        "table-99",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    events = get_replay_events(
        user_id=1,
        channel_group_names=[("table-1", "table"), ("dashboard-2", "dashboard")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert events is not None
    assert len(events) == 2
    groups = {e.channel_group for e in events}
    assert groups == {"table-1", "dashboard-2"}


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_filters_users_group_by_user_id():
    base_id = record_realtime_event("x", {"type": "x"})
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "user_updated"},
            "ignore_web_socket_id": None,
        },
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [2, 3],
            "send_to_all_users": False,
            "payload": {"type": "user_updated"},
            "ignore_web_socket_id": None,
        },
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1, 5],
            "send_to_all_users": True,
            "payload": {"type": "global_notification"},
            "ignore_web_socket_id": None,
        },
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"2": {"data": "for-user-2"}},
            "ignore_web_socket_id": None,
        },
    )

    events = get_replay_events(
        user_id=1,
        channel_group_names=[("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert events is not None
    assert len(events) == 2
    types = [e.payload["type"] for e in events]
    assert "broadcast_to_users" in types


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_users_does_not_inflate_count():
    base_id = record_realtime_event("x", {"type": "x"})
    for i in range(settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 1):
        record_realtime_event(
            "users",
            {
                "type": "broadcast_to_users",
                "user_ids": [999],
                "send_to_all_users": False,
                "payload": {"i": i},
                "ignore_web_socket_id": None,
            },
        )
    record_realtime_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    events = get_replay_events(
        user_id=1,
        channel_group_names=[("table-1", "table"), ("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert events is not None
    assert len(events) == 1
    assert events[0].channel_group == "table-1"


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_includes_individual_payloads_for_matching_user():
    base_id = record_realtime_event("x", {"type": "x"})
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"1": {"data": "for-user-1"}, "2": {"data": "for-user-2"}},
            "ignore_web_socket_id": None,
        },
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"3": {"data": "for-user-3"}},
            "ignore_web_socket_id": None,
        },
    )

    events = get_replay_events(
        user_id=1,
        channel_group_names=[("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id=None,
    )
    assert events is not None
    assert len(events) == 1
    assert "1" in events[0].payload["payload_map"]


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_excludes_previous_web_socket_id_on_users_group():
    base_id = record_realtime_event("x", {"type": "x"})
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "should_skip"},
            "ignore_web_socket_id": "ws-me",
        },
    )
    record_realtime_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "should_include"},
            "ignore_web_socket_id": "ws-other",
        },
    )

    events = get_replay_events(
        user_id=1,
        channel_group_names=[("users", "users")],
        last_seen_id=base_id,
        previous_web_socket_id="ws-me",
    )
    assert events is not None
    assert len(events) == 1
    assert events[0].payload["payload"]["type"] == "should_include"


@pytest.mark.django_db
@pytest.mark.websockets
def test_record_realtime_events_bulk():
    events_data = [
        ("table-1", {"type": "broadcast_to_group", "payload": {"i": 0}}),
        ("table-2", {"type": "broadcast_to_group", "payload": {"i": 1}}),
        ("users", {"type": "broadcast_to_users", "user_ids": [1]}),
    ]
    ids = record_realtime_events_bulk(events_data)
    assert len(ids) == 3
    assert ids[0] < ids[1] < ids[2]

    stored = list(RealtimeEvent.objects.filter(id__in=ids).order_by("id"))
    assert len(stored) == 3
    assert stored[0].channel_group == "table-1"
    assert stored[2].channel_group == "users"


@pytest.mark.django_db
@pytest.mark.websockets
def test_cleanup_deletes_old_rows():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ws_realtime_events "
            "(channel_group, payload, created_at) "
            "VALUES (%s, %s, now() - interval '48 hours') RETURNING id",
            ["table-1", '{"type": "x"}'],
        )
        old_id = cursor.fetchone()[0]

    new_id = record_realtime_event("table-1", {"type": "x"})

    deleted = cleanup_old_realtime_events(retention_hours=24)
    assert deleted >= 1

    remaining = set(RealtimeEvent.objects.values_list("id", flat=True))
    assert old_id not in remaining
    assert new_id in remaining


@pytest.mark.django_db
@pytest.mark.websockets
def test_cleanup_zero_retention_does_nothing():
    record_realtime_event("g", {"type": "x"})
    deleted = cleanup_old_realtime_events(retention_hours=0)
    assert deleted == 0
    assert RealtimeEvent.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.websockets
def test_broadcast_to_channel_group_records_event():
    payload = {"type": "rows_created", "table_id": 5}
    broadcast_to_channel_group("table-5", payload)

    assert "realtime_update_id" in payload
    event = RealtimeEvent.objects.get(id=payload["realtime_update_id"])
    assert event.channel_group == "table-5"
    assert event.payload["type"] == "broadcast_to_group"


@pytest.mark.django_db
@pytest.mark.websockets
def test_broadcast_to_users_records_event():
    payload = {"type": "user_data_updated"}
    broadcast_to_users([1, 2], payload)

    assert "realtime_update_id" in payload
    event = RealtimeEvent.objects.get(id=payload["realtime_update_id"])
    assert event.channel_group == "users"
    assert event.payload["type"] == "broadcast_to_users"
    assert event.payload["user_ids"] == [1, 2]


@pytest.mark.django_db
@pytest.mark.websockets
def test_broadcast_to_users_individual_payloads_records_event():
    payload_map = {
        "1": {"type": "app_created", "workspace_id": 10},
        "2": {"type": "app_created", "workspace_id": 10},
    }
    broadcast_to_users_individual_payloads(payload_map)

    id_1 = payload_map["1"]["realtime_update_id"]
    id_2 = payload_map["2"]["realtime_update_id"]
    assert id_1 == id_2

    event = RealtimeEvent.objects.get(id=id_1)
    assert event.channel_group == "users"
    assert event.payload["type"] == "broadcast_to_users_individual_payloads"


@pytest.mark.django_db
@pytest.mark.websockets
def test_broadcast_to_users_without_workspace_id_still_records():
    payload = {"type": "user_data_updated"}
    broadcast_to_users([1], payload)

    assert "realtime_update_id" in payload
    assert RealtimeEvent.objects.filter(channel_group="users").exists()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_baseline_returns_all_false_updates(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": 1,
            "last_seen_id": None,
            "previous_web_socket_id": None,
        }
    )
    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "realtime_subscribe_result"
    assert all(v is False for v in response["updates"].values())

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_replays_user_event(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    base_id = await sync_to_async(record_realtime_event)(
        "users",
        {"type": "x", "ignore_web_socket_id": None},
    )
    await sync_to_async(record_realtime_event)(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user.id],
            "send_to_all_users": False,
            "payload": {"type": "user_data_updated"},
            "ignore_web_socket_id": "ws-other",
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": 1,
            "last_seen_id": base_id,
            "previous_web_socket_id": "ws-me",
        }
    )

    replayed = await communicator.receive_json_from(timeout=1)
    assert replayed["type"] == "user_data_updated"

    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "realtime_subscribe_result"
    assert all(v is False for v in response["updates"].values())
    assert response["current_latest_id"] > base_id

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_falls_back_to_staleness_when_too_many_events(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    base_id = await sync_to_async(record_realtime_event)(
        "users",
        {"type": "x", "ignore_web_socket_id": None},
    )
    for _ in range(settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 1):
        await sync_to_async(record_realtime_event)(
            "users",
            {
                "type": "broadcast_to_users",
                "user_ids": [user.id],
                "send_to_all_users": False,
                "payload": {"type": "user_data_updated"},
                "ignore_web_socket_id": "ws-other",
            },
        )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": 1,
            "last_seen_id": base_id,
            "previous_web_socket_id": "ws-me",
        }
    )
    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "realtime_subscribe_result"
    assert response["updates"]["users"] is True

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_excludes_own_session(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    base_id = await sync_to_async(record_realtime_event)(
        "users",
        {"type": "x", "ignore_web_socket_id": None},
    )
    await sync_to_async(record_realtime_event)(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user.id],
            "send_to_all_users": False,
            "payload": {"type": "something"},
            "ignore_web_socket_id": "my-old-ws",
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": 1,
            "last_seen_id": base_id,
            "previous_web_socket_id": "my-old-ws",
        }
    )
    response = await communicator.receive_json_from(timeout=1)
    assert response["updates"]["users"] is False

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_replays_page_group_event(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    workspace = await sync_to_async(data_fixture.create_workspace)(user=user)
    database = await sync_to_async(data_fixture.create_database_application)(
        workspace=workspace
    )
    table = await sync_to_async(data_fixture.create_database_table)(database=database)

    base_id = await sync_to_async(record_realtime_event)(
        f"table-{table.id}",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )
    await sync_to_async(record_realtime_event)(
        f"table-{table.id}",
        {
            "type": "broadcast_to_group",
            "payload": {"type": "rows_created", "table_id": table.id},
            "ignore_web_socket_id": "ws-other",
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to({"page": "table", "table_id": table.id})
    page_response = await communicator.receive_json_from(timeout=1)
    assert page_response["type"] == "page_add"

    await communicator.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": workspace.id,
            "last_seen_id": base_id,
            "previous_web_socket_id": "ws-me",
        }
    )

    replayed = await communicator.receive_json_from(timeout=1)
    assert replayed["type"] == "rows_created"
    assert replayed["table_id"] == table.id
    assert "realtime_update_id" in replayed

    result = await communicator.receive_json_from(timeout=1)
    assert result["type"] == "realtime_subscribe_result"
    assert all(v is False for v in result["updates"].values())
    assert result["current_latest_id"] > base_id

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_replays_individual_payloads_event(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    base_id = await sync_to_async(record_realtime_event)(
        "users",
        {"type": "x", "ignore_web_socket_id": None},
    )
    await sync_to_async(record_realtime_event)(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {
                str(user.id): {"type": "app_created", "name": "Test"},
            },
            "ignore_web_socket_id": "ws-other",
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": 1,
            "last_seen_id": base_id,
            "previous_web_socket_id": "ws-me",
        }
    )

    replayed = await communicator.receive_json_from(timeout=1)
    assert replayed["type"] == "app_created"
    assert replayed["name"] == "Test"
    assert "realtime_update_id" in replayed

    result = await communicator.receive_json_from(timeout=1)
    assert result["type"] == "realtime_subscribe_result"
    assert all(v is False for v in result["updates"].values())

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_degrades_when_last_seen_expired(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    await sync_to_async(record_realtime_event)(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user.id],
            "send_to_all_users": False,
            "payload": {"type": "user_data_updated"},
            "ignore_web_socket_id": "ws-other",
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    # last_seen_id=1 does not exist — retention cleaned it (simulated by
    # never having created id=1). Replay should degrade to staleness.
    await communicator.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": 1,
            "last_seen_id": 1,
            "previous_web_socket_id": "ws-me",
        }
    )

    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "realtime_subscribe_result"
    assert response["updates"]["users"] is True

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_subscribe_replays_table_events_only_when_subscribed(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    workspace = await sync_to_async(data_fixture.create_workspace)(user=user)
    database = await sync_to_async(data_fixture.create_database_application)(
        workspace=workspace
    )
    table = await sync_to_async(data_fixture.create_database_table)(database=database)

    base_id = await sync_to_async(record_realtime_event)(
        f"table-{table.id}",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )
    await sync_to_async(record_realtime_event)(
        f"table-{table.id}",
        {
            "type": "broadcast_to_group",
            "payload": {"type": "rows_created", "table_id": table.id},
            "ignore_web_socket_id": "ws-other",
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    # Do NOT subscribe to the table page — replay should not include table events.
    await communicator.send_json_to(
        {
            "type": "realtime_subscribe",
            "workspace_id": workspace.id,
            "last_seen_id": base_id,
            "previous_web_socket_id": "ws-me",
        }
    )

    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "realtime_subscribe_result"
    assert "table" not in response["updates"]

    await communicator.disconnect()
