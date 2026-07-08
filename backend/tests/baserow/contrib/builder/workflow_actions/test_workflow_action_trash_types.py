import pytest

from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    EventTypes,
)
from baserow.contrib.builder.workflow_actions.operations import (
    RestoreBuilderWorkflowActionOperationType,
)
from baserow.contrib.builder.workflow_actions.trash_types import (
    BuilderWorkflowActionTrashableItemType,
)
from baserow.core.models import TrashEntry
from baserow.core.services.models import Service


def make_trash_entry(user, workflow_action):
    return TrashEntry.objects.create(
        user_who_trashed=user,
        workspace=workflow_action.page.builder.workspace,
        application=workflow_action.page.builder,
        trash_item_type=BuilderWorkflowActionTrashableItemType.type,
        trash_item_id=workflow_action.id,
        name=BuilderWorkflowActionTrashableItemType().get_name(workflow_action),
        names=BuilderWorkflowActionTrashableItemType().get_names(workflow_action),
    )


@pytest.mark.django_db
def test_workflow_action_trashable_get_parent(data_fixture):
    workflow_action = data_fixture.create_notification_workflow_action()

    result = BuilderWorkflowActionTrashableItemType().get_parent(workflow_action)

    assert result == workflow_action.page


@pytest.mark.django_db
def test_workflow_action_trashable_get_name(data_fixture):
    workflow_action = data_fixture.create_notification_workflow_action()

    result = BuilderWorkflowActionTrashableItemType().get_name(workflow_action)

    assert result == f"notification ({workflow_action.id})"


@pytest.mark.django_db
def test_workflow_action_trashable_trash(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value
    )

    trash_entry = make_trash_entry(user, workflow_action)
    result = BuilderWorkflowActionTrashableItemType().trash(
        workflow_action, user, trash_entry
    )

    assert result is None
    workflow_action.refresh_from_db()
    assert workflow_action.trashed is True


@pytest.mark.django_db
def test_workflow_action_trashable_restore(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value
    )

    trash_entry = make_trash_entry(user, workflow_action)
    BuilderWorkflowActionTrashableItemType().trash(workflow_action, user, trash_entry)
    workflow_action.refresh_from_db()
    assert workflow_action.trashed is True

    result = BuilderWorkflowActionTrashableItemType().restore(
        workflow_action, trash_entry
    )

    assert result is None
    workflow_action.refresh_from_db()
    assert workflow_action.trashed is False


@pytest.mark.django_db
def test_workflow_action_trashable_permanently_delete_item(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value
    )
    workflow_action_id = workflow_action.id

    trash_entry = make_trash_entry(user, workflow_action)
    BuilderWorkflowActionTrashableItemType().trash(workflow_action, user, trash_entry)
    BuilderWorkflowActionTrashableItemType().permanently_delete_item(workflow_action)

    assert (
        BuilderWorkflowAction.objects_and_trash.filter(id=workflow_action_id).count()
        == 0
    )


@pytest.mark.django_db
def test_workflow_action_trashable_permanently_delete_removes_service(
    data_fixture, django_capture_on_commit_callbacks
):
    # A service-backed action's underlying service is cleaned up on permanent delete
    # (but preserved on trash, so a restore keeps it intact).
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        user=user, page=page, element=element, event=EventTypes.CLICK.value
    )
    service_id = workflow_action.service_id
    assert service_id is not None

    trash_entry = make_trash_entry(user, workflow_action)
    BuilderWorkflowActionTrashableItemType().trash(workflow_action, user, trash_entry)
    # Still present while trashed.
    assert Service.objects.filter(id=service_id).exists()

    # `TrashHandler` permanently deletes via the base model instance (its
    # `model_class`), which is what fires the `pre_delete` service-cleanup receiver.
    # The receiver defers the delete to `transaction.on_commit`.
    base_workflow_action = BuilderWorkflowAction.objects_and_trash.get(
        id=workflow_action.id
    )
    with django_capture_on_commit_callbacks(execute=True):
        BuilderWorkflowActionTrashableItemType().permanently_delete_item(
            base_workflow_action
        )
    assert not Service.objects.filter(id=service_id).exists()


def test_workflow_action_trashable_get_restore_operation_type():
    result = BuilderWorkflowActionTrashableItemType().get_restore_operation_type()

    assert result == RestoreBuilderWorkflowActionOperationType.type
