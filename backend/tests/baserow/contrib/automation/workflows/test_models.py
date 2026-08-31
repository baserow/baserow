from django.db.models import Prefetch

import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import CorePeriodicTriggerNodeType
from baserow.contrib.automation.workflows.models import AutomationWorkflow


@pytest.mark.django_db
def test_automation_workflow_get_parent(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)

    result = workflow.get_parent()

    assert result == workflow.automation


@pytest.mark.django_db
def test_can_be_immediately_dispatched(data_fixture):
    workflow_without_trigger = data_fixture.create_automation_workflow(
        create_trigger=False
    )
    assert workflow_without_trigger.can_be_immediately_dispatched() is False

    # The default trigger type waits for an external event.
    workflow_with_event_trigger = data_fixture.create_automation_workflow()
    assert workflow_with_event_trigger.can_be_immediately_dispatched() is False

    workflow_with_immediate_trigger = data_fixture.create_automation_workflow(
        trigger_type=CorePeriodicTriggerNodeType.type
    )
    assert workflow_with_immediate_trigger.can_be_immediately_dispatched() is True


@pytest.mark.django_db
def test_can_be_immediately_dispatched_uses_prefetched_nodes(
    data_fixture, django_assert_num_queries
):
    workflow = data_fixture.create_automation_workflow(
        trigger_type=CorePeriodicTriggerNodeType.type
    )

    prefetched_workflow = AutomationWorkflow.objects.prefetch_related(
        Prefetch(
            "automation_workflow_nodes",
            queryset=AutomationNode.objects.select_related("service"),
        )
    ).get(id=workflow.id)

    with django_assert_num_queries(0):
        assert prefetched_workflow.can_be_immediately_dispatched() is True
