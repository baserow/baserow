"""
The suspend/resume primitive of the runner: a service returns a
`DispatchResult` with a `pending` part, the runner parks the node as `waiting`
and resumes it later through `resume_pending_node_celery_task`, without holding
a worker in the meantime. No node type of its own yet: the HTTP request node is
patched to suspend itself.
"""

from datetime import timedelta
from unittest.mock import ANY, patch

from django.core.cache import cache
from django.db.models import QuerySet
from django.utils import timezone

import pytest
from celery.canvas import Signature
from celery.exceptions import Ignore
from freezegun import freeze_time

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.nodes.constants import (
    AUTOMATION_PENDING_NODE_COUNTDOWN_CHUNK_SECONDS,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.tasks import resume_pending_node_celery_task
from baserow.contrib.automation.nodes.types import PendingNodeAlreadyClaimed
from baserow.contrib.automation.workflows.tasks import handle_workflow_dispatch_done
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.types import DispatchResult, PendingDispatch

HTTP_NODE_TYPE_PATH = (
    "baserow.contrib.automation.nodes.node_types.CoreHTTPRequestActionNodeType"
)
CREATE_ROW_NODE_TYPE_PATH = (
    "baserow.contrib.automation.nodes.node_types.LocalBaserowCreateRowActionNodeType"
)
HTTP_SERVICE_TYPE_PATH = (
    "baserow.contrib.integrations.core.service_types.CoreHTTPRequestServiceType"
)
NODE_HANDLER_PATH = "baserow.contrib.automation.nodes.handler"
DISPATCH_TASK = "baserow.contrib.automation.nodes.tasks.dispatch_node_celery_task"
RESUME_TASK = "baserow.contrib.automation.nodes.tasks.resume_pending_node_celery_task"
NOW = "2026-10-30 12:00:00"


def create_pending_workflow(data_fixture, user=None, **node_kwargs):
    """
    Trigger -> HTTP request -> create row, with a started run. The tests patch
    the HTTP request node type so that its dispatch suspends the node.
    """

    user = user or data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user, trigger_type="local_baserow_rows_created"
    )
    trigger_node = workflow.get_trigger()
    pending_node = data_fixture.create_automation_node(
        type="http_request",
        workflow=workflow,
        reference_node=trigger_node,
        position="south",
        output="",
        **node_kwargs,
    )
    next_node = data_fixture.create_automation_node(
        type="create_row",
        workflow=workflow,
        reference_node=pending_node,
        position="south",
        output="",
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
        event_payload={"results": [], "has_next_page": False},
    )
    return {
        "user": user,
        "workflow": workflow,
        "trigger_node": trigger_node,
        "pending_node": pending_node,
        "next_node": next_node,
        "workflow_history": workflow_history,
    }


def pending_result(seconds):
    """A dispatch result asking to be resumed `seconds` from now."""

    return DispatchResult(
        pending=PendingDispatch(
            resume_at=timezone.now() + timedelta(seconds=seconds),
            state={"seconds": seconds},
        )
    )


def suspend_node(data, seconds=5):
    """
    Dispatches the pending node at NOW so that it waits `seconds`, and returns
    its `waiting` history.
    """

    with freeze_time(NOW), patch(f"{HTTP_NODE_TYPE_PATH}.dispatch") as mock_dispatch:
        mock_dispatch.return_value = pending_result(seconds)
        result = AutomationNodeHandler().dispatch_node(
            data["pending_node"].id, history_id=data["workflow_history"].id
        )
    assert isinstance(result, Signature)
    return AutomationNodeHistory.objects.get(
        workflow_history=data["workflow_history"], node=data["pending_node"]
    )


def assert_resume_signature(result, node_history, countdown):
    """The resume task, scheduled for `countdown` seconds, replaces the dispatch."""

    assert isinstance(result, Signature)
    assert result.task == RESUME_TASK
    assert result.args == (node_history.id,)
    assert result.options["countdown"] == countdown


def assert_dispatches_next_node(
    result, node, workflow_history, current_iterations=None
):
    """The canvas returned after a resume: a group with the next node's dispatch."""

    assert isinstance(result, Signature)
    assert len(result.tasks) == 1
    task = result.tasks[0]
    if hasattr(task, "tasks"):
        assert len(task.tasks) == 1
        task = task.tasks[0]
    assert task.task == DISPATCH_TASK
    assert task.args == (node.id, workflow_history.id, current_iterations)


