import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.trash_types import (
    DatabaseWorkflowActionTrashableItemType,
)
from baserow.core.exceptions import PermissionException
from baserow.core.models import TrashEntry
from baserow.core.services.models import Service
from baserow.core.trash.exceptions import CannotRestoreChildBeforeParent
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_actions_survive_trashing_and_restoring_the_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    FieldHandler().delete_field(user, button_field)

    assert DatabaseWorkflowAction.objects.filter(id=action.id).exists()

    TrashHandler.restore_item(user, "field", button_field.id)

    assert DatabaseWorkflowAction.objects.filter(id=action.id).exists()


def _trashed_action(data_fixture, user=None):
    user = user or data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    DatabaseWorkflowActionService().delete_workflow_action(user, action)
    return user, button_field, action


@pytest.mark.django_db
def test_a_trashed_action_is_listed_under_its_field(data_fixture):
    user, button_field, action = _trashed_action(data_fixture)

    entry = TrashEntry.objects.get(
        trash_item_type=DatabaseWorkflowActionTrashableItemType.type,
        trash_item_id=action.id,
    )

    assert entry.application_id == button_field.table.database_id
    assert entry.name == f"local_baserow_create_row ({action.id})"
    assert entry.parent_name == button_field.name
    assert not button_field.has_workflow_actions


@pytest.mark.django_db
def test_restoring_an_action_needs_the_field_update_permission(data_fixture):
    user, button_field, action = _trashed_action(data_fixture)
    outsider = data_fixture.create_user()

    with pytest.raises(PermissionException):
        TrashHandler.restore_item(
            outsider, DatabaseWorkflowActionTrashableItemType.type, action.id
        )

    TrashHandler.restore_item(
        user, DatabaseWorkflowActionTrashableItemType.type, action.id
    )
    assert DatabaseWorkflowAction.objects.filter(id=action.id).exists()


@pytest.mark.django_db
def test_an_action_cannot_be_restored_while_its_field_is_trashed(data_fixture):
    user, button_field, action = _trashed_action(data_fixture)
    FieldHandler().delete_field(user, button_field)

    with pytest.raises(CannotRestoreChildBeforeParent):
        TrashHandler.restore_item(
            user, DatabaseWorkflowActionTrashableItemType.type, action.id
        )


@pytest.mark.django_db
def test_permanently_deleting_an_action_deletes_its_service(
    data_fixture, django_capture_on_commit_callbacks
):
    user, button_field, action = _trashed_action(data_fixture)
    service_id = action.service_id
    assert Service.objects.filter(id=service_id).exists()

    with django_capture_on_commit_callbacks(execute=True):
        DatabaseWorkflowActionTrashableItemType().permanently_delete_item(
            DatabaseWorkflowAction.objects_and_trash.get(id=action.id)
        )

    assert not DatabaseWorkflowAction.objects_and_trash.filter(id=action.id).exists()
    assert not Service.objects.filter(id=service_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_trashed_action_follows_its_field_through_an_undone_type_change(
    data_fixture,
):
    """
    Its entry goes with the type change, and the undo trashes it again, so it
    can still be restored.
    """

    import uuid

    from baserow.contrib.database.action.scopes import TableActionScopeType
    from baserow.contrib.database.fields.actions import UpdateFieldActionType
    from baserow.core.action.handler import ActionHandler

    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    user, button_field, action = _trashed_action(data_fixture, user=user)

    UpdateFieldActionType.do(user, button_field, new_type_name="text")
    ActionHandler.undo(
        user, [TableActionScopeType.value(button_field.table_id)], session_id
    )

    assert DatabaseWorkflowAction.trash.filter(id=action.id).exists()
    TrashHandler.restore_item(
        user, DatabaseWorkflowActionTrashableItemType.type, action.id
    )
    assert DatabaseWorkflowAction.objects.filter(id=action.id).exists()


@pytest.mark.django_db
def test_a_field_leaving_the_button_type_takes_its_trashed_actions_entries(
    data_fixture,
):
    """
    The type change deletes the actions outright, so an entry left behind would
    be listed in the trash and fail to restore.
    """

    user, button_field, action = _trashed_action(data_fixture)

    FieldHandler().update_field(user, button_field, new_type_name="text")

    assert not TrashEntry.objects.filter(
        trash_item_type=DatabaseWorkflowActionTrashableItemType.type,
        trash_item_id=action.id,
    ).exists()
