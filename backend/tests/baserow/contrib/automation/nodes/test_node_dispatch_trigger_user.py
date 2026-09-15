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
def test_dispatch_node_does_not_act_as_who_started_the_run(data_fixture):
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

    assert [context.actor for context in captured] == [None]
