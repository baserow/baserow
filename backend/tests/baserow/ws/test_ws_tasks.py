import pytest
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.ws.tasks import (
    broadcast_to_channel_group,
    broadcast_to_group,
    broadcast_to_groups,
    broadcast_to_users,
    broadcast_to_users_individual_payloads,
    force_disconnect_users,
)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_force_disconnect_users(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    response_2["web_socket_id"]

    await sync_to_async(force_disconnect_users)([user_1.id])
    await communicator_2.receive_nothing(0.1)

    payload = await communicator_1.receive_output(0.1)
    assert payload["type"] == "websocket.send"
    assert payload["text"] == '{"type": "force_disconnect"}'

    payload = await communicator_1.receive_output(0.1)
    assert payload["type"] == "websocket.close"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_users(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    response_2["web_socket_id"]

    await sync_to_async(broadcast_to_users)([user_1.id], {"message": "test"})
    response_1 = await communicator_1.receive_json_from(0.1)
    await communicator_2.receive_nothing(0.1)
    assert response_1["message"] == "test"

    await sync_to_async(broadcast_to_users)(
        [user_1.id, user_2.id],
        {"message": "test"},
        ignore_web_socket_id=web_socket_id_1,
    )
    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2["message"] == "test"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_channel_group(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(users=[user_1, user_2])
    database = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(user=user_1)
    table_2 = data_fixture.create_database_table(user=user_2)
    table_3 = data_fixture.create_database_table(database=database)

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    response_2["web_socket_id"]

    # We don't expect any communicator to receive anything because they didn't join a
    # workspace.
    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_1.id}", {"message": "nothing2"}
    )
    await communicator_1.receive_nothing(0.1)
    await communicator_2.receive_nothing(0.1)

    # User 1 is not allowed to join table 2 so we don't expect any response.
    await communicator_1.send_json_to({"page": "table", "table_id": table_2.id})
    await communicator_1.receive_nothing(0.1)

    # Because user 1 did not join table 2 we don't expect anything
    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_2.id}", {"message": "nothing"}
    )
    await communicator_1.receive_nothing(0.1)
    await communicator_2.receive_nothing(0.1)

    # Join the table page.
    await communicator_1.send_json_to({"page": "table", "table_id": table_1.id})
    response = await communicator_1.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "table"
    assert response["parameters"]["table_id"] == table_1.id

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_1.id}", {"message": "test"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    assert response_1["message"] == "test"
    await communicator_2.receive_nothing(0.1)

    await communicator_1.send_json_to({"page": "table", "table_id": table_3.id})

    response = await communicator_1.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "table"
    assert response["parameters"]["table_id"] == table_3.id

    await communicator_2.send_json_to({"page": "table", "table_id": table_3.id})
    response = await communicator_2.receive_json_from(0.1)
    assert response["type"] == "page_add"
    assert response["page"] == "table"
    assert response["parameters"]["table_id"] == table_3.id

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_3.id}", {"message": "test2"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    assert response_1["message"] == "test2"
    response_1 = await communicator_2.receive_json_from(0.1)
    assert response_1["message"] == "test2"

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_3.id}", {"message": "test3"}, web_socket_id_1
    )
    await communicator_1.receive_nothing(0.1)
    response_1 = await communicator_2.receive_json_from(0.1)
    assert response_1["message"] == "test3"

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table_2.id}", {"message": "test4"}
    )
    await communicator_1.receive_nothing(0.1)
    await communicator_2.receive_nothing(0.1)

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_workspace(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    user_3, token_3 = data_fixture.create_user_and_token()
    user_4, token_4 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(users=[user_1, user_2, user_4])
    workspace_2 = data_fixture.create_workspace(users=[user_2, user_3])

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    web_socket_id_2 = response_2["web_socket_id"]

    communicator_3 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_3}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_3.connect()
    await communicator_3.receive_json_from()

    await database_sync_to_async(broadcast_to_group)(
        workspace_1.id, {"message": "test"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_nothing(0.1)

    assert response_1["message"] == "test"
    assert response_2["message"] == "test"

    await database_sync_to_async(broadcast_to_group)(
        workspace_1.id, {"message": "test2"}, ignore_web_socket_id=web_socket_id_1
    )

    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_nothing(0.1)

    assert response_2["message"] == "test2"

    await database_sync_to_async(broadcast_to_group)(
        workspace_2.id, {"message": "test3"}, ignore_web_socket_id=web_socket_id_2
    )

    await communicator_1.receive_nothing(0.1)
    await communicator_2.receive_nothing(0.1)
    await communicator_3.receive_json_from(0.1)

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0
    assert communicator_3.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()
    await communicator_3.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_workspaces(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    user_3, token_3 = data_fixture.create_user_and_token()
    user_4, token_4 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(users=[user_1, user_2, user_4])
    workspace_2 = data_fixture.create_workspace(users=[user_2, user_3])

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()
    web_socket_id_2 = response_2["web_socket_id"]

    communicator_3 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_3}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_3.connect()
    await communicator_3.receive_json_from()

    await database_sync_to_async(broadcast_to_groups)(
        [workspace_1.id], {"message": "test"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_nothing(0.1)

    assert response_1["message"] == "test"
    assert response_2["message"] == "test"

    await database_sync_to_async(broadcast_to_groups)(
        [workspace_1.id], {"message": "test2"}, ignore_web_socket_id=web_socket_id_1
    )

    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_nothing(0.1)

    assert response_2["message"] == "test2"

    communicator_4 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_4}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_4.connect()
    response_4 = await communicator_4.receive_json_from()
    web_socket_id_4 = response_4["web_socket_id"]

    await database_sync_to_async(broadcast_to_groups)(
        [workspace_1.id, workspace_2.id],
        {"message": "test3"},
        ignore_web_socket_id=web_socket_id_4,
    )

    await communicator_1.receive_json_from(0.1)
    await communicator_2.receive_json_from(0.1)
    await communicator_3.receive_json_from(0.1)
    await communicator_4.receive_nothing(0.1)

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0
    assert communicator_3.output_queue.qsize() == 0
    assert communicator_4.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()
    await communicator_3.disconnect()
    await communicator_4.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_can_broadcast_to_every_single_user(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    await sync_to_async(broadcast_to_users)(
        [], {"message": "test"}, send_to_all_users=True
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    await communicator_2.receive_nothing(0.1)
    assert response_1["message"] == "test"

    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2["message"] == "test"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_can_still_ignore_when_sending_to_all_users(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    websocket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    await sync_to_async(broadcast_to_users)(
        [],
        {"message": "test"},
        ignore_web_socket_id=websocket_id_1,
        send_to_all_users=True,
    )
    await communicator_1.receive_nothing(0.1)

    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2["message"] == "test"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_users_individual_payloads(data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    response_1 = await communicator_1.receive_json_from()
    web_socket_id_1 = response_1["web_socket_id"]

    communicator_2 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_2}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_2.connect()
    response_2 = await communicator_2.receive_json_from()

    # Assert each user gets a unique message
    await sync_to_async(broadcast_to_users_individual_payloads)(
        {str(user_1.id): "payload1", str(user_2.id): "payload2"}
    )
    response_1 = await communicator_1.receive_json_from(0.1)
    assert response_1 == "payload1"

    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2 == "payload2"

    # Assert we can ignore a websocket for one user
    await sync_to_async(broadcast_to_users_individual_payloads)(
        {str(user_1.id): "payload1", str(user_2.id): "payload2"},
        ignore_web_socket_id=web_socket_id_1,
    )
    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2 == "payload2"

    # Assert not including a user id wont send them anything
    await sync_to_async(broadcast_to_users_individual_payloads)(
        {str(user_2.id): "payload2"},
    )
    await communicator_1.receive_nothing(0.1)
    response_2 = await communicator_2.receive_json_from(0.1)
    assert response_2 == "payload2"

    assert communicator_1.output_queue.qsize() == 0
    assert communicator_2.output_queue.qsize() == 0

    await communicator_1.disconnect()
    await communicator_2.disconnect()


@pytest.mark.django_db
def test_broadcast_application_created_does_not_fail_for_trashed_applications(
    data_fixture,
):
    from baserow.ws.tasks import broadcast_application_created

    application = data_fixture.create_database_application()
    application.trashed = True
    application.save()

    try:
        broadcast_application_created(application.id)
    except Exception as e:
        pytest.fail(f"broadcast_application_created raised an exception: {e}")


@pytest.mark.django_db
def test_broadcast_to_permitted_users_does_not_fail_for_trashed_objects(data_fixture):
    from baserow.ws.tasks import broadcast_to_permitted_users

    user_1, token_1 = data_fixture.create_user_and_token()

    workspace = data_fixture.create_workspace(users=[user_1])
    application = data_fixture.create_database_application(workspace=workspace)

    workspace.trashed = True
    workspace.save()

    try:
        broadcast_to_permitted_users(
            workspace.id,
            "workspace.create_application",
            "application",
            application.id,
            {},
            None,
        )
    except Exception as e:
        pytest.fail(f"broadcast_to_permitted_users raised an exception: {e}")

    # Now let's try with a deleted scope
    workspace.trashed = False
    workspace.save()

    application_id = application.id
    application.delete()

    try:
        broadcast_to_permitted_users(
            workspace.id,
            "workspace.create_application",
            "application",
            application_id,
            {},
            None,
        )
    except Exception as e:
        pytest.fail(f"broadcast_to_permitted_users raised an exception: {e}")
