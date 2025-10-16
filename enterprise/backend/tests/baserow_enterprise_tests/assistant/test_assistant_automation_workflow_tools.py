import pytest

from baserow_enterprise.assistant.tools.automation.tools import (
    get_create_workflows_tool,
    get_list_workflows_tool,
)
from baserow_enterprise.assistant.tools.automation.types import (
    CreateRowActionCreate,
    TriggerNodeCreate,
    WorkflowCreate,
)

from .utils import fake_tool_helpers


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

    tool = get_create_workflows_tool(user, workspace, fake_tool_helpers)
    result = tool(
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

    tool = get_create_workflows_tool(user, workspace, fake_tool_helpers)
    result = tool(
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
