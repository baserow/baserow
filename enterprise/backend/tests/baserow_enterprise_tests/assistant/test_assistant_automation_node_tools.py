import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.operations import (
    UpdateAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.cache import local_cache
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.assistant.tools.automation import agents as automation_agents
from baserow_enterprise.assistant.tools.automation.agents import (
    update_single_node_formulas,
)
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
from baserow_enterprise.assistant.tools.automation.types.node import (
    AutomationFieldValue,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

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
def test_router_edge_conditions_stay_valid_formulas(data_fixture):
    """
    Generated router edge conditions are written into the edge's JSON
    ``condition`` instead of a service field, so they must go through
    ``ensure_valid_formula`` like every other assistant-written formula. An
    unparsable condition falls back to a string literal so the workflow stays
    duplicable, exportable and importable.
    """

    from baserow.contrib.automation.workflows.service import AutomationWorkflowService
    from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
    from baserow_enterprise.assistant.tools.automation.types.node import (
        RouterEdgeCreate,
    )
    from baserow_enterprise.assistant.tools.shared.formula_utils import is_valid_formula

    user = data_fixture.create_user()
    router_node = data_fixture.create_core_router_action_node_with_edges(
        user=user
    ).router

    node_create = ActionNodeCreate(
        ref="router1",
        label="Router",
        previous_node_ref="trigger1",
        type="router",
        edges=[
            RouterEdgeCreate(label="Do this", condition="High priority"),
            RouterEdgeCreate(label="Do that", condition="Low priority"),
        ],
    )
    node_create.update_service_with_formulas(
        router_node.service,
        {
            "Do this": "get('previous_node.1.field')",
            "Do that": "Managers' pick",  # unparsable: unterminated string literal
        },
    )

    edges = router_node.service.specific.edges
    valid_edge = edges.get(label="Do this")
    assert valid_edge.condition["formula"] == "get('previous_node.1.field')"
    assert valid_edge.condition["mode"] == BASEROW_FORMULA_MODE_ADVANCED

    fallback_edge = edges.get(label="Do that")
    assert fallback_edge.condition["formula"] == "'Managers\\' pick'"
    assert is_valid_formula(fallback_edge.condition["formula"])
    assert fallback_edge.condition["mode"] == BASEROW_FORMULA_MODE_ADVANCED

    # The workflow must remain duplicable, which is where an unparsable
    # condition would surface in the formula importer.
    duplicated = AutomationWorkflowService().duplicate_workflow(
        user, router_node.workflow
    )

    assert duplicated.id != router_node.workflow.id


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
def test_single_node_formula_pass_accepts_a_create_payload(data_fixture, monkeypatch):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation, workflow_id = _create_test_workflow(data_fixture, user, workspace)

    ctx = make_test_ctx(user, workspace)
    nodes = list_nodes(ctx, workflow_id=workflow_id, thought="inspect")["nodes"]
    orm_node = AutomationNode.objects.get(id=int(nodes[1]["id"])).specific

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda model_profile: lambda formulas, context: {
            k: "concat('gen')" for k in formulas
        },
    )

    node_create = ActionNodeCreate(
        ref="email2",
        label="Send Email",
        previous_node_ref=str(nodes[0]["id"]),
        type="smtp_email",
        to_emails="$formula: the recipients from the trigger",
        subject="Hello",
        body="World",
    )
    update_single_node_formulas(node_create, orm_node, ctx.deps.tool_helpers)

    service = AutomationNode.objects.get(id=orm_node.id).specific.service.specific
    assert "gen" in str(service.to_emails)


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

    result = update_nodes(
        make_test_ctx(user, workspace),
        workflow_id=workflow.id,
        nodes=[NodeUpdate(node_id=node.id, **{property_name: payload[property_name]})],
        thought="Update the action",
    )

    assert result["updated_nodes"] == []
    assert len(result["errors"]) == 1
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
