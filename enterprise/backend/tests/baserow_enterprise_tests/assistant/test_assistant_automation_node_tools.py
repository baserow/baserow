import asyncio

import pytest
from asgiref.sync import async_to_sync
from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.operations import (
    DeleteAutomationNodeOperationType,
    UpdateAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionDenied
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.tools.automation import agents as automation_agents
from baserow_enterprise.assistant.tools.automation.tools import (
    add_nodes,
    automation_toolset,
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
from baserow_enterprise.assistant.tools.automation.types.node import (
    AutomationFieldValue,
)
from baserow_enterprise.assistant.tools.routing import ModeAwareToolset
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

from .utils import make_test_ctx


def _fail_formula_generation(*args):
    raise RuntimeError("Formula generation unavailable")


@pytest.fixture
def real_formula_pass():
    """Requesting this fixture opts a test out of mock_formula_generator."""


@pytest.fixture(autouse=True)
def mock_formula_generator(request, monkeypatch):
    """Skip formula generation to avoid LM calls in tests."""

    if "real_formula_pass" in request.fixturenames:
        return
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.automation.agents.repair_formula_errors",
        lambda tool_context, tool_helpers, formula_errors, refs=None: [],
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
def test_add_nodes_returns_formula_errors_without_losing_nodes(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)
    ctx = make_test_ctx(user, workspace)
    previous_node = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")[
        "nodes"
    ][-1]

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda _model_profile: _fail_formula_generation,
    )

    result = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            ActionNodeCreate(
                ref="email2",
                label="Formula Email",
                previous_node_ref=str(previous_node["id"]),
                type="smtp_email",
                to_emails="test@example.com",
                subject="$formula: the trigger name",
                body="Hello",
            )
        ],
        thought="test formula failure",
    )

    created_node = result["created_nodes"][0]
    assert AutomationNode.objects.filter(id=created_node["id"]).exists()
    assert result["formula_errors"] == [
        {
            "node_id": created_node["id"],
            "node_label": "Formula Email",
            "field": "subject",
            "formula": "$formula: the trigger name",
            "error": "Formula generation unavailable",
        }
    ]


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
def test_update_nodes_returns_formula_errors_without_losing_updates(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)
    ctx = make_test_ctx(user, workspace)
    workflow_nodes = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")[
        "nodes"
    ]
    action_node = workflow_nodes[-1]

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda _model_profile: _fail_formula_generation,
    )

    result = update_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            NodeUpdate(
                node_id=action_node["id"],
                label="Updated Email",
                subject="$formula: the trigger name",
            )
        ],
        thought="test formula failure",
    )

    refreshed = AutomationNodeService().get_node(user, action_node["id"])
    assert refreshed.label == "Updated Email"
    assert result["formula_errors"] == [
        {
            "node_id": action_node["id"],
            "node_label": "Updated Email",
            "field": "subject",
            "formula": "$formula: the trigger name",
            "error": "Formula generation unavailable",
        }
    ]


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


@pytest.mark.django_db(transaction=True)
def test_literal_values_with_apostrophes_stay_valid_formulas(data_fixture):
    """
    Regression test: literal values coming from the LLM used to be wrapped as
    `f"'{value}'"`, so a value such as `Sales Managers' Week 3` was persisted as
    an unparsable formula. It only blew up later, when the workflow was
    duplicated, exported or imported.
    """

    from baserow.contrib.automation.workflows.service import AutomationWorkflowService
    from baserow.core.formula import BaserowFormulaObject
    from baserow_enterprise.assistant.tools.shared.formula_utils import is_valid_formula

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(automation=automation)
    result = add_nodes(
        make_test_ctx(user, workspace),
        workflow_id=workflow.id,
        nodes=[
            ActionNodeCreate(
                ref="row1",
                label="Create row",
                previous_node_ref=str(workflow.get_trigger().id),
                type="create_row",
                table_id=table.id,
                values=[{"field_id": field.id, "value": "Sales Managers' Week 3"}],
            )
        ],
        thought="Add an action with a fixed value",
    )
    service = AutomationNode.objects.get(
        id=result["created_nodes"][0]["id"]
    ).service.specific
    mapping = service.field_mappings.get(field_id=field.id)

    assert is_valid_formula(BaserowFormulaObject.to_formula(mapping.value)["formula"])
    assert (
        resolve_formula(mapping.value, formula_runtime_function_registry, {})
        == "Sales Managers' Week 3"
    )

    # The workflow must remain duplicable, which is where the invalid formula
    # used to surface as a `BaserowFormulaSyntaxError`.
    duplicated = AutomationWorkflowService().duplicate_workflow(user, workflow)

    assert duplicated.id != workflow.id


