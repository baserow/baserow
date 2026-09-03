from unittest.mock import MagicMock

import pytest
from pydantic_ai import ModelRetry

from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow_enterprise.assistant.tools.automation import agents as automation_agents
from baserow_enterprise.assistant.tools.automation.agents import AssistantFormulaContext
from baserow_enterprise.assistant.tools.automation.reconciliation import (
    plan_workflow_creation,
)
from baserow_enterprise.assistant.tools.automation.tools import (
    create_workflows,
    list_workflows,
)
from baserow_enterprise.assistant.tools.automation.types import (
    ActionNodeCreate,
    TriggerNodeCreate,
    WorkflowCreate,
)
from baserow_enterprise.assistant.tools.automation.types.node import (
    AutomationFieldValue,
    RouterEdgeCreate,
)

from .utils import make_test_ctx


def _fail_formula_generation(*args):
    raise RuntimeError("Formula generation unavailable")


def test_plan_workflow_creation_keeps_the_first_identical_request():
    request = WorkflowCreate(
        name="Process Orders",
        trigger=TriggerNodeCreate(
            ref="trigger",
            label="Schedule",
            type="periodic",
            periodic_interval={"interval": "DAY"},
        ),
    )

    plan = plan_workflow_creation([request, request.model_copy(deep=True)], [])

    assert plan.requested == [request]
    assert plan.to_create == [request]
    assert plan.conflicting_names == []


def test_plan_workflow_creation_dedupes_identical_router_requests():
    definition = {
        "name": "Route Orders",
        "trigger": {
            "ref": "trigger",
            "label": "Schedule",
            "type": "periodic",
            "periodic_interval": {"interval": "DAY"},
        },
        "nodes": [
            {
                "ref": "router",
                "label": "Router",
                "previous_node_ref": "trigger",
                "type": "router",
                "edges": [{"label": "always", "condition": "true"}],
            }
        ],
    }

    # Two validations of one dict yield distinct RouterEdgeCreate._uid values.
    requests = [
        WorkflowCreate.model_validate(definition),
        WorkflowCreate.model_validate(definition),
    ]

    plan = plan_workflow_creation(requests, [])

    assert plan.conflicting_names == []
    assert plan.to_create == [requests[0]]


@pytest.fixture
def real_formula_pass():
    """Requesting this fixture opts a test out of mock_formula_generator."""


@pytest.fixture(autouse=True)
def mock_formula_generator(request, monkeypatch):
    """Skip formula generation to avoid the LM requirement in tests."""

    if "real_formula_pass" in request.fixturenames:
        return
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.automation.agents.update_workflow_formulas",
        lambda workflow, node_mapping, tool_helpers: [],
    )


@pytest.mark.django_db
def test_list_workflows(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="Test Workflow"
    )

    ctx = make_test_ctx(user, workspace)
    result = list_workflows(ctx, automation_id=automation.id, thought="test")

    assert result == {
        "workflows": [{"id": workflow.id, "name": "Test Workflow", "state": "draft"}]
    }


@pytest.mark.django_db
def test_list_workflows_multiple(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow1 = data_fixture.create_automation_workflow(
        automation=automation, name="Workflow 1"
    )
    workflow2 = data_fixture.create_automation_workflow(
        automation=automation, name="Workflow 2"
    )

    ctx = make_test_ctx(user, workspace)
    result = list_workflows(ctx, automation_id=automation.id, thought="test")

    assert result == {
        "workflows": [
            {"id": workflow1.id, "name": "Workflow 1", "state": "draft"},
            {"id": workflow2.id, "name": "Workflow 2", "state": "draft"},
        ]
    }


@pytest.mark.django_db(transaction=True)
def test_create_workflows(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    ctx = make_test_ctx(user, workspace)

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Process Orders",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="action1",
                        label="Create row",
                        previous_node_ref="trigger1",
                        type="create_row",
                        table_id=table.id,
                        values=[],
                    )
                ],
            )
        ],
        thought="test",
    )

    assert len(result["created_workflows"]) == 1
    assert result["created_workflows"][0]["name"] == "Process Orders"
    assert result["created_workflows"][0]["state"] == "draft"

    # Verify workflow was created with a trigger
    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    trigger = workflow.get_trigger()
    assert trigger is not None
    assert trigger.get_type().type == "periodic"


