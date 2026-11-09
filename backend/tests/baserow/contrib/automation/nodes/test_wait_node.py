"""
The Wait node, end to end through the runner with the real Wait service:
trigger -> Wait -> create row. The suspend/resume primitive it rides on is
covered on its own in `test_pending_node.py`.
"""

from collections import defaultdict
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

import pytest
from celery.canvas import Signature
from freezegun import freeze_time

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.tasks import resume_pending_node_celery_task
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.core.utils import MirrorDict

NODE_HANDLER_PATH = "baserow.contrib.automation.nodes.handler"
DISPATCH_TASK = "baserow.contrib.automation.nodes.tasks.dispatch_node_celery_task"
RESUME_TASK = "baserow.contrib.automation.nodes.tasks.resume_pending_node_celery_task"
NOW = "2026-10-30 12:00:00"
NOW_ISO = "2026-10-30T12:00:00+00:00"


def create_wait_workflow(data_fixture, seconds="5"):
    """Trigger -> Wait(`seconds`) -> create row, with a started run."""

    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user, trigger_type="local_baserow_rows_created"
    )
    trigger_node = workflow.get_trigger()
    wait_node = data_fixture.create_core_wait_action_node(
        workflow=workflow,
        reference_node=trigger_node,
        position="south",
        output="",
        service_kwargs={"seconds": seconds},
    )
    next_node = data_fixture.create_automation_node(
        type="create_row",
        workflow=workflow,
        reference_node=wait_node,
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
        "wait_node": wait_node,
        "next_node": next_node,
        "workflow_history": workflow_history,
    }


def dispatch_wait_node(data):
    return AutomationNodeHandler().dispatch_node(
        data["wait_node"].id, history_id=data["workflow_history"].id
    )


def get_wait_node_history(data):
    return AutomationNodeHistory.objects.get(
        workflow_history=data["workflow_history"], node=data["wait_node"]
    )


def assert_dispatches_next_node(result, node, workflow_history):
    """The canvas returned once the Wait node is done: the next node's dispatch."""

    assert isinstance(result, Signature)
    assert len(result.tasks) == 1
    task = result.tasks[0]
    if hasattr(task, "tasks"):
        assert len(task.tasks) == 1
        task = task.tasks[0]
    assert task.task == DISPATCH_TASK
    assert task.args == (node.id, workflow_history.id, None)


def test_wait_node_type_is_an_action_node_of_the_automation_runner_only():
    node_type = automation_node_type_registry.get("wait")
    assert node_type.is_workflow_action
    assert node_type.service_type == "wait"
    assert str(node_type.display_name) == "Wait"

    # Only the automation runner can park a pending dispatch, so the service
    # is not offered as a builder workflow action.
    assert "wait" not in [
        getattr(action_type, "service_type", None)
        for action_type in builder_workflow_action_type_registry.get_all()
    ]


@pytest.mark.django_db
def test_wait_node_suspends_the_run_for_the_configured_seconds(data_fixture):
    data = create_wait_workflow(data_fixture, seconds="5")
    workflow_history = data["workflow_history"]

    with freeze_time(NOW):
        result = dispatch_wait_node(data)
        resume_at = timezone.now() + timedelta(seconds=5)

    node_history = get_wait_node_history(data)
    assert isinstance(result, Signature)
    assert result.task == RESUME_TASK
    assert result.args == (node_history.id,)
    assert result.options["countdown"] == 5

    assert node_history.status == HistoryStatusChoices.WAITING
    assert node_history.resume_at == resume_at
    assert node_history.resume_state == {
        "state": {"seconds": 5},
        "current_iterations": None,
    }

    # Nothing after the Wait node has run, and the run itself goes on.
    assert not AutomationNodeHistory.objects.filter(node=data["next_node"]).exists()
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.STARTED


@pytest.mark.django_db
def test_wait_node_resumes_the_run_once_the_seconds_have_passed(data_fixture):
    data = create_wait_workflow(data_fixture, seconds="5")
    workflow_history = data["workflow_history"]
    with freeze_time(NOW):
        dispatch_wait_node(data)
    node_history = get_wait_node_history(data)

    with (
        freeze_time("2026-10-30 12:00:05"),
        patch.object(
            resume_pending_node_celery_task, "replace", side_effect=lambda sig: sig
        ),
    ):
        result = resume_pending_node_celery_task.run(node_history.id)

    assert_dispatches_next_node(result, data["next_node"], workflow_history)

    node_history.refresh_from_db()
    assert node_history.status == HistoryStatusChoices.SUCCESS
    assert node_history.resume_state is None
    assert AutomationNodeResult.objects.get(node_history=node_history).result == {
        "seconds": 5,
        "resumed_at": "2026-10-30T12:00:05+00:00",
    }