@pytest.mark.django_db(transaction=True)
def test_router_edge_conditions_stay_valid_formulas(
    data_fixture, monkeypatch, real_formula_pass
):
    """
    Generated router conditions are written in advanced mode. One that doesn't
    parse is not stored: the branch keeps an empty condition and the error is
    returned, so the workflow stays duplicable.
    """

    from baserow.contrib.automation.workflows.service import AutomationWorkflowService
    from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
    from baserow_enterprise.assistant.tools.automation.types.node import (
        RouterEdgeCreate,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)
    ctx = make_test_ctx(user, workspace)
    trigger = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")["nodes"][0]
    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda model_profile: (
            lambda formulas, context: {
                "Do this": "get('previous_node.1.field')",
                "Do that": "Managers' pick",  # unparsable: unterminated string literal
            }
        ),
    )

    result = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            ActionNodeCreate(
                ref="router1",
                label="Router",
                previous_node_ref=str(trigger["id"]),
                type="router",
                edges=[
                    RouterEdgeCreate(label="Do this", condition="High priority"),
                    RouterEdgeCreate(label="Do that", condition="Low priority"),
                ],
            )
        ],
        thought="add router",
    )

    router = AutomationNode.objects.get(id=result["created_nodes"][0]["id"])
    edges = router.service.specific.edges
    valid_edge = edges.get(label="Do this")
    assert valid_edge.condition["formula"] == "get('previous_node.1.field')"
    assert valid_edge.condition["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    assert edges.get(label="Do that").condition["formula"] == ""
    (error,) = result["formula_errors"]
    assert (error["edge_label"], error["formula"]) == ("Do that", "Managers' pick")

    duplicated = AutomationWorkflowService().duplicate_workflow(user, router.workflow)

    assert duplicated.id != router.workflow.id


def test_node_create_types_fold_registered_names():
    trigger = TriggerNodeCreate(
        ref="t",
        label="T",
        type="local_baserow_rows_created",
        rows_triggers_settings={"table_id": 1},
    )
    assert trigger.type == "rows_created"

    action = ActionNodeCreate(
        ref="a",
        label="A",
        previous_node_ref="t",
        type="local_baserow_create_row",
        table_id=1,
        values=[AutomationFieldValue(field_id=1, value="x")],
    )
    assert action.type == "create_row"


@pytest.mark.django_db(transaction=True)
def test_smtp_literal_recipients_are_stored(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    ctx = make_test_ctx(user, workflow.automation.workspace)
    values = {
        "to_emails": "recipient@example.com",
        "cc_emails": "copy@example.com",
        "bcc_emails": "audit@example.com",
        "subject": "Review",
        "body": "Ready",
    }
    result = add_nodes(
        ctx,
        workflow_id=workflow.id,
        nodes=[
            ActionNodeCreate(
                ref="email",
                label="Send email",
                type="smtp_email",
                previous_node_ref=str(workflow.get_trigger().id),
                **values,
            )
        ],
        thought="Create email action",
    )
    node_id = result["created_nodes"][0]["id"]
    service = AutomationNode.objects.get(id=node_id).service.specific
    assert {
        name: resolve_formula(
            getattr(service, name), formula_runtime_function_registry, {}
        )
        for name in values
    } == values

    result = update_nodes(
        ctx,
        workflow_id=workflow.id,
        nodes=[NodeUpdate(node_id=node_id, to_emails="updated@example.com")],
        thought="Change the recipient only",
    )

    assert not result.get("errors")
    service = AutomationNode.objects.get(id=node_id).service.specific
    assert {
        name: resolve_formula(
            getattr(service, name), formula_runtime_function_registry, {}
        )
        for name in values
    } == {**values, "to_emails": "updated@example.com"}


@pytest.mark.django_db
@pytest.mark.parametrize("change_table", [True, False])
def test_update_nodes_row_action_applies_table_and_literal_values(
    data_fixture, row_action_node, change_table
):
    user, node, original_field = row_action_node
    workflow = node.workflow
    database = node.service.specific.table.database
    destination = (
        data_fixture.create_database_table(database=database)
        if change_table
        else original_field.table
    )
    field = data_fixture.create_text_field(table=destination, name="Status")
    row = destination.get_model().objects.create(id=42)

    result = update_nodes(
        make_test_ctx(user, workflow.automation.workspace),
        workflow_id=workflow.id,
        nodes=[
            NodeUpdate(
                node_id=node.id,
                table_id=destination.id,
                row_id=str(row.id),
                values=[AutomationFieldValue(field_id=field.id, value="Reviewed")],
            )
        ],
        thought="Retarget the existing row action",
    )

    assert not result.get("errors")
    assert result["updated_nodes"] == [{"node_id": node.id, "label": node.label}]
    service = AutomationNode.objects.get(id=node.id).service.specific
    assert service.table_id == destination.id
    assert resolve_formula(
        service.row_id, formula_runtime_function_registry, {}
    ) == str(row.id)
    mapping = service.field_mappings.get(field=field)
    assert (
        resolve_formula(mapping.value, formula_runtime_function_registry, {})
        == "Reviewed"
    )
    assert service.field_mappings.filter(field=original_field).exists() == (
        not change_table
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(context={})
    resolved_values = service_type.resolve_service_formulas(service, dispatch_context)
    service_type.dispatch_data(service, resolved_values, dispatch_context)
    row.refresh_from_db()
    assert getattr(row, field.db_column) == "Reviewed"


@pytest.mark.django_db(transaction=True)
def test_update_nodes_reports_an_omitted_required_row_id(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    status = data_fixture.create_text_field(table=table, name="Status")
    ctx = make_test_ctx(user, workspace)

    created = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Order Workflow",
                trigger=TriggerNodeCreate(
                    ref="trigger",
                    label="Rows created",
                    type="rows_created",
                    rows_triggers_settings={"table_id": table.id},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="action",
                        label="Update order",
                        previous_node_ref="trigger",
                        type="update_row",
                        table_id=table.id,
                        row_id="1",
                        values=[
                            AutomationFieldValue(field_id=status.id, value="Pending")
                        ],
                    )
                ],
            )
        ],
        thought="create workflow",
    )
    workflow_id = created["created_workflows"][0]["id"]
    workflow_nodes = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")[
        "nodes"
    ]
    node_id = workflow_nodes[1]["id"]

    def omit_row_id(formulas, context):
        assert "row_id" in formulas
        return {status.id: "'Processing'"}

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda _model_profile: omit_row_id,
    )

    result = update_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            NodeUpdate(
                node_id=node_id,
                label="Process order",
                row_id="$formula: the trigger row id",
                values=[
                    AutomationFieldValue(
                        field_id=status.id,
                        value="$formula: Processing",
                    )
                ],
            )
        ],
        thought="update workflow",
    )

    assert result["updated_nodes"] == [{"node_id": node_id, "label": "Process order"}]
    assert result["formula_errors"][0]["node_id"] == node_id
    assert "row_id" in result["formula_errors"][0]["error"]

    service = AutomationNode.objects.get(id=node_id).specific.service.specific
    assert "Processing" in str(service.field_mappings.get(field_id=status.id).value)


