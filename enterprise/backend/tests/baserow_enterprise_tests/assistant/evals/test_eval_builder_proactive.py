"""
Eval: the agent should ask the user when implied resources don't exist.

When the user says "create an app showing projects", the agent should look for
a "projects" table, and if none exists, ask the user which table to use rather
than creating a new table and building everything on top of it.
"""

import pytest

from baserow_enterprise.assistant.types import (
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)

from .eval_utils import (
    assert_no_tool_errors,
    create_eval_assistant,
    format_message_history,
    print_message_history,
)


def _build_ui_context(user, workspace) -> str:
    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


def _get_tool_calls(result, tool_name):
    history = format_message_history(result)
    return [
        e
        for e in history
        if e["role"] == "assistant" and e.get("tool_name") == tool_name and "args" in e
    ]


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_asks_when_implied_table_missing(data_fixture, eval_model):
    """
    Agent should NOT create a table when the user's request implies one exists.

    Scenario: workspace has an "Invoices" table but no "Projects" table.
    Prompt: "create an app showing projects in a list".
    Expected: agent calls list_tables, finds no match, and asks the user.
    Not expected: agent calls create_tables to make a "Projects" table.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # Create an unrelated table so list_tables returns something
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Finance"
    )
    table = data_fixture.create_database_table(
        user=user, database=database, name="Invoices"
    )
    data_fixture.create_text_field(table=table, name="Invoice Number", primary=True)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = _build_ui_context(user, workspace)
    deps.tool_helpers.request_context["ui_context"] = ui_context

    result = agent.run_sync(
        user_prompt=(
            "Create an app showing projects in a list with cards showing "
            "project name and status."
        ),
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # The agent should NOT have created tables
    create_table_calls = _get_tool_calls(result, "create_tables")
    assert len(create_table_calls) == 0, (
        "Agent should NOT create a table when the user's request implies one "
        "already exists. It should ask the user instead.\n"
        f"create_tables calls: {create_table_calls}"
    )

    # The agent should have searched for tables
    list_table_calls = _get_tool_calls(result, "list_tables")
    assert len(list_table_calls) >= 1, (
        "Agent should have called list_tables to look for a 'projects' table. "
        f"Tools called: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}"
    )

    # The agent's final message should be text (a question), not a tool call
    history = format_message_history(result)
    last_assistant = [e for e in history if e["role"] == "assistant"][-1]
    assert last_assistant["type"] == "TextPart", (
        f"Expected the agent to end with a text response (asking the user), "
        f"but got {last_assistant['type']}"
    )
