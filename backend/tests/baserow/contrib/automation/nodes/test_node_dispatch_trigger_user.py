from unittest.mock import patch

import pytest

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.node_types import CoreManualTriggerNodeType
from baserow.core.services.types import DispatchResult


def _capture_context(captured):
    """A node type `dispatch` that records the context it was handed."""

    def dispatch(self, node, dispatch_context):
        captured.append(dispatch_context)
        return DispatchResult(data={})

    return dispatch


@pytest.mark.django_db
def test_dispatch_node_hands_the_trigger_user_to_the_context(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    trigger = workflow.get_trigger()
    history = data_fixture.create_automation_workflow_history(
        workflow=workflow, triggered_by_id=user.id, triggered_by_type="auth.User"
    )
    captured = []

    with patch.object(
        CoreManualTriggerNodeType, "dispatch", _capture_context(captured)
    ):
        AutomationNodeHandler().dispatch_node(trigger.id, history.id)

    assert [context.triggered_by for context in captured] == [user]
    assert [context.actor for context in captured] == [None]


@pytest.mark.django_db
def test_dispatch_node_hands_no_trigger_user_when_nobody_started_it(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    trigger = workflow.get_trigger()
    history = data_fixture.create_automation_workflow_history(workflow=workflow)
    captured = []

    with patch.object(
        CoreManualTriggerNodeType, "dispatch", _capture_context(captured)
    ):
        AutomationNodeHandler().dispatch_node(trigger.id, history.id)

    assert [context.triggered_by for context in captured] == [None]


@pytest.mark.django_db
def test_dispatch_node_hands_no_trigger_user_once_the_user_is_deleted(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    trigger = workflow.get_trigger()
    starter = data_fixture.create_user()
    history = data_fixture.create_automation_workflow_history(
        workflow=workflow, triggered_by_id=starter.id, triggered_by_type="auth.User"
    )
    starter.delete()
    captured = []

    with patch.object(
        CoreManualTriggerNodeType, "dispatch", _capture_context(captured)
    ):
        AutomationNodeHandler().dispatch_node(trigger.id, history.id)

    assert [context.triggered_by for context in captured] == [None]