@pytest.mark.django_db(transaction=True)
def test_add_nodes_generates_formulas_after_the_nodes_are_written(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)
    ctx = make_test_ctx(user, workspace)
    nodes = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")["nodes"]

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda model_profile: (
            lambda formulas, context: {k: "concat('a', 'gen')" for k in formulas}
        ),
    )

    result = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            ActionNodeCreate(
                ref="email2",
                label="Send Email",
                previous_node_ref=str(nodes[-1]["id"]),
                type="smtp_email",
                to_emails="$formula: the recipients from the trigger",
                subject="Hello",
                body="World",
            )
        ],
        thought="add email",
    )

    assert "formula_errors" not in result
    node_id = result["created_nodes"][0]["id"]
    service = AutomationNode.objects.get(id=node_id).specific.service.specific
    assert service.to_emails["formula"] == "concat('a', 'gen')"


@pytest.mark.django_db(transaction=True)
def test_inline_formula_marker_is_generated_not_stored_literally(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)

    ctx = make_test_ctx(user, workspace)
    nodes = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")["nodes"]

    requested = {}

    def generate(formulas, context):
        requested.update(formulas)
        return {k: "concat('New deal: ', 'gen')" for k in formulas}

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda model_profile: generate,
    )

    update_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            NodeUpdate(
                node_id=nodes[1]["id"],
                subject="New deal: $formula: the deal name from the trigger",
            )
        ],
        thought="update subject",
    )

    assert set(requested) == {"subject"}
    assert "New deal: $formula: the deal name from the trigger" in requested["subject"]
    service = AutomationNode.objects.get(id=nodes[1]["id"]).specific.service.specific
    assert "$formula" not in str(service.subject)
    assert "gen" in str(service.subject)


