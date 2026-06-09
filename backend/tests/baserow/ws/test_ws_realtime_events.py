from datetime import timedelta

from django.conf import settings
from django.test import override_settings

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.ws.models import RealtimeEvent
from baserow.ws.realtime_events import (
    FIRST_CONNECT_CURSOR,
    NO_REPLAY_AVAILABLE,
    RealtimeEventHandler,
)
from baserow.ws.tasks import (
    broadcast_to_channel_group,
    broadcast_to_users,
    broadcast_to_users_individual_payloads,
)


def _record_event(channel_group: str, payload: dict) -> int:
    """Test helper: record single event via handler, return its ID."""
    return RealtimeEventHandler.record_events([(channel_group, payload)])[0]


def _record_group_broadcast(
    channel_group: str,
    payload: dict | None = None,
    web_socket_id: str | None = None,
    exclude_user_ids: list[int] | None = None,
) -> int:
    event_payload = {
        "type": "broadcast_to_group",
        "payload": payload or {},
        "ignore_web_socket_id": web_socket_id,
    }
    if exclude_user_ids is not None:
        event_payload["exclude_user_ids"] = exclude_user_ids
    return _record_event(channel_group, event_payload)


def _record_user_broadcast(
    user_id: int,
    payload: dict | None = None,
    web_socket_id: str | None = None,
    send_to_all_users: bool = False,
) -> int:
    return _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user_id],
            "send_to_all_users": send_to_all_users,
            "payload": payload or {},
            "ignore_web_socket_id": web_socket_id,
        },
    )


def _replay_events_result(
    user_id: int,
    page_group_names: list[str],
    last_seen_id: int,
    web_socket_id: str | None = None,
):
    return RealtimeEventHandler.get_replay_events_result(
        user_id,
        page_group_names,
        last_seen_id,
        web_socket_id,
    )


def _users_channel_event_matrix(user_id: int) -> list[tuple[dict, bool]]:
    """Return (event, expected_delivery) pairs covering every users-channel
    payload shape. Used by both the live-delivery and replay-filter parity
    test to keep ``should_deliver_users_channel_event`` and
    ``get_users_channel_live_delivery_filter`` from drifting apart."""

    other_user_id = user_id + 1
    return [
        # broadcast_to_users targeting the user
        (
            {
                "type": "broadcast_to_users",
                "user_ids": [user_id],
                "send_to_all_users": False,
                "payload": {"x": 1},
            },
            True,
        ),
        # broadcast_to_users targeting somebody else
        (
            {
                "type": "broadcast_to_users",
                "user_ids": [other_user_id],
                "send_to_all_users": False,
                "payload": {"x": 1},
            },
            False,
        ),
        # broadcast_to_users with send_to_all_users
        (
            {
                "type": "broadcast_to_users",
                "user_ids": [],
                "send_to_all_users": True,
                "payload": {"x": 1},
            },
            True,
        ),
        # broadcast_to_users_individual_payloads with our user_id in the map
        (
            {
                "type": "broadcast_to_users_individual_payloads",
                "payload_map": {str(user_id): {"y": 1}},
            },
            True,
        ),
        # broadcast_to_users_individual_payloads without our user_id
        (
            {
                "type": "broadcast_to_users_individual_payloads",
                "payload_map": {str(other_user_id): {"y": 1}},
            },
            False,
        ),
    ]


