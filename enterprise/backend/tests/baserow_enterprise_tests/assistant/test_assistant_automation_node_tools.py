import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow_enterprise.assistant.tools.automation.tools import (
    add_nodes,
    create_workflows,
    delete_nodes,
    list_nodes,
    update_nodes,
)
from baserow_enterprise.assistant.tools.automation.types import (
    ActionNodeCreate,
    NodeUpdate,
    TriggerNodeCreate,
    WorkflowCreate,
)

from .utils import make_test_ctx


@pytest.fixture(autouse=True)
def mock_formula_generator(monkeypatch):
    """Mock update_workflow_formulas and update_single_node_formulas to avoid LM calls."""

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.automation.agents.update_workflow_formulas",
        lambda workflow, node_mapping, tool_helpers: None,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.automation.agents.update_single_node_formulas",
        lambda node_update, orm_node, tool_helpers: None,
    )


def _create_test_workflow(data_fixture, user, workspace):
    """Create a workflow with a trigger and an email action node."""
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )

    ctx = make_test_ctx(user, workspace)
    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Workflow",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="email1",
                        label="Send Email",
                        previous_node_ref="trigger1",
                        type="smtp_email",
                        to_emails="test@example.com",
                        subject="Hello",
                        body="World",
                    ),
                ],
            )
        ],
        thought="test",
    )

    workflow_id = result["created_workflows"][0]["id"]
    return automation, workflow_id


@pytest.mark.django_db(transaction=True)
def test_list_nodes(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)

    ctx = make_test_ctx(user, workspace)
    result = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")

    nodes = result["nodes"]
    assert len(nodes) == 2

    # First node is the trigger
    assert nodes[0]["label"] == "Periodic Trigger"
    assert nodes[0]["type"] == "periodic"

    # Second node is the email action
    assert nodes[1]["label"] == "Send Email"
    assert nodes[1]["type"] == "smtp_email"

    # All nodes have IDs
    assert all("id" in n for n in nodes)


@pytest.mark.django_db(transaction=True)
def test_add_node_after_existing(data_fixture):
    """Add a router node between the trigger and existing email node."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)

    # Get existing nodes
    ctx = make_test_ctx(user, workspace)
    existing = list_nodes(ctx, workflow_id=workflow_id, thought="check")
    trigger_id = existing["nodes"][0]["id"]
    email_id = existing["nodes"][1]["id"]

    # Delete the existing email node first (we'll re-add it after the router)
    delete_nodes(
        ctx, node_ids=[email_id], thought="remove email to re-add after router"
    )

    # Add a router after the trigger, then a new email after the router
    result = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            ActionNodeCreate(
                ref="router1",
                label="My Router",
                type="router",
                previous_node_ref=str(trigger_id),
                edges=[
                    {"label": "always", "condition": "true"},
                ],
            ),
            ActionNodeCreate(
                ref="slack1",
                label="Send Slack After Router",
                type="smtp_email",
                previous_node_ref="router1",
                router_edge_label="always",
                to_emails="test@example.com",
                subject="Hello",
                body="Routed message",
            ),
        ],
        thought="insert router between trigger and email",
    )

    assert len(result["created_nodes"]) == 2
    assert result["created_nodes"][0]["type"] == "router"
    assert result["created_nodes"][0]["label"] == "My Router"
    assert result["created_nodes"][1]["label"] == "Send Slack After Router"

    # Verify final workflow order
    final = list_nodes(ctx, workflow_id=workflow_id, thought="verify")
    assert len(final["nodes"]) == 3
    assert final["nodes"][0]["type"] == "periodic"
    assert final["nodes"][1]["type"] == "router"
    assert final["nodes"][2]["type"] == "smtp_email"


@pytest.mark.django_db(transaction=True)
def test_add_node_append_to_workflow(data_fixture):
    """Append a new action node at the end of an existing workflow."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)

    ctx = make_test_ctx(user, workspace)
    existing = list_nodes(ctx, workflow_id=workflow_id, thought="check")
    email_id = existing["nodes"][1]["id"]

    # Append a new email node after the existing email node
    result = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            ActionNodeCreate(
                ref="email1",
                label="Follow-up Email",
                type="smtp_email",
                previous_node_ref=str(email_id),
                to_emails="followup@example.com",
                subject="Follow-up",
                body="This is a follow-up.",
            ),
        ],
        thought="append email after email",
    )

    assert len(result["created_nodes"]) == 1
    assert result["created_nodes"][0]["label"] == "Follow-up Email"

    # Verify workflow now has 3 nodes
    final = list_nodes(ctx, workflow_id=workflow_id, thought="verify")
    assert len(final["nodes"]) == 3
    assert final["nodes"][2]["type"] == "smtp_email"
    assert final["nodes"][2]["label"] == "Follow-up Email"


@pytest.mark.django_db(transaction=True)
def test_update_node_label(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)

    # Get the action node
    from baserow.contrib.automation.workflows.service import AutomationWorkflowService

    workflow = AutomationWorkflowService().get_workflow(user, workflow_id)
    nodes = list(workflow.automation_workflow_nodes.all().order_by("id"))
    action_node = nodes[-1]  # The email action node

    ctx = make_test_ctx(user, workspace)
    result = update_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[NodeUpdate(node_id=action_node.id, label="Updated Email")],
        thought="rename node",
    )

    assert result["updated_nodes"][0]["label"] == "Updated Email"

    # Verify in DB
    refreshed = AutomationNodeService().get_node(user, action_node.id)
    assert refreshed.label == "Updated Email"


@pytest.mark.django_db(transaction=True)
def test_update_node_service_config(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)

    from baserow.contrib.automation.workflows.service import AutomationWorkflowService

    workflow = AutomationWorkflowService().get_workflow(user, workflow_id)
    nodes = list(workflow.automation_workflow_nodes.all().order_by("id"))
    action_node = nodes[-1]

    ctx = make_test_ctx(user, workspace)
    result = update_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            NodeUpdate(
                node_id=action_node.id,
                subject="New Subject",
            )
        ],
        thought="update email subject",
    )

    assert len(result["updated_nodes"]) == 1
    assert "errors" not in result


@pytest.mark.django_db(transaction=True)
def test_delete_node(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)

    from baserow.contrib.automation.workflows.service import AutomationWorkflowService

    workflow = AutomationWorkflowService().get_workflow(user, workflow_id)
    nodes = list(workflow.automation_workflow_nodes.all().order_by("id"))
    action_node = nodes[-1]

    ctx = make_test_ctx(user, workspace)
    result = delete_nodes(
        ctx,
        node_ids=[action_node.id],
        thought="delete node",
    )

    assert result["deleted_node_ids"] == [action_node.id]

    # Node should be gone
    assert not AutomationNode.objects.filter(id=action_node.id).exists()


@pytest.mark.django_db(transaction=True)
def test_delete_node_wrong_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace1 = data_fixture.create_workspace(user=user)
    workspace2 = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace1)

    from baserow.contrib.automation.workflows.service import AutomationWorkflowService

    workflow = AutomationWorkflowService().get_workflow(user, workflow_id)
    nodes = list(workflow.automation_workflow_nodes.all().order_by("id"))
    action_node = nodes[-1]

    # Try to delete from wrong workspace
    ctx = make_test_ctx(user, workspace2)
    result = delete_nodes(
        ctx,
        node_ids=[action_node.id],
        thought="delete from wrong workspace",
    )

    assert result["deleted_node_ids"] == []
    assert len(result["errors"]) == 1

    # Node should still exist
    assert AutomationNode.objects.filter(id=action_node.id).exists()
