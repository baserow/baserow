import datetime
from unittest.mock import MagicMock, patch

from django.db import connection
from django.db.utils import IntegrityError
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest
from freezegun import freeze_time

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import AutomationWorkflowHistory
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
    AutomationWorkflowBeforeRunError,
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNotInAutomation,
    AutomationWorkflowRateLimited,
    AutomationWorkflowTooManyErrors,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.trash.handler import TrashHandler
from tests.baserow.contrib.automation.history.utils import assert_history

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

    AutomationWorkflowHandler().update_workflow(workflow_2, name=workflow_1.name)

    workflow_1.refresh_from_db()
    assert workflow_1.name == "test1"
    workflow_2.refresh_from_db()
    assert workflow_2.name == "test1"


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

    workflow = published_workflow.get_original()

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


@pytest.mark.django_db
def test_check_is_rate_limited_returns_false_if_no_history_entry(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2025-08-01 14:00:00"):
        result = AutomationWorkflowHandler()._check_is_rate_limited(original_workflow)
        assert result is False


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((5, 5),),
)
@pytest.mark.django_db
def test_check_is_rate_limited_returns_none_if_below_limit(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2025-08-01 14:00:00"):
        for _ in range(4):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.SUCCESS,
            )

        # The next attempt shouldn't be rate limited.
        result = AutomationWorkflowHandler()._check_is_rate_limited(original_workflow)
        assert result is False


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((5, 5),),
)
@pytest.mark.django_db
def test_check_is_rate_limited_returns_false_if_workflow_history_too_old(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2025-08-01 14:00:00"):
        for _ in range(5):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.SUCCESS,
            )

    # 6 seconds after the first/initial history entry
    with freeze_time("2025-08-01 14:00:06"):
        assert (
            AutomationWorkflowHandler()._check_is_rate_limited(original_workflow)
            is False
        )


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((5, 5),),
)
@pytest.mark.django_db
def test_check_is_rate_limited_raises_if_above_limit(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2025-08-01 14:00:00"):
        for _ in range(5):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.SUCCESS,
            )

        with pytest.raises(AutomationWorkflowRateLimited) as exc:
            AutomationWorkflowHandler()._check_is_rate_limited(original_workflow)

        assert str(exc.value) == (
            "The workflow was rate limited due to too many recent or unfinished "
            "runs. Limit exceeded: 5 runs in 5 seconds."
        )


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((2, 5),),
)
@pytest.mark.django_db
def test_check_is_rate_limited_returns_true_if_too_many_histories_in_window(
    data_fixture,
):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    for _ in range(2):
        data_fixture.create_automation_workflow_history(
            workflow=original_workflow, status=HistoryStatusChoices.STARTED
        )

    with freeze_time("2025-08-01 14:00:00"):
        with pytest.raises(AutomationWorkflowRateLimited) as exc:
            AutomationWorkflowHandler()._check_is_rate_limited(published_workflow)

        assert str(exc.value) == (
            "The workflow was rate limited due to too many recent or unfinished "
            "runs. Limit exceeded: 2 runs in 5 seconds."
        )


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((2, 5), (4, 60)),
)
@pytest.mark.django_db
def test_check_is_rate_limited_returns_true_for_multiple_time_frames(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2025-08-01 14:00:00"):
        for _ in range(3):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.SUCCESS,
            )

    with freeze_time("2025-08-01 14:00:10"):
        assert AutomationWorkflowHandler()._check_is_rate_limited(
            original_workflow
        ) is (False)

    with freeze_time("2025-08-01 14:00:30"):
        data_fixture.create_automation_workflow_history(
            workflow=original_workflow,
            status=HistoryStatusChoices.STARTED,
        )
        with pytest.raises(AutomationWorkflowRateLimited) as exc:
            AutomationWorkflowHandler()._check_is_rate_limited(original_workflow)

        assert str(exc.value) == (
            "The workflow was rate limited due to too many recent or unfinished "
            "runs. Limit exceeded: 4 runs in 60 seconds."
        )


