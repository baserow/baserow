from unittest.mock import AsyncMock, Mock, patch

import pytest
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.ws.auth import ANONYMOUS_USER_TOKEN
from baserow.ws.consumers import CoreConsumer, PageContext, PageScope, SubscribedPages
from baserow.ws.presence import PresenceHandler
from baserow.ws.realtime_events import FIRST_CONNECT_CURSOR, NO_REPLAY_AVAILABLE
from baserow.ws.registries import PageType, page_registry


class AcceptingTestPageType(PageType):
    type = "test_page_type"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-page-{test_param}"

    def get_permission_channel_group_name(self, test_param, **kwargs):
        return f"permissions-test-page-{test_param}"


class NotAcceptingTestPageType(AcceptingTestPageType):
    type = "test_page_type_not_accepting"

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return False


class DifferentPermissionsGroupTestPageType(PageType):
    type = "diff_perm_page_type"
    parameters = ["test_param"]

    def get_group_name(self, test_param, **kwargs):
        return f"different-perm-group-{test_param}"

    def get_permission_channel_group_name(self, test_param, **kwargs):
        return f"permissions-different-perm-group-{test_param}"


@pytest.fixture
def test_page_types():
    page_types = (
        AcceptingTestPageType(),
        NotAcceptingTestPageType(),
        DifferentPermissionsGroupTestPageType(),
    )
    page_registry.register(page_types[0])
    page_registry.register(page_types[1])
    page_registry.register(page_types[2])
    yield page_types
    page_registry.unregister(AcceptingTestPageType.type)
    page_registry.unregister(NotAcceptingTestPageType.type)
    page_registry.unregister(DifferentPermissionsGroupTestPageType.type)