@pytest.mark.django_db(transaction=True)
def test_create_workflows_returns_formula_errors_without_losing_workflow(
    data_fixture, monkeypatch, real_formula_pass
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    ctx = make_test_ctx(user, workspace)

    monkeypatch.setattr(
        automation_agents,
        "get_generate_formulas_tool",
        lambda: _fail_formula_generation,
    )

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Formula Workflow",
                trigger=TriggerNodeCreate(
                    ref="trigger",
                    label="Periodic Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="email",
                        label="Send Email",
                        previous_node_ref="trigger",
                        type="smtp_email",
                        to_emails="test@example.com",
                        subject="$formula: the trigger name",
                        body="Hello",
                    )
                ],
            )
        ],
        thought="test formula failure",
    )

    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    action = workflow.automation_workflow_nodes.exclude(
        id=workflow.get_trigger().id
    ).get()
    assert result["formula_errors"] == [
        {
            "node_id": action.id,
            "label": "Send Email",
            "error": "Formula generation unavailable",
        }
    ]


@pytest.mark.django_db(transaction=True)
def test_create_workflows_reuses_exact_names_and_does_not_navigate_when_all_reused(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    existing = data_fixture.create_automation_workflow(
        automation=automation, name="Process Orders"
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    ctx = make_test_ctx(user, workspace)
    ctx.deps.tool_helpers.navigate_to = MagicMock()

    def workflow(name, ref):
        return WorkflowCreate(
            name=name,
            trigger=TriggerNodeCreate(
                ref=f"trigger-{ref}",
                label="Periodic Trigger",
                type="periodic",
                periodic_interval={"interval": "DAY"},
            ),
            nodes=[
                ActionNodeCreate(
                    ref=f"action-{ref}",
                    label="Create row",
                    previous_node_ref=f"trigger-{ref}",
                    type="create_row",
                    table_id=table.id,
                    values=[],
                )
            ],
        )

    workflow_specs = [
        workflow("Process Orders", "orders"),
        workflow("Notify Kitchen", "kitchen"),
    ]
    first = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=workflow_specs,
        thought="finish automation",
    )

    assert [item["name"] for item in first["created_workflows"]] == ["Notify Kitchen"]
    assert first["reused_workflows"][0]["id"] == existing.id
    assert first["reused_workflows"][0]["name"] == "Process Orders"
    assert first["reused_workflows"][0]["state"] == existing.state
    assert first["reused_workflows"][0]["nodes"]
    conflict = first["incomplete_reused_workflows"][0]
    assert conflict["id"] == existing.id
    assert conflict["requested_nodes"][0]["type"] == "periodic"
    assert "actual_nodes" not in conflict
    assert "configuration_unverified_reused_workflows" not in first
    assert "add_nodes" in first["next_steps"]
    assert "trigger" in first["next_steps"]
    assert automation.workflows.count() == 2

    ctx.deps.tool_helpers.navigate_to.reset_mock()
    second = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=workflow_specs,
        thought="continue",
    )

    assert second["created_workflows"] == []
    assert [item["name"] for item in second["reused_workflows"]] == [
        "Process Orders",
        "Notify Kitchen",
    ]
    assert automation.workflows.count() == 2
    ctx.deps.tool_helpers.navigate_to.assert_not_called()
    assert [item["name"] for item in second["incomplete_reused_workflows"]] == [
        "Process Orders"
    ]
    assert "next_steps" in second