# Suspending ------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "seconds,countdown",
    [
        (5, 5),
        # Rounded up: the wake-up never lands before the node is due.
        (4.2, 5),
        # Cut to one chunk: the task wakes up before the broker's visibility
        # timeout and reschedules itself for the rest.
        (3600, AUTOMATION_PENDING_NODE_COUNTDOWN_CHUNK_SECONDS),
    ],
)
@patch(f"{HTTP_NODE_TYPE_PATH}.dispatch")
def test_dispatch_node_suspends_a_pending_node(
    mock_dispatch, data_fixture, seconds, countdown
):
    data = create_pending_workflow(data_fixture)
    pending_node = data["pending_node"]
    workflow_history = data["workflow_history"]

    with freeze_time(NOW):
        now = timezone.now()
        mock_dispatch.return_value = pending_result(seconds)
        result = AutomationNodeHandler().dispatch_node(
            pending_node.id, history_id=workflow_history.id
        )

    node_history = AutomationNodeHistory.objects.get(
        workflow_history=workflow_history, node=pending_node
    )
    assert_resume_signature(result, node_history, countdown)
    assert node_history.status == HistoryStatusChoices.WAITING
    assert node_history.resume_at == now + timedelta(seconds=seconds)
    assert node_history.resume_state == {
        "state": {"seconds": seconds},
        "current_iterations": None,
    }
    assert node_history.message == ""
    assert node_history.completed_on is None
    # The node has no result until it resumes.
    assert not AutomationNodeResult.objects.filter(node_history=node_history).exists()

    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.STARTED


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_dispatch_completed")
@patch(f"{NODE_HANDLER_PATH}.automation_node_dispatch_suspended")
def test_dispatch_node_sends_the_suspended_signal(
    mock_suspended, mock_completed, data_fixture
):
    data = create_pending_workflow(data_fixture)
    handler = AutomationNodeHandler()

    with freeze_time(NOW), patch(f"{HTTP_NODE_TYPE_PATH}.dispatch") as mock_dispatch:
        mock_dispatch.return_value = pending_result(5)
        handler.dispatch_node(
            data["pending_node"].id, history_id=data["workflow_history"].id
        )

    node_history = AutomationNodeHistory.objects.get(node=data["pending_node"])
    mock_suspended.send.assert_called_once_with(
        sender=handler, node=data["pending_node"], node_history=node_history
    )
    # The node is not done yet.
    mock_completed.send.assert_not_called()