@pytest.fixture
def row_action_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    database = data_fixture.create_database_application(
        workspace=workflow.automation.workspace
    )
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    node = data_fixture.create_local_baserow_update_row_action_node(
        workflow=workflow,
        label="Update row",
        service_kwargs={
            "table": table,
            "row_id": "'1'",
            "integration_args": {
                "application": workflow.automation,
                "authorized_user": user,
            },
        },
    )
    node.service.specific.field_mappings.create(field=field, value="'Initial'")
    return user, node, field


@pytest.mark.django_db
@pytest.mark.parametrize("property_name", ["values", "row_id"])
def test_update_nodes_direct_values_require_update_permission(
    enable_enterprise, enterprise_data_fixture, row_action_node, property_name
):
    _, node, field = row_action_node
    workflow = node.workflow
    workspace = workflow.automation.workspace
    user = enterprise_data_fixture.create_user()
    enterprise_data_fixture.create_user_workspace(
        user=user, workspace=workspace, permissions="NO_ACCESS"
    )
    read_only_role = Role.objects.create(name="Read automation", workspace=workspace)
    read_only_role.operations.set(
        Role.objects.get(uid="BUILDER").operations.exclude(
            name=UpdateAutomationNodeOperationType.type
        )
    )
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(
        user, workspace, role=read_only_role, scope=workflow.automation.application_ptr
    )
    assert AutomationNodeService().get_node(user, node.id).id == node.id
    payload = {
        "values": [{"field_id": field.id, "value": "Updated"}],
        "row_id": "2",
    }

    with pytest.raises(PermissionDenied):
        update_nodes(
            make_test_ctx(user, workspace),
            workflow_id=workflow.id,
            nodes=[
                NodeUpdate(node_id=node.id, **{property_name: payload[property_name]})
            ],
            thought="Update the action",
        )

    service = AutomationNode.objects.get(id=node.id).specific.service.specific
    assert service.row_id["formula"] == "'1'"
    assert service.field_mappings.get(field=field).value["formula"] == "'Initial'"


@pytest.mark.django_db
@pytest.mark.parametrize("property_name", ["values", "row_id"])
def test_update_nodes_direct_values_refresh_test_run_clone(
    row_action_node, property_name
):
    user, node, field = row_action_node
    workflow = node.workflow
    handler = AutomationWorkflowHandler()
    with local_cache.context():
        original_clone = handler._ensure_published_for_run(workflow)
    payload = {
        "values": [{"field_id": field.id, "value": "Updated"}],
        "row_id": "2",
    }

    result = update_nodes(
        make_test_ctx(user, workflow.automation.workspace),
        workflow_id=workflow.id,
        nodes=[NodeUpdate(node_id=node.id, **{property_name: payload[property_name]})],
        thought="Update the action",
    )

    assert not result.get("errors")
    with local_cache.context():
        updated_clone = handler._ensure_published_for_run(workflow)
    assert updated_clone.id != original_clone.id
    cloned_node = updated_clone.automation_workflow_nodes.get(label=node.label)
    service = cloned_node.service.specific
    assert service.row_id["formula"] == ("'2'" if property_name == "row_id" else "'1'")
    assert service.field_mappings.get(field=field).value["formula"] == (
        "'Updated'" if property_name == "values" else "'Initial'"
    )