@pytest.mark.django_db
@pytest.mark.websockets
def test_users_channel_live_and_replay_filters_agree():
    """Enforce the invariant the realtime_events docstring claims: the live
    delivery decision (``should_deliver_users_channel_event``) and the replay
    decision (``get_users_channel_live_delivery_filter``) must target the
    same set of users-channel events. Drift between them would silently make
    a reconnect either miss events the live client received or replay events
    the live client never saw."""

    user_id = 42
    matrix = _users_channel_event_matrix(user_id)

    expected_event_ids: list[int] = []
    for event, expected_delivery in matrix:
        event_id = _record_event("users", event)
        # Live delivery decision
        assert (
            RealtimeEventHandler.should_deliver_users_channel_event(user_id, event)
            is expected_delivery
        ), f"live delivery mismatch for event: {event}"
        if expected_delivery:
            expected_event_ids.append(event_id)

    # Replay decision via the DB filter
    replay_filter = RealtimeEventHandler.get_users_channel_live_delivery_filter(user_id)
    actual_event_ids = sorted(
        RealtimeEvent.objects.filter(replay_filter).values_list("id", flat=True)
    )
    assert actual_event_ids == sorted(expected_event_ids)


@pytest.mark.django_db
@pytest.mark.websockets
def test_record_creates_row_with_correct_fields():
    payload = {"type": "broadcast_to_group", "payload": {"foo": 1}}
    event_id = _record_event("table-42", payload)

    row = RealtimeEvent.objects.get(id=event_id)
    assert row.channel_group == "table-42"
    assert row.payload == payload


@pytest.mark.django_db
@pytest.mark.websockets
def test_record_returns_monotonically_increasing_ids():
    a = _record_event("g1", {"type": "x"})
    b = _record_event("g1", {"type": "x"})
    c = _record_event("g2", {"type": "x"})
    assert a < b < c


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_baseline_returns_no_refresh_needed():
    _record_event("table-1", {"type": "broadcast_to_group", "payload": {}})
    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=FIRST_CONNECT_CURSOR,
        web_socket_id=None,
    )
    assert result.force_refresh is False
    assert result.latest_event_id > 0
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_no_events_returns_zero_latest():
    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-99"],
        last_seen_id=FIRST_CONNECT_CURSOR,
        web_socket_id=None,
    )
    assert result.force_refresh is False
    assert result.latest_event_id == NO_REPLAY_AVAILABLE
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_reconnect_without_high_water_mark_forces_refresh():
    # Client reconnects with NO_REPLAY_AVAILABLE (e.g. previous session had
    # replay disabled). The server cannot prove what was missed.
    _record_event("table-1", {"type": "broadcast_to_group", "payload": {}})
    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=NO_REPLAY_AVAILABLE,
        web_socket_id=None,
    )
    assert result.force_refresh is True
    assert result.latest_event_id == NO_REPLAY_AVAILABLE
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_detects_missed_events_in_page_group():
    base_id = _record_event(
        "table-5",
        {
            "type": "broadcast_to_group",
            "payload": {"table_id": 5},
            "ignore_web_socket_id": None,
        },
    )
    _record_event(
        "table-5",
        {
            "type": "broadcast_to_group",
            "payload": {"table_id": 5},
            "ignore_web_socket_id": "ws-other",
        },
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-5"],
        last_seen_id=base_id,
        web_socket_id="ws-me",
    )
    assert result.force_refresh is False
    assert len(result.replay_events) == 1


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_excludes_originator():
    base_id = _record_group_broadcast("table-6")
    _record_event(
        "table-6",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": "ws-me"},
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-6"],
        last_seen_id=base_id,
        web_socket_id="ws-me",
    )
    assert result.force_refresh is False
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_null_originator_counts_as_someone_else():
    base_id = _record_group_broadcast("table-7")
    _record_event(
        "table-7",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-7"],
        last_seen_id=base_id,
        web_socket_id="ws-me",
    )
    assert result.force_refresh is False
    assert len(result.replay_events) == 1


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_users_group_filters_by_user_id():
    base_id = _record_user_broadcast(42, send_to_all_users=True)
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [42],
            "send_to_all_users": False,
            "payload": {"type": "user_data_updated"},
            "ignore_web_socket_id": None,
        },
    )

    result_target = _replay_events_result(
        user_id=42,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result_target.force_refresh is False
    assert len(result_target.replay_events) == 1

    result_other = _replay_events_result(
        user_id=999,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result_other.force_refresh is False
    assert result_other.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_users_group_send_to_all_users():
    base_id = _record_user_broadcast(999, send_to_all_users=True)
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [],
            "send_to_all_users": True,
            "payload": {"type": "something"},
            "ignore_web_socket_id": None,
        },
    )

    result = _replay_events_result(
        user_id=999,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result.force_refresh is False
    assert len(result.replay_events) == 1


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_users_group_individual_payloads():
    base_id = _record_user_broadcast(7, send_to_all_users=True)
    _record_event(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"7": {"type": "app_created"}},
            "ignore_web_socket_id": None,
        },
    )

    result_target = _replay_events_result(
        user_id=7,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result_target.force_refresh is False
    assert len(result_target.replay_events) == 1

    result_other = _replay_events_result(
        user_id=8,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result_other.force_refresh is False
    assert result_other.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_users_channel_replay_filter_matches_live_delivery_predicates():
    user_id = 7
    payloads = [
        {
            "type": "broadcast_to_users",
            "user_ids": [user_id],
            "send_to_all_users": False,
            "payload": {"type": "targeted"},
            "ignore_web_socket_id": None,
        },
        {
            "type": "broadcast_to_users",
            "user_ids": [999],
            "send_to_all_users": False,
            "payload": {"type": "not_targeted"},
            "ignore_web_socket_id": None,
        },
        {
            "type": "broadcast_to_users",
            "user_ids": [],
            "send_to_all_users": True,
            "payload": {"type": "global"},
            "ignore_web_socket_id": None,
        },
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {str(user_id): {"type": "individual"}},
            "ignore_web_socket_id": None,
        },
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {str(user_id): "scalar-individual"},
            "ignore_web_socket_id": None,
        },
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"999": {"type": "other_individual"}},
            "ignore_web_socket_id": None,
        },
    ]

    expected_ids = []
    for payload in payloads:
        event_id = _record_event("users", payload)
        if RealtimeEventHandler.should_deliver_users_channel_event(user_id, payload):
            expected_ids.append(event_id)

    _record_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    matching_ids = list(
        RealtimeEvent.objects.filter(
            RealtimeEventHandler.get_users_channel_live_delivery_filter(user_id)
        )
        .order_by("id")
        .values_list("id", flat=True)
    )

    assert matching_ids == expected_ids