@pytest.mark.django_db
@patch(f"{HTTP_NODE_TYPE_PATH}.dispatch")
def test_dispatch_node_refuses_a_pending_node_without_a_resume_time(
    mock_dispatch, data_fixture
):
    """Event-driven resumes are not supported yet: the node cannot run."""

    mock_dispatch.return_value = DispatchResult(
        pending=PendingDispatch(state={"token": "abc"})
    )
    data = create_pending_workflow(data_fixture)
    pending_node = data["pending_node"]
    workflow_history = data["workflow_history"]

    result = AutomationNodeHandler().dispatch_node(
        pending_node.id, history_id=workflow_history.id
    )

    assert result is None
    error = (
        "The node is misconfigured and cannot be dispatched. The node suspended "
        "itself without a time to resume at."
    )
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.ERROR
    assert workflow_history.message == error

    node_history = AutomationNodeHistory.objects.get(
        workflow_history=workflow_history, node=pending_node
    )
    assert node_history.status == HistoryStatusChoices.ERROR
    assert node_history.message == error
    assert node_history.resume_at is None
    assert node_history.resume_state is None


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
@patch(f"{HTTP_NODE_TYPE_PATH}.resume_dispatch")
@patch(f"{HTTP_NODE_TYPE_PATH}.dispatch")
def test_dispatch_node_never_waits_while_simulating(
    mock_dispatch, mock_resume_dispatch, mock_node_updated, data_fixture
):
    """
    A service is expected to answer at once when it uses sample data. Should
    one still suspend itself, the runner resumes it right away: a simulation
    never waits.
    """

    data = create_pending_workflow(data_fixture)
    pending_node = data["pending_node"]
    workflow_history = data["workflow_history"]
    workflow_history.simulate_until_node = pending_node
    workflow_history.save()
    mock_dispatch.return_value = pending_result(3600)
    mock_resume_dispatch.return_value = DispatchResult(
        data={"seconds": 3600, "resumed_at": "now"}
    )

    result = AutomationNodeHandler().dispatch_node(
        pending_node.id, history_id=workflow_history.id
    )

    # The simulated node was reached: the frontend is told, nothing follows.
    assert result is None
    mock_resume_dispatch.assert_called_once_with(pending_node, {"seconds": 3600}, ANY)
    mock_node_updated.send.assert_called_once_with(ANY, user=None, node=pending_node)

    # Nothing waits: the node's entry is the plain one of a simulated node, and
    # the simulation's history is thrown away as usual.
    node_history = AutomationNodeHistory.objects.get(
        workflow_history=workflow_history, node=pending_node
    )
    assert node_history.status != HistoryStatusChoices.WAITING
    assert node_history.resume_at is None
    assert node_history.resume_state is None
    handle_workflow_dispatch_done(
        workflow_history.id, simulate_until_node_id=pending_node.id
    )
    assert not AutomationWorkflowHistory.objects.filter(id=workflow_history.id).exists()


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
@patch(f"{HTTP_NODE_TYPE_PATH}.resume_dispatch")
@patch(f"{HTTP_SERVICE_TYPE_PATH}._dispatch_and_transform")
@patch(f"{HTTP_SERVICE_TYPE_PATH}.resolve_service_formulas", return_value={})
def test_pending_dispatch_is_never_stored_as_sample_data(
    mock_resolve,
    mock_dispatch_and_transform,
    mock_resume_dispatch,
    mock_node_updated,
    data_fixture,
):
    """
    A simulation stores the dispatch result as the service's sample data, which
    later simulations replay as a `DispatchResult`. A pending result has nothing
    to replay: its `pending` part is left out, like the deferred fields are.
    """

    data = create_pending_workflow(data_fixture)
    pending_node = data["pending_node"]
    workflow_history = data["workflow_history"]
    workflow_history.simulate_until_node = pending_node
    workflow_history.save()
    mock_dispatch_and_transform.return_value = pending_result(5)
    mock_resume_dispatch.return_value = DispatchResult(data={"seconds": 5})

    AutomationNodeHandler().dispatch_node(
        pending_node.id, history_id=workflow_history.id
    )

    service = pending_node.service.specific
    service.refresh_from_db()
    assert set(service.sample_data) == {
        "data",
        "status",
        "output_uid",
        "destination_service_id",
    }


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.AutomationNodeHandler._retry_condition_matches")
def test_dispatch_node_does_not_evaluate_the_retry_condition_on_a_pending_result(
    mock_matches, data_fixture
):
    """
    Like a deferred node, a pending one has no data to check yet: it is parked
    without its retry condition being evaluated.
    """

    data = create_pending_workflow(
        data_fixture,
        on_failure="retry",
        max_retries=2,
        retry_condition={"formula": "get('current_node.status_code') = 429"},
    )

    node_history = suspend_node(data)

    mock_matches.assert_not_called()
    assert node_history.status == HistoryStatusChoices.WAITING


# Resuming --------------------------------------------------------------------


