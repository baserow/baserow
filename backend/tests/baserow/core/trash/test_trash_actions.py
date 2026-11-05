import pytest

from baserow.core.action.registries import action_type_registry
from baserow.core.models import TrashEntry, Workspace
from baserow.core.trash.actions import EmptyTrashActionType, RestoreFromTrashActionType
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_empty_application_level_trash_action_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    TrashHandler.trash(user, workspace, application, application)

    assert TrashEntry.objects.filter(should_be_permanently_deleted=True).count() == 0
    action_type_registry.get(EmptyTrashActionType.type).do(
        user, workspace.id, application.id
    )
    assert TrashEntry.objects.filter(should_be_permanently_deleted=True).count() == 1


@pytest.mark.django_db
def test_empty_workspace_level_trash_action_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    TrashHandler.trash(user, workspace, application, application)

    assert TrashEntry.objects.filter(should_be_permanently_deleted=True).count() == 0
    action_type_registry.get(EmptyTrashActionType.type).do(user, workspace.id)
    assert TrashEntry.objects.filter(should_be_permanently_deleted=True).count() == 1


@pytest.mark.django_db
def test_restore_item_action_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    TrashHandler.trash(user, workspace, None, workspace)

    assert Workspace.objects.count() == 0
    action_type_registry.get(RestoreFromTrashActionType.type).do(
        user, "workspace", workspace.id
    )
    assert Workspace.objects.count() == 1


@pytest.mark.parametrize(
    "item_type,expected_type",
    [
        ("agent", "identity"),
        ("workspace", "workspace"),
        ("removed_type", "removed_type"),
    ],
)
def test_restore_item_action_long_description(item_type, expected_type):
    params = {
        "item_id": 2,
        "item_type": item_type,
        "workspace_id": 1,
        "workspace_name": "Workspace",
    }

    assert RestoreFromTrashActionType.get_long_description(params) == (
        f'Item of type "{expected_type}" (2) has been restored from trash '
        'in group "Workspace" (1).'
    )
