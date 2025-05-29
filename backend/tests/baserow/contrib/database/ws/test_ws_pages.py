from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser

import pytest
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.ws.auth import ANONYMOUS_USER_TOKEN
from baserow.ws.registries import page_registry

# TablePageType


@pytest.mark.django_db
@pytest.mark.websockets
def test_table_page_can_add(data_fixture):
    table_page = page_registry.get("table")
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    user_1_websocket_id = 234
    user_2_websocket_id = 235
    anonymous_websocket_id = 123
    table_1 = data_fixture.create_database_table(user=user_1)

    # Success
    table_page.can_add(user_1, user_1_websocket_id, table_1.id) is True

    # Table doesn't exist
    table_page.can_add(user_1, user_1_websocket_id, 999) is False

    # User not in workspace
    table_page.can_add(user_2, user_2_websocket_id, table_1.id) is False

    # Permission denied
    table_page.can_add(AnonymousUser(), anonymous_websocket_id, table_1.id) is False


@pytest.mark.websockets
def test_table_page_get_group_name():
    table_page = page_registry.get("table")
    table_id = 22

    assert table_page.get_group_name(table_id) == "table-22"


@pytest.mark.websockets
def test_table_page_get_permission_channel_group_name():
    table_page = page_registry.get("table")
    table_id = 22

    assert (
        table_page.get_permission_channel_group_name(table_id) == "permissions-table-22"
    )


@patch("baserow.ws.registries.broadcast_to_channel_group")
@pytest.mark.websockets
def test_table_page_broadcast(mock_broadcast_to_channel_group):
    table_page = page_registry.get("table")
    ignore_web_socket_id = 999
    payload = {"sample": "payload"}
    kwargs = {"table_id": 22}

    table_page.broadcast(payload, ignore_web_socket_id, **kwargs)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == "table-22"
    assert args[0][1] == payload
    assert args[0][2] == ignore_web_socket_id


# PublicViewPageType


@pytest.mark.django_db
@pytest.mark.websockets
def test_public_view_page_can_add(data_fixture):
    view_page = page_registry.get("view")
    user_1, token_1 = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user_1)
    public_grid_view = data_fixture.create_grid_view(user_1, table=table_1, public=True)
    non_public_grid_view = data_fixture.create_grid_view(
        user_1, table=table_1, public=False
    )
    public_form_view_which_cant_be_subbed = data_fixture.create_form_view(
        user_1, table=table_1, public=True
    )
    (
        password_protected_grid_view,
        public_view_token,
    ) = data_fixture.create_public_password_protected_grid_view_with_token(  # nosec
        user_1, table=table_1, password="99999999"
    )
    user_2, token_2 = data_fixture.create_user_and_token()
    user_1_websocket_id = 234
    user_2_websocket_id = 235
    anonymous_websocket_id = 123

    # Success
    view_page.can_add(user_1, user_1_websocket_id, public_grid_view.slug) is True
    view_page.can_add(
        AnonymousUser(), anonymous_websocket_id, public_grid_view.slug
    ) is True
    view_page.can_add(
        user_1, user_1_websocket_id, password_protected_grid_view.slug
    ) is True

    # View doesn't exist
    view_page.can_add(user_1, user_1_websocket_id, "non-existing-slug") is False

    # Not a public view
    view_page.can_add(user_1, user_1_websocket_id, non_public_grid_view.slug) is False

    # Some views don't have realtime events
    view_page.can_add(
        user_1, user_1_websocket_id, public_form_view_which_cant_be_subbed.slug
    ) is False
    view_page.can_add(
        AnonymousUser(),
        anonymous_websocket_id,
        public_form_view_which_cant_be_subbed.slug,
    ) is False

    # Not allowed when view is password protected
    view_page.can_add(
        user_2, user_2_websocket_id, password_protected_grid_view.slug
    ) is False
    view_page.can_add(
        AnonymousUser(), anonymous_websocket_id, password_protected_grid_view.slug
    ) is False


@pytest.mark.websockets
def test_public_view_page_get_group_name():
    view_page = page_registry.get("view")
    slug = "public-view-slug"

    assert view_page.get_group_name(slug) == "view-public-view-slug"


@patch("baserow.ws.registries.broadcast_to_channel_group")
@pytest.mark.websockets
def test_public_view_page_broadcast(mock_broadcast_to_channel_group):
    view_page = page_registry.get("view")
    ignore_web_socket_id = 999
    payload = {"sample": "payload"}
    kwargs = {"slug": "public-view-slug"}

    view_page.broadcast(payload, ignore_web_socket_id, **kwargs)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == "view-public-view-slug"
    assert args[0][1] == payload
    assert args[0][2] == ignore_web_socket_id


# RowPageType


