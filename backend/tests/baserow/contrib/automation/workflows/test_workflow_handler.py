import datetime
from unittest.mock import MagicMock, patch

from django.db.utils import IntegrityError
from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.node_types import (
    CorePeriodicTriggerNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.contrib.automation.workflows.constants import (
    ALLOW_TEST_RUN_MINUTES,
    WorkflowState,
)
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNameNotUnique,
    AutomationWorkflowNotInAutomation,
    AutomationWorkflowRateLimited,
    AutomationWorkflowTooManyErrors,
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
def test_duplicate_workflow_with_nodes(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")
    data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
        reference_node=workflow.get_trigger(),
    )

    reference = {
        "0": "local_baserow_rows_created",
        "fallback node": {},
        "output edge 1": {},
        "output edge 2": {},
        "router": {
            "next": {
                "Default": ["fallback node"],
                "Do that": ["output edge 2"],
                "Do this": ["output edge 1"],
            }
        },
        "local_baserow_rows_created": {"next": {"": ["router"]}},
    }

    workflow.assert_reference(reference)

    workflow_clone = AutomationWorkflowHandler().duplicate_workflow(workflow)

    workflow_clone.assert_reference(reference)


@pytest.mark.django_db
def test_import_workflow_only(data_fixture):
    automation = data_fixture.create_automation_application()

    serialized_workflow = {
        "name": "new workflow",
        "id": 1,
        "order": 88,
        "state": "draft",
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

    assert result == {
        "name": "test",
        "allow_test_run_until": None,
        "state": WorkflowState.DRAFT,
    }


@pytest.mark.django_db
def test_publish_returns_published_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    published_workflow = AutomationWorkflowHandler().publish(workflow)

    workflow.refresh_from_db()

    assert workflow.is_published is True
    # Existing workflow shouldn't be affected
    assert workflow.state == WorkflowState.DRAFT

    assert published_workflow.automation.workspace is None
    assert published_workflow.automation.published_from == workflow

    assert published_workflow.is_published is True
    assert published_workflow.state == WorkflowState.LIVE


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
    assert published_3.is_published is False

    # The latest published workflow should be active
    assert published_4.is_published is True


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
    data_fixture.create_automation_workflow(
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
    data_fixture.create_automation_workflow(
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

    assert published_workflow.state == WorkflowState.LIVE

    # Let's pause the workflow. Note that we're passing in the original
    # workflow, not the published one. This is because the published
    # workflow is a backend-specific implementation detail.
    updated = handler.update_workflow(workflow, state=WorkflowState.PAUSED)

    assert updated.workflow == workflow
    assert updated.original_values == {
        "name": "foo",
        "allow_test_run_until": None,
        "state": WorkflowState.DRAFT,
    }
    assert updated.new_values == {
        "name": "foo",
        "allow_test_run_until": None,
        # The original workflow should indeed be unaffected
        "state": WorkflowState.DRAFT,
    }

    published_workflow.refresh_from_db()
    assert published_workflow.state == WorkflowState.PAUSED


@pytest.mark.django_db
def test_get_original_workflow_returns_original_workflow(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    workflow = AutomationWorkflowHandler().get_original_workflow(published_workflow)

    assert workflow == original_workflow


@pytest.mark.django_db
def test_trashing_workflow_deletes_published_workflow(data_fixture):
    user = data_fixture.create_user()
    original_workflow = data_fixture.create_automation_workflow(user=user)
    published_workflow = data_fixture.create_automation_workflow(
        user=user, state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    AutomationWorkflowHandler().delete_workflow(user, original_workflow)

    original_workflow.refresh_from_db()
    assert original_workflow.trashed is True
    assert AutomationWorkflow.objects.filter(id=published_workflow.id).exists() is False


@pytest.mark.parametrize("workflow_id", [10, 100, 200, 300])
def test_get_rate_limit_cache_key(workflow_id):
    result = AutomationWorkflowHandler()._get_rate_limit_cache_key(workflow_id)
    assert result == f"automation_workflow_{workflow_id}"


def test_check_is_rate_limited_returns_none_if_empty_cache():
    with freeze_time("2025-08-01 14:00:00"):
        result = AutomationWorkflowHandler()._check_is_rate_limited(100)
        assert result is None


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMIT_CACHE_EXPIRY_SECONDS=5,
    AUTOMATION_WORKFLOW_RATE_LIMIT_MAX_RUNS=5,
)
def test_check_is_rate_limited_returns_none_if_below_limit():
    with freeze_time("2025-08-01 14:00:00"):
        for _ in range(4):
            result = AutomationWorkflowHandler()._check_is_rate_limited(100)
            assert result is None

        # This 5th attempt shouldn't be rate limited
        result = AutomationWorkflowHandler()._check_is_rate_limited(100)
        assert result is None


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMIT_CACHE_EXPIRY_SECONDS=5,
    AUTOMATION_WORKFLOW_RATE_LIMIT_MAX_RUNS=5,
)
def test_check_is_rate_limited_returns_none_if_cache_expires():
    with freeze_time("2025-08-01 14:00:00"):
        for _ in range(5):
            result = AutomationWorkflowHandler()._check_is_rate_limited(100)
            assert result is None

    # 6 seconds after the first/initial cache entry
    with freeze_time("2025-08-01 14:00:06"):
        # The next 5 requests should not be rate limited
        for _ in range(5):
            result = AutomationWorkflowHandler()._check_is_rate_limited(100)
            assert result is None


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMIT_CACHE_EXPIRY_SECONDS=5,
    AUTOMATION_WORKFLOW_RATE_LIMIT_MAX_RUNS=5,
)
def test_check_is_rate_limited_raises_if_above_limit():
    with freeze_time("2025-08-01 14:00:00"):
        for _ in range(5):
            result = AutomationWorkflowHandler()._check_is_rate_limited(100)
            assert result is None

        # This 6th attempt should be rate limited
        with pytest.raises(AutomationWorkflowRateLimited) as e:
            AutomationWorkflowHandler()._check_is_rate_limited(100)

        assert (
            str(e.value) == "The workflow was rate limited due to too many recent runs."
        )


@pytest.mark.django_db
def test_disable_workflow_disables_original_workflow(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    now_str = "2025-08-01 14:00:00+00:00"
    with freeze_time(now_str):
        AutomationWorkflowHandler().disable_workflow(original_workflow)

    original_workflow.refresh_from_db()
    assert original_workflow.state == WorkflowState.DISABLED


@pytest.mark.django_db
def test_disable_workflow_disables_published_workflow(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    now_str = "2025-08-01 14:00:00+00:00"
    with freeze_time(now_str):
        AutomationWorkflowHandler().disable_workflow(published_workflow)

    published_workflow.refresh_from_db()
    original_workflow.refresh_from_db()

    # Ensure both published and original workflows are disabled
    assert published_workflow.state == WorkflowState.DISABLED
    assert original_workflow.state == WorkflowState.DISABLED


@override_settings(AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=5)
@pytest.mark.django_db
def test_check_too_many_errors_raises_if_above_limit(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    for _ in range(4):
        data_fixture.create_automation_workflow_history(
            workflow=original_workflow,
            status=HistoryStatusChoices.ERROR,
        )

    AutomationWorkflowHandler()._check_too_many_errors(original_workflow)

    # This 6th error should cause True to be returned
    data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        status=HistoryStatusChoices.ERROR,
    )

    with pytest.raises(AutomationWorkflowTooManyErrors) as e:
        AutomationWorkflowHandler()._check_too_many_errors(original_workflow)

    assert str(e.value) == (
        f"The workflow {original_workflow.id} was disabled "
        "due to too many consecutive errors."
    )


@override_settings(AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=5)
@pytest.mark.django_db
def test_check_too_many_errors_returns_none_if_below_limit(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    for _ in range(4):
        data_fixture.create_automation_workflow_history(
            workflow=original_workflow,
            status=HistoryStatusChoices.ERROR,
        )

    AutomationWorkflowHandler()._check_too_many_errors(original_workflow)

    # The next history is not an error, which should break the
    # consecutive count.
    data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        status=HistoryStatusChoices.SUCCESS,
    )

    AutomationWorkflowHandler()._check_too_many_errors(original_workflow)

    # Create another 4 errors
    for _ in range(4):
        data_fixture.create_automation_workflow_history(
            workflow=original_workflow,
            status=HistoryStatusChoices.ERROR,
        )

    # This should still be False, because it is below the threshold of 5
    AutomationWorkflowHandler()._check_too_many_errors(original_workflow)


@patch(f"{WORKFLOWS_MODULE}.handler.automation_workflow_updated")
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.async_start_workflow")
@pytest.mark.django_db
def test_toggle_test_mode_on(
    mock_async_start_workflow, mock_automation_workflow_updated, data_fixture
):
    workflow = data_fixture.create_automation_workflow(
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type
    )

    frozen_time = "2025-06-04 11:00"
    with freeze_time(frozen_time):
        AutomationWorkflowHandler().toggle_test_run(workflow)

    workflow.refresh_from_db()

    assert workflow.allow_test_run_until == datetime.datetime(
        2025, 6, 4, 11, ALLOW_TEST_RUN_MINUTES, tzinfo=datetime.timezone.utc
    )
    assert workflow.simulate_until_node is None

    mock_automation_workflow_updated.send.assert_called_once()
    mock_async_start_workflow.assert_not_called()


@patch(f"{WORKFLOWS_MODULE}.handler.automation_workflow_updated")
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.async_start_workflow")
@pytest.mark.django_db
def test_toggle_test_mode_on_immediate(
    mock_async_start_workflow, mock_automation_workflow_updated, data_fixture
):
    workflow = data_fixture.create_automation_workflow(
        trigger_type=CorePeriodicTriggerNodeType.type
    )

    frozen_time = "2025-06-04 11:00"
    with freeze_time(frozen_time):
        AutomationWorkflowHandler().toggle_test_run(workflow)

    workflow.refresh_from_db()

    assert workflow.allow_test_run_until == datetime.datetime(
        2025, 6, 4, 11, ALLOW_TEST_RUN_MINUTES, tzinfo=datetime.timezone.utc
    )
    assert workflow.simulate_until_node is None

    mock_automation_workflow_updated.send.assert_called_once()
    mock_async_start_workflow.assert_called_once()


@patch(f"{WORKFLOWS_MODULE}.handler.automation_workflow_updated")
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.async_start_workflow")
@pytest.mark.django_db
def test_toggle_test_mode_off(
    mock_async_start_workflow, mock_automation_workflow_updated, data_fixture
):
    workflow = data_fixture.create_automation_workflow(
        allow_test_run_until=datetime.datetime.now(),
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
    )

    AutomationWorkflowHandler().toggle_test_run(workflow)

    workflow.refresh_from_db()

    assert workflow.allow_test_run_until is None
    assert workflow.simulate_until_node is None

    mock_automation_workflow_updated.send.assert_called_once()
    mock_async_start_workflow.assert_not_called()


@patch(f"{WORKFLOWS_MODULE}.handler.automation_workflow_updated")
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.async_start_workflow")
@pytest.mark.django_db
def test_toggle_simulate_mode_on(
    mock_async_start_workflow, mock_automation_workflow_updated, data_fixture
):
    workflow = data_fixture.create_automation_workflow(
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type
    )

    AutomationWorkflowHandler().toggle_test_run(
        workflow, simulate_until_node=workflow.get_trigger()
    )

    workflow.refresh_from_db()

    assert workflow.allow_test_run_until is None
    assert workflow.simulate_until_node.id == workflow.get_trigger().id

    mock_automation_workflow_updated.send.assert_called_once()
    mock_async_start_workflow.assert_not_called()


@patch(f"{WORKFLOWS_MODULE}.handler.automation_workflow_updated")
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.async_start_workflow")
@pytest.mark.django_db
def test_toggle_simulate_mode_off(
    mock_async_start_workflow, mock_automation_workflow_updated, data_fixture
):
    workflow = data_fixture.create_automation_workflow(
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type
    )
    trigger = workflow.get_trigger()

    workflow.simulate_until_node = trigger
    workflow.save()

    AutomationWorkflowHandler().toggle_test_run(workflow, simulate_until_node=trigger)

    workflow.refresh_from_db()

    assert workflow.allow_test_run_until is None
    assert workflow.simulate_until_node is None

    mock_automation_workflow_updated.send.assert_called_once()
    mock_async_start_workflow.assert_not_called()


@patch(f"{WORKFLOWS_MODULE}.handler.automation_workflow_updated")
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.async_start_workflow")
@pytest.mark.django_db
def test_toggle_simulate_mode_on_immediate(
    mock_async_start_workflow, mock_automation_workflow_updated, data_fixture
):
    workflow = data_fixture.create_automation_workflow(
        trigger_type=CorePeriodicTriggerNodeType.type
    )

    AutomationWorkflowHandler().toggle_test_run(
        workflow, simulate_until_node=workflow.get_trigger()
    )

    workflow.refresh_from_db()

    assert workflow.allow_test_run_until is None
    assert workflow.simulate_until_node.id == workflow.get_trigger().id

    mock_automation_workflow_updated.send.assert_called_once()
    mock_async_start_workflow.assert_called_once()