@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((2, 5), (4, 60), (10, 3600)),
)
@pytest.mark.django_db
def test_check_is_rate_limited_uses_a_single_query_for_multiple_windows(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2025-08-01 14:00:00"):
        for _ in range(4):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.SUCCESS,
            )

        with CaptureQueriesContext(connection) as queries:
            with pytest.raises(AutomationWorkflowRateLimited) as exc:
                AutomationWorkflowHandler()._check_is_rate_limited(original_workflow)

        assert str(exc.value) == (
            "The workflow was rate limited due to too many recent or unfinished "
            "runs. Limit exceeded: 2 runs in 5 seconds."
        )

    assert len(queries) == 1


@pytest.mark.django_db
@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((2, 5),),
    AUTOMATION_WORKFLOW_HISTORY_RATE_LIMIT_CACHE_EXPIRY_SECONDS=5,
)
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_workflow_rate_limiter_is_checked_before_starting_celery_task(
    mock_celery_task, data_fixture, django_capture_on_commit_callbacks
):
    with freeze_time("2026-01-26 13:00:00"):
        user = data_fixture.create_user()

        original_workflow = data_fixture.create_automation_workflow(user=user)
        published_workflow = data_fixture.create_automation_workflow(
            state=WorkflowState.LIVE, user=user
        )
        published_workflow.automation.published_from = original_workflow
        published_workflow.automation.save()

        handler = AutomationWorkflowHandler()
        rate_limited_error = (
            "The workflow was rate limited due to too many recent or unfinished "
            "runs. Limit exceeded: 2 runs in 5 seconds."
        )

        with django_capture_on_commit_callbacks(execute=True):
            # First 2 calls should queue workflow runs
            handler.async_start_workflow(published_workflow)
            handler.async_start_workflow(published_workflow)
        assert mock_celery_task.delay.call_count == 2

        # 3rd call should be rate limited
        handler.async_start_workflow(published_workflow)
        assert mock_celery_task.delay.call_count == 2
        assert_history(
            original_workflow, 3, "error", rate_limited_error, history_index=2
        )


@pytest.mark.django_db
@override_settings(
    AUTOMATION_WORKFLOW_HISTORY_RATE_LIMIT_CACHE_EXPIRY_SECONDS=5,
)
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.before_run")
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_creates_rate_limited_history_once_until_cache_reset(
    mock_celery_task, mock_before_run, data_fixture
):
    user = data_fixture.create_user()

    original_workflow = data_fixture.create_automation_workflow(user=user)
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE, user=user
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    mock_before_run.side_effect = AutomationWorkflowRateLimited(
        "The workflow was rate limited due to too many recent or unfinished runs. "
        "Limit exceeded: 2 runs in 5 seconds."
    )

    handler = AutomationWorkflowHandler()

    with freeze_time("2026-01-26 13:00:00"):
        handler.async_start_workflow(published_workflow)
        handler.async_start_workflow(published_workflow)
        handler.async_start_workflow(published_workflow)

    histories = AutomationWorkflowHistory.objects.filter(workflow=original_workflow)
    assert histories.count() == 1
    assert_history(
        original_workflow,
        1,
        "error",
        "The workflow was rate limited due to too many recent or unfinished runs. "
        "Limit exceeded: 2 runs in 5 seconds.",
    )
    mock_celery_task.delay.assert_not_called()

    with freeze_time("2026-01-26 13:00:06"):
        handler.async_start_workflow(published_workflow)

    histories = AutomationWorkflowHistory.objects.filter(workflow=original_workflow)
    assert histories.count() == 2


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
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    for _ in range(5):
        data_fixture.create_automation_workflow_history(
            workflow=original_workflow,
            status=HistoryStatusChoices.ERROR,
        )

    assert (
        AutomationWorkflowHandler()._check_too_many_errors(published_workflow) is False
    )

    # This 6th error should cause True to be returned
    data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        status=HistoryStatusChoices.ERROR,
    )

    assert (
        AutomationWorkflowHandler()._check_too_many_errors(published_workflow) is True
    )


@override_settings(AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=5)
@pytest.mark.django_db
def test_check_too_many_errors_does_not_trigger_for_unpublished_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    for _ in range(6):
        data_fixture.create_automation_workflow_history(
            workflow=workflow,
            status=HistoryStatusChoices.ERROR,
        )

    assert AutomationWorkflowHandler()._check_too_many_errors(workflow) is False