@pytest.mark.django_db
@pytest.mark.websockets
def test_check_detects_missed_events_across_groups():
    base_id = _record_group_broadcast("table-1", {"type": "baseline"})
    _record_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1", "table-2"],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result.force_refresh is False
    assert len(result.replay_events) == 1


class FakePageScope:
    def __init__(self, page_type, page_parameters):
        self.page_type = page_type
        self.page_parameters = page_parameters


class FakeSubscribedPages:
    def __init__(self, pages):
        self.pages = pages


@pytest.mark.django_db
@pytest.mark.websockets
def test_get_page_group_names_returns_page_group_names():
    pages = FakeSubscribedPages(
        [
            FakePageScope("table", {"table_id": 42}),
        ]
    )
    result = RealtimeEventHandler.get_page_group_names(pages)
    assert "table-42" in result
    assert "users" not in result


@pytest.mark.django_db
@pytest.mark.websockets
def test_users_group_is_checked_without_being_passed_as_channel_group():
    base_id = _record_user_broadcast(42)
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [42],
            "send_to_all_users": False,
            "payload": {"type": "user_data_updated"},
            "ignore_web_socket_id": None,
        },
    )

    result = _replay_events_result(
        user_id=42,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result.force_refresh is False
    assert len(result.replay_events) == 1


@pytest.mark.django_db
@pytest.mark.websockets
def test_get_page_group_names_skips_unknown_page_types():
    pages = FakeSubscribedPages(
        [
            FakePageScope("nonexistent_type", {}),
        ]
    )
    result = RealtimeEventHandler.get_page_group_names(pages)
    assert result == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_returns_events_in_id_order():
    base_id = _record_group_broadcast("table-1", {"type": "baseline"})
    _record_event(
        "table-1",
        {
            "type": "broadcast_to_group",
            "payload": {"a": 1},
            "ignore_web_socket_id": None,
        },
    )
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "user_updated"},
            "ignore_web_socket_id": None,
        },
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    events = result.replay_events
    assert result.force_refresh is False
    assert len(events) == 2
    assert events[0].id < events[1].id


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_raises_when_over_threshold():
    base_id = _record_group_broadcast("table-1", {"type": "baseline"})
    for i in range(settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 1):
        _record_event(
            "table-1",
            {
                "type": "broadcast_to_group",
                "payload": {"i": i},
                "ignore_web_socket_id": None,
            },
        )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result.force_refresh is True
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_raises_when_last_seen_id_not_in_table():
    _record_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=999999,
        web_socket_id=None,
    )
    assert result.force_refresh is True
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_succeeds_at_exactly_max_events():
    base_id = _record_group_broadcast("table-1", {"type": "baseline"})
    for i in range(settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS):
        _record_event(
            "table-1",
            {
                "type": "broadcast_to_group",
                "payload": {"i": i},
                "ignore_web_socket_id": None,
            },
        )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    events = result.replay_events
    assert result.force_refresh is False
    assert len(events) == settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_excludes_own_web_socket_id():
    base_id = _record_group_broadcast("table-1")
    _record_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": "ws-me"},
    )
    _record_event(
        "table-1",
        {
            "type": "broadcast_to_group",
            "payload": {},
            "ignore_web_socket_id": "ws-other",
        },
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=base_id,
        web_socket_id="ws-me",
    )
    events = result.replay_events
    assert result.force_refresh is False
    assert len(events) == 1
    assert events[0].payload["ignore_web_socket_id"] == "ws-other"


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_excludes_group_events_filtered_by_user_id():
    base_id = _record_group_broadcast("table-1", {"type": "baseline"})
    _record_event(
        "table-1",
        {
            "type": "broadcast_to_group",
            "payload": {"type": "should_skip"},
            "exclude_user_ids": [1],
            "ignore_web_socket_id": None,
        },
    )
    _record_event(
        "table-1",
        {
            "type": "broadcast_to_group",
            "payload": {"type": "should_include"},
            "exclude_user_ids": [2],
            "ignore_web_socket_id": None,
        },
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=base_id,
        web_socket_id=None,
    )

    assert result.force_refresh is False
    assert len(result.replay_events) == 1
    assert result.replay_events[0].payload["payload"]["type"] == "should_include"


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_returns_empty_list_when_no_new_events():
    base_id = _record_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    assert result.force_refresh is False
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_includes_events_from_all_subscribed_groups():
    base_id = _record_group_broadcast("table-1", {"type": "baseline"})
    _record_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )
    _record_event(
        "dashboard-2",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )
    _record_event(
        "table-99",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1", "dashboard-2"],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    events = result.replay_events
    assert result.force_refresh is False
    assert len(events) == 2
    groups = {e.channel_group for e in events}
    assert groups == {"table-1", "dashboard-2"}


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_filters_users_group_by_user_id():
    base_id = _record_user_broadcast(1, {"type": "baseline"})
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "user_updated"},
            "ignore_web_socket_id": None,
        },
    )
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [2, 3],
            "send_to_all_users": False,
            "payload": {"type": "user_updated"},
            "ignore_web_socket_id": None,
        },
    )
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1, 5],
            "send_to_all_users": True,
            "payload": {"type": "global_notification"},
            "ignore_web_socket_id": None,
        },
    )
    _record_event(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"2": {"data": "for-user-2"}},
            "ignore_web_socket_id": None,
        },
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    events = result.replay_events
    assert result.force_refresh is False
    assert len(events) == 2
    types = [e.payload["type"] for e in events]
    assert "broadcast_to_users" in types


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_users_does_not_inflate_count():
    base_id = _record_group_broadcast("table-1", {"type": "baseline"})
    for i in range(settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 1):
        _record_event(
            "users",
            {
                "type": "broadcast_to_users",
                "user_ids": [999],
                "send_to_all_users": False,
                "payload": {"i": i},
                "ignore_web_socket_id": None,
            },
        )
    _record_event(
        "table-1",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=["table-1"],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    events = result.replay_events
    assert result.force_refresh is False
    assert len(events) == 1
    assert events[0].channel_group == "table-1"


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_includes_individual_payloads_for_matching_user():
    base_id = _record_user_broadcast(1, {"type": "baseline"})
    _record_event(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"1": {"data": "for-user-1"}, "2": {"data": "for-user-2"}},
            "ignore_web_socket_id": None,
        },
    )
    _record_event(
        "users",
        {
            "type": "broadcast_to_users_individual_payloads",
            "payload_map": {"3": {"data": "for-user-3"}},
            "ignore_web_socket_id": None,
        },
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id=None,
    )
    events = result.replay_events
    assert result.force_refresh is False
    assert len(events) == 1
    assert "1" in events[0].payload["payload_map"]


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_excludes_own_web_socket_id_on_users_group():
    base_id = _record_user_broadcast(1, {"type": "baseline"})
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "should_skip"},
            "ignore_web_socket_id": "ws-me",
        },
    )
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "should_include"},
            "ignore_web_socket_id": "ws-other",
        },
    )

    result = _replay_events_result(
        user_id=1,
        page_group_names=[],
        last_seen_id=base_id,
        web_socket_id="ws-me",
    )
    events = result.replay_events
    assert result.force_refresh is False
    assert len(events) == 1
    assert events[0].payload["payload"]["type"] == "should_include"


