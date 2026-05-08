from datetime import date

import pytest

from baserow.contrib.automation.nodes.signals import automation_node_dispatch_completed
from baserow.contrib.automation.usage.models import WorkspaceAutomationUsage


@pytest.mark.django_db
def test_usage_incremented_on_dispatch(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_local_baserow_create_row_action_node(user=user)

    automation_node_dispatch_completed.send(
        sender=None,
        node=node,
    )

    usage = WorkspaceAutomationUsage.objects.get(
        workspace=node.workflow.automation.workspace,
        period=date.today(),
    )
    assert usage.dispatch_count == 1


@pytest.mark.django_db
def test_usage_not_incremented_for_free_nodes(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user, trigger_type="local_baserow_rows_created"
    )
    trigger = workflow.get_trigger()

    automation_node_dispatch_completed.send(
        sender=None,
        node=trigger,
    )

    assert not WorkspaceAutomationUsage.objects.exists()


@pytest.mark.django_db
def test_usage_accumulates_on_same_day(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_local_baserow_create_row_action_node(user=user)

    for _ in range(3):
        automation_node_dispatch_completed.send(
            sender=None,
            node=node,
        )

    today = date.today()
    usage = WorkspaceAutomationUsage.objects.get(
        workspace=node.workflow.automation.workspace,
        period=today,
    )
    assert usage.dispatch_count == 3
