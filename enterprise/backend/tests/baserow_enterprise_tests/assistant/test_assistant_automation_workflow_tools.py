from unittest.mock import Mock

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow_enterprise.assistant.tools.automation.tools import (
    get_list_workflows_tool,
    get_workflow_tool_factory,
)
from baserow_enterprise.assistant.tools.automation.types import (
    CreateRowActionCreate,
    DeleteRowActionCreate,
    RouterNodeCreate,
    TriggerNodeCreate,
    UpdateRowActionCreate,
    WorkflowCreate,
)
from baserow_enterprise.assistant.tools.automation.types.node import RouterEdgeCreate
from baserow_enterprise.assistant.tools.automation.utils import AssistantFormulaContext

from .utils import fake_tool_helpers


@pytest.fixture(autouse=True)
def mock_formula_generator(monkeypatch):
    """
    Mock update_workflow_formulas to avoid LM requirement in tests.
    Simply skips formula generation entirely.
    """

    def mock_update_workflow_formulas(workflow, node_mapping, tool_helpers):
        """Mock that does nothing - skips formula generation."""

        pass

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.automation.utils.update_workflow_formulas",
        mock_update_workflow_formulas,
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

    tool = get_list_workflows_tool(user, workspace, fake_tool_helpers)
    result = tool(automation_id=automation.id)

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

    tool = get_list_workflows_tool(user, workspace, fake_tool_helpers)
    result = tool(automation_id=automation.id)

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

    factory = get_workflow_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_workflows_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflows"), None
    )
    assert create_workflows_tool is not None

    result = create_workflows_tool.func(
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Process Orders",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                ),
                nodes=[
                    CreateRowActionCreate(
                        ref="action1",
                        label="Create row",
                        previous_node_ref="trigger1",
                        type="create_row",
                        table_id=table.id,
                        values={},
                    )
                ],
            )
        ],
    )

    assert len(result["created_workflows"]) == 1
    assert result["created_workflows"][0]["name"] == "Process Orders"
    assert result["created_workflows"][0]["state"] == "draft"

    # Verify workflow was created with a trigger
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    trigger = workflow.get_trigger()
    assert trigger is not None
    assert trigger.get_type().type == "periodic"


