from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.db.models import QuerySet
from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationWorkflowHistory,
    AutomationWorkflowHistoryResponse,
)
from baserow.contrib.automation.workflows.constants import (
    STALLED_RUN_CANCELLED_ERROR,
    STALLED_RUN_ERROR,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.tasks import automation_run_stall_check

HANDLER_PATH = "baserow.contrib.automation.workflows.handler"

NOW = datetime(2026, 4, 16, 12, 0, 0, tzinfo=timezone.utc)

# 60 minute stall timeout, 5 minute warning and interval. With the default 60
# minute cleanup interval, the waiting grace is 75 + 2 * 60 = 195 minutes.
STALL_SETTINGS = dict(
    AUTOMATION_RUN_STALL_TIMEOUT_MINUTES=60,
    AUTOMATION_RUN_STALL_WARNING_MINUTES=5,
    AUTOMATION_RUN_STALL_SWEEP_INTERVAL_MINUTES=5,
    AUTOMATION_WORKFLOW_HISTORY_CLEANUP_INTERVAL_MINUTES=60,
    AUTOMATION_WORKFLOW_TIMEOUT_HOURS=24,
)


def ago(**kwargs):
    return NOW - timedelta(**kwargs)


def create_run(data_fixture, workflow, started_on, **kwargs):
    return data_fixture.create_automation_workflow_history(
        workflow=workflow,
        started_on=started_on,
        status=HistoryStatusChoices.STARTED,
        **kwargs,
    )


def create_node_row(
    workflow_history,
    node,
    started_on,
    completed_on=None,
    status=HistoryStatusChoices.SUCCESS,
    **kwargs,
):
    return AutomationNodeHistory.objects.create(
        workflow_history=workflow_history,
        node=node,
        started_on=started_on,
        completed_on=completed_on,
        status=status,
        **kwargs,
    )


def sweep():
    with freeze_time(NOW):
        return AutomationWorkflowHandler().mark_failure_for_stalled_history()


def assert_untouched(history):
    history.refresh_from_db()
    assert history.status == HistoryStatusChoices.STARTED
    assert history.completed_on is None


def assert_interrupted(history, message=STALLED_RUN_ERROR):
    history.refresh_from_db()
    expected_status = (
        HistoryStatusChoices.CANCELLED
        if message == STALLED_RUN_CANCELLED_ERROR
        else HistoryStatusChoices.ERROR
    )
    assert history.status == expected_status
    assert history.message == message
    assert history.completed_on == NOW


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_fails_run_without_node_rows(data_fixture):
    """Case A: the first publish was lost, so no node row was ever created."""

    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(minutes=61))

    assert sweep() == 1

    assert_interrupted(history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_leaves_young_run_without_node_rows(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(minutes=59))

    assert sweep() == 0

    assert_untouched(history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_fails_run_whose_last_node_completed_long_ago(data_fixture):
    """Case B: the nodes completed, the next one never started."""

    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=3))
    node_row = create_node_row(
        history, workflow.get_trigger(), ago(hours=3), completed_on=ago(minutes=61)
    )

    assert sweep() == 1

    assert_interrupted(history)
    # A completed node row is left as it is.
    node_row.refresh_from_db()
    assert node_row.status == HistoryStatusChoices.SUCCESS


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_leaves_run_whose_last_node_completed_recently(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=3))
    create_node_row(
        history, workflow.get_trigger(), ago(hours=3), completed_on=ago(hours=2)
    )
    create_node_row(
        history, workflow.get_trigger(), ago(hours=2), completed_on=ago(minutes=30)
    )

    assert sweep() == 0

    assert_untouched(history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_leaves_run_with_recently_retried_node(data_fixture):
    """The next attempt of a retried node follows within seconds."""

    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=3))
    create_node_row(
        history,
        workflow.get_trigger(),
        ago(seconds=6),
        completed_on=ago(seconds=5),
        status=HistoryStatusChoices.RETRIED,
    )

    assert sweep() == 0

    assert_untouched(history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_resolves_cancellation_requested_run_as_cancelled(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    cancelled_history = create_run(
        data_fixture,
        workflow,
        ago(minutes=90),
        cancellation_requested_by=user,
        cancellation_requested_on=ago(minutes=80),
    )
    error_history = create_run(data_fixture, workflow, ago(minutes=90))

    assert sweep() == 2

    assert_interrupted(cancelled_history, STALLED_RUN_CANCELLED_ERROR)
    assert_interrupted(error_history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_closes_half_open_node_row_of_deferred_parent(data_fixture):
    """
    Case D: a parent waiting on a deferred child keeps its node row `started`
    with no `completed_on`. If the poller is lost, the row's `started_on` is the
    last progress, and the row is closed with the run.
    """

    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=2))
    node_row = create_node_row(
        history,
        workflow.get_trigger(),
        ago(minutes=61),
        status=HistoryStatusChoices.STARTED,
    )

    assert sweep() == 1

    assert_interrupted(history)
    node_row.refresh_from_db()
    assert node_row.status == HistoryStatusChoices.ERROR
    assert node_row.message == STALLED_RUN_ERROR
    assert node_row.completed_on == NOW


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_leaves_recently_started_half_open_node_row(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=2))
    create_node_row(
        history,
        workflow.get_trigger(),
        ago(minutes=30),
        status=HistoryStatusChoices.STARTED,
    )

    assert sweep() == 0

    assert_untouched(history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_fails_stalled_test_run(data_fixture):
    """A test run is dispatched, and dies, the same way as a live one."""

    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    history = create_run(
        data_fixture,
        workflow,
        ago(minutes=61),
        simulate_until_node=trigger,
        is_test_run=True,
    )

    assert sweep() == 1

    assert_interrupted(history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_does_not_rewrite_run_resolved_after_read(data_fixture):
    """
    A run that finishes on its own between the sweep's read and its writes is
    not rewritten, and no event is sent for it: it sent its own.
    """

    workflow = data_fixture.create_automation_workflow()
    finishing_history = create_run(data_fixture, workflow, ago(minutes=90))
    stalled_history = create_run(data_fixture, workflow, ago(minutes=90))

    real_update = QuerySet.update
    raced = False

    def racing_update(queryset, *args, **kwargs):
        nonlocal raced
        if queryset.model is AutomationWorkflowHistory and not raced:
            raced = True
            real_update(
                AutomationWorkflowHistory.objects.filter(id=finishing_history.id),
                status=HistoryStatusChoices.SUCCESS,
                completed_on=ago(seconds=1),
            )
        return real_update(queryset, *args, **kwargs)

    with (
        patch.object(QuerySet, "update", racing_update),
        patch(f"{HANDLER_PATH}.automation_workflow_dispatch_done.send") as send,
    ):
        assert sweep() == 1

    finishing_history.refresh_from_db()
    assert finishing_history.status == HistoryStatusChoices.SUCCESS
    assert finishing_history.completed_on == ago(seconds=1)
    assert_interrupted(stalled_history)

    assert send.call_count == 1
    assert send.call_args.kwargs["workflow_history"].id == stalled_history.id


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_sends_dispatch_done_once_per_resolved_run(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    first = create_run(data_fixture, workflow, ago(minutes=90))
    second = create_run(data_fixture, workflow, ago(minutes=80))
    create_run(data_fixture, workflow, ago(minutes=10))

    with patch(f"{HANDLER_PATH}.automation_workflow_dispatch_done.send") as send:
        assert sweep() == 2

    sent_ids = sorted(
        call.kwargs["workflow_history"].id for call in send.call_args_list
    )
    assert sent_ids == sorted([first.id, second.id])


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_creates_no_default_response(data_fixture):
    """Every response waiter gave up long before a run counts as stalled."""

    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(minutes=61))

    assert sweep() == 1

    assert not AutomationWorkflowHistoryResponse.objects.filter(
        workflow_history=history
    ).exists()


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_resolves_a_batch_oldest_first(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    oldest = create_run(data_fixture, workflow, ago(minutes=90))
    middle = create_run(data_fixture, workflow, ago(minutes=80))
    newest = create_run(data_fixture, workflow, ago(minutes=70))

    with patch(f"{HANDLER_PATH}.STALLED_RUN_SWEEP_BATCH_SIZE", 2):
        assert sweep() == 2

        assert_interrupted(oldest)
        assert_interrupted(middle)
        assert_untouched(newest)

        # The next pass takes the rest.
        assert sweep() == 1

    assert_interrupted(newest)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_timeout_sweep_keeps_its_own_message_when_it_runs_first(data_fixture):
    """
    A run past the run timeout that the timeout sweep reaches first keeps the
    timeout message, so the two cases stay distinguishable in the history.
    """

    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=25))

    with freeze_time(NOW):
        AutomationWorkflowHandler().mark_failure_for_timed_out_history()
    assert sweep() == 0

    history.refresh_from_db()
    assert history.status == HistoryStatusChoices.ERROR
    assert history.message == "This workflow took too long and was timed out."


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_leaves_run_with_waiting_node_not_due(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=10))
    create_node_row(
        history,
        workflow.get_trigger(),
        ago(hours=10),
        status=HistoryStatusChoices.WAITING,
        resume_at=NOW + timedelta(hours=2),
    )

    assert sweep() == 0

    assert_untouched(history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_leaves_run_with_waiting_node_overdue_inside_grace(
    data_fixture,
):
    """The recovery of a lost resume gets two tries inside the grace."""

    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=10))
    create_node_row(
        history,
        workflow.get_trigger(),
        ago(hours=10),
        status=HistoryStatusChoices.WAITING,
        resume_at=ago(minutes=100),
    )

    assert sweep() == 0

    assert_untouched(history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_fails_run_with_waiting_node_overdue_past_grace(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, ago(hours=10))
    node_row = create_node_row(
        history,
        workflow.get_trigger(),
        ago(hours=10),
        status=HistoryStatusChoices.WAITING,
        resume_at=ago(minutes=200),
    )

    assert sweep() == 1

    assert_interrupted(history)
    node_row.refresh_from_db()
    assert node_row.status == HistoryStatusChoices.ERROR
    assert node_row.message == STALLED_RUN_ERROR
    assert node_row.completed_on == NOW


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_stall_sweep_waiting_guard_matches_one_node_row(data_fixture):
    """
    The guard is about a single waiting row inside the grace. An old resolved
    row next to it does not change that, and a waiting row past the grace is not
    saved by another, non-waiting row whose `resume_at` is inside it.
    """

    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()

    guarded_history = create_run(data_fixture, workflow, ago(hours=10))
    create_node_row(guarded_history, trigger, ago(hours=10), completed_on=ago(hours=9))
    create_node_row(
        guarded_history,
        trigger,
        ago(hours=9),
        status=HistoryStatusChoices.WAITING,
        resume_at=ago(minutes=100),
    )

    unguarded_history = create_run(data_fixture, workflow, ago(hours=10))
    create_node_row(
        unguarded_history,
        trigger,
        ago(hours=10),
        completed_on=ago(minutes=61),
        status=HistoryStatusChoices.SUCCESS,
        resume_at=ago(minutes=100),
    )
    create_node_row(
        unguarded_history,
        trigger,
        ago(hours=9),
        status=HistoryStatusChoices.WAITING,
        resume_at=ago(minutes=200),
    )

    assert sweep() == 1

    assert_untouched(guarded_history)
    assert_interrupted(unguarded_history)


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_count_runs_newly_stalled_counts_a_run_once(data_fixture):
    """
    With a 5 minute warning and a 5 minute interval, a run is counted by the
    one sweep whose last 5 minutes saw it cross the warning threshold.
    """

    workflow = data_fixture.create_automation_workflow()
    create_run(data_fixture, workflow, NOW)
    handler = AutomationWorkflowHandler()

    # One call per sweep, a sweep interval apart.
    counts = []
    for minutes in (3, 8, 13, 18):
        with freeze_time(NOW + timedelta(minutes=minutes)):
            counts.append(handler.count_runs_newly_stalled())

    assert counts == [0, 1, 0, 0]


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_count_runs_newly_stalled_applies_the_waiting_guard(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    history = create_run(data_fixture, workflow, NOW)
    create_node_row(
        history,
        workflow.get_trigger(),
        NOW,
        status=HistoryStatusChoices.WAITING,
        resume_at=NOW + timedelta(hours=1),
    )

    with freeze_time(NOW + timedelta(minutes=7)):
        assert AutomationWorkflowHandler().count_runs_newly_stalled() == 0


@override_settings(**STALL_SETTINGS)
@pytest.mark.django_db
def test_automation_run_stall_check_task_resolves_stalled_runs(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    stalled_history = create_run(data_fixture, workflow, ago(minutes=61))
    running_history = create_run(data_fixture, workflow, ago(minutes=10))

    with freeze_time(NOW):
        automation_run_stall_check()

    assert_interrupted(stalled_history)
    assert_untouched(running_history)
