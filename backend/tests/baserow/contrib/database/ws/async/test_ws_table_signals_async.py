import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceUser
from tests.baserow.contrib.database.utils import received_message

pytestmark = pytest.mark.usefixtures("fake_async_redis")


@pytest.fixture(autouse=True)
def use_async_event_loop_here(async_event_loop):
    pass


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_unsubscribe_subject_from_table_workspace_user_deleted(data_fixture):
    workspace_owner = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=workspace_owner, members=[user])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    # Establish websocket connection and subscribe to table
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await communicator.send_json_to({"page": "table", "table_id": table.id})
    await communicator.receive_json_from()

    # Kick user from workspace
    await sync_to_async(CoreHandler().delete_workspace_user)(
        workspace_owner, WorkspaceUser.objects.get(user=user, workspace=workspace)
    )

    # Make sure the user has been un-subscribed
    assert await received_message(communicator, "page_discard") is True
    await communicator.disconnect()