@override_settings(AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=5)
@pytest.mark.django_db
def test_check_too_many_errors_ignores_errors_before_latest_publish(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-03-10 10:00:00"):
        for _ in range(6):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.ERROR,
            )

    with freeze_time("2026-03-10 12:00:00"):
        published_workflow = AutomationWorkflowHandler().publish(original_workflow)

    assert (
        AutomationWorkflowHandler()._check_too_many_errors(published_workflow) is False
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


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=7)
@pytest.mark.django_db
def test_clear_old_history_deletes_history_older_than_max_days(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2025-02-01 12:00:00"):
        old_history = data_fixture.create_automation_workflow_history(
            workflow=workflow,
            status=HistoryStatusChoices.SUCCESS,
        )

    with freeze_time("2025-02-02 12:00:00"):
        recent_history = data_fixture.create_automation_workflow_history(
            workflow=workflow,
            status=HistoryStatusChoices.SUCCESS,
        )

    # This is 8 days after old_history was created, so it should be deleted.
    with freeze_time("2025-02-09 12:00:00"):
        AutomationWorkflowHandler()._clear_old_history(workflow)

    assert workflow.workflow_histories.filter(id=old_history.id).exists() is False
    assert workflow.workflow_histories.filter(id=recent_history.id).exists() is True


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=3)
@pytest.mark.django_db
def test_clear_old_history_keeps_only_max_entries(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    histories = []
    day = 10
    for i in range(5):
        day += i
        with freeze_time(f"2025-02-{day} 12:00:00"):
            histories.append(
                data_fixture.create_automation_workflow_history(
                    workflow=workflow,
                    status=HistoryStatusChoices.SUCCESS,
                )
            )

    with freeze_time(f"2025-02-16 12:00:00"):
        AutomationWorkflowHandler()._clear_old_history(workflow)

    assert workflow.workflow_histories.all().count() == 3

    # The two oldest should be deleted
    for history in histories[:2]:
        assert workflow.workflow_histories.filter(id=history.id).exists() is False

    # The three newest should be kept
    for history in histories[2:]:
        assert workflow.workflow_histories.filter(id=history.id).exists() is True


@override_settings(
    AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=3,
    AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=1,
)
@pytest.mark.django_db
def test_clear_old_history_keeps_entries(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2025-02-01 12:00:00"):
        history = data_fixture.create_automation_workflow_history(workflow=workflow)

    with freeze_time("2025-02-02 12:00:00"):
        AutomationWorkflowHandler()._clear_old_history(workflow)

    # history is within limits, so it should be kept
    assert workflow.workflow_histories.filter(id=history.id).exists() is True


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.before_run")
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_too_many_errors(
    mock_start_workflow_celery_task, mock_before_run, data_fixture
):
    mock_before_run.side_effect = AutomationWorkflowTooManyErrors(
        "mock too many errors"
    )

    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    AutomationWorkflowHandler().async_start_workflow(published_workflow)

    # The workflow shouldn't be started because before_run() should return early.
    mock_start_workflow_celery_task.delay.assert_not_called()
    assert_history(original_workflow, 1, "disabled", "mock too many errors")

    original_workflow.refresh_from_db()
    published_workflow.refresh_from_db()

    assert original_workflow.state == WorkflowState.DISABLED
    assert published_workflow.state == WorkflowState.DISABLED


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_with_simulate_until_node(
    mock_start_workflow_celery_task, data_fixture, django_capture_on_commit_callbacks
):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    workflow.simulate_until_node = trigger
    workflow.save(update_fields=["simulate_until_node"])

    with django_capture_on_commit_callbacks(execute=True):
        AutomationWorkflowHandler().async_start_workflow(workflow)

    workflow.refresh_from_db()
    history = workflow.workflow_histories.get()

    assert workflow.simulate_until_node is None
    assert history.is_test_run is True
    assert history.simulate_until_node_id == trigger.id

    mock_start_workflow_celery_task.delay.assert_called_once_with(
        workflow.id, history.id
    )


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.before_run")
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_with_simulate_until_node_and_error_creates_no_history(
    mock_start_workflow_celery_task, mock_before_run, data_fixture
):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    workflow.simulate_until_node = trigger
    workflow.save(update_fields=["simulate_until_node"])

    mock_before_run.side_effect = AutomationWorkflowBeforeRunError("unexpected error")

    AutomationWorkflowHandler().async_start_workflow(workflow)

    workflow.refresh_from_db()

    assert workflow.workflow_histories.count() == 0
    mock_start_workflow_celery_task.delay.assert_not_called()


@pytest.mark.django_db
@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((2, 4),),
    AUTOMATION_WORKFLOW_HISTORY_RATE_LIMIT_CACHE_EXPIRY_SECONDS=2,
    AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=2,
)
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_rate_limited_runs_eventually_disable_workflow(
    mock_start_workflow_celery_task, data_fixture, django_capture_on_commit_callbacks
):
    original_workflow = data_fixture.create_automation_workflow()
    with freeze_time("2026-03-08 12:00:00"):
        published_workflow = data_fixture.create_automation_workflow(
            state=WorkflowState.LIVE
        )
        published_workflow.automation.published_from = original_workflow
        published_workflow.automation.save()

    with freeze_time("2026-03-10 12:00:00"):
        with django_capture_on_commit_callbacks(execute=True):
            # Two regular history entries
            AutomationWorkflowHandler().async_start_workflow(published_workflow)
            AutomationWorkflowHandler().async_start_workflow(published_workflow)
        # only this one is an error
        AutomationWorkflowHandler().async_start_workflow(published_workflow)

    assert original_workflow.workflow_histories.count() == 3

    with freeze_time("2026-03-10 12:00:03"):
        # Should create another error
        AutomationWorkflowHandler().async_start_workflow(published_workflow)
        AutomationWorkflowHandler().async_start_workflow(published_workflow)
        AutomationWorkflowHandler().async_start_workflow(published_workflow)

    assert original_workflow.workflow_histories.count() == 4

    with freeze_time("2026-03-10 12:00:06"):
        with django_capture_on_commit_callbacks(execute=True):
            AutomationWorkflowHandler().async_start_workflow(published_workflow)

        # Another error is created but we also disable the workflow
        AutomationWorkflowHandler().async_start_workflow(published_workflow)

    histories = list(
        AutomationWorkflowHistory.objects.filter(workflow=original_workflow).order_by(
            "started_on", "id"
        )
    )

    assert len(histories) == 6

    # We should have 6 successful call
    assert mock_start_workflow_celery_task.delay.call_count == 2

    assert histories[2].status == HistoryStatusChoices.ERROR
    assert histories[2].message == (
        "The workflow was rate limited due to too many recent or unfinished runs. "
        "Limit exceeded: 2 runs in 4 seconds."
    )
    assert histories[3].status == HistoryStatusChoices.ERROR
    assert histories[3].message == (
        "The workflow was rate limited due to too many recent or unfinished runs. "
        "Limit exceeded: 2 runs in 4 seconds."
    )

    assert histories[4].status == HistoryStatusChoices.ERROR
    assert histories[4].message == (
        "The workflow was rate limited due to too many recent or unfinished runs. "
        "Limit exceeded: 2 runs in 4 seconds."
    )

    assert histories[5].status == HistoryStatusChoices.DISABLED
    assert histories[5].message == (
        "The workflow was disabled due to too many consecutive errors."
    )

    original_workflow.refresh_from_db()
    published_workflow.refresh_from_db()

    assert original_workflow.state == WorkflowState.DISABLED
    assert published_workflow.state == WorkflowState.DISABLED


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.transaction.on_commit")
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_queues_celery_task_on_commit(
    mock_start_workflow_celery_task, mock_on_commit, data_fixture
):
    workflow = data_fixture.create_automation_workflow()

    mock_on_commit.reset_mock()

    AutomationWorkflowHandler().async_start_workflow(workflow)

    history = workflow.workflow_histories.get()

    mock_on_commit.assert_called_once()
    mock_start_workflow_celery_task.delay.assert_not_called()

    mock_on_commit.call_args.args[0]()
    mock_start_workflow_celery_task.delay.assert_called_once_with(
        workflow.id, history.id
    )


@pytest.mark.django_db
@override_settings(
    AUTOMATION_WORKFLOW_RATE_LIMITS=((2, 30),),
    AUTOMATION_WORKFLOW_HISTORY_RATE_LIMIT_CACHE_EXPIRY_SECONDS=30,
)
def test_check_is_rate_limited_ignores_runs_before_latest_publish(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    handler = AutomationWorkflowHandler()

    with freeze_time("2026-03-10 10:00:00"):
        for _ in range(3):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.STARTED,
            )

    with freeze_time("2026-03-10 12:00:00"):
        published_workflow = handler.publish(original_workflow)
        assert handler._check_is_rate_limited(published_workflow) is False


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.before_run")
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_before_run_error(
    mock_start_workflow_celery_task, mock_before_run, data_fixture
):
    # We already test the specific AutomationWorkflowTooManyErrors error above,
    # but we should also test that before_run() has error handling.
    mock_before_run.side_effect = AutomationWorkflowBeforeRunError("unexpected error")

    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    AutomationWorkflowHandler().async_start_workflow(published_workflow)

    # The workflow shouldn't be started because before_run() should return early.
    mock_start_workflow_celery_task.delay.assert_not_called()
    assert_history(original_workflow, 1, "error", "unexpected error")

    original_workflow.refresh_from_db()
    published_workflow.refresh_from_db()

    assert original_workflow.state == WorkflowState.DRAFT
    assert published_workflow.state == WorkflowState.LIVE


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.before_run")
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_unexpected_error_creates_history(
    mock_start_workflow_celery_task, mock_before_run, data_fixture
):
    mock_before_run.side_effect = Exception("unexpected error")

    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    AutomationWorkflowHandler().async_start_workflow(published_workflow)

    mock_start_workflow_celery_task.delay.assert_not_called()
    assert_history(original_workflow, 1, "error", "Unknown exception: unexpected error")

    history = original_workflow.workflow_histories.get()
    assert history.started_on is not None
    assert history.completed_on == history.started_on

    original_workflow.refresh_from_db()
    published_workflow.refresh_from_db()

    assert original_workflow.state == WorkflowState.DRAFT
    assert published_workflow.state == WorkflowState.LIVE


@override_settings(AUTOMATION_WORKFLOW_TIMEOUT_HOURS=1)
@pytest.mark.django_db
def test_before_run_marks_timed_out_started_history_as_failed(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    with freeze_time("2026-03-10 10:00:00"):
        timed_out_history = data_fixture.create_automation_workflow_history(
            workflow=original_workflow,
            status=HistoryStatusChoices.STARTED,
        )

    with freeze_time("2026-03-10 12:00:00"):
        AutomationWorkflowHandler().before_run(published_workflow)

    timed_out_history.refresh_from_db()

    assert timed_out_history.status == HistoryStatusChoices.ERROR
    assert timed_out_history.message == "This workflow took too long and was timed out."


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.AutomationWorkflowHandler.before_run")
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_unknown_exception(
    mock_start_workflow_celery_task, mock_before_run, data_fixture
):
    mock_before_run.side_effect = Exception("unexpected failure")

    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    AutomationWorkflowHandler().async_start_workflow(published_workflow)

    mock_start_workflow_celery_task.delay.assert_not_called()
    assert_history(
        original_workflow,
        1,
        "error",
        "Unknown exception: unexpected failure",
    )


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=2)
@pytest.mark.django_db
def test_clear_old_history_excludes_started_workflows_max_entries(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    # Create three history entries
    with freeze_time("2026-03-10 12:00:00"):
        started_history = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.STARTED
        )

    with freeze_time("2026-03-10 13:00:00"):
        data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-03-10 14:00:00"):
        data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )

    # Although max entries is 2 and the oldest history should be deleted,
    # the oldest one is still kept because its status is STARTED.
    with freeze_time("2026-03-10 15:00:00"):
        AutomationWorkflowHandler()._clear_old_history(workflow)

    assert workflow.workflow_histories.filter(id=started_history.id).exists() is True
    assert workflow.workflow_histories.count() == 3


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=1)
@pytest.mark.django_db
def test_clear_old_history_excludes_started_workflows_max_days(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-03-10 12:00:00"):
        history_1 = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.STARTED
        )

    with freeze_time("2026-03-11 12:00:00"):
        history_2 = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )

    # After 2 days, both history entries are older than MAX_DAYS, but since
    # history_1 hasn't finished yet it shouldn't be deleted.
    with freeze_time("2026-03-13 12:00:00"):
        AutomationWorkflowHandler()._clear_old_history(workflow)

    assert workflow.workflow_histories.filter(id=history_1.id).exists() is True
    assert workflow.workflow_histories.filter(id=history_2.id).exists() is False
