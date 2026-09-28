import pytest

from baserow.contrib.automation.workflows.last_viewed_types import (
    AutomationWorkflowLastViewedItemType,
)
from baserow.core.registries import last_viewed_item_type_registry
from baserow.core.trash.handler import TrashHandler


def test_type_is_registered():
    assert isinstance(
        last_viewed_item_type_registry.get("automation_workflow"),
        AutomationWorkflowLastViewedItemType,
    )


@pytest.mark.django_db
def test_get_queryset_for_user_only_returns_workflows_the_user_can_open(
    data_fixture,
):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    trashed_workflow = data_fixture.create_automation_workflow(automation=automation)
    trashed_automation = data_fixture.create_automation_application(workspace=workspace)
    workflow_of_trashed_automation = data_fixture.create_automation_workflow(
        automation=trashed_automation
    )
    trashed_workspace = data_fixture.create_workspace(user=user)
    workflow_of_trashed_workspace = data_fixture.create_automation_workflow(
        automation=data_fixture.create_automation_application(
            workspace=trashed_workspace
        )
    )

    TrashHandler.trash(user, workspace, automation, trashed_workflow)
    TrashHandler.trash(user, workspace, None, trashed_automation)
    TrashHandler.trash(user, trashed_workspace, None, trashed_workspace)

    item_type = AutomationWorkflowLastViewedItemType()
    assert set(item_type.get_queryset_for_user(user.id)) == {workflow}
    assert list(item_type.get_queryset_for_user(other_user.id)) == []
    assert workflow_of_trashed_automation not in item_type.get_queryset_for_user(
        user.id
    )
    assert workflow_of_trashed_workspace not in item_type.get_queryset_for_user(user.id)
    assert set(item_type.get_existing_item_ids_queryset()) >= {
        workflow,
        trashed_workflow,
    }


@pytest.mark.django_db
def test_get_parent_ids(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    item_type = AutomationWorkflowLastViewedItemType()
    instance = item_type.get_queryset_for_user(user.id).get(id=workflow.id)
    assert item_type.get_application_id(instance) == automation.id
    assert item_type.get_workspace_id(instance) == workspace.id


@pytest.mark.django_db
def test_get_item_ids_of_permanently_deleted(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    item_type = AutomationWorkflowLastViewedItemType()

    assert list(
        item_type.get_item_ids_of_permanently_deleted("automation_workflow", workflow)
    ) == [workflow.id]
    assert (
        list(
            item_type.get_item_ids_of_permanently_deleted(
                "application", workflow.automation
            )
        )
        == []
    )