@pytest.mark.django_db(transaction=True)
def test_create_workflows_does_not_treat_matching_structure_as_matching_config(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    original_table = data_fixture.create_database_table(
        user=user, database=database, name="Original Orders"
    )
    requested_table = data_fixture.create_database_table(
        user=user, database=database, name="Requested Orders"
    )
    ctx = make_test_ctx(user, workspace)

    def workflow(table_id):
        return WorkflowCreate(
            name="Process Orders",
            trigger=TriggerNodeCreate(
                ref="trigger",
                label="Rows created",
                type="rows_created",
                rows_triggers_settings={"table_id": table_id},
            ),
            nodes=[
                ActionNodeCreate(
                    ref="action",
                    label="Create row",
                    previous_node_ref="trigger",
                    type="create_row",
                    table_id=table_id,
                    values=[],
                )
            ],
        )

    first = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[workflow(original_table.id)],
        thought="create workflow",
    )
    second = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[workflow(requested_table.id)],
        thought="verify workflow",
    )

    workflow_id = first["created_workflows"][0]["id"]
    persisted = AutomationWorkflowHandler().get_workflow(workflow_id)
    action = persisted.automation_workflow_nodes.exclude(
        id=persisted.get_trigger().id
    ).get()
    assert persisted.get_trigger().service.specific.table_id == original_table.id
    assert action.service.specific.table_id == original_table.id
    assert second["created_workflows"] == []
    assert "incomplete_reused_workflows" not in second
    assert "configuration_unverified_reused_workflows" not in second
    assert [(w["id"], w["name"]) for w in second["reused_workflows"]] == [
        (workflow_id, "Process Orders")
    ]
    assert "update_nodes" in second["next_steps"]
    assert "trigger" in second["next_steps"]
    assert "complete" in second["next_steps"]


@pytest.mark.django_db
def test_create_workflows_rejects_conflicting_same_name_requests(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    ctx = make_test_ctx(user, workspace)

    def workflow(interval):
        return WorkflowCreate(
            name="Process Orders",
            trigger=TriggerNodeCreate(
                ref="trigger",
                label="Schedule",
                type="periodic",
                periodic_interval={"interval": interval},
            ),
        )

    with pytest.raises(ModelRetry, match="Conflicting workflow definitions"):
        create_workflows(
            ctx,
            automation_id=automation.id,
            workflows=[workflow("DAY"), workflow("HOUR")],
            thought="create workflow",
        )

    assert automation.workflows.count() == 0


@pytest.mark.django_db(transaction=True)
def test_create_multiple_workflows(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    ctx = make_test_ctx(user, workspace)

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Workflow 1",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="action1",
                        label="Action",
                        previous_node_ref="trigger1",
                        type="create_row",
                        table_id=table.id,
                        values=[],
                    )
                ],
            ),
            WorkflowCreate(
                name="Workflow 2",
                trigger=TriggerNodeCreate(
                    ref="trigger2",
                    label="Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="action2",
                        label="Action",
                        previous_node_ref="trigger2",
                        type="create_row",
                        table_id=table.id,
                        values=[],
                    )
                ],
            ),
        ],
        thought="test",
    )

    assert len(result["created_workflows"]) == 2
    assert result["created_workflows"][0]["name"] == "Workflow 1"
    assert result["created_workflows"][1]["name"] == "Workflow 2"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "trigger,action",
    [
        (
            TriggerNodeCreate(
                type="rows_created",
                ref="trigger",
                label="Rows Created Trigger",
                rows_triggers_settings={"table_id": 999},
            ),
            ActionNodeCreate(
                type="create_row",
                ref="action",
                previous_node_ref="trigger",
                label="Create Row Action",
                table_id=999,
                values=[],
            ),
        ),
        (
            TriggerNodeCreate(
                type="rows_updated",
                ref="trigger",
                label="Rows Updated Trigger",
                rows_triggers_settings={"table_id": 999},
            ),
            ActionNodeCreate(
                type="update_row",
                ref="action",
                previous_node_ref="trigger",
                label="Update Row Action",
                table_id=999,
                row_id="1",
                values=[],
            ),
        ),
        (
            TriggerNodeCreate(
                type="rows_deleted",
                ref="trigger",
                label="Rows Deleted Trigger",
                rows_triggers_settings={"table_id": 999},
            ),
            ActionNodeCreate(
                type="delete_row",
                ref="action",
                previous_node_ref="trigger",
                label="Delete Row Action",
                table_id=999,
                row_id="1",
            ),
        ),
    ],
)
def test_create_workflow_with_row_triggers_and_actions(data_fixture, trigger, action):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    table.pk = 999  # To match the action's table_id
    table.save()

    ctx = make_test_ctx(user, workspace)

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Row Trigger Workflow",
                trigger=trigger,
                nodes=[action],
            )
        ],
        thought="test",
    )

    assert len(result["created_workflows"]) == 1
    assert result["created_workflows"][0]["name"] == "Test Row Trigger Workflow"
    assert result["created_workflows"][0]["state"] == "draft"

    # Verify workflow was created with correct trigger type
    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    orm_trigger = workflow.get_trigger()
    assert orm_trigger is not None
    assert orm_trigger.service.get_type().type == f"local_baserow_{trigger.type}"