# Core consumer


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_connect_not_authenticated(data_fixture):
    communicator = WebsocketCommunicator(
        application,
        "ws/core/?jwt_token=",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, subprotocol = await communicator.connect()
    assert connected is True

    response = await communicator.receive_json_from()
    assert response["type"] == "authentication"
    assert response["success"] is False
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_connect_authenticated(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, subprotocol = await communicator.connect()
    assert connected is True

    response = await communicator.receive_json_from()
    assert response["type"] == "authentication"
    assert response["success"] is True
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_connect_authenticated_anonymous(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={ANONYMOUS_USER_TOKEN}&web_socket_id=ws-anon",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, subprotocol = await communicator.connect()
    assert connected is True

    response = await communicator.receive_json_from()
    assert response["type"] == "authentication"
    assert response["success"] is True
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_add_to_page_success(data_fixture, test_page_types):
    user_1, token_1 = data_fixture.create_user_and_token()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await communicator.send_json_to({"page": "test_page_type", "test_param": 1})
    response = await communicator.receive_json_from(timeout=0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "test_page_type"
    assert response["parameters"]["test_param"] == 1

    # Adding again will have the same behavior
    # but the page will still be subscribed only once
    await communicator.send_json_to({"page": "test_page_type", "test_param": 1})
    response = await communicator.receive_json_from(timeout=0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "test_page_type"
    assert response["parameters"]["test_param"] == 1

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_add_page_doesnt_exist(data_fixture):
    # When trying to subscribe to not existing page
    # we do not expect the confirmation
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={ANONYMOUS_USER_TOKEN}&web_socket_id=ws-anon",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await communicator.send_json_to({"page": "doesnt_exist", "test_param": 1})
    assert communicator.output_queue.qsize() == 0
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_add_to_page_failure(data_fixture, test_page_types):
    user_1, token_1 = data_fixture.create_user_and_token()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    # Page that will return False from can_add()
    # won't send the confirmation
    await communicator.send_json_to(
        {"page": "test_page_type_not_accepting", "test_param": 1}
    )
    assert communicator.output_queue.qsize() == 0

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_remove_page_success(data_fixture, test_page_types):
    user_1, token_1 = data_fixture.create_user_and_token()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await communicator.send_json_to({"page": "test_page_type", "test_param": 1})
    response = await communicator.receive_json_from(timeout=0.1)

    await communicator.send_json_to({"remove_page": "test_page_type", "test_param": 1})
    response = await communicator.receive_json_from(timeout=0.1)

    assert response["type"] == "page_discard"
    assert response["page"] == "test_page_type"
    assert response["parameters"]["test_param"] == 1

    # Removing a page will send a confirmation again
    # even if it is unsubscribed already
    await communicator.send_json_to({"remove_page": "test_page_type", "test_param": 1})
    response = await communicator.receive_json_from(timeout=0.1)

    assert response["type"] == "page_discard"
    assert response["page"] == "test_page_type"
    assert response["parameters"]["test_param"] == 1

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_remove_page_doesnt_exist(data_fixture):
    # When trying to unsubscribe from not existing page
    # we do not expect the confirmation
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={ANONYMOUS_USER_TOKEN}&web_socket_id=ws-anon",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await communicator.send_json_to({"page_remove": "doesnt_exist", "test_param": 1})
    assert communicator.output_queue.qsize() == 0
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_get_page_context(data_fixture, test_page_types):
    page_type = test_page_types[0]
    user_1, token_1 = data_fixture.create_user_and_token()
    consumer = CoreConsumer()
    consumer.scope = {}
    consumer.scope["user"] = user_1
    consumer.scope["web_socket_id"] = 234
    content = {
        "page": page_type.type,
        "test_param": 2,
    }
    result = await consumer._get_page_context(content, "page")
    assert result == PageContext(
        resolved_page_type=page_type,
        page_scope=PageScope(
            page_type=page_type.type, page_parameters={"test_param": 2}
        ),
        user=user_1,
        web_socket_id=234,
    )

    # Not existing page type
    content = {
        "page": "doesnt_exist",
        "test_param": 2,
    }
    result = await consumer._get_page_context(content, "page")
    assert result is None

    # Missing user
    consumer.scope["user"] = None
    content = {
        "page": page_type.type,
        "test_param": 2,
    }
    result = await consumer._get_page_context(content, "page")
    assert result is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_remove_all_page_scopes(data_fixture, test_page_types):
    user_1, token_1 = data_fixture.create_user_and_token()
    scope_1 = PageScope("test_page_type", {"test_param": 1})
    scope_2 = PageScope("test_page_type", {"test_param": 2})
    pages = SubscribedPages()
    pages.add(scope_1)
    pages.add(scope_2)

    consumer = CoreConsumer()
    consumer.scope = {"pages": pages, "user": user_1, "web_socket_id": "ws-test"}
    consumer.channel_name = "test_channel_name"
    consumer.channel_layer = AsyncMock()
    consumer.presence = PresenceHandler(
        consumer=consumer,
        web_socket_id="ws-test",
        user_id=user_1.id,
    )

    async def base_send(message):
        pass

    consumer.base_send = base_send

    assert len(consumer.scope["pages"]) == 2

    await consumer._remove_all_page_scopes()

    assert len(consumer.scope["pages"]) == 0


# SubscribedPages


@pytest.mark.websockets
@pytest.mark.parametrize(
    "last_seen_id,expected",
    [
        # Missing or invalid input falls back to the safe baseline cursor.
        ({}, FIRST_CONNECT_CURSOR),
        ({"last_seen_id": None}, FIRST_CONNECT_CURSOR),
        ({"last_seen_id": "abc"}, FIRST_CONNECT_CURSOR),
        # Anything below NO_REPLAY_AVAILABLE is clamped to the baseline.
        ({"last_seen_id": -3}, FIRST_CONNECT_CURSOR),
        # The two sentinels and positive ids are passed through verbatim.
        ({"last_seen_id": FIRST_CONNECT_CURSOR}, FIRST_CONNECT_CURSOR),
        ({"last_seen_id": NO_REPLAY_AVAILABLE}, NO_REPLAY_AVAILABLE),
        ({"last_seen_id": 42}, 42),
        ({"last_seen_id": "42"}, 42),
    ],
)
def test_parse_last_seen_id(last_seen_id, expected):
    assert CoreConsumer._parse_last_seen_id(last_seen_id) == expected


@pytest.mark.websockets
def test_subscribed_pages_adds_page_without_duplicates():
    scope_1 = PageScope("test_page_type", {"test_param": 1})
    scope_2 = PageScope("test_page_type", {"test_param": 2})
    scope_3 = PageScope("test_page_type_not_accepting", {"test_param": 1})
    scope_4 = PageScope("test_page_type", {"test_param": 1})
    pages = SubscribedPages()

    pages.add(scope_1)
    pages.add(scope_2)
    pages.add(scope_3)
    pages.add(scope_4)

    assert len(pages) == 3


@pytest.mark.websockets
def test_subscribed_pages_removes_pages_by_parameters():
    scope_1 = PageScope("test_page_type", {"test_param": 1})
    scope_2 = PageScope("test_page_type", {"test_param": 2})
    scope_3 = PageScope("test_page_type", {"test_param": 3})
    pages = SubscribedPages()

    pages.add(scope_1)
    pages.add(scope_2)
    pages.add(scope_3)

    assert len(pages) == 3

    pages.remove(scope_2)

    assert scope_1 in pages.pages
    assert scope_2 not in pages.pages
    assert scope_3 in pages.pages


@pytest.mark.websockets
def test_subscribed_pages_removes_pages_without_error():
    scope_1 = PageScope("test_page_type", {"test_param": 1})
    scope_2 = PageScope("test_page_type", {"test_param": 2})
    pages = SubscribedPages()

    pages.add(scope_1)
    pages.add(scope_2)

    assert len(pages) == 2

    # should not throw error
    pages.remove(scope_1)
    pages.remove(scope_1)
    pages.remove(scope_2)
    pages.remove(scope_2)

    assert len(pages) == 0


@pytest.mark.websockets
def test_subscribed_pages_is_page_in_permission_group(test_page_types):
    scope_1 = PageScope("test_page_type", {"test_param": 1})
    pages = SubscribedPages()

    assert pages.is_page_in_permission_group(scope_1, "permissions-test-page-1") is True
    assert (
        pages.is_page_in_permission_group(scope_1, "permissions-different-perm-group-1")
        is False
    )


@pytest.mark.websockets
def test_subscribed_pages_has_pages_with_permission_group(test_page_types):
    scope_1 = PageScope("test_page_type", {"test_param": 1})
    pages = SubscribedPages()
    pages.add(scope_1)

    assert pages.has_pages_with_permission_group("permissions-test-page-1") is True
    assert (
        pages.has_pages_with_permission_group("permissions-different-perm-group-1")
        is False
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.websockets
@pytest.mark.parametrize(
    "ignore_web_socket_id, web_socket_id, user, exclude_user_ids, expect_call",
    [
        # Sending the message is expected:
        # ...because `ignore_web_socket_id` is empty:
        (None, "some_web_socket_id", Mock(id=1), [], True),
        # ...or when socket_ids are not matching and user ID is not exluded:
        ("some_web_socket_id", "another_web_socket_id", Mock(id=1), [], True),
        # ...or when `ignore_web_socket_id` is empty and the user is not excluded:
        (None, "some_web_socket_id", Mock(id=1), [2], True),
        # Sending the message is NOT expected:
        # ...because web socket IDs are matching and should be ignored:
        ("some_web_socket_id", "some_web_socket_id", Mock(id=1), [], False),
        # ...or when user_id is exluded:
        (None, "some_web_socket_id", Mock(id=1), [1], False),
        # ...or when user ID is excluded (within multiple IDs):
        (None, "some_web_socket_id", Mock(id=1), [1, 2], False),
        # ...or when user ID is excluded (within multiple IDs) and web socket
        # IDs are not matching:
        ("some_web_socket_id", "another_web_socket_id", Mock(id=1), [1, 2], False),
    ],
)
async def test_core_consumer_broadcast_to_group(
    data_fixture,
    test_page_types,
    ignore_web_socket_id,
    web_socket_id,
    user,
    exclude_user_ids,
    expect_call,
):
    consumer = CoreConsumer()

    # Mock the required attributes and methods
    consumer.scope = {
        "web_socket_id": web_socket_id,
        "user": user,
    }
    event = {
        "payload": {
            "message": "test message",
        },
        "ignore_web_socket_id": ignore_web_socket_id,
        "exclude_user_ids": exclude_user_ids,
    }

    mock_send_json = AsyncMock()

    consumer.send_json = mock_send_json
    await consumer.broadcast_to_group(event)

    if expect_call:
        mock_send_json.assert_called_once_with(event["payload"])
    else:
        mock_send_json.assert_not_called()


def test_bucket_close_code():
    from baserow.ws.consumers import _bucket_close_code

    assert _bucket_close_code(1011) == "1011"
    assert _bucket_close_code(1001) == "1001"
    # Application/unknown codes collapse to "other" to bound label cardinality.
    assert _bucket_close_code(4999) == "other"
    assert _bucket_close_code(None) == "other"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_core_consumer_records_connection_and_disconnect_metrics(data_fixture):
    from baserow.ws import consumers as ws_consumers

    _, token_1 = data_fixture.create_user_and_token()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}&web_socket_id=ws-1",
        headers=[(b"origin", b"http://localhost")],
    )

    with (
        patch.object(ws_consumers, "websocket_connections_counter") as connections,
        patch.object(ws_consumers, "websocket_disconnects_counter") as disconnects,
    ):
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.receive_json_from()
        connections.add.assert_called_once_with(1)

        await communicator.disconnect(code=1011)
        disconnects.add.assert_called_once_with(1, attributes={"code": "1011"})


@pytest.mark.asyncio
async def test_core_consumer_records_disconnect_metric_when_cleanup_fails():
    from baserow.ws import consumers as ws_consumers

    consumer = CoreConsumer()
    consumer.channel_name = "test_channel_name"
    consumer.channel_layer = AsyncMock()
    # A Redis hiccup during cleanup must not swallow the disconnect metric.
    consumer.channel_layer.group_discard.side_effect = RuntimeError("redis down")
    consumer._remove_all_page_scopes = AsyncMock()

    with patch.object(ws_consumers, "websocket_disconnects_counter") as disconnects:
        with pytest.raises(RuntimeError):
            await consumer.disconnect(code=1006)

    disconnects.add.assert_called_once_with(1, attributes={"code": "1006"})
