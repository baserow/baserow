from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings
from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet
from django.utils import timezone

# Lazy-imported: a module-level import here chains through the WS router
# before ``get_asgi_application()`` runs and triggers AppRegistryNotReady
# under gunicorn/uvicorn workers.
if TYPE_CHECKING:
    from baserow.ws.models import RealtimeEvent

REALTIME_EVENTS_CLEANUP_INTERVAL_MINUTES = 60

# ``replay_events`` cursor sentinels. Must match the constants in
# web-frontend/modules/core/plugins/realtimeProtocol.js.
#
# FIRST_CONNECT_CURSOR: first connect of a session, ask for a baseline only.
# NO_REPLAY_AVAILABLE:  reconnect with no usable high-water mark, force refresh.
FIRST_CONNECT_CURSOR = -1
NO_REPLAY_AVAILABLE = 0


@dataclass(frozen=True)
class ReplayEventsResult:
    """
    The server decision for a ``replay_events`` client message.
    """

    force_refresh: bool
    latest_event_id: int
    replay_events: list[RealtimeEvent]


class RealtimeEventHandler:
    @staticmethod
    def is_recording_enabled() -> bool:
        """
        :returns: ``True`` when event recording is active.
        """

        return settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS > 0

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

        user_id_str = str(user_id)
        return Q(channel_group="users") & (
            Q(
                payload__contains={
                    "type": "broadcast_to_users",
                    "send_to_all_users": True,
                },
            )
            | Q(
                payload__contains={
                    "type": "broadcast_to_users",
                    "user_ids": [user_id],
                },
            )
            | Q(
                payload__contains={
                    "type": "broadcast_to_users_individual_payloads",
                },
                payload__payload_map__has_key=user_id_str,
            )
        )

    @staticmethod
    def cleanup_old_realtime_events(retention: timedelta) -> int:
        """
        Delete ``RealtimeEvent`` rows older than ``retention``.

        :param retention: Maximum age of events to keep.
        :returns: Number of rows deleted.
        """

        from baserow.ws.models import RealtimeEvent

        if retention.total_seconds() <= 0:
            return 0
        cutoff = timezone.now() - retention
        deleted, _ = RealtimeEvent.objects.filter(created_at__lt=cutoff).delete()
        return deleted

    @staticmethod
    def get_page_group_names(pages) -> list[str]:
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
        """
        Decide how a realtime client should catch up after connecting. Only
        called when replay recording is enabled — well-behaved clients skip
        ``replay_events`` when the authentication handshake says it is off,
        and ``_handle_replay_events`` drops the message otherwise.

        :param user_id: The id of the reconnecting user.
        :param page_group_names: Page channel group names the user is
            subscribed to. Must not include ``"users"`` — that channel is
            added unconditionally by
            ``get_users_channel_live_delivery_filter``.
        :param last_seen_id: ``FIRST_CONNECT_CURSOR`` for a fresh connection,
            ``NO_REPLAY_AVAILABLE`` for a reconnect with no usable high-water
            mark, or a positive event id the client last saw.
        :param web_socket_id: The client's persistent web socket id, used to
            exclude events the client itself originated.
        :returns: A result containing replay events or a force-refresh instruction.
        """

        if last_seen_id == FIRST_CONNECT_CURSOR:
            # Connecting for the first time - clients only need the latest event id to
            # know where to start for future reconnects.
            return ReplayEventsResult(
                force_refresh=False,
                latest_event_id=RealtimeEventHandler.get_latest_event_id(),
                replay_events=[],
            )

        if last_seen_id == NO_REPLAY_AVAILABLE:
            # Reconnect without a high-water mark — we can't prove what was
            # missed, so the client has to refresh.
            return ReplayEventsResult(
                force_refresh=True,
                latest_event_id=NO_REPLAY_AVAILABLE,
                replay_events=[],
            )

        replay_window_events = list(
            RealtimeEventHandler.get_replay_window(
                user_id, page_group_names, last_seen_id, web_socket_id
            )
        )

        if replay_window_events:
            # The first event must be the last seen event, and we must not exceed the
            # replay limit with the remaining events, for a successful replay.
            latest_event_id = replay_window_events[-1].id
            replay_events = replay_window_events[1:]
            max_events = settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS
            can_replay = (
                replay_window_events[0].id == last_seen_id
                and len(replay_events) <= max_events
            )
            if can_replay:
                return ReplayEventsResult(
                    force_refresh=False,
                    latest_event_id=latest_event_id,
                    replay_events=replay_events,
                )

        # Empty window or unable to anchor against ``last_seen_id`` — the
        # cursor has expired, the client missed too many events, or the
        # filter excluded the baseline. Force a refresh.
        return ReplayEventsResult(
            force_refresh=True,
            latest_event_id=NO_REPLAY_AVAILABLE,
            replay_events=[],
        )

    @staticmethod
    def get_latest_event_id() -> int:
        """
        Return the latest persisted realtime event id.

        :return: The highest event id, or ``0`` when no events exist.
        """

        from baserow.ws.models import RealtimeEvent

        return RealtimeEvent.objects.aggregate(latest=Coalesce(Max("id"), 0))["latest"]

    @staticmethod
    def get_replay_window(
        user_id: int,
        page_group_names: list[str],
        last_seen_id: int,
        web_socket_id: Optional[str],
    ) -> QuerySet[RealtimeEvent]:
        """
        Return the baseline event followed by replayable events.

        :param user_id: The id of the reconnecting user.
        :param page_group_names: Page channel group names the user is
            subscribed to. Must not include ``"users"``.
        :param last_seen_id: Highest event id the client has already processed.
        :param web_socket_id: The client's persistent web socket id, used to
            exclude events the client itself originated.
        :return: An ordered queryset containing ``last_seen_id`` when it still
            exists, plus relevant events after it. The queryset is capped at
            baseline plus one more than the configured replay limit so the caller
            can detect that the client must refresh.
        """

        from baserow.ws.models import RealtimeEvent

        replay_filter = (
            Q(id__gt=last_seen_id)
            & RealtimeEventHandler.get_not_own_event_filter(web_socket_id)
            & RealtimeEventHandler.get_relevant_events_filter(
                user_id, page_group_names
            )
        )

        replay_filter |= Q(id=last_seen_id)

        return RealtimeEvent.objects.filter(replay_filter).order_by("id")[
            : settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS + 2
        ]

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
        conditions &= RealtimeEventHandler.get_not_user_filtered_group_event_filter(user_id)

        return conditions

    @staticmethod
    def get_not_own_event_filter(web_socket_id: Optional[str]) -> Q:
        """
        Build a filter that excludes events from the same websocket connection.

        :param web_socket_id: The client's persistent web socket id.
        :return: A ``Q`` object that can be combined with replay filters.
        """

        return (
            ~Q(payload__ignore_web_socket_id=web_socket_id)
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
