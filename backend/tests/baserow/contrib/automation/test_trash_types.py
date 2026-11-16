from django.urls import reverse

import pytest
from rest_framework.status import HTTP_204_NO_CONTENT

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.trash_types import AutomationTrashableItemType
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.actions import DeleteApplicationActionType
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.models import TrashEntry
from baserow.core.trash.handler import TrashHandler
from baserow.core.trash.trash_types import ApplicationTrashableItemType


@pytest.mark.django_db
def test_trashing_automation_deletes_published_automations(data_fixture):
    """
    When an Automation application is trashed, ensure that all published
    automations are deleted.
    """

    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    original_workflow = data_fixture.create_automation_workflow(
        user, automation=automation
    )
    published_workflow = data_fixture.create_automation_workflow(
        user, state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    TrashHandler.trash(user, automation.workspace, automation, automation)

    automation.refresh_from_db()

    assert automation.trashed is True
    assert (
        AutomationWorkflow.objects_and_trash.filter(id=original_workflow.id).exists()
        is True
    )
    assert (
        AutomationWorkflow.objects_and_trash.filter(id=published_workflow.id).exists()
        is False
    )


def _create_automation_with_published_copy(data_fixture, user):
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    published_workflow = data_fixture.create_automation_workflow(
        user, state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = workflow
    published_workflow.automation.save()
    return automation, published_workflow


@pytest.mark.django_db
def test_deleting_automation_stores_an_application_trash_entry(data_fixture):
    user = data_fixture.create_user()
    automation, published_workflow = _create_automation_with_published_copy(
        data_fixture, user
    )

    CoreHandler().delete_application(user, automation)

    trash_entry = TrashEntry.objects.get(trash_item_id=automation.id)
    assert trash_entry.trash_item_type == ApplicationTrashableItemType.type
    assert not Automation.objects_and_trash.filter(
        id=published_workflow.automation_id
    ).exists()


@pytest.mark.django_db
def test_deleted_automation_can_be_restored_as_an_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)

    CoreHandler().delete_application(user, automation)

    response = api_client.patch(
        reverse("api:trash:restore"),
        {
            "trash_item_type": ApplicationTrashableItemType.type,
            "trash_item_id": automation.id,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    automation.refresh_from_db()
    assert automation.trashed is False
    assert not TrashEntry.objects.filter(trash_item_id=automation.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_delete_automation(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    automation = data_fixture.create_automation_application(user=user)

    action_type_registry.get_by_type(DeleteApplicationActionType).do(user, automation)

    ActionHandler.undo(
        user,
        [WorkspaceActionScopeType.value(workspace_id=automation.workspace_id)],
        session_id,
    )

    automation.refresh_from_db()
    assert automation.trashed is False


@pytest.mark.django_db
def test_emptied_automation_is_hidden_from_the_trash(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workspace = automation.workspace

    CoreHandler().delete_application(user, automation)
    TrashHandler.empty(user, workspace.id, None)

    structure = TrashHandler.get_trash_structure(user)
    assert structure["workspaces"][0]["applications"] == []
    with pytest.raises(ApplicationDoesNotExist):
        TrashHandler.get_trash_contents(user, workspace.id, automation.id)


@pytest.mark.django_db
def test_automation_trash_entry_stored_before_entry_type_can_be_restored(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)
    CoreHandler().delete_application(user, automation)
    TrashEntry.objects.filter(trash_item_id=automation.id).update(
        trash_item_type=AutomationTrashableItemType.type
    )

    response = api_client.patch(
        reverse("api:trash:restore"),
        {
            "trash_item_type": AutomationTrashableItemType.type,
            "trash_item_id": automation.id,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    automation.refresh_from_db()
    assert automation.trashed is False


@pytest.mark.django_db
def test_automation_trash_entry_stored_before_entry_type_can_be_deleted(
    data_fixture,
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    CoreHandler().delete_application(user, automation)
    TrashEntry.objects.filter(trash_item_id=automation.id).update(
        trash_item_type=AutomationTrashableItemType.type,
        should_be_permanently_deleted=True,
    )

    TrashHandler.permanently_delete_marked_trash()

    assert not Automation.objects_and_trash.filter(id=automation.id).exists()
    assert not TrashEntry.objects.filter(trash_item_id=automation.id).exists()