@pytest.mark.django_db
@pytest.mark.websockets
def test_record_events_bulk():
    events_data = [
        ("table-1", {"type": "broadcast_to_group", "payload": {"i": 0}}),
        ("table-2", {"type": "broadcast_to_group", "payload": {"i": 1}}),
        ("users", {"type": "broadcast_to_users", "user_ids": [1]}),
    ]
    ids = RealtimeEventHandler.record_events(events_data)
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

    new_id = _record_event("table-1", {"type": "x"})

    deleted = RealtimeEventHandler.cleanup_old_realtime_events(
        retention=timedelta(hours=24)
    )
    assert deleted >= 1

    remaining = set(RealtimeEvent.objects.values_list("id", flat=True))
    assert old_id not in remaining
    assert new_id in remaining


@pytest.mark.django_db
@pytest.mark.websockets
def test_cleanup_zero_retention_does_nothing():
    _record_event("g", {"type": "x"})
    deleted = RealtimeEventHandler.cleanup_old_realtime_events(retention=timedelta(0))
    assert deleted == 0
    assert RealtimeEvent.objects.count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
def test_broadcast_to_channel_group_records_event():
    payload = {"type": "rows_created", "table_id": 5}
    broadcast_to_channel_group("table-5", payload)

    assert "_event_id" in payload
    event = RealtimeEvent.objects.get(id=payload["_event_id"])
    assert event.channel_group == "table-5"
    assert event.payload["type"] == "broadcast_to_group"


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
def test_broadcast_to_users_records_event():
    payload = {"type": "user_data_updated"}
    broadcast_to_users([1, 2], payload)

    assert "_event_id" in payload
    event = RealtimeEvent.objects.get(id=payload["_event_id"])
    assert event.channel_group == "users"
    assert event.payload["type"] == "broadcast_to_users"
    assert event.payload["user_ids"] == [1, 2]


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
def test_broadcast_to_users_individual_payloads_records_event():
    payload_map = {
        "1": {"type": "app_created", "workspace_id": 10},
        "2": {"type": "app_created", "workspace_id": 10},
    }
    broadcast_to_users_individual_payloads(payload_map)

    id_1 = payload_map["1"]["_event_id"]
    id_2 = payload_map["2"]["_event_id"]
    assert id_1 == id_2

    event = RealtimeEvent.objects.get(id=id_1)
    assert event.channel_group == "users"
    assert event.payload["type"] == "broadcast_to_users_individual_payloads"


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
def test_broadcast_to_users_without_workspace_id_still_records():
    payload = {"type": "user_data_updated"}
    broadcast_to_users([1], payload)

    assert "_event_id" in payload
    assert RealtimeEvent.objects.filter(channel_group="users").exists()