@pytest.mark.django_db
@pytest.mark.websockets
def test_row_page_can_add(data_fixture):
    row_page = page_registry.get("row")
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    user_1_websocket_id = 234
    user_2_websocket_id = 235
    anonymous_websocket_id = 123
    table_1 = data_fixture.create_database_table(user=user_1)
    model = table_1.get_model()
    row_1 = model.objects.create()

    # Success
    row_page.can_add(user_1, user_1_websocket_id, table_1.id, row_1.id) is True

    # Row doesn't exist
    row_page.can_add(user_1, user_1_websocket_id, table_1.id, 999) is False

    # Table doesn't exist
    row_page.can_add(user_1, user_1_websocket_id, 999, row_1.id) is False

    # User not in workspace
    row_page.can_add(user_2, user_2_websocket_id, table_1.id, row_1.id) is False

    # Permission denied
    row_page.can_add(
        AnonymousUser(), anonymous_websocket_id, table_1.id, row_1.id
    ) is False


@pytest.mark.websockets
def test_row_page_get_group_name():
    row_page = page_registry.get("row")
    table_id = 22
    row_id = 2
    assert row_page.get_group_name(table_id, row_id) == "table-22-row-2"


@pytest.mark.websockets
def test_row_page_get_permission_channel_group_name():
    row_page = page_registry.get("row")
    table_id = 22
    assert (
        row_page.get_permission_channel_group_name(table_id) == "permissions-table-22"
    )


@patch("baserow.ws.registries.broadcast_to_channel_group")
@pytest.mark.websockets
def test_row_page_broadcast(mock_broadcast_to_channel_group):
    row_page = page_registry.get("row")
    ignore_web_socket_id = 999
    payload = {"sample": "payload"}
    kwargs = {"table_id": 22, "row_id": 2}

    row_page.broadcast(payload, ignore_web_socket_id, **kwargs)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == "table-22-row-2"
    assert args[0][1] == payload
    assert args[0][2] == ignore_web_socket_id


# Integration tests via CoreConsumer


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_join_view_page_as_anonymous_user(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user_1)
    public_grid_view = data_fixture.create_grid_view(user_1, table=table_1, public=True)
    non_public_grid_view = data_fixture.create_grid_view(
        user_1, table=table_1, public=False
    )
    public_form_view_which_cant_be_subbed = data_fixture.create_form_view(
        user_1, table=table_1, public=True
    )
    (
        password_protected_grid_view,
        public_view_token,
    ) = data_fixture.create_public_password_protected_grid_view_with_token(  # nosec
        user_1, table=table_1, password="99999999"
    )

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={ANONYMOUS_USER_TOKEN}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    await communicator_1.receive_json_from()

    # Join the public view page.
    await communicator_1.send_json_to({"page": "view", "slug": public_grid_view.slug})
    response = await communicator_1.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "view"
    assert response["parameters"]["slug"] == public_grid_view.slug

    # Cant join a table page.
    await communicator_1.send_json_to({"page": "table", "table_id": table_1.id})
    assert communicator_1.output_queue.qsize() == 0

    # Can't join a non public grid view page
    await communicator_1.send_json_to(
        {"page": "view", "slug": non_public_grid_view.slug}
    )
    assert communicator_1.output_queue.qsize() == 0

    # Can't join a public form view page as it has
    # `FormViewTypewhen_shared_publicly_requires_realtime_events=False`
    await communicator_1.send_json_to(
        {"page": "view", "slug": public_form_view_which_cant_be_subbed.slug}
    )
    assert communicator_1.output_queue.qsize() == 0

    # Can't join an invalid view page
    await communicator_1.send_json_to({"page": "view", "slug": "invalid slug"})
    assert communicator_1.output_queue.qsize() == 0

    # Can't join a view page without a slug
    await communicator_1.send_json_to({"page": "view"})
    assert communicator_1.output_queue.qsize() == 0

    # Can't join an invalid page
    await communicator_1.send_json_to({"page": ""})
    assert communicator_1.output_queue.qsize() == 0

    # Can't join a password protected view page without a token
    await communicator_1.send_json_to(
        {"page": "view", "slug": password_protected_grid_view.slug}
    )
    assert communicator_1.output_queue.qsize() == 0

    # Can't join a password protected view page with an invalid token
    await communicator_1.send_json_to(
        {
            "page": "view",
            "slug": password_protected_grid_view.slug,
            "token": "invalid token",
        }
    )
    assert communicator_1.output_queue.qsize() == 0

    # Can connect to a password protected view page with a valid token
    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={ANONYMOUS_USER_TOKEN}",
        headers=[(b"origin", b"http://localhost")],
    )

    await communicator_2.connect()
    await communicator_2.receive_json_from()
    await communicator_2.send_json_to(
        {
            "page": "view",
            "slug": password_protected_grid_view.slug,
            "token": public_view_token,
        }
    )
    response = await communicator_2.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "view"
    assert response["parameters"]["slug"] == password_protected_grid_view.slug

    # the owner of the view can still connect to the password protected view page
    communicator_3 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_3.connect()
    await communicator_3.receive_json_from()

    await communicator_3.send_json_to(
        {"page": "view", "slug": password_protected_grid_view.slug}
    )
    response = await communicator_3.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "view"
    assert response["parameters"]["slug"] == password_protected_grid_view.slug

    await communicator_1.disconnect()
    await communicator_2.disconnect()
    await communicator_3.disconnect()
