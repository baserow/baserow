from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.workflows.constants import (
    WORKFLOW_DIRTY_CACHE_KEY,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.tasks import automation_periodic_cleanup
from baserow.core.cache import global_cache


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=2)
@pytest.mark.django_db
def test_automation_periodic_cleanup_keeps_max_entries_per_workflow(data_fixture):
    workflow_a = data_fixture.create_automation_workflow()
    workflow_b = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-13 12:00:00"):
        workflow_a_history_1 = data_fixture.create_automation_workflow_history(
            workflow=workflow_a, status=HistoryStatusChoices.SUCCESS
        )
    with freeze_time("2026-04-14 12:00:00"):
        workflow_a_history_2 = data_fixture.create_automation_workflow_history(
            workflow=workflow_a, status=HistoryStatusChoices.SUCCESS
        )
    with freeze_time("2026-04-15 12:00:00"):
        workflow_a_history_3 = data_fixture.create_automation_workflow_history(
            workflow=workflow_a, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-14 12:00:00"):
        workflow_b_history_1 = data_fixture.create_automation_workflow_history(
            workflow=workflow_b, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-15 12:00:00"):
        automation_periodic_cleanup()

    # Since workflow_a had 3 entries and max is 2, the oldest entry is deleted.
    assert not workflow_a.workflow_histories.filter(id=workflow_a_history_1.id).exists()
    assert workflow_a.workflow_histories.filter(id=workflow_a_history_2.id).exists()
    assert workflow_a.workflow_histories.filter(id=workflow_a_history_3.id).exists()

    # workflow_b has only 1 entry, which is under the max limit, so it
    # isn't deleted.
    assert workflow_b.workflow_histories.filter(id=workflow_b_history_1.id).exists()


@override_settings(
    AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=1,
    # Little over 3 days
    AUTOMATION_WORKFLOW_TIMEOUT_HOURS=73,
)
@pytest.mark.django_db
def test_automation_periodic_cleanup_excludes_started_from_date_cleanup(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-13 12:00:00"):
        workflow_history_started = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.STARTED
        )

    with freeze_time("2026-04-14 12:00:00"):
        workflow_history_success = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )
        workflow_history_error = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.ERROR
        )
        workflow_history_disabled = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.DISABLED
        )

    with freeze_time("2026-04-16 12:00:00"):
        automation_periodic_cleanup()

    # Although both history entries are older than max_days,
    # entries with status=STARTED should be excluded from deletion.
    assert workflow.workflow_histories.filter(id=workflow_history_started.id).exists()

    # Other statuses should be deleted.
    assert (
        workflow.workflow_histories.filter(
            id__in=[
                workflow_history_success.id,
                workflow_history_error.id,
                workflow_history_disabled.id,
            ]
        ).count()
        == 0
    )


@override_settings(
    AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=2,
    # Little over 3 days
    AUTOMATION_WORKFLOW_TIMEOUT_HOURS=73,
)
@pytest.mark.django_db
def test_automation_periodic_cleanup_excludes_started_from_count_cleanup(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-13 12:00:00"):
        history_started = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.STARTED
        )
    with freeze_time("2026-04-14 12:00:00"):
        data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )
    with freeze_time("2026-04-15 12:00:00"):
        data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-15 12:00:00"):
        automation_periodic_cleanup()

    # There are 3 history entries. Even though max_entries is 2, the oldest
    # entry is STARTED, so it is not deleted.
    assert workflow.workflow_histories.filter(id=history_started.id).exists()
    assert workflow.workflow_histories.count() == 3


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=7)
@pytest.mark.django_db
def test_automation_periodic_cleanup_deletes_entries_older_than_max_days(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-01 12:00:00"):
        old_history = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-07 12:00:00"):
        recent_history = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-10 12:00:00"):
        automation_periodic_cleanup()

    # This should be deleted, since it's more than 7 days since creation.
    assert not workflow.workflow_histories.filter(id=old_history.id).exists()
    # This is only 3 days since creation, so it shouldn't be deleted.
    assert workflow.workflow_histories.filter(id=recent_history.id).exists()


@override_settings(
    AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=2,
    AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=2,
)
@pytest.mark.django_db
def test_automation_periodic_cleanup_keeps_entries_within_both_limits(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-01 12:00:00"):
        history_1 = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-01 13:00:00"):
        history_2 = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-02 12:00:00"):
        automation_periodic_cleanup()

    # The histories are under both date and count limits, so are kept.
    assert (
        workflow.workflow_histories.filter(id__in=[history_1.id, history_2.id]).count()
        == 2
    )


@override_settings(AUTOMATION_WORKFLOW_TIMEOUT_HOURS=1)
@pytest.mark.django_db
def test_automation_periodic_cleanup_marks_timed_out_entries(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-10 11:00:00"):
        timed_out_history = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.STARTED
        )

    with freeze_time("2026-04-10 12:30:00"):
        running_history = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.STARTED
        )

    with freeze_time("2026-04-10 13:00:00"):
        automation_periodic_cleanup()

    timed_out_history.refresh_from_db()
    running_history.refresh_from_db()

    assert timed_out_history.status == HistoryStatusChoices.ERROR
    assert timed_out_history.message == "This workflow took too long and was timed out."
    assert running_history.status == HistoryStatusChoices.STARTED


@override_settings(
    AUTOMATION_WORKFLOW_TIMEOUT_HOURS=1,
    AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=7,
)
@pytest.mark.django_db
def test_automation_periodic_cleanup_marks_timeout_before_cleanup(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-10 12:00:00"):
        old_history = data_fixture.create_automation_workflow_history(
            workflow=workflow, status=HistoryStatusChoices.STARTED
        )

    with freeze_time("2026-04-18 12:00:00"):
        automation_periodic_cleanup()

    assert not workflow.workflow_histories.filter(id=old_history.id).exists()


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=2)
@pytest.mark.django_db
def test_automation_periodic_cleanup_max_entries_with_different_clones(data_fixture):
    """
    Since every test run can create a new clone (if workflow is dirty),
    history entries will have different workflow_ids but the same
    original_workflow_id. Therefore the max entries cleanup should group
    by original_workflow_id.
    """

    handler = AutomationWorkflowHandler()
    original_workflow = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-27 12:00:00"):
        clone_1 = handler._ensure_published_for_run(original_workflow)
        data_fixture.create_automation_workflow_history(
            original_workflow=original_workflow,
            workflow=clone_1,
            status=HistoryStatusChoices.SUCCESS,
        )

    with freeze_time("2026-04-28 12:00:00"):
        global_cache.update(
            WORKFLOW_DIRTY_CACHE_KEY.format(original_workflow.id), lambda _: True
        )
        clone_2 = handler._ensure_published_for_run(original_workflow)
        data_fixture.create_automation_workflow_history(
            original_workflow=original_workflow,
            workflow=clone_2,
            status=HistoryStatusChoices.SUCCESS,
        )

    with freeze_time("2026-04-29 12:00:00"):
        global_cache.update(
            WORKFLOW_DIRTY_CACHE_KEY.format(original_workflow.id), lambda _: True
        )
        clone_3 = handler._ensure_published_for_run(original_workflow)
        data_fixture.create_automation_workflow_history(
            original_workflow=original_workflow,
            workflow=clone_3,
            status=HistoryStatusChoices.SUCCESS,
        )

    assert clone_1.id != clone_2.id
    assert clone_2.id != clone_3.id
    assert original_workflow.workflow_histories.count() == 3

    with freeze_time("2026-04-30 12:00:00"):
        automation_periodic_cleanup()

    assert original_workflow.workflow_histories.count() == 2