def _update_row_node(**overrides):
    kwargs = {
        "ref": "action",
        "label": "Update row",
        "previous_node_ref": "trigger",
        "type": "update_row",
        "table_id": 1,
        "row_id": "1",
        "values": [AutomationFieldValue(field_id=1, value="Reviewed")],
    }
    kwargs.update(overrides)
    return ActionNodeCreate(**kwargs)


def test_a_blank_row_id_cannot_satisfy_the_requirement():
    """An update_row node with a blank row id names no row to update."""

    _update_row_node()

    for blank in ("", "   "):
        with pytest.raises(ValidationError) as exc_info:
            _update_row_node(row_id=blank)
        assert "row_id" in str(exc_info.value)


def test_a_row_action_without_values_is_still_allowed():
    """Creating or clearing a row without field values is a real request."""

    assert _update_row_node(values=[]).values == []


def test_a_required_node_field_still_accepts_a_falsy_but_real_value():
    """Rejecting every falsy value would refuse legitimate zeroes."""

    assert _update_row_node(table_id=0).table_id == 0


@pytest.mark.django_db(transaction=True)
def test_partial_delete_is_reported_when_a_later_node_is_forbidden(
    data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    owner = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner)
    allowed_workflow = data_fixture.create_automation_workflow(
        user=owner,
        automation=data_fixture.create_automation_application(workspace=workspace),
    )
    forbidden_workflow = data_fixture.create_automation_workflow(
        user=owner,
        automation=data_fixture.create_automation_application(workspace=workspace),
    )
    allowed_node = data_fixture.create_core_iterator_action_node(
        workflow=allowed_workflow
    )
    forbidden_node = data_fixture.create_core_iterator_action_node(
        workflow=forbidden_workflow
    )
    user = enterprise_data_fixture.create_user()
    enterprise_data_fixture.create_user_workspace(
        user=user, workspace=workspace, permissions="NO_ACCESS"
    )
    no_delete = Role.objects.create(name="Read without delete", workspace=workspace)
    no_delete.operations.set(
        Role.objects.get(uid="BUILDER").operations.exclude(
            name=DeleteAutomationNodeOperationType.type
        )
    )
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(
        user,
        workspace,
        role=Role.objects.get(uid="BUILDER"),
        scope=allowed_workflow.automation.application_ptr,
    )
    RoleAssignmentHandler().assign_role(
        user,
        workspace,
        role=no_delete,
        scope=forbidden_workflow.automation.application_ptr,
    )
    deps = make_test_ctx(user, workspace).deps
    deps.mode = AgentMode.AUTOMATION
    ctx = RunContext(
        deps=deps, model=TestModel(), usage=RunUsage(), tool_name="delete_nodes"
    )
    router = ModeAwareToolset(automation_toolset, deps)

    async def invoke():
        tools = await router.get_tools(ctx)
        return await router.call_tool(
            "delete_nodes",
            {"node_ids": [allowed_node.id, forbidden_node.id], "thought": "test"},
            ctx,
            tools["delete_nodes"],
        )

    result = async_to_sync(invoke)()
    assert not AutomationNode.objects.filter(pk=allowed_node.id).exists()
    assert AutomationNode.objects.filter(pk=forbidden_node.id).exists()
    assert result["deleted_node_ids"] == [allowed_node.id]
    assert result["errors"] == [
        f"Permission denied for node {forbidden_node.id}; it was not deleted."
    ]


