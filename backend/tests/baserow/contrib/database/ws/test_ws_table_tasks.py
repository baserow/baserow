import pytest
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.contrib.database.table.tasks import (
    unsubscribe_user_from_tables_when_removed_from_workspace,
)
from baserow.ws.tasks import send_message_to_channel_group


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_unsubscribe_user_from_tables_and_rows_when_removed_from_workspace(
    data_fixture,
):
    channel_layer = get_channel_layer()
    user_1, token_1 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user_1)
    workspace_2 = data_fixture.create_workspace(user=user_1)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    application_2 = data_fixture.create_database_application(
        workspace=workspace_2, order=1
    )
    table_1 = data_fixture.create_database_table(database=application_1)
    table_1_model = table_1.get_model()
    row_1 = table_1_model.objects.create()
    table_2 = data_fixture.create_database_table(database=application_2)

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    response = await communicator.receive_json_from(timeout=0.1)

    # Subscribe user to a table and a row from workspace 1
    await communicator.send_json_to({"page": "table", "table_id": table_1.id})
    response = await communicator.receive_json_from(timeout=0.1)

    await communicator.send_json_to(
        {"page": "row", "table_id": table_1.id, "row_id": row_1.id}
    )
    response = await communicator.receive_json_from(timeout=0.1)

    # Subscribe user to a table from workspace 2
    await communicator.send_json_to({"page": "table", "table_id": table_2.id})
    response = await communicator.receive_json_from(timeout=0.1)

    # Send a message to consumers that user was removed from the workspace 1
    await sync_to_async(unsubscribe_user_from_tables_when_removed_from_workspace)(
        user_1.id, workspace_1.id
    )

    # Receiving messages about being removed from the pages
    response = await communicator.receive_json_from(timeout=0.1)
    assert response == {
        "page": "table",
        "parameters": {
            "table_id": table_1.id,
        },
        "type": "page_discard",
    }

    response = await communicator.receive_json_from(timeout=0.1)
    assert response == {
        "page": "row",
        "parameters": {
            "table_id": table_1.id,
            "row_id": row_1.id,
        },
        "type": "page_discard",
    }

    # User should not receive any messages to a table in workspace 1
    await send_message_to_channel_group(
        channel_layer, f"table-{table_1.id}", {"test": "message"}
    )
    await communicator.receive_nothing(timeout=0.1)

    # User should not receive any messages to a row in workspace 1
    await send_message_to_channel_group(
        channel_layer, f"table-{table_1.id}-row-{row_1.id}", {"test": "message"}
    )
    await communicator.receive_nothing(timeout=0.1)

    # User should still receive messages to a table in workspace 2
    await send_message_to_channel_group(
        channel_layer,
        f"table-{table_2.id}",
        {
            "type": "broadcast_to_group",
            "payload": {"test": "message"},
            "ignore_web_socket_id": None,
        },
    )
    response = await communicator.receive_json_from(timeout=0.1)
    assert response["test"] == "message"

    assert communicator.output_queue.qsize() == 0
    await communicator.disconnect()
