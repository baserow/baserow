from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings
from django.db import connection
from django.db.models import Case, F, Q, When
from django.db.models.query import QuerySet
from django.utils import timezone

from baserow.ws.telemetry import (
    realtime_cleanup_batch,
    realtime_cleanup_run,
    realtime_recording,
)

# Lazy-imported: a module-level import here chains through the WS router
# before ``get_asgi_application()`` runs and triggers AppRegistryNotReady
# under gunicorn/uvicorn workers.
if TYPE_CHECKING:
    from baserow.ws.consumers import SubscribedPages
    from baserow.ws.models import RealtimeEvent

REALTIME_EVENTS_CLEANUP_INTERVAL_MINUTES = 10
REALTIME_EVENTS_CLEANUP_BATCH_SIZE = 5000
# Leave headroom below Celery's default five-minute soft task limit.
REALTIME_EVENTS_CLEANUP_BUDGET_SECONDS = 4 * 60
REALTIME_EVENTS_CLEANUP_STATEMENT_TIMEOUT_MS = 3000
REALTIME_EVENTS_CLEANUP_LOCK_TIMEOUT_MS = 250
REALTIME_EVENTS_CLEANUP_LOCK_SECONDS = REALTIME_EVENTS_CLEANUP_BUDGET_SECONDS + 90

# ``replay_events`` cursor sentinels. Must match the constants in
# web-frontend/modules/core/plugins/realtimeProtocol.js.
#
# FIRST_CONNECT_CURSOR: first connect of a session, ask for a baseline only.
# NO_REPLAY_AVAILABLE:  reconnect with no usable high-water mark, force refresh.
FIRST_CONNECT_CURSOR = -1
NO_REPLAY_AVAILABLE = -2


@dataclass(frozen=True)
class ReplayEventsResult:
    """
    The server decision for a ``replay_events`` client message.
    """

    force_refresh: bool
    latest_event_id: int
    replay_events: list[RealtimeEvent]
    # Transient infrastructure failure, rather than an unrecoverable replay gap.
    # Older clients still receive the force-refresh fallback.
    retry_after_ms: int | None = None
    refresh_reason: str | None = None


