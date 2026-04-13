from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.workflows.tasks import clear_old_automation_history


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=2)
@pytest.mark.django_db
def test_clear_old_automation_history_keeps_max_entries_per_workflow(data_fixture):
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
        clear_old_automation_history()

    # Since workflow_a had 3 entries and max is 2, the oldest entry is deleted.
    assert not workflow_a.workflow_histories.filter(id=workflow_a_history_1.id).exists()
    assert workflow_a.workflow_histories.filter(id=workflow_a_history_2.id).exists()
    assert workflow_a.workflow_histories.filter(id=workflow_a_history_3.id).exists()

    # workflow_b has only 1 entry, which is under the max limit, so it
    # isn't deleted.
    assert workflow_b.workflow_histories.filter(id=workflow_b_history_1.id).exists()


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=1)
@pytest.mark.django_db
def test_clear_old_automation_history_excludes_started_from_date_cleanup(data_fixture):
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
        clear_old_automation_history()

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


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=2)
@pytest.mark.django_db
def test_clear_old_automation_history_excludes_started_from_count_cleanup(data_fixture):
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
        clear_old_automation_history()

    # There are 3 history entries. Even though max_entries is 2, the oldest
    # entry is STARTED, so it is not deleted.
    assert workflow.workflow_histories.filter(id=history_started.id).exists()
    assert workflow.workflow_histories.count() == 3


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=7)
@pytest.mark.django_db
def test_clear_old_automation_history_deletes_entries_older_than_max_days(data_fixture):
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
        clear_old_automation_history()

    # This should be deleted, since it's more than 7 days since creation.
    assert not workflow.workflow_histories.filter(id=old_history.id).exists()
    # This is only 3 days since creation, so it shouldn't be deleted.
    assert workflow.workflow_histories.filter(id=recent_history.id).exists()


@override_settings(
    AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=2,
    AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES=2,
)
@pytest.mark.django_db
def test_clear_old_automation_history_keeps_entries_within_both_limits(data_fixture):
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
        clear_old_automation_history()

    # The histories are under both date and count limits, so are kept.
    assert (
        workflow.workflow_histories.filter(id__in=[history_1.id, history_2.id]).count()
        == 2
    )
