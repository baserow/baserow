import pytest

from baserow.contrib.automation.models import Automation
from baserow.contrib.database.models import Database

from .eval_utils import (
    EvalChecklist,
    build_database_ui_context,
    count_tool_errors,
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
    err_count, err_hint = count_tool_errors(result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "list_builders" and e["role"] == "user"
    ]

    with EvalChecklist("lists databases") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called list_builders",
            len(tool_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            "answer mentions 'Inventory'",
            "Inventory" in result.output,
            hint=f"answer: {result.output[:200]}",
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
    err_count, err_hint = count_tool_errors(result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "create_builders" and e["role"] == "user"
    ]
    created = Database.objects.filter(workspace=workspace, name__icontains="customer")

    with EvalChecklist("creates database") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called create_builders",
            len(tool_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            "database 'Customer Portal' exists",
            created.exists(),
            hint=f"databases: {list(Database.objects.filter(workspace=workspace).values_list('name', flat=True))}",
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
    err_count, err_hint = count_tool_errors(result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "create_builders" and e["role"] == "user"
    ]
    created = list(Automation.objects.all())
    automation = created[0] if created else None

    with EvalChecklist("creates automation") as checks:
        checks.check("<=1 tool errors", err_count <= 1, hint=err_hint)
        checks.check(
            "called create_builders",
            len(tool_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            "exactly 1 automation created",
            len(created) == 1,
            hint=f"found {len(created)}: {[a.name for a in created]}",
        )
        checks.check(
            "automation named 'Overdue Task Reminder'",
            automation is not None and "overdue" in automation.name.lower(),
            hint=f"got: '{automation.name if automation else None}'",
        )
        checks.check(
            "automation in correct workspace",
            automation is not None and automation.workspace_id == workspace.id,
            hint=f"workspace_id={automation.workspace_id if automation else None} vs {workspace.id}",
        )
        checks.check(
            "automation has no workflows",
            automation is not None and automation.workflows.count() == 0,
            hint=f"workflows: {list(automation.workflows.all()) if automation else []}",
        )
