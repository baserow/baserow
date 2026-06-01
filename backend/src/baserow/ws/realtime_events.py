from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from baserow.ws.exceptions import EventReplayNotPossible

if TYPE_CHECKING:
    from baserow.ws.models import RealtimeEvent

REALTIME_EVENTS_CLEANUP_INTERVAL_MINUTES = 60


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

        from baserow.ws.models import RealtimeEvent

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

        from baserow.ws.models import RealtimeEvent

        if retention.total_seconds() <= 0:
            return 0
        cutoff = timezone.now() - retention
        deleted, _ = RealtimeEvent.objects.filter(created_at__lt=cutoff).delete()
        return deleted

    @staticmethod
    def get_channel_group_names(pages, authenticated: bool = True) -> list[str]:
        """
        Collect channel group names from a ``SubscribedPages`` instance.

        :param pages: A ``SubscribedPages`` instance.
        :param authenticated: Whether to include the ``"users"`` group.
        :returns: List of channel group name strings.
        """

        from baserow.ws.registries import page_registry

        result: list[str] = []
        for page in pages.pages:
            try:
                page_type = page_registry.get(page.page_type)
            except page_registry.does_not_exist_exception_class:
                continue
            result.append(page_type.get_group_name(**page.page_parameters))
        if authenticated:
            result.append("users")
        return result

    @staticmethod
    def get_replay_events(
        user_id: int,
        channel_group_names: list[str],
        last_seen_id: int,
        web_socket_id: Optional[str],
    ) -> list[RealtimeEvent]:
        """
        Fetch events for replay on reconnect.

        The ``"users"`` group is filtered to only include events relevant to
        ``user_id``, preventing unrelated user events from inflating the count.

        :param user_id: The id of the reconnecting user.
        :param channel_group_names: Channel group names from
            ``get_channel_group_names``.
        :param last_seen_id: Highest event id the client has already processed.
        :param web_socket_id: The client's persistent web socket id, used to
            exclude events the client itself originated.
        :returns: Ordered list of events to replay. Empty list means nothing
            was missed.
        :raises EventReplayNotPossible: When the event gap is too large to
            replay or ``last_seen_id`` has been cleaned up by retention.
        """

        from baserow.ws.models import RealtimeEvent

        first_row = (
            RealtimeEvent.objects.filter(id__gte=last_seen_id)
            .values("id")
            .order_by("id")
            .first()
        )
        if first_row is None or first_row["id"] != last_seen_id:
            raise EventReplayNotPossible()

        page_group_names = [name for name in channel_group_names if name != "users"]
        has_users_group = "users" in channel_group_names

        base_q = Q(id__gt=last_seen_id)
        conditions = Q()

        if page_group_names:
            conditions |= Q(channel_group__in=page_group_names)

        if has_users_group:
            user_id_str = str(user_id)
            user_q = Q(channel_group="users") & (
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
                        "payload_map": {user_id_str: {}},
                    },
                )
            )
            conditions |= user_q

        if not conditions:
            return []

        qs = RealtimeEvent.objects.filter(base_q & conditions)
        if web_socket_id is not None:
            qs = qs.exclude(payload__ignore_web_socket_id=web_socket_id)

        max_events = settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS
        result = list(qs.order_by("id")[: max_events + 1])

        if len(result) > max_events:
            raise EventReplayNotPossible()

        return result

    @staticmethod
    def check_realtime_events(
        user_id: int,
        channel_group_names: list[str],
        last_seen_id: Optional[int],
        web_socket_id: Optional[str],
    ) -> tuple[bool, int]:
        """
        Check whether any relevant events exist since ``last_seen_id``.

        Used for the baseline path (``last_seen_id=None``) to return the
        current latest event id without replay.

        :param user_id: The id of the reconnecting user.
        :param channel_group_names: Channel group names from
            ``get_channel_group_names``.
        :param last_seen_id: Highest event id the client has already processed,
            or ``None`` for a baseline check.
        :param web_socket_id: The client's persistent web socket id, used to
            exclude events the client itself originated.
        :returns: ``(outdated, current_latest_id)`` tuple.
        """

        from baserow.ws.models import RealtimeEvent

        current_latest_id = RealtimeEvent.objects.aggregate(
            latest=Coalesce(Max("id"), 0)
        )["latest"]

        if last_seen_id is None:
            return False, current_latest_id

        page_group_names = [name for name in channel_group_names if name != "users"]
        has_users_group = "users" in channel_group_names

        base_q = Q(id__gt=last_seen_id)
        conditions = Q()

        if page_group_names:
            conditions |= Q(channel_group__in=page_group_names)

        if has_users_group:
            user_id_str = str(user_id)
            user_q = Q(channel_group="users") & (
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
                        "payload_map": {user_id_str: {}},
                    },
                )
            )
            conditions |= user_q

        if not conditions:
            return False, current_latest_id

        qs = RealtimeEvent.objects.filter(base_q & conditions)
        if web_socket_id is not None:
            qs = qs.exclude(payload__ignore_web_socket_id=web_socket_id)

        return qs.exists(), current_latest_id
