import dataclasses
from functools import cache

from django.conf import settings

from loguru import logger

from baserow.core.cache import local_cache

TABLE_GROUP_PREFIX = "table-"


@dataclasses.dataclass(frozen=True)
class TableRealtimeListeners:
    """
    Describes which kinds of listeners could consume realtime row payloads of
    a table, so expensive serialization can be skipped when nobody would ever
    receive it.
    """

    # Whether the table page channel group has at least one subscribed
    # websocket client (or the presence check isn't supported, in which case
    # this is True to fail open).
    ws_table_subscribers: bool
    # Whether any view of the table requires realtime events when shared.
    has_realtime_views: bool
    # Whether an active webhook on the table, or on a table linking to it,
    # could consume the payloads.
    has_webhooks: bool

    @property
    def any(self) -> bool:
        return self.ws_table_subscribers or self.has_realtime_views or self.has_webhooks


@cache
def _zcard_subscriber_check_supported() -> bool:
    """
    The subscriber presence check reads the group ZSET maintained by
    channels_redis' classic RedisChannelLayer directly from Redis. It's only
    safe when that exact backend is configured with a single host reachable
    through the django_redis "default" connection; the pubsub variant keeps no
    group keys at all, so checking there would wrongly report zero
    subscribers and drop events.
    """

    if not getattr(settings, "REALTIME_SUBSCRIBER_GATE", True):
        return False
    try:
        channel_layer = settings.CHANNEL_LAYERS["default"]
        if channel_layer["BACKEND"] != "channels_redis.core.RedisChannelLayer":
            return False
        hosts = channel_layer["CONFIG"]["hosts"]
        if len(hosts) != 1:
            return False
        redis_cache_location = settings.CACHES["default"]["LOCATION"]
        return hosts[0] == redis_cache_location
    except (KeyError, TypeError):
        return False


def group_has_subscribers(group_name: str) -> bool:
    """
    Returns whether the channel layer group has at least one subscribed
    channel. Fails open: any unsupported configuration or Redis error reports
    True, so a broadcast can never be wrongly skipped for a live subscriber.
    Stale members of ungracefully disconnected clients only cause false
    positives until channels_redis' group_expiry prunes them.

    :param group_name: The channel layer group name, e.g. `table-42`.
    :return: True when the group (possibly) has subscribers.
    """

    if not _zcard_subscriber_check_supported():
        return True
    try:
        from channels.layers import get_channel_layer
        from django_redis import get_redis_connection

        prefix = get_channel_layer().prefix
        redis = get_redis_connection("default")
        return redis.zcard(f"{prefix}:group:{group_name}") > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("Realtime subscriber check failed, failing open: {}", exc)
        return True


def table_group_has_ws_subscribers(table_id: int) -> bool:
    """
    Returns whether the table page channel group of the given table has at
    least one subscribed websocket client, memoized per request/task. When
    event recording for reconnect replay is enabled, this always returns True
    because recorded events must exist regardless of current subscribers.

    :param table_id: The id of the table to check the channel group of.
    :return: True when the group (possibly) has subscribers.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    if RealtimeEventHandler.is_recording_enabled():
        return True

    return local_cache.get(
        f"ws_table_subscribers_{table_id}",
        lambda: group_has_subscribers(f"{TABLE_GROUP_PREFIX}{table_id}"),
    )


def get_table_realtime_listeners(table, model=None) -> TableRealtimeListeners:
    """
    Returns which kinds of listeners could consume realtime row payloads of
    the given table, memoized per request/task so every gate in one request
    sees a consistent answer. When event recording for reconnect replay is
    enabled everything reports True, keeping the replay stream complete.

    :param table: The table the row payloads belong to.
    :param model: Optionally the generated model of the table, used to find
        the tables linking to this one without extra queries.
    :return: The listeners of the table.
    """

    from baserow.ws.realtime_events import RealtimeEventHandler

    if RealtimeEventHandler.is_recording_enabled():
        return TableRealtimeListeners(True, True, True)

    return local_cache.get(
        f"realtime_listeners_table_{table.id}",
        lambda: _compute_table_realtime_listeners(table, model),
    )


def _compute_table_realtime_listeners(table, model) -> TableRealtimeListeners:
    return TableRealtimeListeners(
        ws_table_subscribers=group_has_subscribers(f"{TABLE_GROUP_PREFIX}{table.id}"),
        has_realtime_views=_has_realtime_views(table),
        has_webhooks=_has_webhooks(table, model),
    )


def _has_realtime_views(table) -> bool:
    from django.db.models import Q

    from baserow.contrib.database.ws.views.rows.registries import (
        view_realtime_rows_registry,
    )

    combined_q = Q()
    for realtime_rows_type in view_realtime_rows_registry.get_all():
        combined_q |= realtime_rows_type.get_views_filter()
    return table.view_set.filter(combined_q).exists()


def _has_webhooks(table, model=None) -> bool:
    from baserow.contrib.database.webhooks.models import TableWebhook

    # Webhooks on tables linking to this one consume the serialized old rows
    # too, to detect which of their rows had link values changed.
    table_ids = {table.id}
    if model is None:
        model = table.get_model()
    for field_object in model._field_objects.values():
        field = field_object["field"]
        link_row_table_id = getattr(field, "link_row_table_id", None)
        if link_row_table_id is not None:
            table_ids.add(link_row_table_id)
    return TableWebhook.objects.filter(table_id__in=table_ids, active=True).exists()