@pytest.mark.django_db(transaction=True)
def test_create_row_action_with_field_ids(data_fixture):
    """Test ActionNodeCreate uses field IDs in values dict, not field names."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    text_field = data_fixture.create_text_field(table=table, name="Name")
    number_field = data_fixture.create_number_field(table=table, name="Age")

    ctx = make_test_ctx(user, workspace)

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Field IDs",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="action1",
                        label="Create row with field IDs",
                        previous_node_ref="trigger1",
                        type="create_row",
                        table_id=table.id,
                        values=[
                            AutomationFieldValue(
                                field_id=text_field.id, value="John Doe"
                            ),
                            AutomationFieldValue(field_id=number_field.id, value="25"),
                        ],
                    )
                ],
            )
        ],
        thought="test",
    )

    assert len(result["created_workflows"]) == 1
    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

    # Get the action node and verify it was created with the correct table
    action_nodes = workflow.automation_workflow_nodes.exclude(
        id=workflow.get_trigger().id
    )
    assert action_nodes.count() == 1
    action_node = action_nodes.first()
    assert action_node.service.specific.table_id == table.id


@pytest.mark.django_db(transaction=True)
def test_update_row_action_with_row_id_and_field_ids(data_fixture):
    """Test ActionNodeCreate uses row_id parameter and field IDs in values."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    text_field = data_fixture.create_text_field(table=table, name="Status")

    ctx = make_test_ctx(user, workspace)

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Update Row",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="action1",
                        label="Update row",
                        previous_node_ref="trigger1",
                        type="update_row",
                        table_id=table.id,
                        row_id="123",
                        values=[
                            AutomationFieldValue(
                                field_id=text_field.id, value="completed"
                            )
                        ],
                    )
                ],
            )
        ],
        thought="test",
    )

    assert len(result["created_workflows"]) == 1
    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

    action_nodes = workflow.automation_workflow_nodes.exclude(
        id=workflow.get_trigger().id
    )
    assert action_nodes.count() == 1
    action_node = action_nodes.first()
    assert action_node.service.specific.table_id == table.id
    assert action_node.service.get_type().type == "local_baserow_upsert_row"