@pytest.mark.django_db(transaction=True)
def test_create_multiple_workflows(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    factory = get_workflow_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_workflows_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflows"), None
    )
    assert create_workflows_tool is not None

    result = create_workflows_tool.func(
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Workflow 1",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Trigger",
                    type="periodic",
                ),
                nodes=[
                    CreateRowActionCreate(
                        ref="action1",
                        label="Action",
                        previous_node_ref="trigger1",
                        type="create_row",
                        table_id=table.id,
                        values={},
                    )
                ],
            ),
            WorkflowCreate(
                name="Workflow 2",
                trigger=TriggerNodeCreate(
                    ref="trigger2",
                    label="Trigger",
                    type="periodic",
                ),
                nodes=[
                    CreateRowActionCreate(
                        ref="action2",
                        label="Action",
                        previous_node_ref="trigger2",
                        type="create_row",
                        table_id=table.id,
                        values={},
                    )
                ],
            ),
        ],
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
                type="rows_created", ref="trigger", label="Rows Created Trigger"
            ),
            CreateRowActionCreate(
                type="create_row",
                ref="action",
                previous_node_ref="trigger",
                label="Create Row Action",
                table_id=999,
                values={},
            ),
        ),
        (
            TriggerNodeCreate(
                type="rows_updated", ref="trigger", label="Rows Updated Trigger"
            ),
            UpdateRowActionCreate(
                type="update_row",
                ref="action",
                previous_node_ref="trigger",
                label="Update Row Action",
                table_id=999,
                row_id="1",
                values={},
            ),
        ),
        (
            TriggerNodeCreate(
                type="rows_deleted", ref="trigger", label="Rows Deleted Trigger"
            ),
            DeleteRowActionCreate(
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

    factory = get_workflow_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_workflows_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflows"), None
    )
    assert create_workflows_tool is not None

    result = create_workflows_tool.func(
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Row Trigger Workflow",
                trigger=trigger,
                nodes=[action],
            )
        ],
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
    """Test CreateRowActionCreate uses field IDs in values dict, not field names."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    text_field = data_fixture.create_text_field(table=table, name="Name")
    number_field = data_fixture.create_number_field(table=table, name="Age")

    factory = get_workflow_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_workflows_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflows"), None
    )
    assert create_workflows_tool is not None

    result = create_workflows_tool.func(
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Field IDs",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                ),
                nodes=[
                    CreateRowActionCreate(
                        ref="action1",
                        label="Create row with field IDs",
                        previous_node_ref="trigger1",
                        type="create_row",
                        table_id=table.id,
                        values={
                            text_field.id: "John Doe",
                            number_field.id: 25,
                        },
                    )
                ],
            )
        ],
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
    """Test UpdateRowActionCreate uses row_id parameter and field IDs in values."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    text_field = data_fixture.create_text_field(table=table, name="Status")

    factory = get_workflow_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_workflows_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflows"), None
    )
    assert create_workflows_tool is not None

    result = create_workflows_tool.func(
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Update Row",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                ),
                nodes=[
                    UpdateRowActionCreate(
                        ref="action1",
                        label="Update row",
                        previous_node_ref="trigger1",
                        type="update_row",
                        table_id=table.id,
                        row_id="123",
                        values={text_field.id: "completed"},
                    )
                ],
            )
        ],
    )

    assert len(result["created_workflows"]) == 1
    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

    # Get the action node and verify it was created with the correct table
    # Note: row_id formula generation occurs in a separate transaction and may fail
    # if DSPy is not configured, so we only verify basic service configuration
    action_nodes = workflow.automation_workflow_nodes.exclude(
        id=workflow.get_trigger().id
    )
    assert action_nodes.count() == 1
    action_node = action_nodes.first()
    assert action_node.service.specific.table_id == table.id
    # Verify the service type is correct for upsert_row (update operation)
    assert action_node.service.get_type().type == "local_baserow_upsert_row"


@pytest.mark.django_db(transaction=True)
def test_delete_row_action_with_row_id(data_fixture):
    """Test DeleteRowActionCreate uses row_id parameter."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    factory = get_workflow_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_workflows_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflows"), None
    )
    assert create_workflows_tool is not None

    result = create_workflows_tool.func(
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Delete Row",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                ),
                nodes=[
                    DeleteRowActionCreate(
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
    )

    assert len(result["created_workflows"]) == 1
    workflow_id = result["created_workflows"][0]["id"]
    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

    # Get the action node and verify it was created with the correct table
    # Note: row_id formula generation occurs in a separate transaction and may fail
    # if DSPy is not configured, so we only verify basic service configuration
    action_nodes = workflow.automation_workflow_nodes.exclude(
        id=workflow.get_trigger().id
    )
    assert action_nodes.count() == 1
    action_node = action_nodes.first()
    assert action_node.service.specific.table_id == table.id
    # Verify the service type is correct for delete_row
    assert action_node.service.get_type().type == "local_baserow_delete_row"


@pytest.mark.django_db(transaction=True)
def test_router_node_with_required_conditions(data_fixture):
    """Test RouterNodeCreate requires condition field for each edge."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    factory = get_workflow_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_workflows_tool = next(
        (tool for tool in added_tools if tool.name == "create_workflows"), None
    )
    assert create_workflows_tool is not None

    result = create_workflows_tool.func(
        automation_id=automation.id,
        workflows=[
            WorkflowCreate(
                name="Test Router with Conditions",
                trigger=TriggerNodeCreate(
                    ref="trigger1",
                    label="Periodic Trigger",
                    type="periodic",
                ),
                nodes=[
                    RouterNodeCreate(
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
                    CreateRowActionCreate(
                        ref="action1",
                        label="Create row",
                        previous_node_ref="router1",
                        type="create_row",
                        table_id=table.id,
                        values={},
                    ),
                ],
            )
        ],
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
