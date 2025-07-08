from unittest.mock import MagicMock, patch

from django.db.utils import IntegrityError

import pytest

from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.types import AutomationNodeDict
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNameNotUnique,
    AutomationWorkflowNotInAutomation,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.trash.handler import TrashHandler

WORKFLOWS_MODULE = "baserow.contrib.automation.workflows"
HANDLER_MODULE = f"{WORKFLOWS_MODULE}.handler"
HANDLER_PATH = f"{HANDLER_MODULE}.AutomationWorkflowHandler"
TRASH_TYPES_PATH = f"{WORKFLOWS_MODULE}.trash_types"


@pytest.mark.django_db
def test_get_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    assert AutomationWorkflowHandler().get_workflow(workflow.id).id == workflow.id


@pytest.mark.django_db
def test_get_workflow_excludes_trashed_application(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    automation = workflow.automation

    # Trash the automation application
    TrashHandler.trash(user, automation.workspace, automation, automation)

    with pytest.raises(AutomationWorkflowDoesNotExist):
        AutomationWorkflowHandler().get_workflow(workflow.id)


@pytest.mark.django_db
def test_get_workflows(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflows = AutomationWorkflowHandler().get_workflows(workflow.automation.id)
    assert [w.id for w in workflows] == [workflow.id]


@pytest.mark.django_db
def test_get_workflows_excludes_trashed_application(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    automation = workflow.automation

    # Trash the automation application
    TrashHandler.trash(user, automation.workspace, automation, automation)

    workflows = AutomationWorkflowHandler().get_workflows(workflow.id)
    assert workflows.count() == 0


@pytest.mark.django_db
def test_get_workflow_does_not_exist():
    with pytest.raises(AutomationWorkflowDoesNotExist):
        AutomationWorkflowHandler().get_workflow(123)


@pytest.mark.django_db
def test_get_workflow_base_queryset(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    # With selecting related
    base_queryset = AutomationWorkflow.objects.exclude(id=workflow.id)

    with pytest.raises(AutomationWorkflowDoesNotExist):
        AutomationWorkflowHandler().get_workflow(
            workflow.id, base_queryset=base_queryset
        )


@pytest.mark.django_db
def test_create_workflow(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    expected_order = AutomationWorkflow.get_last_order(automation)

    workflow = AutomationWorkflowHandler().create_workflow(automation, "test")

    assert workflow.order == expected_order
    assert workflow.name == "test"


@pytest.mark.django_db
def test_create_workflow_name_not_unique(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    handler = AutomationWorkflowHandler()
    # Simulate it returning the same name
    handler.find_unused_workflow_name = MagicMock(return_value="test")

    with pytest.raises(AutomationWorkflowNameNotUnique):
        handler.create_workflow(workflow.automation, name="test")

    handler.find_unused_workflow_name.assert_called_once_with(
        workflow.automation, "test"
    )


@pytest.mark.django_db
def test_create_workflow_integrity_error(data_fixture):
    unexpected_error = IntegrityError("unexpected integrity error")
    workflow = data_fixture.create_automation_workflow(name="test")

    with patch(
        f"{HANDLER_MODULE}.AutomationWorkflow.objects.create",
        side_effect=unexpected_error,
    ):
        with pytest.raises(IntegrityError) as exc_info:
            AutomationWorkflowHandler().create_workflow(
                workflow.automation, name="test"
            )

        assert str(exc_info.value) == "unexpected integrity error"


@patch(f"{TRASH_TYPES_PATH}.automation_workflow_deleted")
@pytest.mark.django_db
def test_delete_workflow(workflow_deleted_mock, data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow()

    previous_count = AutomationWorkflow.objects.count()

    AutomationWorkflowHandler().delete_workflow(user, workflow)

    assert AutomationWorkflow.objects.count() == previous_count - 1
    workflow_deleted_mock.send.assert_called_once()


@pytest.mark.django_db
def test_update_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    AutomationWorkflowHandler().update_workflow(workflow, name="new")

    workflow.refresh_from_db()

    assert workflow.name == "new"


@pytest.mark.django_db
def test_update_workflow_name_not_unique(data_fixture):
    workflow_1 = data_fixture.create_automation_workflow(name="test1")
    workflow_2 = data_fixture.create_automation_workflow(
        automation=workflow_1.automation, name="test2"
    )

    with pytest.raises(AutomationWorkflowNameNotUnique):
        AutomationWorkflowHandler().update_workflow(workflow_2, name=workflow_1.name)


@pytest.mark.django_db
def test_update_workflow_integrity_error(data_fixture):
    workflow_1 = data_fixture.create_automation_workflow(name="test1")
    workflow_2 = data_fixture.create_automation_workflow(
        automation=workflow_1.automation, name="test2"
    )
    unexpected_error = IntegrityError("unexpected integrity error")
    workflow_2.save = MagicMock(side_effect=unexpected_error)

    with pytest.raises(IntegrityError) as exc_info:
        AutomationWorkflowHandler().update_workflow(workflow_2, name="foo")

    assert str(exc_info.value) == "unexpected integrity error"


@pytest.mark.django_db
def test_order_workflows(data_fixture):
    automation = data_fixture.create_automation_application()
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=10
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2", order=20
    )

    assert AutomationWorkflowHandler().order_workflows(
        automation, [workflow_2.id, workflow_1.id]
    ) == [
        workflow_2.id,
        workflow_1.id,
    ]

    workflow_1.refresh_from_db()
    workflow_2.refresh_from_db()

    assert workflow_1.order > workflow_2.order


@pytest.mark.django_db
def test_order_workflows_excludes_trashed_application(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=10
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2", order=20
    )

    # Trash the automation application
    TrashHandler.trash(user, automation.workspace, automation, automation)

    with pytest.raises(AutomationWorkflowNotInAutomation) as e:
        AutomationWorkflowHandler().order_workflows(
            automation, [workflow_2.id, workflow_1.id]
        )

    assert (
        str(e.value)
        == f"The workflow {workflow_2.id} does not belong to the automation."
    )


@pytest.mark.django_db
def test_order_workflows_not_in_automation(data_fixture):
    automation = data_fixture.create_automation_application()
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=10
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2", order=20
    )

    base_qs = AutomationWorkflow.objects.filter(id=workflow_2.id)

    with pytest.raises(AutomationWorkflowNotInAutomation):
        AutomationWorkflowHandler().order_workflows(
            automation, [workflow_2.id, workflow_1.id], base_qs=base_qs
        )


@pytest.mark.django_db
def test_duplicate_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    previous_count = AutomationWorkflow.objects.count()

    workflow_clone = AutomationWorkflowHandler().duplicate_workflow(workflow)

    assert AutomationWorkflow.objects.count() == previous_count + 1
    assert workflow_clone.id != workflow.id
    assert workflow_clone.name != workflow.name
    assert workflow_clone.order != workflow.order


@pytest.mark.django_db
def test_import_workflow_only(data_fixture):
    automation = data_fixture.create_automation_application()

    serialized_workflow = {
        "name": "new workflow",
        "id": 1,
        "order": 88,
    }

    id_mapping = {}

    workflow = AutomationWorkflowHandler().import_workflow_only(
        automation,
        serialized_workflow,
        id_mapping,
    )

    assert id_mapping["automation_workflows"] == {
        serialized_workflow["id"]: workflow.id
    }


@pytest.mark.django_db
def test_export_prepared_values(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    result = AutomationWorkflowHandler().export_prepared_values(workflow)

    assert result == {"name": "test", "allow_test_run_until": None, "paused": False}


def test_sort_serialized_nodes_by_priority():
    serialized_nodes = [
        AutomationNodeDict(id=1, parent_node_id=None, order=0),
        AutomationNodeDict(id=2, parent_node_id=1, order=0),
        AutomationNodeDict(id=3, parent_node_id=1, order=1),
        AutomationNodeDict(id=4, parent_node_id=1, order=2),
        AutomationNodeDict(id=5, parent_node_id=None, order=1),
        AutomationNodeDict(id=6, parent_node_id=None, order=2),
    ]
    assert AutomationWorkflowHandler()._sort_serialized_nodes_by_priority(
        serialized_nodes
    ) == [
        AutomationNodeDict(id=1, parent_node_id=None, order=0),
        AutomationNodeDict(id=5, parent_node_id=None, order=1),
        AutomationNodeDict(id=6, parent_node_id=None, order=2),
        AutomationNodeDict(id=2, parent_node_id=1, order=0),
        AutomationNodeDict(id=3, parent_node_id=1, order=1),
        AutomationNodeDict(id=4, parent_node_id=1, order=2),
    ]


@pytest.mark.django_db
def test_publish_returns_published_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    published_workflow = AutomationWorkflowHandler().publish(workflow)

    workflow.refresh_from_db()
    # Existing workflow shouldn't be affected
    assert workflow.published is False
    assert workflow.paused is False

    assert published_workflow.automation.workspace is None
    assert published_workflow.automation.published_from == workflow

    assert published_workflow.published is True
    assert published_workflow.paused is False
    assert published_workflow.disabled_on is None


@pytest.mark.django_db
def test_publish_cleans_up_old_workflows(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    published_1 = AutomationWorkflowHandler().publish(workflow)
    published_2 = AutomationWorkflowHandler().publish(workflow)
    published_3 = AutomationWorkflowHandler().publish(workflow)
    published_4 = AutomationWorkflowHandler().publish(workflow)

    # The first two workflows should no longer exist
    assert AutomationWorkflow.objects_and_trash.filter(id=published_1.id).count() == 0
    assert AutomationWorkflow.objects_and_trash.filter(id=published_2.id).count() == 0

    # The 3rd workflow should exist but in a disabled state
    published_3.refresh_from_db()
    assert published_3.published is False

    # The latest published workflow should be active
    assert published_4.published is True


@pytest.mark.django_db
def test_publish_only_exports_specific_workflow(data_fixture):
    """
    In the event that an Automation app has multiple workflows, when
    a specific workflow is published, the other workflows should not
    be included in the exported Automation.
    """

    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation,
        name="foo",
    )
    data_fixture.create_automation_workflow(automation=automation, name="bar")
    data_fixture.create_automation_workflow(automation=automation, name="baz")

    published_workflow = AutomationWorkflowHandler().publish(workflow_1)

    # The 2nd and 3rd workflows should not exist in the published automation
    assert published_workflow.automation.workflows.all().count() == 1
    assert published_workflow.automation.workflows.get().name == "foo"
    assert published_workflow.automation.published_from == workflow_1


@pytest.mark.django_db
def test_get_published_workflow_returns_none(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation,
        name="foo",
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation,
        name="bar",
    )

    result = AutomationWorkflowHandler().get_published_workflow(workflow_1)

    # Since the workflow hasn't been published, there is nothing to returns
    assert result is None


@pytest.mark.django_db
def test_get_published_workflow_returns_workflow(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation,
        name="foo",
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation,
        name="bar",
    )

    published_workflow = AutomationWorkflowHandler().publish(workflow_1)

    result = AutomationWorkflowHandler().get_published_workflow(workflow_1)

    # Should return the published workflow
    assert result == published_workflow


@pytest.mark.django_db
def test_update_workflow_correctly_pauses_published_workflow(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="foo"
    )

    handler = AutomationWorkflowHandler()
    published_workflow = handler.publish(workflow)

    assert published_workflow.paused is False

    # Let's pause the workflow. Note that we're passing in the actual
    # workflow, not the published one. This is because the published
    # workflow is a backend-specific implementation detail.
    updated = handler.update_workflow(workflow, paused=True)

    assert updated.workflow == workflow
    assert updated.original_values == {
        "name": "foo",
        "allow_test_run_until": None,
        "paused": False,
    }
    assert updated.new_values == {
        "name": "foo",
        "allow_test_run_until": None,
        # The original workflow should indeed be unaffected
        "paused": False,
    }

    published_workflow.refresh_from_db()
    assert published_workflow.paused is True