@pytest.mark.django_db(transaction=True)
def test_delete_row_action_with_row_id(data_fixture):
    """Test ActionNodeCreate uses row_id parameter."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    ctx = make_test_ctx(user, workspace)

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Delete Row",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="action1",
                        label="Delete row",
                        previous_node_ref="trigger1",
                        type="delete_row",
                        table_id=table.id,
                        row_id="456",
                    )
                ],
            )
        ],
        thought="test",
    )

    assert len(result["created_workflows"]) == 1
    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

    action_nodes = workflow.automation_workflow_nodes.exclude(
        id=workflow.get_trigger().id
    )
    assert action_nodes.count() == 1
    action_node = action_nodes.first()
    assert action_node.service.specific.table_id == table.id
    assert action_node.service.get_type().type == "local_baserow_delete_row"


@pytest.mark.django_db(transaction=True)
def test_router_node_with_required_conditions(data_fixture):
    """Test ActionNodeCreate requires condition field for each edge."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    ctx = make_test_ctx(user, workspace)

    result = create_workflows(
        ctx,
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Router with Conditions",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                    periodic_interval={"interval": "DAY"},
                ),
                nodes=[
                    ActionNodeCreate(
                        ref="router1",
                        label="Router",
                        previous_node_ref="trigger1",
                        type="router",
                        edges=[
                            RouterEdgeCreate(
                                label="High Priority",
                                condition="Priority is high",
                            ),
                            RouterEdgeCreate(
                                label="Low Priority",
                                condition="Priority is low",
                            ),
                        ],
                    ),
                    ActionNodeCreate(
                        ref="action1",
                        label="Create row",
                        previous_node_ref="router1",
                        type="create_row",
                        table_id=table.id,
                        values=[],
                    ),
                ],
            )
        ],
        thought="test",
    )

    assert len(result["created_workflows"]) == 1
    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

    # Get the router node and verify it was created with edges
    router_nodes = workflow.automation_workflow_nodes.filter(
        service__isnull=False
    ).exclude(id=workflow.get_trigger().id)

    # Find the router node (service type will be router)
    router_node = None
    for node in router_nodes:
        if "router" in node.service.get_type().type:
            router_node = node
            break

    assert router_node is not None, "Router node should be created"
    # Verify edges were created
    edges = router_node.service.specific.edges.all()
    assert edges.count() == 2
    assert {e.label for e in edges} == {"High Priority", "Low Priority"}


def test_check_formula_with_basic_formulas():
    """Test that check_formula validates basic formulas correctly."""

    def check_formula(generated_formula: str, context: AssistantFormulaContext) -> str:
        try:
            resolve_formula(
                {"formula": generated_formula, "mode": BASEROW_FORMULA_MODE_ADVANCED},
                formula_runtime_function_registry,
                context,
            )
        except Exception as exc:
            raise ValueError(f"Generated formula is invalid: {str(exc)}")
        return "ok, the formula is valid"

    # Test basic string literal
    context = AssistantFormulaContext()
    result = check_formula("'a'", context)
    assert result == "ok, the formula is valid"

    # Test numeric literal
    result = check_formula("1", context)
    assert result == "ok, the formula is valid"

    # Test simple arithmetic
    result = check_formula("1 + 1", context)
    assert result == "ok, the formula is valid"

    # Test with context values
    context = AssistantFormulaContext()
    context.add_node_context(
        node_id=1,
        node_context=[{"name": "John", "age": 30, "active": True}],
    )

    # Test accessing context values
    result = check_formula("get('previous_node.1[0].name')", context)
    assert result == "ok, the formula is valid"

    result = check_formula("get('previous_node.1[0].age')", context)
    assert result == "ok, the formula is valid"

    result = check_formula("get('previous_node.1[0].active')", context)
    assert result == "ok, the formula is valid"

    # Test concat with context
    result = check_formula(
        "concat('Hello ', get('previous_node.1[0].name'), '!')", context
    )
    assert result == "ok, the formula is valid"

    # Test arithmetic with context
    result = check_formula("get('previous_node.1[0].age') + 5", context)
    assert result == "ok, the formula is valid"

    # Test invalid formula should raise ValueError
    try:
        check_formula("invalid_function()", context)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Generated formula is invalid" in str(e)