@pytest.mark.django_db(transaction=True)
def test_formulas_are_never_generated_inside_a_transaction(
    data_fixture, monkeypatch, real_formula_pass
):
    from django.db import connection

    calls = []

    def generate(formulas, context):
        calls.append(connection.in_atomic_block)
        return {key: "'generated'" for key in formulas}

    monkeypatch.setattr(
        automation_agents, "get_generate_formulas_tool", lambda profile: generate
    )
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    ctx = make_test_ctx(user, workspace)

    def email(ref, previous):
        return ActionNodeCreate(
            ref=ref,
            label=ref,
            previous_node_ref=previous,
            type="smtp_email",
            to_emails="team@example.com",
            subject="$formula: the trigger name",
            body="Hello",
        )

    created = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Flow",
                trigger=TriggerNodeCreate(
                    ref="trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[email("first", "trigger")],
            )
        ],
        thought="create",
    )
    workflow_id = created["created_workflows"][0]["id"]
    first = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")["nodes"][1]
    added = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[email("second", str(first["id"]))],
        thought="add",
    )
    updated = update_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[NodeUpdate(node_id=first["id"], body="$formula: the trigger name")],
        thought="update",
    )

    assert calls == [False, False, False]
    for result in (created, added, updated):
        assert "formula_errors" not in result
    service = AutomationNode.objects.get(id=first["id"]).specific.service.specific
    assert service.subject["formula"] == "'generated'"
    assert service.body["formula"] == "'generated'"


@pytest.mark.django_db(transaction=True)
def test_a_failed_repair_keeps_the_created_nodes(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)
    ctx = make_test_ctx(user, workspace)
    previous = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")["nodes"][-1]

    def delete_then_generate(formulas, context):
        # The node disappears between the write and the repair.
        AutomationNode.objects.filter(label="Formula Email").update(trashed=True)
        return {key: "'x'" for key in formulas}

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda _model_profile: delete_then_generate,
    )

    result = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            ActionNodeCreate(
                ref="email2",
                label="Formula Email",
                previous_node_ref=str(previous["id"]),
                type="smtp_email",
                to_emails="test@example.com",
                subject="$formula: the trigger name",
                body="Hello",
            )
        ],
        thought="add",
    )

    assert result["created_nodes"][0]["label"] == "Formula Email"
    (error,) = result["formula_errors"]
    assert error["field"] == "subject"


@pytest.mark.django_db(transaction=True)
def test_formulas_only_see_the_nodes_before_them(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    ctx = make_test_ctx(user, workspace)
    seen = []

    def generate(formulas, context):
        seen.append(set(context.context))
        return {key: "'x'" for key in formulas}

    monkeypatch.setattr(
        automation_agents, "get_generate_formulas_tool", lambda profile: generate
    )

    def email(ref, previous):
        return ActionNodeCreate(
            ref=ref,
            label=ref,
            previous_node_ref=previous,
            type="smtp_email",
            to_emails="a@example.com",
            subject="$formula: the trigger" if ref == "first" else "Hi",
            body="Hello",
        )

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Flow",
                trigger=TriggerNodeCreate(
                    ref="trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[email("first", "trigger"), email("second", "first")],
            )
        ],
        thought="create",
    )

    workflow = AutomationWorkflowHandler().get_workflow(
        result["created_workflows"][0]["id"]
    )
    trigger = workflow.get_trigger()
    assert seen == [{str(trigger.id)}]


@pytest.mark.django_db(transaction=True)
def test_a_repair_the_update_refuses_stays_in_formula_errors(
    data_fixture, monkeypatch, real_formula_pass
):
    from uuid import uuid4

    from baserow.contrib.automation.nodes.registries import (
        automation_node_type_registry,
    )
    from baserow.contrib.automation.nodes.service import AutomationNodeService

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)
    ctx = make_test_ctx(user, workspace)
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    router = AutomationNodeService().create_node(
        user,
        automation_node_type_registry.get("router"),
        workflow,
        reference_node_id=workflow.get_trigger().id,
        service={"edges": [{"uid": str(uuid4()), "label": "Yes"}]},
    )

    def rename_then_generate(formulas, context):
        # Someone renames the branch between the update and the repair.
        router.service.specific.edges.update(label="No")
        return {key: "true" for key in formulas}

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda profile: rename_then_generate,
    )

    result = update_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            NodeUpdate(
                node_id=router.id,
                edges=[{"label": "Yes", "condition": "$formula: always"}],
            )
        ],
        thought="update",
    )

    (error,) = result["formula_errors"]
    assert error["edge_label"] == "Yes"
    assert "'Yes' is not a branch" in error["error"]