@pytest.mark.django_db
@pytest.mark.websockets
@override_settings(BASEROW_REALTIME_REPLAY_MAX_EVENTS=0)
def test_broadcast_skips_recording_when_disabled():
    RealtimeEvent.objects.all().delete()
    payload = {"type": "rows_created", "table_id": 5}
    broadcast_to_channel_group("table-5", payload)

    assert "_event_id" not in payload
    assert not RealtimeEvent.objects.exists()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@override_settings(BASEROW_REALTIME_REPLAY_MAX_EVENTS=0)
async def test_connect_advertises_replay_disabled(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    auth = await communicator.receive_json_from()
    assert auth["type"] == "authentication"
    assert auth["success"] is True
    assert auth["replay_enabled"] is False
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_connect_advertises_replay_enabled(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    auth = await communicator.receive_json_from()
    assert auth["replay_enabled"] is True
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@override_settings(BASEROW_REALTIME_REPLAY_MAX_EVENTS=0)
async def test_replay_events_ignored_when_recording_disabled(data_fixture):
    # Well-behaved clients respect ``replay_enabled`` and don't send the
    # message. If a stale client does anyway, the server drops it silently.
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()  # drain authentication

    await communicator.send_json_to(
        {"type": "replay_events", "last_seen_id": FIRST_CONNECT_CURSOR}
    )
    assert await communicator.receive_nothing(timeout=0.5) is True

    await communicator.disconnect()


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_events_result_baseline_uses_one_query(django_assert_num_queries):
    latest_id = _record_event("users", {"type": "x"})

    with django_assert_num_queries(1):
        result = _replay_events_result(
            user_id=1,
            page_group_names=[],
            last_seen_id=FIRST_CONNECT_CURSOR,
            web_socket_id=None,
        )

    assert result.force_refresh is False
    assert result.latest_event_id == latest_id
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_events_result_current_reconnect_uses_one_query(
    django_assert_num_queries,
):
    latest_id = _record_user_broadcast(1, {"type": "baseline"})

    with django_assert_num_queries(1):
        result = _replay_events_result(
            user_id=1,
            page_group_names=[],
            last_seen_id=latest_id,
            web_socket_id=None,
        )

    assert result.force_refresh is False
    assert result.latest_event_id == latest_id
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_events_result_future_last_seen_uses_one_query(
    django_assert_num_queries,
):
    latest_id = _record_user_broadcast(1, {"type": "baseline"})

    with django_assert_num_queries(1):
        result = _replay_events_result(
            user_id=1,
            page_group_names=[],
            last_seen_id=latest_id + 1,
            web_socket_id=None,
        )

    assert result.force_refresh is True
    assert result.latest_event_id == 0
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_events_result_missing_last_seen_uses_one_query(
    django_assert_num_queries,
):
    missing_id = _record_user_broadcast(1, {"type": "missing"})
    RealtimeEvent.objects.filter(id=missing_id).delete()
    _record_user_broadcast(1, {"type": "latest"})

    with django_assert_num_queries(1):
        result = _replay_events_result(
            user_id=1,
            page_group_names=[],
            last_seen_id=missing_id,
            web_socket_id=None,
        )

    assert result.force_refresh is True
    assert result.latest_event_id == 0
    assert result.replay_events == []


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_events_result_normal_replay_uses_one_query(django_assert_num_queries):
    base_id = _record_user_broadcast(1, {"type": "baseline"})
    latest_id = _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "user_data_updated"},
            "ignore_web_socket_id": None,
        },
    )

    with django_assert_num_queries(1):
        result = _replay_events_result(
            user_id=1,
            page_group_names=[],
            last_seen_id=base_id,
            web_socket_id=None,
        )

    assert result.force_refresh is False
    assert result.latest_event_id == latest_id
    assert len(result.replay_events) == 1