@pytest.mark.django_db
def test_wait_node_with_zero_seconds_completes_at_once_as_skipped(data_fixture):
    """
    Zero is a valid wait that has nothing to wait for: the node completes at
    once and its history says `skipped`, so a computed zero is visibly a no-op.
    """

    data = create_wait_workflow(data_fixture, seconds="0")

    with freeze_time(NOW):
        result = dispatch_wait_node(data)

    assert_dispatches_next_node(result, data["next_node"], data["workflow_history"])

    node_history = get_wait_node_history(data)
    assert node_history.status == HistoryStatusChoices.SKIPPED
    assert node_history.resume_at is None
    assert node_history.resume_state is None
    assert AutomationNodeResult.objects.get(node_history=node_history).result == {
        "seconds": 0,
        "resumed_at": NOW_ISO,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula",
    [
        pytest.param("", id="empty"),
        pytest.param("'abc'", id="text"),
        pytest.param("1.5", id="fractional"),
        pytest.param("minus(0, 3)", id="negative"),
    ],
)
def test_wait_node_fails_on_an_invalid_number_of_seconds(data_fixture, formula):
    data = create_wait_workflow(data_fixture, seconds=formula)
    workflow_history = data["workflow_history"]

    result = dispatch_wait_node(data)

    assert result is None
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.ERROR

    node_history = get_wait_node_history(data)
    assert node_history.status == HistoryStatusChoices.ERROR
    assert 'Value error for property "seconds"' in node_history.message
    assert node_history.resume_at is None
    assert node_history.resume_state is None


@pytest.mark.django_db
@override_settings(AUTOMATION_WAIT_MAX_SECONDS=10)
def test_wait_node_fails_when_the_wait_exceeds_the_maximum(data_fixture):
    data = create_wait_workflow(data_fixture, seconds="11")
    workflow_history = data["workflow_history"]

    result = dispatch_wait_node(data)

    assert result is None
    error = (
        "The node is misconfigured and cannot be dispatched. The wait of 11 "
        "seconds exceeds the maximum of 10 seconds."
    )
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.ERROR
    assert workflow_history.message == error

    node_history = get_wait_node_history(data)
    assert node_history.status == HistoryStatusChoices.ERROR
    assert node_history.message == error


@pytest.mark.django_db
def test_wait_node_has_no_error_policy(data_fixture):
    """
    A wait only fails on its duration, which a retry would evaluate to the same
    value, so the node type does not accept the error policy fields.
    """

    data = create_wait_workflow(data_fixture)
    wait_node = data["wait_node"]

    assert not wait_node.get_type().has_error_policy

    AutomationNodeHandler().update_node(
        wait_node, label="Pause", on_failure="retry", max_retries=5
    )

    wait_node.refresh_from_db()
    assert wait_node.label == "Pause"
    assert wait_node.on_failure == "stop"
    assert wait_node.max_retries == 2


@pytest.mark.django_db
def test_wait_node_never_retries_a_stored_retry_policy(data_fixture):
    """
    An import can still store a retry policy on a Wait node: the runner ignores
    it, so an invalid wait fails at once rather than after pointless retries.
    """

    data = create_wait_workflow(data_fixture, seconds="'abc'")
    type(data["wait_node"]).objects.filter(id=data["wait_node"].id).update(
        on_failure="retry", max_retries=3
    )
    workflow_history = data["workflow_history"]

    result = dispatch_wait_node(data)

    assert result is None
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.ERROR
    node_history = get_wait_node_history(data)
    assert node_history.status == HistoryStatusChoices.ERROR
    assert node_history.attempt == 1


@pytest.mark.django_db
def test_wait_node_never_evaluates_a_stored_retry_condition(data_fixture):
    """
    The same holds for the retry condition: a completed wait moves on to the
    next node even when a stored condition would match its result.
    """

    data = create_wait_workflow(data_fixture, seconds="0")
    type(data["wait_node"]).objects.filter(id=data["wait_node"].id).update(
        on_failure="retry",
        max_retries=3,
        retry_condition={
            "formula": "get('current_node.seconds') = 0",
            "mode": "advanced",
            "version": "0.1",
        },
    )

    with freeze_time(NOW):
        result = dispatch_wait_node(data)

    assert_dispatches_next_node(result, data["next_node"], data["workflow_history"])
    node_history = get_wait_node_history(data)
    assert node_history.status == HistoryStatusChoices.SKIPPED
    assert node_history.attempt == 1


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
def test_wait_node_never_waits_while_simulating(mock_node_updated, data_fixture):
    """
    Simulating up to the Wait node returns at once with the result a real wait
    would have produced, which is stored as the node's sample data.
    """

    data = create_wait_workflow(data_fixture, seconds="3600")
    wait_node = data["wait_node"]
    workflow_history = data["workflow_history"]
    workflow_history.simulate_until_node = wait_node
    workflow_history.save()

    with freeze_time(NOW):
        result = dispatch_wait_node(data)

    # The simulated node was reached: nothing follows.
    assert result is None

    # Nothing waits. The runner stops at the simulated node before it closes the
    # node's history entry, which is thrown away with the simulation's run.
    node_history = get_wait_node_history(data)
    assert node_history.status != HistoryStatusChoices.WAITING
    assert node_history.resume_at is None
    assert node_history.resume_state is None

    service = wait_node.service.specific
    service.refresh_from_db()
    assert service.sample_data["data"] == {"seconds": 3600, "resumed_at": NOW_ISO}
    assert "pending" not in service.sample_data


@pytest.mark.django_db
def test_wait_node_export_import_keeps_the_seconds_formula(data_fixture):
    data = create_wait_workflow(data_fixture, seconds="5")
    handler = AutomationNodeHandler()
    serialized = handler.export_node(data["wait_node"])

    target_workflow = data_fixture.create_automation_workflow(user=data["user"])
    id_mapping = defaultdict(MirrorDict)
    id_mapping["services"] = {}
    [imported] = handler.import_nodes(target_workflow, [serialized], id_mapping)

    assert imported.get_type().type == "wait"
    assert imported.service.specific.seconds["formula"] == "5"
