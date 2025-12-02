import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.trash.trash_types import TableTrashableItemType
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler
from baserow.core.trash.trash_types import (
    ApplicationTrashableItemType,
    WorkspaceTrashableItemType,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from tests.baserow.contrib.database.utils import get_message, received_message


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.fixture(autouse=True)
def use_async_event_loop_here(async_event_loop):
    pass


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_table_updated_message_not_leaking(data_fixture):
    user = data_fixture.create_user()
    user_excluded, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, members=[user_excluded])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    await sync_to_async(RoleAssignmentHandler().assign_role)(
        user_excluded, workspace, no_access_role, table
    )

    # Establish websocket connection and subscribe to table
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await sync_to_async(TableHandler().update_table)(
        user=user, table=table, name="Test"
    )

    assert await received_message(communicator, "table_updated") is False
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_table_deleted_message_not_leaking(data_fixture):
    user = data_fixture.create_user()
    user_excluded, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, members=[user_excluded])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    await sync_to_async(RoleAssignmentHandler().assign_role)(
        user_excluded, workspace, no_access_role, table
    )

    # Establish websocket connection and subscribe to table
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await sync_to_async(TableHandler().delete_table)(user, table)

    assert await received_message(communicator, "table_deleted") is False
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_table_created_message_not_leaking(data_fixture):
    user = data_fixture.create_user()
    user_excluded, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, members=[user_excluded])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    await sync_to_async(RoleAssignmentHandler().assign_role)(
        user_excluded, workspace, no_access_role, table
    )

    # Establish websocket connection and subscribe to table
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await sync_to_async(TableHandler().delete_table)(user, table)
    await sync_to_async(TrashHandler().restore_item)(
        user, TableTrashableItemType.type, table.id
    )

    assert await received_message(communicator, "table_created") is False
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.enable_all_signals
async def test_workspace_restored_tables_not_leaking(data_fixture):
    user = data_fixture.create_user()
    user_excluded, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, members=[user_excluded])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    await sync_to_async(RoleAssignmentHandler().assign_role)(
        user_excluded, workspace, no_access_role, table
    )

    # Establish websocket connection and subscribe to table
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await sync_to_async(CoreHandler().delete_workspace)(user, workspace)
    await sync_to_async(TrashHandler().restore_item)(
        user, WorkspaceTrashableItemType.type, workspace.id
    )

    application_created_message = await get_message(communicator, "group_restored")
    assert application_created_message["applications"][0]["tables"] == []
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.enable_all_signals
async def test_database_restored_tables_not_leaking(data_fixture):
    user = data_fixture.create_user()
    user_excluded, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, members=[user_excluded])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    no_access_role = Role.objects.get(uid="NO_ACCESS")

    await sync_to_async(RoleAssignmentHandler().assign_role)(
        user_excluded, workspace, no_access_role, table
    )

    # Establish websocket connection and subscribe to table
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await sync_to_async(CoreHandler().delete_application)(user, database)
    await sync_to_async(TrashHandler().restore_item)(
        user, ApplicationTrashableItemType.type, database.id
    )

    application_created_message = await get_message(communicator, "application_created")
    assert application_created_message["application"]["tables"] == []
    await communicator.disconnect()
