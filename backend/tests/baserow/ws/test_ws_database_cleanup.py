from threading import get_ident
from time import monotonic
from unittest.mock import AsyncMock

from django.db import InterfaceError, connection, connections

import pytest
from asgiref.sync import ThreadSensitiveContext, sync_to_async
from channels.exceptions import StopConsumer

from baserow.ws import auth
from baserow.ws.consumers import CoreConsumer, SubscribedPages
from baserow.ws.presence import NullPresenceHandler, PresenceHandler
from baserow.ws.registries import page_registry


def _open_expired_connection():
    connection.ensure_connection()
    connection.close_at = monotonic() - 1
    return connection.connection


def _current_connection():
    return connection.connection


def _consumer(user=None):
    consumer = CoreConsumer()
    consumer.scope = {
        "user": user,
        "web_socket_id": "cleanup-test",
        "pages": SubscribedPages(),
    }
    consumer.channel_name = "cleanup-channel"
    consumer.channel_layer = AsyncMock()
    consumer.send_json = AsyncMock()
    consumer.presence = NullPresenceHandler()
    return consumer


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@pytest.mark.parametrize("boundary", ["authentication", "page", "presence"])
@pytest.mark.parametrize("database_error", [False, True], ids=["success", "error"])
async def test_ws_orm_boundaries_clean_actual_thread_connection(
    data_fixture, settings, monkeypatch, boundary, database_error
):
    settings.BASEROW_CACHE_TTL_SECONDS = 0
    settings.CACHALOT_ENABLED = False
    # Keep healthy connections open so cleanup must react to the actual expired
    # or unusable connection, rather than relying on CONN_MAX_AGE=0 in tests.
    monkeypatch.setitem(connection.settings_dict, "CONN_MAX_AGE", None)
    monkeypatch.setitem(connection.settings_dict, "CONN_HEALTH_CHECKS", False)
    user, token = data_fixture.create_user_and_token()
    consumer = _consumer(user)

    if boundary == "authentication":
        target, method_name = auth, "_get_authenticated_user"

        async def call_boundary():
            assert (await auth.get_user(token)).id == user.id

    elif boundary == "page":
        table = data_fixture.create_database_table(user=user)
        target, method_name = page_registry.get("table"), "can_add"

        async def call_boundary():
            await consumer._add_page_scope({"page": "table", "table_id": table.id})
            consumer.send_json.assert_awaited_once_with(
                {
                    "type": "page_add",
                    "page": "table",
                    "parameters": {"table_id": table.id},
                }
            )

    else:
        view = data_fixture.create_grid_view(user=user, public=True)
        target, method_name = page_registry.get("view"), "get_presence_space_name"

        async def call_boundary():
            assert (
                await PresenceHandler.resolve_space_name("view", {"slug": view.slug})
                == f"table-{view.table_id}"
            )

    real_operation = getattr(target, method_name)
    event_loop_thread = get_ident()
    operation_connections = []

    def check_connection_lifecycle(*args, **kwargs):
        assert get_ident() != event_loop_thread
        assert expired_connection.closed
        assert connection.connection is None

        # Exercise the real auth/permission/public-view query, not an adapter mock.
        result = real_operation(*args, **kwargs)
        operation_connection = connection.connection
        assert operation_connection is not None
        assert operation_connection is not expired_connection
        operation_connections.append(operation_connection)

        if database_error:
            # Simulate a lost database session. A real driver error marks Django's
            # connection unusable; the adapter must clean it in its finally block.
            operation_connection.close()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            pytest.fail("A closed database session unexpectedly accepted a query")

        connection.close_at = monotonic() - 1
        return result

    monkeypatch.setattr(target, method_name, check_connection_lifecycle)
    async with ThreadSensitiveContext():
        # Raw sync_to_async deliberately performs no cleanup itself. Seeding and
        # inspecting use the exact thread-local connection the real boundary owns.
        expired_connection = await sync_to_async(_open_expired_connection)()
        try:
            if database_error:
                with pytest.raises(InterfaceError):
                    await call_boundary()
            else:
                await call_boundary()

            assert len(operation_connections) == 1
            assert operation_connections[0].closed
            assert await sync_to_async(_current_connection)() is None
        finally:
            await sync_to_async(connections.close_all)()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_ws_disconnect_preserves_channels_final_connection_cleanup():
    consumer = _consumer()
    async with ThreadSensitiveContext():
        expired_connection = await sync_to_async(_open_expired_connection)()
        try:
            with pytest.raises(StopConsumer):
                await consumer.dispatch({"type": "websocket.disconnect", "code": 1000})

            assert expired_connection.closed
            assert await sync_to_async(_current_connection)() is None
        finally:
            await sync_to_async(connections.close_all)()
