import pytest

from baserow.contrib.automation.models import Automation
from baserow.contrib.database.models import Database

from .eval_utils import (
    assert_no_tool_errors,
    build_database_ui_context,
    create_eval_assistant,
    format_message_history,
    print_message_history,
)

# ---------------------------------------------------------------------------
# Eval prompts — one per test, easy to scan for coverage
# ---------------------------------------------------------------------------

PROMPT_LISTS_DATABASES = "What databases do I have in this workspace?"

PROMPT_CREATES_DATABASE = "Create a new database called 'Customer Portal'"

PROMPT_CREATES_AUTOMATION = "Create an empty automation called 'Overdue Task Reminder'."


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    deps.tool_helpers.request_context["ui_context"] = ui_context
    return agent.run_sync(
        user_prompt=question,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_lists_databases(data_fixture, eval_model):
    """Agent should call list_builders when asked what databases exist."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Inventory"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=10, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_LISTS_DATABASES,
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "list_builders" and e["role"] == "user"
    ]
    assert len(tool_calls) >= 1, (
        "Agent should have called list_builders. "
        f"Tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}"
    )

    # The agent's answer should mention the database name
    assert "Inventory" in result.output, (
        f"Agent answer should mention 'Inventory', got: {result.output[:200]}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_database(data_fixture, eval_model):
    """Agent should create a new database when asked."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_DATABASE,
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "create_builders" and e["role"] == "user"
    ]
    assert len(tool_calls) >= 1, (
        "Agent should have called create_builders. "
        f"Tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}"
    )

    # Verify the database was actually created
    created = Database.objects.filter(workspace=workspace, name__icontains="customer")
    assert created.exists(), (
        "Database 'Customer Portal' was not found in the workspace. "
        f"Databases: {list(Database.objects.filter(workspace=workspace).values_list('name', flat=True))}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_automation(data_fixture, eval_model):
    """Agent should create a new automation when asked."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace)
    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_AUTOMATION,
        ui_context=ui_context,
    )
    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "create_builders" and e["role"] == "user"
    ]
    assert len(tool_calls) >= 1, (
        "Agent should have called create_builders to create automation. "
        f"Tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}"
    )

    # Verify the automation was actually created
    created = Automation.objects.all()
    assert len(created) == 1, (
        "Expected exactly one automation to be created, but found "
        f"{len(created)}. "
        "Automations: "
        f"{list(Automation.objects.filter(workspace=workspace).values_list('name', flat=True))}"
    )
    automation = created[0]
    assert "overdue" in automation.name.lower(), (
        f"Created automation should be named 'Overdue Task Reminder', but got '{automation.name}'."
    )
    assert automation.workspace_id == workspace.id, (
        "Created automation should be in the correct workspace, but got "
        f"{automation.workspace_id} instead of {workspace.id}."
    )

    # Verify the created automation has an empty workflow
    assert automation.workflows.count() == 0, (
        "Created automation should have no workflows, but found: "
        f"{automation.workflows.all()}"
    )
