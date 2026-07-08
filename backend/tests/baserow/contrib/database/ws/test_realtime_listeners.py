from unittest.mock import MagicMock, patch

from django.test.utils import override_settings

import pytest

from baserow.contrib.database.ws.realtime_listeners import (
    _zcard_subscriber_check_supported,
    get_table_realtime_listeners,
    group_has_subscribers,
    table_group_has_ws_subscribers,
)

REDIS_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": ["redis://redis:6379"]},
    }
}
REDIS_CACHES_LOCATION = "redis://redis:6379"


@pytest.fixture(autouse=True)
def clear_support_cache():
    _zcard_subscriber_check_supported.cache_clear()
    yield
    _zcard_subscriber_check_supported.cache_clear()


def test_group_has_subscribers_fails_open_with_unsupported_channel_layer(settings):
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }
    assert group_has_subscribers("table-1") is True


def test_group_has_subscribers_fails_open_when_gate_disabled(settings):
    settings.REALTIME_SUBSCRIBER_GATE = False
    settings.CHANNEL_LAYERS = REDIS_CHANNEL_LAYERS
    assert group_has_subscribers("table-1") is True


def test_group_has_subscribers_fails_open_with_multiple_hosts(settings):
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": ["redis://a", "redis://b"]},
        }
    }
    assert group_has_subscribers("table-1") is True


def test_group_has_subscribers_fails_open_with_mismatched_redis(settings):
    settings.CHANNEL_LAYERS = REDIS_CHANNEL_LAYERS
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "somewhere-else",
        }
    }
    assert group_has_subscribers("table-1") is True


def _supported_settings(settings):
    settings.CHANNEL_LAYERS = REDIS_CHANNEL_LAYERS
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": REDIS_CACHES_LOCATION,
        }
    }


def test_group_has_subscribers_reads_the_channels_group_zset(settings):
    _supported_settings(settings)
    redis = MagicMock()
    redis.zcard.return_value = 0
    channel_layer = MagicMock(prefix="asgi")
    with (
        patch("django_redis.get_redis_connection", return_value=redis),
        patch("channels.layers.get_channel_layer", return_value=channel_layer),
    ):
        assert group_has_subscribers("table-42") is False
    redis.zcard.assert_called_once_with("asgi:group:table-42")

    redis.zcard.return_value = 2
    with (
        patch("django_redis.get_redis_connection", return_value=redis),
        patch("channels.layers.get_channel_layer", return_value=channel_layer),
    ):
        assert group_has_subscribers("table-42") is True


def test_group_has_subscribers_fails_open_on_redis_errors(settings):
    _supported_settings(settings)
    with patch("django_redis.get_redis_connection", side_effect=Exception("down")):
        assert group_has_subscribers("table-1") is True


@override_settings(BASEROW_REALTIME_REPLAY_MAX_EVENTS=10)
def test_recording_enabled_reports_all_listeners():
    table = MagicMock(id=1)
    listeners = get_table_realtime_listeners(table)
    assert listeners.ws_table_subscribers is True
    assert listeners.has_realtime_views is True
    assert listeners.has_webhooks is True
    assert table_group_has_ws_subscribers(1) is True


@pytest.mark.django_db
def test_get_table_realtime_listeners_detects_webhooks_on_linked_tables(
    settings, data_fixture
):
    _supported_settings(settings)
    settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS = 0
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    other_table = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_link_row_field(
        table=table, link_row_table=other_table, name="link"
    )

    with patch(
        "baserow.contrib.database.ws.realtime_listeners.group_has_subscribers",
        return_value=False,
    ):
        listeners = get_table_realtime_listeners(table)
        assert listeners.any is False

        # A webhook on the LINKED table consumes the serialized old rows of
        # this table to detect link value changes, so it must count.
        data_fixture.create_table_webhook(table=other_table, user=user, active=True)
        from baserow.core.cache import local_cache

        local_cache.delete(f"realtime_listeners_table_{table.id}")
        listeners = get_table_realtime_listeners(table)
        assert listeners.has_webhooks is True
        assert listeners.any is True


@pytest.mark.django_db
def test_row_update_skips_realtime_serialization_without_listeners(
    settings, data_fixture
):
    from baserow.contrib.database.rows.handler import RowHandler

    settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS = 0
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="text")
    model = table.get_model()
    row = model.objects.create(**{field.db_column: "a"})

    no_listeners = patch(
        "baserow.contrib.database.ws.realtime_listeners.group_has_subscribers",
        return_value=False,
    )
    serialize = patch(
        "baserow.contrib.database.ws.rows.signals.native_serialize_rows",
    )
    broadcast = patch(
        "baserow.ws.registries.PageType.broadcast",
    )
    with no_listeners, serialize as serialize_mock, broadcast as broadcast_mock:
        RowHandler().update_rows(user, table, [{"id": row.id, field.db_column: "b"}])
    serialize_mock.assert_not_called()
    broadcast_mock.assert_not_called()
    row.refresh_from_db()
    assert getattr(row, field.db_column) == "b"


@pytest.mark.django_db
def test_row_update_broadcasts_when_subscribers_exist(settings, data_fixture):
    from baserow.contrib.database.rows.handler import RowHandler

    settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS = 0
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="text")
    model = table.get_model()
    row = model.objects.create(**{field.db_column: "a"})

    has_listeners = patch(
        "baserow.contrib.database.ws.realtime_listeners.group_has_subscribers",
        return_value=True,
    )
    broadcast = patch("baserow.ws.registries.PageType.broadcast")
    with has_listeners, broadcast as broadcast_mock, transaction_on_commit_now():
        RowHandler().update_rows(user, table, [{"id": row.id, field.db_column: "b"}])
    assert broadcast_mock.called


def transaction_on_commit_now():
    from unittest.mock import patch as _patch

    from django.db import transaction

    return _patch.object(
        transaction, "on_commit", side_effect=lambda func, using=None: func()
    )