@pytest.mark.django_db
def test_resume_pending_node_task_wakes_up_again_while_the_node_is_not_due(
    data_fixture,
):
    data = create_pending_workflow(data_fixture)
    node_history = suspend_node(data, seconds=1000)

    with (
        freeze_time("2026-10-30 12:05:00"),
        patch.object(
            resume_pending_node_celery_task,
            "retry",
            side_effect=RuntimeError("retry requested"),
        ) as retry,
        pytest.raises(RuntimeError, match="retry requested"),
    ):
        resume_pending_node_celery_task.run(node_history.id)

    # 700 s left, cut to one chunk.
    retry.assert_called_once_with(
        countdown=AUTOMATION_PENDING_NODE_COUNTDOWN_CHUNK_SECONDS
    )

    with (
        freeze_time("2026-10-30 12:14:00"),
        patch.object(
            resume_pending_node_celery_task,
            "retry",
            side_effect=RuntimeError("retry requested"),
        ) as retry,
        pytest.raises(RuntimeError, match="retry requested"),
    ):
        resume_pending_node_celery_task.run(node_history.id)

    # 160 s left.
    retry.assert_called_once_with(countdown=160)
    node_history.refresh_from_db()
    assert node_history.status == HistoryStatusChoices.WAITING


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_dispatch_completed")
@patch(f"{NODE_HANDLER_PATH}.automation_node_dispatch_resumed")
@patch(f"{HTTP_NODE_TYPE_PATH}.resume_dispatch")
def test_resume_pending_node_task_resumes_a_due_node(
    mock_resume_dispatch, mock_resumed, mock_completed, data_fixture
):
    data = create_pending_workflow(data_fixture)
    pending_node = data["pending_node"]
    next_node = data["next_node"]
    workflow_history = data["workflow_history"]
    node_history = suspend_node(data, seconds=5)
    resumed_data = {"seconds": 5, "resumed_at": "2026-10-30T12:00:05+00:00"}
    mock_resume_dispatch.return_value = DispatchResult(data=resumed_data)
    dispatch_count_key = AutomationNodeHandler()._node_dispatch_count_cache_key(
        workflow_history.id
    )
    dispatch_count = cache.get(dispatch_count_key)

    with (
        freeze_time("2026-10-30 12:00:05"),
        patch.object(
            resume_pending_node_celery_task, "replace", side_effect=lambda sig: sig
        ),
    ):
        resumed_on = timezone.now()
        result = resume_pending_node_celery_task.run(node_history.id)

    # The run goes on from the resumed node.
    assert_dispatches_next_node(result, next_node, workflow_history)
    mock_resume_dispatch.assert_called_once_with(pending_node, {"seconds": 5}, ANY)
    dispatch_context = mock_resume_dispatch.call_args.args[2]
    assert isinstance(dispatch_context, AutomationDispatchContext)
    assert dispatch_context.current_iterations == {}

    node_history.refresh_from_db()
    assert node_history.status == HistoryStatusChoices.SUCCESS
    assert node_history.completed_on == resumed_on
    # Kept, so the history still tells when the node resumed.
    assert node_history.resume_at == resumed_on
    assert node_history.resume_state is None
    assert (
        AutomationNodeResult.objects.get(node_history=node_history).result
        == resumed_data
    )
    # A resume is not a dispatch for the per-run limit.
    assert cache.get(dispatch_count_key) == dispatch_count

    mock_resumed.send.assert_called_once_with(
        sender=ANY, node=pending_node, node_history=node_history
    )
    mock_completed.send.assert_called_once()

    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.STARTED


@pytest.mark.django_db
@patch(f"{CREATE_ROW_NODE_TYPE_PATH}.resume_dispatch")
@patch(f"{CREATE_ROW_NODE_TYPE_PATH}.dispatch")
def test_resume_pending_node_keeps_the_iterator_position(
    mock_dispatch, mock_resume_dispatch, data_fixture
):
    """
    A node waiting inside an iterator resumes in the iteration it was
    dispatched for, and its next node is dispatched for that iteration too.
    """

    data = data_fixture.iterator_graph_fixture()
    iterator_node = data["iterator_node"]
    child_1 = data["iterator_child_1_node"]
    child_2 = data["iterator_child_2_node"]
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=data["workflow"].get_original(),
        event_payload={"results": [{"id": 1}, {"id": 2}], "has_next_page": False},
    )
    # As received from Celery: the keys of the iterator positions are strings.
    current_iterations = {str(iterator_node.id): 1}
    handler = AutomationNodeHandler()

    with freeze_time(NOW):
        mock_dispatch.return_value = pending_result(5)
        result = handler.dispatch_node(
            child_1.id,
            history_id=workflow_history.id,
            current_iterations=current_iterations,
        )

    node_history = AutomationNodeHistory.objects.get(
        workflow_history=workflow_history, node=child_1
    )
    assert_resume_signature(result, node_history, 5)
    assert node_history.resume_state == {
        "state": {"seconds": 5},
        "current_iterations": current_iterations,
    }

    mock_resume_dispatch.return_value = DispatchResult(data={"id": 10})
    with freeze_time("2026-10-30 12:00:05"):
        result = handler.resume_pending_node(node_history.id)

    dispatch_context = mock_resume_dispatch.call_args.args[2]
    assert dispatch_context.current_iterations == {iterator_node.id: 1}
    assert_dispatches_next_node(result, child_2, workflow_history, current_iterations)
    node_result = AutomationNodeResult.objects.get(node_history=node_history)
    assert node_result.iteration_path == "1"
    assert node_result.result == {"id": 10}