@pytest.mark.django_db
@pytest.mark.websockets
def test_replay_events_result_replay_acknowledges_latest_replay_window_event(
    django_assert_num_queries,
):
    base_id = _record_user_broadcast(1, {"type": "baseline"})
    replayed_id = _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [1],
            "send_to_all_users": False,
            "payload": {"type": "user_data_updated"},
            "ignore_web_socket_id": None,
        },
    )
    _record_event(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [999],
            "send_to_all_users": False,
            "payload": {"type": "other_user_updated"},
            "ignore_web_socket_id": None,
        },
    )

    with django_assert_num_queries(1):
        result = _replay_events_result(
            user_id=1,
            page_group_names=[],
            last_seen_id=base_id,
            web_socket_id=None,
        )

    assert result.force_refresh is False
    assert result.latest_event_id == replayed_id
    assert len(result.replay_events) == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_baseline_returns_no_refresh_needed(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "replay_events",
            "last_seen_id": FIRST_CONNECT_CURSOR,
        }
    )
    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "replay_events_result"
    assert response["force_refresh"] is False

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_replays_user_event(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    base_id = await sync_to_async(_record_event)(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user.id],
            "send_to_all_users": False,
            "payload": {"type": "baseline"},
            "ignore_web_socket_id": None,
        },
    )
    await sync_to_async(_record_event)(
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
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "replay_events",
            "last_seen_id": base_id,
        }
    )

    replayed = await communicator.receive_json_from(timeout=1)
    assert replayed["type"] == "user_data_updated"

    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "replay_events_result"
    assert response["force_refresh"] is False
    assert response["latest_event_id"] > base_id

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_cant_replay_when_too_many_events(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    base_id = await sync_to_async(_record_event)(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user.id],
            "send_to_all_users": False,
            "payload": {"type": "baseline"},
            "ignore_web_socket_id": None,
        },
    )
    for _ in range(settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 1):
        await sync_to_async(_record_event)(
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
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "replay_events",
            "last_seen_id": base_id,
        }
    )
    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "replay_events_result"
    assert response["force_refresh"] is True

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_excludes_own_session(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    base_id = await sync_to_async(_record_event)(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user.id],
            "send_to_all_users": False,
            "payload": {"type": "baseline"},
            "ignore_web_socket_id": None,
        },
    )
    await sync_to_async(_record_event)(
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
        f"ws/core/?jwt_token={token}&web_socket_id=my-old-ws",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "replay_events",
            "last_seen_id": base_id,
        }
    )
    response = await communicator.receive_json_from(timeout=1)
    assert response["force_refresh"] is False

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_replays_page_group_event(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    workspace = await sync_to_async(data_fixture.create_workspace)(user=user)
    database = await sync_to_async(data_fixture.create_database_application)(
        workspace=workspace
    )
    table = await sync_to_async(data_fixture.create_database_table)(database=database)

    base_id = await sync_to_async(_record_event)(
        f"table-{table.id}",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )
    await sync_to_async(_record_event)(
        f"table-{table.id}",
        {
            "type": "broadcast_to_group",
            "payload": {"type": "rows_created", "table_id": table.id},
            "ignore_web_socket_id": "ws-other",
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
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
            "type": "replay_events",
            "last_seen_id": base_id,
        }
    )

    replayed = await communicator.receive_json_from(timeout=1)
    assert replayed["type"] == "rows_created"
    assert replayed["table_id"] == table.id
    assert "_event_id" in replayed

    result = await communicator.receive_json_from(timeout=1)
    assert result["type"] == "replay_events_result"
    assert result["force_refresh"] is False
    assert result["latest_event_id"] > base_id

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_forces_refresh_when_replay_event_type_is_unsupported(
    caplog, data_fixture
):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    workspace = await sync_to_async(data_fixture.create_workspace)(user=user)
    database = await sync_to_async(data_fixture.create_database_application)(
        workspace=workspace
    )
    table = await sync_to_async(data_fixture.create_database_table)(database=database)

    base_id = await sync_to_async(_record_event)(
        f"table-{table.id}",
        {"type": "broadcast_to_group", "payload": {}, "ignore_web_socket_id": None},
    )
    await sync_to_async(_record_event)(
        f"table-{table.id}",
        {
            "type": "rows_created",
            "table_id": table.id,
            "ignore_web_socket_id": None,
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to({"page": "table", "table_id": table.id})
    page_response = await communicator.receive_json_from(timeout=1)
    assert page_response["type"] == "page_add"

    caplog.set_level("ERROR", logger="baserow.ws.consumers")
    await communicator.send_json_to(
        {
            "type": "replay_events",
            "last_seen_id": base_id,
        }
    )

    result = await communicator.receive_json_from(timeout=1)
    assert result["type"] == "replay_events_result"
    assert result["force_refresh"] is True
    assert result["latest_event_id"] == 0
    assert "unsupported payload type" in caplog.text

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_replays_individual_payloads_event(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    base_id = await sync_to_async(_record_event)(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user.id],
            "send_to_all_users": False,
            "payload": {"type": "baseline"},
            "ignore_web_socket_id": None,
        },
    )
    await sync_to_async(_record_event)(
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
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    await communicator.send_json_to(
        {
            "type": "replay_events",
            "last_seen_id": base_id,
        }
    )

    replayed = await communicator.receive_json_from(timeout=1)
    assert replayed["type"] == "app_created"
    assert replayed["name"] == "Test"
    assert "_event_id" in replayed

    result = await communicator.receive_json_from(timeout=1)
    assert result["type"] == "replay_events_result"
    assert result["force_refresh"] is False

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_cant_replay_when_last_seen_expired(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    await sync_to_async(data_fixture.create_workspace)(user=user)

    await sync_to_async(_record_event)(
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
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    # last_seen_id=1 does not exist — retention cleaned it (simulated by
    # never having created id=1). Replay can't proceed — client must refresh.
    await communicator.send_json_to(
        {
            "type": "replay_events",
            "last_seen_id": 1,
        }
    )

    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "replay_events_result"
    assert response["force_refresh"] is True

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_replay_events_replays_table_events_only_when_subscribed(data_fixture):
    user, token = await sync_to_async(data_fixture.create_user_and_token)()
    workspace = await sync_to_async(data_fixture.create_workspace)(user=user)
    database = await sync_to_async(data_fixture.create_database_application)(
        workspace=workspace
    )
    table = await sync_to_async(data_fixture.create_database_table)(database=database)

    base_id = await sync_to_async(_record_event)(
        "users",
        {
            "type": "broadcast_to_users",
            "user_ids": [user.id],
            "send_to_all_users": False,
            "payload": {"type": "baseline"},
            "ignore_web_socket_id": None,
        },
    )
    await sync_to_async(_record_event)(
        f"table-{table.id}",
        {
            "type": "broadcast_to_group",
            "payload": {"type": "rows_created", "table_id": table.id},
            "ignore_web_socket_id": "ws-other",
        },
    )

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id=ws-me",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.receive_json_from()

    # Do NOT subscribe to the table page — replay should not include table events.
    await communicator.send_json_to(
        {
            "type": "replay_events",
            "last_seen_id": base_id,
        }
    )

    response = await communicator.receive_json_from(timeout=1)
    assert response["type"] == "replay_events_result"
    assert response["force_refresh"] is False

    await communicator.disconnect()
