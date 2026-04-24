from collections import defaultdict
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from baserow.ws.models import RealtimeEvent

REALTIME_EVENTS_CLEANUP_INTERVAL_MINUTES = 60


def record_realtime_event(channel_group: str, payload: dict) -> int:
    """
    Insert one row into ``ws_realtime_events`` and return its id.
    """

    row = RealtimeEvent.objects.create(
        channel_group=channel_group,
        payload=payload,
    )
    return row.id


def record_realtime_events_bulk(
    events: list[tuple[str, dict]],
) -> list[int]:
    """
    Insert multiple rows into ``ws_realtime_events`` in a single query
    and return their ids in the same order as the input.
    """

    objects = [
        RealtimeEvent(channel_group=channel_group, payload=payload)
        for channel_group, payload in events
    ]
    created = RealtimeEvent.objects.bulk_create(objects)
    return [obj.id for obj in created]


def cleanup_old_realtime_events(retention_hours: int) -> int:
    """
    Delete ``RealtimeEvent`` rows older than ``retention_hours``.
    Returns number of rows deleted.
    """

    if not retention_hours or retention_hours <= 0:
        return 0
    cutoff = timezone.now() - timedelta(hours=retention_hours)
    deleted, _ = RealtimeEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted


def get_channel_group_names(pages, authenticated: bool = True) -> list[tuple[str, str]]:
    """
    Derive ``(channel_group_name, category)`` pairs from a
    ``SubscribedPages`` instance. Category is the page type string
    (e.g. ``"table"``, ``"dashboard"``). Appends the ``"users"``
    group only for authenticated connections.
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


def get_replay_events(
    user_id: int,
    channel_group_names: list[tuple[str, str]],
    last_seen_id: int,
    previous_web_socket_id: Optional[str],
) -> Optional[list[RealtimeEvent]]:
    """
    Fetch events for replay on reconnect.

    Returns an ordered list of ``RealtimeEvent`` rows if replay is possible
    (total count ≤ ``settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS`` and ``last_seen_id`` still
    exists in the table). Returns ``None`` for the degraded path (too many
    events or retention expired).

    The ``"users"`` group is filtered to only include events relevant to
    ``user_id``, preventing unrelated user events from inflating the count.
    """

    if not RealtimeEvent.objects.filter(id=last_seen_id).exists():
        return None

    page_group_names = [name for name, cat in channel_group_names if cat != "users"]
    has_users_group = any(cat == "users" for _, cat in channel_group_names)

    querysets = []

    if page_group_names:
        qs = RealtimeEvent.objects.filter(
            channel_group__in=page_group_names,
            id__gt=last_seen_id,
        )
        if previous_web_socket_id is not None:
            qs = qs.exclude(payload__ignore_web_socket_id=previous_web_socket_id)
        querysets.append(qs)

    if has_users_group:
        user_id_str = str(user_id)
        qs = RealtimeEvent.objects.filter(
            channel_group="users",
            id__gt=last_seen_id,
        ).filter(
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
        if previous_web_socket_id is not None:
            qs = qs.exclude(payload__ignore_web_socket_id=previous_web_socket_id)
        querysets.append(qs)

    combined = (
        querysets[0].union(*querysets[1:])
        if querysets
        else RealtimeEvent.objects.none()
    )
    max_events = settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS
    result = list(combined.order_by("id")[:max_events])
    if len(result) >= max_events:
        return None

    return result


def check_realtime_events(
    user_id: int,
    channel_group_names: list[tuple[str, str]],
    last_seen_id: Optional[int],
    previous_web_socket_id: Optional[str],
) -> tuple[dict[str, bool], int]:
    """
    Check which categories have new events since ``last_seen_id``.

    Returns ``(staleness_map, current_latest_id)`` where staleness_map
    is ``{"users": True, "table": False, ...}`` keyed by category.

    Two queries: one for all PageType groups, one for the ``"users"``
    group (needs user-specific JSON filtering).
    """

    page_groups: dict[str, list[str]] = defaultdict(list)
    has_users_group = False

    for group_name, category in channel_group_names:
        if category == "users":
            has_users_group = True
        else:
            page_groups[category].append(group_name)

    all_categories = set(page_groups.keys())
    if has_users_group:
        all_categories.add("users")

    current_latest_id = RealtimeEvent.objects.aggregate(latest=Coalesce(Max("id"), 0))[
        "latest"
    ]

    if last_seen_id is None:
        return {cat: False for cat in all_categories}, current_latest_id

    staleness_map: dict[str, bool] = {}

    # --- Query 1: PageType groups ---
    if page_groups:
        all_group_names = []
        for names in page_groups.values():
            all_group_names.extend(names)

        qs = RealtimeEvent.objects.filter(
            channel_group__in=all_group_names,
            id__gt=last_seen_id,
        )
        if previous_web_socket_id is not None:
            qs = qs.exclude(payload__ignore_web_socket_id=previous_web_socket_id)

        stale_groups = set(qs.values_list("channel_group", flat=True).distinct())

        group_to_category = {}
        for category, names in page_groups.items():
            for name in names:
                group_to_category[name] = category

        stale_categories = {
            group_to_category[g] for g in stale_groups if g in group_to_category
        }
        for category in page_groups:
            staleness_map[category] = category in stale_categories

    # --- Query 2: "users" group ---
    if has_users_group:
        qs = RealtimeEvent.objects.filter(
            channel_group="users",
            id__gt=last_seen_id,
        )
        if previous_web_socket_id is not None:
            qs = qs.exclude(payload__ignore_web_socket_id=previous_web_socket_id)

        user_id_str = str(user_id)
        staleness_map["users"] = qs.filter(
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
        ).exists()

    return staleness_map, current_latest_id