@pytest.mark.django_db(transaction=True)
def test_a_repaired_formula_can_name_a_node_by_its_ref(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    ctx = make_test_ctx(user, workspace)
    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda profile: (
            lambda formulas, context: {
                key: "get('previous_node.trigger.0.id')" for key in formulas
            }
        ),
    )

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Flow",
                trigger=TriggerNodeCreate(
                    ref="trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="mail",
                        label="Mail",
                        previous_node_ref="trigger",
                        type="smtp_email",
                        to_emails="a@example.com",
                        subject="$formula: the trigger id",
                        body="Hello",
                    )
                ],
            )
        ],
        thought="create",
    )

    assert "formula_errors" not in result
    workflow = AutomationWorkflowHandler().get_workflow(
        result["created_workflows"][0]["id"]
    )
    mail = workflow.automation_workflow_nodes.get(label="Mail").specific
    trigger_id = workflow.get_trigger().id
    assert mail.service.specific.subject["formula"] == (
        f"get('previous_node.{trigger_id}.0.id')"
    )


@pytest.mark.django_db
def test_formula_repair_stops_when_cancelled(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    ctx = make_test_ctx(user, workspace)
    calls = []

    def cancel_then_generate(formulas, context):
        # The user cancels while the model is generating this node's formulas.
        calls.append(formulas)
        ctx.deps.tool_helpers.cancel()
        return {key: "'fixed'" for key in formulas}

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda profile: cancel_then_generate,
    )

    with pytest.raises(asyncio.CancelledError):
        create_workflows(
            ctx,
            automation_id=automation.id,
            workflows=[
                WorkflowCreate(
                    name="Flow",
                    trigger=TriggerNodeCreate(
                        ref="trigger",
                        type="periodic",
                        periodic_interval={"interval": "DAY"},
                    ),
                    nodes=[
                        ActionNodeCreate(
                            ref=ref,
                            label=ref,
                            previous_node_ref=previous,
                            type="smtp_email",
                            to_emails="a@example.com",
                            subject="$formula: the trigger id",
                            body="Hello",
                        )
                        for ref, previous in [("one", "trigger"), ("two", "one")]
                    ],
                )
            ],
            thought="create",
        )

    assert len(calls) == 1
    nodes = AutomationNode.objects.filter(workflow__automation=automation)
    for label in ("one", "two"):
        node = nodes.get(label=label).specific
        assert node.service.specific.subject["formula"] == ""


@pytest.mark.django_db
def test_formula_repair_stops_when_the_generator_fails_after_a_cancel(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)
    ctx = make_test_ctx(user, workspace)
    previous = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")["nodes"][-1]

    def cancel_then_fail(formulas, context):
        ctx.deps.tool_helpers.cancel()
        raise ValueError("Failed to generate any valid formulas")

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda profile: cancel_then_fail,
    )

    with pytest.raises(asyncio.CancelledError):
        add_nodes(
            ctx,
            workflow_id=workflow_id,
            nodes=[
                ActionNodeCreate(
                    ref="mail",
                    label="Mail",
                    previous_node_ref=str(previous["id"]),
                    type="smtp_email",
                    to_emails="a@example.com",
                    subject="$formula: the trigger name",
                    body="Hello",
                )
            ],
            thought="add",
        )


@pytest.mark.django_db(transaction=True)
def test_a_missing_field_only_keeps_its_own_value_in_formula_errors(
    data_fixture, row_action_node, monkeypatch, real_formula_pass
):
    user, node, kept = row_action_node
    deleted = data_fixture.create_text_field(table=kept.table, name="Gone")

    def delete_then_generate(formulas, context):
        # Someone deletes a field between the update and the repair.
        deleted.delete()
        return {key: "'fixed'" for key in formulas}

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda profile: delete_then_generate,
    )

    result = update_nodes(
        make_test_ctx(user, node.workflow.automation.workspace),
        workflow_id=node.workflow.id,
        nodes=[
            NodeUpdate(
                node_id=node.id,
                values=[
                    AutomationFieldValue(field_id=kept.id, value="$formula: a name"),
                    AutomationFieldValue(field_id=deleted.id, value="$formula: a name"),
                ],
            )
        ],
        thought="update",
    )

    (error,) = result["formula_errors"]
    assert error["field_id"] == deleted.id
    mapping = AutomationNode.objects.get(id=node.id).service.specific.field_mappings
    assert mapping.get(field=kept).value["formula"] == "'fixed'"