@pytest.mark.django_db
@patch(f"{HTTP_NODE_TYPE_PATH}.resume_dispatch")
def test_resume_pending_node_task_drops_a_duplicate_delivery(
    mock_resume_dispatch, data_fixture
):
    """
    A redelivered message, or the recovery sweep, can deliver the resume task
    twice. The copy that finds the node already claimed is dropped with
    `Ignore`, chain included, so the run is not completed twice.
    """

    data = create_pending_workflow(data_fixture)
    node_history = suspend_node(data, seconds=5)
    # The other delivery claimed the node.
    AutomationNodeHistory.objects.filter(id=node_history.id).update(
        status=HistoryStatusChoices.STARTED
    )

    with freeze_time("2026-10-30 12:00:05"), pytest.raises(Ignore):
        resume_pending_node_celery_task.run(node_history.id)

    mock_resume_dispatch.assert_not_called()


@pytest.mark.django_db
@patch(f"{HTTP_NODE_TYPE_PATH}.resume_dispatch")
def test_resume_pending_node_loses_the_claim_to_a_concurrent_delivery(
    mock_resume_dispatch, data_fixture
):
    """
    Two deliveries can both find the node `waiting`; the conditional update
    lets only one of them resume it.
    """

    data = create_pending_workflow(data_fixture)
    node_history = suspend_node(data, seconds=5)

    with (
        freeze_time("2026-10-30 12:00:05"),
        # The other delivery wins the update between our read and our write.
        patch.object(QuerySet, "update", return_value=0),
    ):
        result = AutomationNodeHandler().resume_pending_node(node_history.id)

    assert result == PendingNodeAlreadyClaimed()
    mock_resume_dispatch.assert_not_called()


@pytest.mark.django_db
# Noticed whether the node is due or not: nobody waits for a cancelled run.
@pytest.mark.parametrize("wake_up", ["2026-10-30 12:00:02", "2026-10-30 12:00:05"])
@patch(f"{HTTP_NODE_TYPE_PATH}.resume_dispatch")
def test_resume_pending_node_task_finalizes_a_requested_cancellation(
    mock_resume_dispatch, data_fixture, wake_up
):
    user = data_fixture.create_user(first_name="Ada")
    data = create_pending_workflow(data_fixture, user=user)
    workflow_history = data["workflow_history"]
    node_history = suspend_node(data, seconds=5)
    AutomationHistoryHandler().request_workflow_history_cancellation(
        workflow_history, user
    )

    with freeze_time(wake_up):
        completed_on = timezone.now()
        result = resume_pending_node_celery_task.run(node_history.id)

    assert result is None
    mock_resume_dispatch.assert_not_called()

    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.CANCELLED
    assert workflow_history.message == f"Cancelled by Ada ({user.id})."
    assert workflow_history.completed_on == completed_on

    node_history.refresh_from_db()
    assert node_history.status == HistoryStatusChoices.CANCELLED
    assert node_history.message == workflow_history.message
    assert node_history.completed_on == completed_on

    # The chain's tail keeps the cancelled outcome.
    handle_workflow_dispatch_done(history_id=workflow_history.id)
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.CANCELLED


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", [HistoryStatusChoices.ERROR, HistoryStatusChoices.CANCELLED]
)
@patch(f"{HTTP_NODE_TYPE_PATH}.resume_dispatch")
def test_resume_pending_node_task_closes_the_node_of_a_resolved_run(
    mock_resume_dispatch, data_fixture, status
):
    """The run was resolved while the node waited, e.g. by the timeout sweep."""

    data = create_pending_workflow(data_fixture)
    workflow_history = data["workflow_history"]
    node_history = suspend_node(data, seconds=5)
    AutomationWorkflowHistory.objects.filter(id=workflow_history.id).update(
        status=status, message="Resolved elsewhere.", completed_on=timezone.now()
    )

    with freeze_time("2026-10-30 12:00:05"):
        result = resume_pending_node_celery_task.run(node_history.id)

    assert result is None
    mock_resume_dispatch.assert_not_called()
    node_history.refresh_from_db()
    assert node_history.status == status
    assert node_history.message == "Resolved elsewhere."
    assert node_history.completed_on is not None


