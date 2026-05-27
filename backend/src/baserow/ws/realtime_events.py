from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from baserow.ws.models import RealtimeEvent

REALTIME_EVENTS_CLEANUP_INTERVAL_MINUTES = 60


@dataclass
class ReplayResult:
    events: list[RealtimeEvent]
    degraded: bool


class RealtimeEventHandler:
    @staticmethod
    def is_recording_enabled() -> bool:
        """
        :returns: ``True`` when event recording is active.
        """

        return settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS > 0

    @staticmethod
    def record_events(events_data: list[tuple[str, dict]]) -> list[int]:
        """
        Insert rows into ``ws_realtime_events`` and return their ids
        in the same order as the input.

        :param events_data: List of ``(channel_group, payload)`` tuples.
        :returns: List of created row ids, same order as input.
        """

        objects = [
            RealtimeEvent(channel_group=channel_group, payload=payload)
            for channel_group, payload in events_data
        ]
        created = RealtimeEvent.objects.bulk_create(objects)
        return [obj.id for obj in created]

    @staticmethod
    def cleanup_old_realtime_events(retention: timedelta) -> int:
        """
        Delete ``RealtimeEvent`` rows older than ``retention``.

        :param retention: Maximum age of events to keep.
        :returns: Number of rows deleted.
        """

        if retention.total_seconds() <= 0:
            return 0
        cutoff = timezone.now() - retention
        deleted, _ = RealtimeEvent.objects.filter(created_at__lt=cutoff).delete()
        return deleted

    @staticmethod
    def get_channel_group_names(
        pages, authenticated: bool = True
    ) -> list[tuple[str, str]]:
        """
        Derive ``(channel_group_name, category)`` pairs from a
        ``SubscribedPages`` instance. Category is the page type string
        (e.g. ``"table"``, ``"dashboard"``). Appends the ``"users"``
        group only for authenticated connections.

        :param pages: A ``SubscribedPages`` instance.
        :param authenticated: Whether to include the ``"users"`` group.
        :returns: List of ``(channel_group_name, category)`` tuples.
        """

        from baserow.ws.registries import page_registry

        result: list[tuple[str, str]] = []
        for page in pages.pages:
            try:
                page_type = page_registry.get(page.page_type)
            except page_registry.does_not_exist_exception_class:
                continue
            group_name = page_type.get_group_name(**page.page_parameters)
            result.append((group_name, page.page_type))
        if authenticated:
            result.append(("users", "users"))
        return result

    @staticmethod
    def get_replay_events(
        user_id: int,
        channel_group_names: list[tuple[str, str]],
        last_seen_id: int,
        web_socket_id: Optional[str],
    ) -> ReplayResult:
        """
        Fetch events for replay on reconnect.

        Returns a ``ReplayResult`` with ``degraded=False`` and an ordered list
        of events when replay is possible. Returns ``degraded=True`` when the
        event count exceeds ``BASEROW_REALTIME_REPLAY_MAX_EVENTS`` or
        ``last_seen_id`` has been cleaned up by retention.

        The ``"users"`` group is filtered to only include events relevant to
        ``user_id``, preventing unrelated user events from inflating the count.

        :param user_id: The id of the reconnecting user.
        :param channel_group_names: ``(group_name, category)`` pairs from
            ``get_channel_group_names``.
        :param last_seen_id: Highest event id the client has already processed.
        :param web_socket_id: The client's persistent web socket id, used to
            exclude events the client itself originated.
        :returns: A ``ReplayResult`` with ``events`` and ``degraded`` fields.
        """

        if not RealtimeEvent.objects.filter(id=last_seen_id).exists():
            return ReplayResult(events=[], degraded=True)

        page_group_names = [name for name, cat in channel_group_names if cat != "users"]
        has_users_group = any(cat == "users" for _, cat in channel_group_names)

        base_q = Q(id__gt=last_seen_id)
        conditions = Q()

        if page_group_names:
            conditions |= Q(channel_group__in=page_group_names)

        if has_users_group:
            user_id_str = str(user_id)
            user_q = Q(channel_group="users") & (
                Q(
                    payload__type="broadcast_to_users",
                    payload__send_to_all_users=True,
                )
                | Q(
                    payload__type="broadcast_to_users",
                    payload__user_ids__contains=[user_id],
                )
                | Q(
                    payload__type="broadcast_to_users_individual_payloads",
                    payload__payload_map__has_key=user_id_str,
                )
            )
            conditions |= user_q

        if not conditions:
            return ReplayResult(events=[], degraded=False)

        qs = RealtimeEvent.objects.filter(base_q & conditions)
        if web_socket_id is not None:
            qs = qs.exclude(payload__ignore_web_socket_id=web_socket_id)

        max_events = settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS
        result = list(qs.order_by("id")[:max_events])
        if len(result) >= max_events:
            return ReplayResult(events=[], degraded=True)

        return ReplayResult(events=result, degraded=False)

    @staticmethod
    def check_realtime_events(
        user_id: int,
        channel_group_names: list[tuple[str, str]],
        last_seen_id: Optional[int],
        web_socket_id: Optional[str],
    ) -> tuple[bool, int]:
        """
        Check whether any relevant events exist since ``last_seen_id``.

        Uses the same OR-based query strategy as ``get_replay_events``.

        :param user_id: The id of the user to check staleness for.
        :param channel_group_names: ``(group_name, category)`` pairs from
            ``get_channel_group_names``.
        :param last_seen_id: Highest event id the client has already processed,
            or ``None`` for a baseline check.
        :param web_socket_id: The client's persistent web socket id, used to
            exclude events the client itself originated.
        :returns: ``(stale, current_latest_id)`` tuple.
        """

        current_latest_id = RealtimeEvent.objects.aggregate(
            latest=Coalesce(Max("id"), 0)
        )["latest"]

        if last_seen_id is None:
            return False, current_latest_id

        page_group_names = [name for name, cat in channel_group_names if cat != "users"]
        has_users_group = any(cat == "users" for _, cat in channel_group_names)

        base_q = Q(id__gt=last_seen_id)
        conditions = Q()

        if page_group_names:
            conditions |= Q(channel_group__in=page_group_names)

        if has_users_group:
            user_id_str = str(user_id)
            user_q = Q(channel_group="users") & (
                Q(
                    payload__type="broadcast_to_users",
                    payload__send_to_all_users=True,
                )
                | Q(
                    payload__type="broadcast_to_users",
                    payload__user_ids__contains=[user_id],
                )
                | Q(
                    payload__type="broadcast_to_users_individual_payloads",
                    payload__payload_map__has_key=user_id_str,
                )
            )
            conditions |= user_q

        if not conditions:
            return False, current_latest_id

        qs = RealtimeEvent.objects.filter(base_q & conditions)
        if web_socket_id is not None:
            qs = qs.exclude(payload__ignore_web_socket_id=web_socket_id)

        return qs.exists(), current_latest_id
