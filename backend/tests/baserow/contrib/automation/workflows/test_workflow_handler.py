import datetime
from unittest.mock import MagicMock, patch

from django.db import connection
from django.db.utils import IntegrityError
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest
from freezegun import freeze_time

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.models import Automation, AutomationWorkflow
from baserow.contrib.automation.nodes.node_types import (
    CorePeriodicTriggerNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.contrib.automation.workflows.constants import (
    ALLOW_TEST_RUN_MINUTES,
    WORKFLOW_DIRTY_CACHE_KEY,
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
from baserow.core.cache import global_cache, local_cache
from baserow.core.notifications.models import Notification, NotificationRecipient
from baserow.core.registries import ImportExportConfig
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


@pytest.mark.django_db
def test_export_workflow_excludes_notification_recipients_when_not_duplicating(
    data_fixture,
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    recipient = data_fixture.create_user(workspace=automation.workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    workflow.notification_recipients.add(recipient)

    exported_workflow = AutomationWorkflowHandler().export_workflow(
        workflow,
        import_export_config=ImportExportConfig(
            include_permission_data=True,
            is_duplicate=False,
        ),
    )

    assert exported_workflow["notification_recipient_emails"] == []


@pytest.mark.django_db
def test_exported_workflow_import_maps_notification_recipients_to_target_workspace(
    data_fixture,
):
    source_workspace = data_fixture.create_workspace()
    target_workspace = data_fixture.create_workspace()

    shared_recipient = data_fixture.create_user(
        email="shared-recipient@example.com", workspace=source_workspace
    )
    source_only_recipient = data_fixture.create_user(
        email="source-only-recipient@example.com", workspace=source_workspace
    )
    target_only_user = data_fixture.create_user(
        email="target-only-user@example.com", workspace=target_workspace
    )
    data_fixture.create_user_workspace(
        workspace=target_workspace, user=shared_recipient
    )

    source_automation = data_fixture.create_automation_application(
        workspace=source_workspace
    )
    source_workflow = data_fixture.create_automation_workflow(
        automation=source_automation,
        create_trigger=False,
    )
    source_workflow.notification_recipients.add(shared_recipient, source_only_recipient)

    exported_workflow = AutomationWorkflowHandler().export_workflow(
        source_workflow,
        import_export_config=ImportExportConfig(
            include_permission_data=True,
            is_duplicate=True,
        ),
    )

    assert exported_workflow["notification_recipient_emails"] == [
        shared_recipient.email,
        source_only_recipient.email,
    ]

    target_automation = data_fixture.create_automation_application(
        workspace=target_workspace
    )

    imported_workflow = AutomationWorkflowHandler().import_workflow(
        target_automation,
        exported_workflow,
        {},
    )

    assert list(imported_workflow.notification_recipients.all()) == [shared_recipient]
    assert target_only_user not in imported_workflow.notification_recipients.all()


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
        "notification_recipients": [],
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
    handler = AutomationWorkflowHandler()

    test_clone_automation, _ = handler._clone_workflow(
        workflow, WorkflowState.TEST_CLONE
    )
    test_clone_workflow = test_clone_automation.workflows.first()
    data_fixture.create_automation_workflow_history(
        original_workflow=workflow,
        workflow=test_clone_workflow,
        status=HistoryStatusChoices.SUCCESS,
    )

    published_1 = handler.publish(workflow)
    published_2 = handler.publish(workflow)
    published_3 = handler.publish(workflow)
    published_4 = handler.publish(workflow)

    # The first two published workflows should no longer exist
    assert AutomationWorkflow.objects_and_trash.filter(id=published_1.id).count() == 0
    assert AutomationWorkflow.objects_and_trash.filter(id=published_2.id).count() == 0

    # The 3rd workflow should exist but in a disabled state
    published_3.refresh_from_db()
    assert published_3.is_published is False

    # The latest published workflow should be active
    assert published_4.is_published is True

    # The test clone should still exist and the state should still be correct
    test_clone_workflow.refresh_from_db()
    assert AutomationWorkflow.objects_and_trash.filter(
        id=test_clone_workflow.id
    ).exists()
    assert test_clone_workflow.state == WorkflowState.TEST_CLONE


@pytest.mark.django_db
def test_publish_disables_live_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    handler = AutomationWorkflowHandler()

    # Publish the workflow
    published = handler.publish(workflow)
    data_fixture.create_automation_workflow_history(
        original_workflow=workflow,
        workflow=published,
        status=HistoryStatusChoices.SUCCESS,
    )
    assert published.state == WorkflowState.LIVE

    # Edit the draft to force _ensure_published_for_run to create a new clone
    workflow.refresh_from_db()
    workflow.save()

    # Create a test clone to simulate a test run
    test_clone_automation, _ = handler._clone_workflow(
        workflow, WorkflowState.TEST_CLONE
    )
    test_clone_workflow = test_clone_automation.workflows.first()

    # The test clone should be the newest automation
    assert test_clone_automation.id > published.automation.id

    # The previously published workflow should now be disabled
    new_published = handler.publish(workflow)
    published.refresh_from_db()
    assert published.state == WorkflowState.DISABLED

    # Make sure the newly published workflow is live
    assert new_published.state == WorkflowState.LIVE

    # The test clone should be unaffected
    test_clone_workflow.refresh_from_db()
    assert test_clone_workflow.state == WorkflowState.TEST_CLONE


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
def test_get_published_workflow_ignores_newer_test_clone(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    handler = AutomationWorkflowHandler()

    published_workflow = handler.publish(workflow)
    test_clone_automation, _ = handler._clone_workflow(
        workflow, WorkflowState.TEST_CLONE
    )
    test_clone_workflow = test_clone_automation.workflows.first()

    # Sanity check that the newer clone would win without the TEST_CLONE exclusion.
    assert test_clone_automation.id > published_workflow.automation.id
    assert test_clone_workflow.state == WorkflowState.TEST_CLONE

    result = handler.get_published_workflow(workflow, with_cache=False)

    assert result == published_workflow
    assert result != test_clone_workflow


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
        "notification_recipients": [],
    }
    assert updated.new_values == {
        "name": "foo",
        "allow_test_run_until": None,
        # The original workflow should indeed be unaffected
        "state": WorkflowState.DRAFT,
        "notification_recipients": [],
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
def test_get_original_workflow_uses_local_cache(
    data_fixture, django_assert_num_queries
):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    with local_cache.context():
        cached_original_workflow = published_workflow.get_original()
        reloaded_published_workflow = AutomationWorkflow.objects.select_related(
            "automation"
        ).get(id=published_workflow.id)

        with django_assert_num_queries(0):
            assert (
                reloaded_published_workflow.get_original() is cached_original_workflow
            )


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

    histories = AutomationWorkflowHistory.objects.filter(
        original_workflow=original_workflow
    )
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

    histories = AutomationWorkflowHistory.objects.filter(
        original_workflow=original_workflow
    )
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


@pytest.mark.django_db(transaction=True)
def test_disable_workflow_notifies_selected_recipients(data_fixture):
    workspace = data_fixture.create_workspace()
    original_workflow = data_fixture.create_automation_workflow(
        automation=data_fixture.create_automation_application(workspace=workspace)
    )
    recipient_1 = data_fixture.create_user(workspace=workspace)
    recipient_2 = data_fixture.create_user(workspace=workspace)
    published_workflow = data_fixture.create_automation_workflow(
        automation=data_fixture.create_automation_application(workspace=workspace),
        state=WorkflowState.LIVE,
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()
    original_workflow.notification_recipients.add(recipient_1, recipient_2)

    AutomationWorkflowHandler().disable_workflow(published_workflow)

    notification = Notification.objects.get(type="automation_workflow_disabled")
    assert notification.workspace == workspace
    assert notification.data == {
        "workspace_id": workspace.id,
        "automation_id": original_workflow.automation_id,
        "workflow_id": original_workflow.id,
        "workflow_name": original_workflow.name,
    }
    assert set(
        NotificationRecipient.objects.filter(notification=notification).values_list(
            "recipient_id", flat=True
        )
    ) == {recipient_1.id, recipient_2.id}


@pytest.mark.django_db(transaction=True)
def test_disable_workflow_with_no_selected_recipients_does_not_notify(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    AutomationWorkflowHandler().disable_workflow(published_workflow)

    assert Notification.objects.filter(type="automation_workflow_disabled").count() == 0


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

    # This 6th error should exceed the configured consecutive error limit.
    data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        status=HistoryStatusChoices.ERROR,
    )

    with pytest.raises(AutomationWorkflowTooManyErrors) as exc:
        AutomationWorkflowHandler()._check_too_many_errors(published_workflow)

    assert str(exc.value) == (
        "The workflow was disabled due to too many consecutive errors. "
        "Limit exceeded: 5 consecutive errors."
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


@override_settings(
    AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=10,
    AUTOMATION_WORKFLOW_ERROR_LIMITS=((5, 30),),
)
@pytest.mark.django_db
def test_check_too_many_errors_raises_if_above_error_window_limit(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-03-10 09:59:00"):
        published_workflow = data_fixture.create_automation_workflow(
            state=WorkflowState.LIVE
        )
        published_workflow.automation.published_from = original_workflow
        published_workflow.automation.save()

    with freeze_time("2026-03-10 10:00:00"):
        for _ in range(5):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.ERROR,
            )

        assert (
            AutomationWorkflowHandler()._check_too_many_errors(published_workflow)
            is False
        )

        data_fixture.create_automation_workflow_history(
            workflow=original_workflow,
            status=HistoryStatusChoices.ERROR,
        )

        with pytest.raises(AutomationWorkflowTooManyErrors) as exc:
            AutomationWorkflowHandler()._check_too_many_errors(published_workflow)

        assert str(exc.value) == (
            "The workflow was disabled due to too many recent errors. "
            "Limit exceeded: 5 errors in 30 seconds."
        )


@override_settings(
    AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=10,
    AUTOMATION_WORKFLOW_ERROR_LIMITS=((2, 5), (4, 60)),
)
@pytest.mark.django_db
def test_check_too_many_errors_uses_multiple_error_windows(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    with freeze_time("2026-03-10 09:59:00"):
        published_workflow = data_fixture.create_automation_workflow(
            state=WorkflowState.LIVE
        )
        published_workflow.automation.published_from = original_workflow
        published_workflow.automation.save()

    with freeze_time("2026-03-10 10:00:00"):
        for _ in range(3):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.ERROR,
            )

    with freeze_time("2026-03-10 10:00:10"):
        assert (
            AutomationWorkflowHandler()._check_too_many_errors(published_workflow)
            is False
        )

    with freeze_time("2026-03-10 10:00:30"):
        for _ in range(2):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.ERROR,
            )

        with pytest.raises(AutomationWorkflowTooManyErrors) as exc:
            AutomationWorkflowHandler()._check_too_many_errors(published_workflow)

        assert str(exc.value) == (
            "The workflow was disabled due to too many recent errors. "
            "Limit exceeded: 4 errors in 60 seconds."
        )


@override_settings(
    AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=10,
    AUTOMATION_WORKFLOW_ERROR_LIMITS=((2, 5), (4, 60), (10, 3600)),
)
@pytest.mark.django_db
def test_check_too_many_errors_uses_a_single_query_for_multiple_windows(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    with freeze_time("2026-03-10 09:59:00"):
        published_workflow = data_fixture.create_automation_workflow(
            state=WorkflowState.LIVE
        )
        published_workflow.automation.published_from = original_workflow
        published_workflow.automation.save()

    with freeze_time("2026-03-10 10:00:00"):
        for _ in range(5):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.ERROR,
            )

        with CaptureQueriesContext(connection) as queries:
            with pytest.raises(AutomationWorkflowTooManyErrors) as exc:
                AutomationWorkflowHandler()._check_too_many_errors(published_workflow)

        assert str(exc.value) == (
            "The workflow was disabled due to too many recent errors. "
            "Limit exceeded: 2 errors in 5 seconds."
        )

    assert len(queries) == 2


@override_settings(
    AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=10,
    AUTOMATION_WORKFLOW_ERROR_LIMITS=((2, 30),),
)
@pytest.mark.django_db
def test_check_too_many_errors_ignores_errors_before_latest_publish_for_windows(
    data_fixture,
):
    original_workflow = data_fixture.create_automation_workflow()
    handler = AutomationWorkflowHandler()

    with freeze_time("2026-03-10 10:00:00"):
        for _ in range(3):
            data_fixture.create_automation_workflow_history(
                workflow=original_workflow,
                status=HistoryStatusChoices.ERROR,
            )

    with freeze_time("2026-03-10 12:00:00"):
        published_workflow = handler.publish(original_workflow)
        assert handler._check_too_many_errors(published_workflow) is False


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
        AutomationWorkflowHandler().toggle_test_run(workflow, None)

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
        AutomationWorkflowHandler().toggle_test_run(workflow, None)

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

    AutomationWorkflowHandler().toggle_test_run(workflow, None)

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

    cloned_trigger = history.workflow.get_trigger()
    assert history.simulate_until_node_id == cloned_trigger.id
    assert workflow.simulate_until_node is None
    assert history.is_test_run is True

    mock_start_workflow_celery_task.delay.assert_called_once_with(
        history.workflow_id, history.id
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
        AutomationWorkflowHistory.objects.filter(
            original_workflow=original_workflow
        ).order_by("started_on", "id")
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
        "The workflow was disabled due to too many consecutive errors. "
        "Limit exceeded: 2 consecutive errors."
    )

    original_workflow.refresh_from_db()
    published_workflow.refresh_from_db()

    assert original_workflow.state == WorkflowState.DISABLED
    assert published_workflow.state == WorkflowState.DISABLED


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.transaction.on_commit")
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
@patch(f"{WORKFLOWS_MODULE}.handler.automation_workflow_dispatch_started")
def test_async_start_workflow_queues_celery_task_on_commit(
    mock_automation_workflow_dispatch_started,
    mock_start_workflow_celery_task,
    mock_on_commit,
    data_fixture,
):
    workflow = data_fixture.create_automation_workflow()

    mock_on_commit.reset_mock()

    AutomationWorkflowHandler().async_start_workflow(workflow)

    history = workflow.workflow_histories.get()
    # Ensure the workflow_id is the cloned workflow, not the draft
    assert history.workflow_id != workflow.id

    mock_on_commit.assert_called_once()
    mock_start_workflow_celery_task.delay.assert_not_called()

    mock_on_commit.call_args.args[0]()
    mock_start_workflow_celery_task.delay.assert_called_once_with(
        history.workflow_id, history.id
    )
    mock_automation_workflow_dispatch_started.send.assert_called_once_with(
        sender=None,
        workflow_history=history,
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
def test_mark_failure_for_timed_out_history(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-16 12:00:00"):
        timed_out_history = data_fixture.create_automation_workflow_history(
            workflow=workflow,
            status=HistoryStatusChoices.STARTED,
        )
        node_history = AutomationNodeHistory.objects.create(
            workflow_history=timed_out_history,
            node=workflow.get_trigger(),
            started_on=timed_out_history.started_on,
            status=HistoryStatusChoices.STARTED,
        )

    with freeze_time("2026-04-16 13:00:01"):
        AutomationWorkflowHandler().mark_failure_for_timed_out_history()

    error_message = "This workflow took too long and was timed out."

    timed_out_history.refresh_from_db()
    assert timed_out_history.status == HistoryStatusChoices.ERROR
    assert timed_out_history.message == error_message
    assert timed_out_history.completed_on is not None

    node_history.refresh_from_db()
    assert node_history.status == HistoryStatusChoices.ERROR
    assert node_history.message == error_message
    assert node_history.completed_on == timed_out_history.completed_on


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


@pytest.mark.django_db
def test_ensure_published_for_run_creates_new_clone(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    cloned_workflow = AutomationWorkflowHandler()._ensure_published_for_run(workflow)

    # Ensure that the cloned workflow is a new workflow
    assert cloned_workflow.id != workflow.id
    assert cloned_workflow.automation.published_from == workflow
    assert cloned_workflow.state == WorkflowState.TEST_CLONE


@pytest.mark.django_db
def test_ensure_published_for_run_creates_new_after_workflow_update(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    handler = AutomationWorkflowHandler()

    cloned_workflow_1 = handler._ensure_published_for_run(workflow)

    # Set the dirty flag to trigger a new clone
    cache_key = WORKFLOW_DIRTY_CACHE_KEY.format(workflow.id)
    global_cache.update(cache_key, lambda _: True)

    cloned_workflow_2 = handler._ensure_published_for_run(workflow)

    # Because the workflow was updated, a new clone should be created
    assert cloned_workflow_1.id != cloned_workflow_2.id


@pytest.mark.django_db
def test_ensure_published_for_run_reuse_automation(data_fixture):
    """
    If a cloned automation exists and is still fresh (no edits to draft
    since publish), we should reuse it rather than creating a new clone.
    """

    workflow = data_fixture.create_automation_workflow()

    handler = AutomationWorkflowHandler()

    cloned_workflow = handler._ensure_published_for_run(workflow)

    second_cloned_workflow = handler._ensure_published_for_run(workflow)

    assert cloned_workflow.automation_id == second_cloned_workflow.automation_id


@pytest.mark.django_db
def test_ensure_published_for_run_ignores_published_workflow_states(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    handler = AutomationWorkflowHandler()

    published_workflow = handler.publish(workflow)
    clone = handler._ensure_published_for_run(workflow)
    second_clone = handler._ensure_published_for_run(workflow)

    assert published_workflow.state == WorkflowState.LIVE
    assert clone.id != published_workflow.id
    assert clone.state == WorkflowState.TEST_CLONE
    assert clone.automation.published_from == workflow
    assert second_clone.id == clone.id

    handler.update_workflow(workflow, state=WorkflowState.PAUSED)
    published_workflow.refresh_from_db()

    clone_after = handler._ensure_published_for_run(workflow)
    second_clone_after = handler._ensure_published_for_run(workflow)

    assert published_workflow.state == WorkflowState.PAUSED
    assert clone_after.id == clone.id
    assert clone_after.id != published_workflow.id
    assert clone_after.state == WorkflowState.TEST_CLONE
    assert clone_after.automation.published_from == workflow
    assert second_clone_after.id == clone_after.id


@pytest.mark.django_db
def test_publish_preserves_old_live_automation_with_history(data_fixture):
    """
    When re-publishing, old live automations that have history entries
    pointing at them should not be deleted.
    """

    workflow = data_fixture.create_automation_workflow()
    handler = AutomationWorkflowHandler()

    published = handler.publish(workflow)
    published_automation = published.automation

    # Create a history entry pointing to the first published automation
    data_fixture.create_automation_workflow_history(
        original_workflow=workflow,
        workflow=published,
        status=HistoryStatusChoices.SUCCESS,
    )

    # Publish twice. Normally, this would deleted the oldest published entry.
    handler.publish(workflow)
    handler.publish(workflow)

    # The first automation shouldn't be deleted because it has history entries
    assert Automation.objects.filter(id=published_automation.id).exists()


@override_settings(
    AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=100,
    AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=1,
)
@pytest.mark.django_db
def test_clear_old_history_deletes_orphaned_automations(data_fixture):
    """
    When history entries are cleaned up, any published automations
    that no longer have history entries pointing at them should be deleted.
    """

    workflow = data_fixture.create_automation_workflow()
    handler = AutomationWorkflowHandler()

    with freeze_time("2026-04-20 11:00:00"):
        cloned_workflow = handler._ensure_published_for_run(workflow)

    clone_automation_id = cloned_workflow.automation_id

    handler.publish(workflow)

    with freeze_time("2026-04-20 12:00:00"):
        data_fixture.create_automation_workflow_history(
            original_workflow=workflow,
            workflow=cloned_workflow,
            status=HistoryStatusChoices.SUCCESS,
        )

    # 12 hours later but within 1 day, so history survives
    with freeze_time("2026-04-21 00:00:00"):
        handler.clear_old_history()

    assert Automation.objects.filter(id=clone_automation_id).exists()

    # 2 days later, so history should have been deleted, and the cloned
    # automation should be pruned as well.
    with freeze_time("2026-04-22 12:00:00"):
        handler.clear_old_history()

    assert not Automation.objects.filter(id=clone_automation_id).exists()


@pytest.mark.django_db
def test_clear_old_history_keeps_live_published_automation_when_newer_test_clone_exists(
    data_fixture,
):
    workflow = data_fixture.create_automation_workflow()
    handler = AutomationWorkflowHandler()

    with freeze_time("2026-04-27 12:00:00"):
        published_workflow = handler.publish(workflow)
        test_clone_workflow = handler._ensure_published_for_run(workflow)

    assert test_clone_workflow.automation_id != published_workflow.automation_id
    assert test_clone_workflow.automation_id > published_workflow.automation_id

    with freeze_time("2026-04-27 12:01:00"):
        handler.clear_old_history()

    assert Automation.objects.filter(id=published_workflow.automation_id).exists()
    assert not Automation.objects.filter(id=test_clone_workflow.automation_id).exists()


@pytest.mark.django_db
@patch(f"{WORKFLOWS_MODULE}.handler.start_workflow_celery_task")
def test_async_start_workflow_test_run_creates_test_clone(
    mock_start_workflow_celery_task, data_fixture, django_capture_on_commit_callbacks
):
    """
    When async_start_workflow is called, it should call the celery task
    using a history that is based on a cloned workflow, not the draft.
    """

    workflow = data_fixture.create_automation_workflow()

    with django_capture_on_commit_callbacks(execute=True):
        AutomationWorkflowHandler().async_start_workflow(workflow)

    history = workflow.workflow_histories.get()

    # History's workflow should be a clone, not the draft
    assert history.original_workflow == workflow
    assert history.is_test_run is True
    assert history.workflow_id != workflow.id
    assert history.workflow.automation.published_from == workflow
    assert history.workflow.state == WorkflowState.TEST_CLONE

    mock_start_workflow_celery_task.delay.assert_called_once_with(
        history.workflow_id, history.id
    )