@pytest.mark.django_db
def test_resume_pending_node_task_returns_none_for_a_deleted_node_history(
    data_fixture,
):
    """The node or its workflow was deleted while the node waited."""

    data = create_pending_workflow(data_fixture)
    node_history = suspend_node(data, seconds=5)
    AutomationNodeHistory.objects.filter(id=node_history.id).delete()

    with freeze_time("2026-10-30 12:00:05"):
        assert resume_pending_node_celery_task.run(node_history.id) is None


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.logger")
@patch(f"{HTTP_NODE_TYPE_PATH}.resume_dispatch", side_effect=ValueError("Clock broken"))
def test_resume_pending_node_marks_the_run_as_errored_when_the_resume_fails(
    mock_resume_dispatch, mock_logger, data_fixture
):
    # The node retries failed dispatches, but a resume is never retried.
    data = create_pending_workflow(data_fixture, on_failure="retry", max_retries=2)
    pending_node = data["pending_node"]
    workflow_history = data["workflow_history"]
    node_history = suspend_node(data, seconds=5)

    with freeze_time("2026-10-30 12:00:05"):
        result = resume_pending_node_celery_task.run(node_history.id)

    assert result is None
    workflow_id = data["workflow"].id
    error = f"Error while resuming workflow {workflow_id}. Error: Clock broken"
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.ERROR
    assert workflow_history.message == error

    node_history.refresh_from_db()
    assert node_history.status == HistoryStatusChoices.ERROR
    assert node_history.message == error
    assert node_history.attempt == 1
    assert AutomationNodeResult.objects.get(node_history=node_history).result == {}
    assert AutomationNodeHistory.objects.filter(node=pending_node).count() == 1


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.logger")
def test_resume_pending_node_fails_when_the_service_type_cannot_resume(
    mock_logger, data_fixture
):
    """A service type that returns a pending result must implement resume_dispatch()."""

    data = create_pending_workflow(data_fixture)
    workflow_history = data["workflow_history"]
    node_history = suspend_node(data, seconds=5)

    with freeze_time("2026-10-30 12:00:05"):
        result = resume_pending_node_celery_task.run(node_history.id)

    assert result is None
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.ERROR
    assert workflow_history.message == (
        f"Error while resuming workflow {data['workflow'].id}. Error: The "
        "http_request service type returned a pending dispatch but does not "
        "implement resume_dispatch()."
    )


# Node type -------------------------------------------------------------------


@pytest.mark.django_db
@patch(f"{HTTP_SERVICE_TYPE_PATH}.resume_dispatch")
def test_node_type_resume_dispatch_resumes_the_service(
    mock_service_resume_dispatch, data_fixture
):
    data = create_pending_workflow(data_fixture)
    pending_node = data["pending_node"]
    dispatch_context = AutomationDispatchContext(
        pending_node.workflow, data["workflow_history"]
    )
    mock_service_resume_dispatch.return_value = DispatchResult(data={"seconds": 5})

    result = pending_node.get_type().resume_dispatch(
        pending_node, {"seconds": 5}, dispatch_context
    )

    assert result == DispatchResult(data={"seconds": 5})
    mock_service_resume_dispatch.assert_called_once_with(
        pending_node.service.specific, {"seconds": 5}, dispatch_context
    )


@pytest.mark.django_db
@patch(f"{HTTP_NODE_TYPE_PATH}.is_deactivated", return_value=True)
def test_node_type_resume_dispatch_refuses_a_deactivated_node_type(
    mock_is_deactivated, data_fixture
):
    data = create_pending_workflow(data_fixture)
    pending_node = data["pending_node"]
    dispatch_context = AutomationDispatchContext(
        pending_node.workflow, data["workflow_history"]
    )

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        pending_node.get_type().resume_dispatch(pending_node, {}, dispatch_context)