class RealtimeEventHandler:
    @staticmethod
    def is_recording_enabled() -> bool:
        """
        :returns: ``True`` when event recording is active.
        """

        return settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS > 0

    @staticmethod
    def get_replay_retention() -> timedelta:
        """Maximum age of full events accepted by replay and retained by cleanup."""

        return timedelta(hours=settings.REALTIME_REPLAY_RETENTION_HOURS)

    @staticmethod
    def record_events(
        events_data: list[tuple[str, dict[str, Any]]],
    ) -> list[int]:
        """
        Insert rows into ``ws_realtime_events`` and return their ids
        in the same order as the input.

        :param events_data: List of ``(channel_group, payload)`` tuples.
        :returns: List of created row ids, same order as input.
        """

        from baserow.ws.models import RealtimeEvent

        with realtime_recording(events_data):
            objects = [
                RealtimeEvent(channel_group=channel_group, payload=payload)
                for channel_group, payload in events_data
            ]
            created = RealtimeEvent.objects.bulk_create(objects)
            return [obj.id for obj in created]

    @staticmethod
    def add_event_id_to_payload(event_id: int, payload: dict[str, Any]) -> None:
        """
        Inject the persisted event id into dict payloads sent to clients.

        :param event_id: The ``RealtimeEvent`` id that identifies the broadcast.
        :param payload: The channel-layer message that contains either ``payload``
            or ``payload_map`` entries.
        """

        inner_payload = payload.get("payload")
        if isinstance(inner_payload, dict):
            inner_payload["_event_id"] = event_id
            return

        payload_map = payload.get("payload_map")
        if isinstance(payload_map, dict):
            for mapped_payload in payload_map.values():
                if isinstance(mapped_payload, dict):
                    mapped_payload["_event_id"] = event_id
            return

        raise ValueError(
            "Invalid payload structure, missing 'payload' or 'payload_map'"
        )

    @staticmethod
    def should_deliver_users_channel_event(
        user_id: int,
        event: dict[str, Any],
    ) -> bool:
        """
        Decide whether a shared ``users`` channel event targets a user.

        :param user_id: The id of the websocket user.
        :param event: The channel-layer ``users`` event.
        :return: Whether the user should receive the event.
        """

        event_type = event.get("type")
        if event_type == "broadcast_to_users":
            return event["send_to_all_users"] or user_id in event["user_ids"]
        if event_type == "broadcast_to_users_individual_payloads":
            return str(user_id) in event["payload_map"]
        return False

    @staticmethod
    def get_users_channel_live_delivery_filter(user_id: int) -> Q:
        """
        Build the replay-side equivalent of live users-channel delivery.

        This must mirror ``should_deliver_users_channel_event`` because replay
        and live delivery must target the same users for this channel.

        :param user_id: The id of the reconnecting user.
        :return: A ``Q`` object matching users-channel events the user receives.
        """

        # The database maintains recipient metadata even for older writers.
        # Every users-channel arm can use an index without reading payload_map.
        return Q(channel_group="users") & (
            Q(all_users=True) | Q(target_user_ids__contains=[user_id])
        )

    @staticmethod
    def cleanup_old_realtime_events(
        retention: timedelta, *, deadline: float | None = None
    ) -> int:
        """
        Delete expired events in separately committed, time-bounded batches.

        :param retention: Maximum age of events to keep.
        :param deadline: Optional earlier monotonic deadline, including time
            already spent acquiring the task's cleanup lease.
        :returns: Number of rows committed before the run finishes or its work
            budget expires. A later batch failure leaves earlier commits intact.
        """

        if retention.total_seconds() <= 0:
            return 0
        cutoff = timezone.now() - retention
        budget_deadline = monotonic() + REALTIME_EVENTS_CLEANUP_BUDGET_SECONDS
        deadline = (
            min(deadline, budget_deadline) if deadline is not None else budget_deadline
        )
        with realtime_cleanup_run() as run:
            while monotonic() < deadline:
                with realtime_cleanup_batch() as batch:
                    batch.deleted = RealtimeEventHandler._delete_realtime_events_batch(
                        cutoff, deadline
                    )
                run.deleted += batch.deleted
                if batch.deleted < REALTIME_EVENTS_CLEANUP_BATCH_SIZE:
                    if monotonic() >= deadline:
                        run.outcome = "budget"
                    return run.deleted
            run.outcome = "budget"
            return run.deleted

    @staticmethod
    def _delete_realtime_events_batch(cutoff, deadline) -> int:
        """Save expired delivery evidence and delete one independently committed batch."""

        from baserow.ws.history import compact_events_batch

        return compact_events_batch(
            cutoff,
            deadline,
            batch_size=REALTIME_EVENTS_CLEANUP_BATCH_SIZE,
            statement_timeout_ms=REALTIME_EVENTS_CLEANUP_STATEMENT_TIMEOUT_MS,
            lock_timeout_ms=REALTIME_EVENTS_CLEANUP_LOCK_TIMEOUT_MS,
        )

    @staticmethod
    def get_page_group_names(pages: "SubscribedPages") -> list[str]:
        """
        Collect page channel group names from a ``SubscribedPages`` instance.
        Never returns ``"users"`` — that channel is handled separately by
        ``get_relevant_events_filter``.

        :param pages: A ``SubscribedPages`` instance.
        :returns: Page channel group name strings.
        """

        from baserow.ws.registries import page_registry

        result: list[str] = []
        for page in pages.pages:
            try:
                page_type = page_registry.get(page.page_type)
            except page_registry.does_not_exist_exception_class:
                continue
            result.append(page_type.get_group_name(**page.page_parameters))
        return result

    @staticmethod
    def get_replay_events_result(
        user_id: int,
        page_group_names: list[str],
        last_seen_id: int,
        web_socket_id: Optional[str],
    ) -> ReplayEventsResult:
        """Distinguish unchanged, replayable and expired history in one snapshot."""

        from baserow.ws.models import RealtimeEvent

        def refresh(reason):
            return ReplayEventsResult(
                True, NO_REPLAY_AVAILABLE, [], refresh_reason=reason
            )

        if last_seen_id == NO_REPLAY_AVAILABLE:
            return refresh("missing_cursor")
        if last_seen_id == FIRST_CONNECT_CURSOR:
            return ReplayEventsResult(
                False, RealtimeEventHandler.get_latest_event_id(), []
            )

        rows = RealtimeEventHandler._get_replay_snapshot(
            user_id,
            page_group_names,
            last_seen_id,
            web_socket_id,
        )
        if not rows or last_seen_id < rows[0][0]:
            return refresh("unknown_history")
        latest_event_id = rows[0][1]
        if last_seen_id > latest_event_id:
            return refresh("cursor_ahead")

        if rows[0][2]:
            return refresh("expired_payload")

        cutoff = timezone.now() - RealtimeEventHandler.get_replay_retention()
        events = []
        for _, _, _, event_id, channel_group, payload, created_at in rows:
            if event_id is None:
                continue
            if created_at < cutoff:
                return refresh("expired_payload")
            events.append(
                RealtimeEvent(
                    id=event_id,
                    channel_group=channel_group,
                    payload=json.loads(payload)
                    if isinstance(payload, str)
                    else payload,
                    created_at=created_at,
                )
            )
        if len(events) > settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS:
            return refresh("event_limit")
        # Do not acknowledge unrelated higher IDs: a lower relevant INSERT may
        # still be uncommitted. Retain the original cursor when nothing replays.
        return ReplayEventsResult(
            False, events[-1].id if events else last_seen_id, events
        )

    @staticmethod
    def _initialize_realtime_history():
        # Usually a cheap existence check. After an UNLOGGED reset the function
        # waits for in-flight inserts before recording a conservative loss floor.
        with connection.cursor() as cursor:
            cursor.execute("SELECT ws_initialize_realtime_history()")

    @staticmethod
    def get_latest_event_id() -> int:
        """Return the high-water mark, including evicted history."""

        with connection.cursor() as cursor:
            sql = (
                "SELECT GREATEST(floor, compacted_event_id, "
                "COALESCE((SELECT id FROM ws_realtime_events "
                "ORDER BY id DESC LIMIT 1), 0)) "
                "FROM ws_realtime_event_history_state WHERE id = 1"
            )
            cursor.execute(sql)
            row = cursor.fetchone()
            if row is None:
                RealtimeEventHandler._initialize_realtime_history()
                cursor.execute(sql)
                row = cursor.fetchone()
            return row[0]

    @staticmethod
    def _get_replay_snapshot(user_id, page_group_names, last_seen_id, web_socket_id):
        """Read expired evidence, payloads and loss state together across cleanup."""

        events = RealtimeEventHandler.get_replay_window(
            user_id, page_group_names, last_seen_id, web_socket_id
        )
        history = RealtimeEventHandler.get_expired_history(
            user_id, page_group_names, last_seen_id, web_socket_id
        )
        events_sql, events_params = events.values_list(
            "id", "channel_group", "payload", "created_at"
        ).query.sql_with_params()
        history_sql, history_params = history.values(
            "route_key"
        ).query.sql_with_params()
        sql = (
            "WITH history AS MATERIALIZED ("  # noqa: S608
            "SELECT state.floor, GREATEST(state.floor, state.compacted_event_id, "
            "COALESCE((SELECT id FROM ws_realtime_events "
            "ORDER BY id DESC LIMIT 1), 0)) AS latest_event_id, "
            f"CASE WHEN state.floor <= %s THEN EXISTS({history_sql}) "
            "ELSE false END AS expired "
            "FROM ws_realtime_event_history_state AS state WHERE state.id = 1) "
            "SELECT history.*, replay.* FROM history "
            "LEFT JOIN LATERAL ("
            "SELECT events.id, events.channel_group, "
            "CASE WHEN events.created_at < %s THEN NULL ELSE events.payload END, "
            f"events.created_at FROM ({events_sql}) AS events "
            "WHERE history.floor <= %s AND NOT history.expired"
            ") AS replay ON true ORDER BY replay.id"
        )
        params = [
            last_seen_id,
            *history_params,
            timezone.now() - RealtimeEventHandler.get_replay_retention(),
            *events_params,
            last_seen_id,
        ]
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                RealtimeEventHandler._initialize_realtime_history()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            return rows

    @staticmethod
    def get_expired_history(user_id, page_group_names, last_seen_id, web_socket_id):
        """Match compacted audiences, accounting for the client's socket exclusion."""

        from baserow.ws.models import RealtimeEventHistorySummary

        latest = F("latest_event_id")
        if web_socket_id is not None:
            latest = Case(
                When(latest_socket_id=web_socket_id, then=F("previous_event_id")),
                default=latest,
            )
        return RealtimeEventHistorySummary.objects.alias(
            relevant_event_id=latest
        ).filter(
            RealtimeEventHandler.get_relevant_events_filter(user_id, page_group_names),
            relevant_event_id__gt=last_seen_id,
        )

    @staticmethod
    def get_replay_window(
        user_id: int,
        page_group_names: list[str],
        last_seen_id: int,
        web_socket_id: Optional[str],
    ) -> QuerySet[RealtimeEvent]:
        """Return relevant payloads after the cursor, capped at limit plus one.

        Keep the ID bound outside audience OR predicates so PostgreSQL's ordered
        index scan can start at the cursor instead of visiting retained prehistory.
        """

        from baserow.ws.models import RealtimeEvent

        return RealtimeEvent.objects.filter(
            RealtimeEventHandler.get_not_own_event_filter(web_socket_id)
            & RealtimeEventHandler.get_relevant_events_filter(
                user_id, page_group_names
            ),
            id__gt=last_seen_id,
        ).order_by("id")[: settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 1]

    @staticmethod
    def get_relevant_events_filter(
        user_id: int,
        page_group_names: list[str],
    ) -> Q:
        """
        Build the database filter for events relevant to a user: page-group events plus
        the user's events on the shared ``users`` channel.

        :param user_id: The id of the reconnecting user.
        :param page_group_names: Page channel group names the user is subscribed to.
            Must not include ``"users"`` — that channel is added unconditionally by
            `get_users_channel_live_delivery_filter`.
        :return: A `Q` object matching relevant events.
        """

        conditions = Q()

        if page_group_names:
            conditions |= Q(channel_group__in=page_group_names)

        # The users-channel filter must mirror the live delivery logic used by
        # CoreConsumer.broadcast_to_users and broadcast_to_users_individual_payloads.
        conditions |= RealtimeEventHandler.get_users_channel_live_delivery_filter(
            user_id
        )
        conditions &= RealtimeEventHandler.get_not_user_filtered_group_event_filter(
            user_id
        )

        return conditions

    @staticmethod
    def get_not_own_event_filter(web_socket_id: Optional[str]) -> Q:
        """
        Build a filter that excludes events from the same websocket connection.

        :param web_socket_id: The client's persistent web socket id.
        :return: A ``Q`` object that can be combined with replay filters.
        """

        return (
            (
                ~Q(payload__ignore_web_socket_id=web_socket_id)
                | ~Q(payload__has_key="ignore_web_socket_id")
            )
            if web_socket_id is not None
            else Q()
        )

    @staticmethod
    def get_not_user_filtered_group_event_filter(user_id: int) -> Q:
        """
        Build a filter that excludes group events skipped by live delivery.

        :param user_id: The id of the reconnecting user.
        :return: A ``Q`` object that can be combined with replay filters.
        """

        return ~Q(
            payload__contains={
                "type": "broadcast_to_group",
                "exclude_user_ids": [user_id],
            }
        )
