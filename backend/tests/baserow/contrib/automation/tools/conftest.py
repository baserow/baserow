import pytest
from pydantic_ai import Agent

from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.tools import ToolContext


@pytest.fixture(autouse=True)
def no_model_calls(monkeypatch):
    """
    The shared tools must never call a model, whichever client runs them. Calls
    are also checked after the test, in case the caller swallowed the error.
    """

    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        raise AssertionError("A shared tool called a model.")

    for method in ("run", "run_sync", "run_stream", "iter"):
        monkeypatch.setattr(Agent, method, fail)
    yield
    assert not calls, "A shared tool called a model."


@pytest.fixture
def automation_ctx(data_fixture):
    """A user's workspace with an automation and a table with a Name field."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    return ToolContext(user=user, workspace=workspace), automation, table, name


def create_node(user, workflow, node_type, **kwargs):
    return AutomationNodeService().create_node(
        user, automation_node_type_registry.get(node_type), workflow, **kwargs
    )


def create_workflow(user, automation, name="Flow", table=None):
    """A workflow with a "rows created" trigger on the table."""

    workflow = AutomationWorkflowService().create_workflow(user, automation.id, name)
    trigger = create_node(
        user,
        workflow,
        "local_baserow_rows_created",
        service={"table_id": table.id} if table else {},
    )
    return workflow, trigger
