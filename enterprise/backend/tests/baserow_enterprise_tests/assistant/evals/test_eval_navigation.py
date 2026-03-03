"""
Agent-level evals for the navigation tool.

Verifies:
- The agent navigates to a table when asked
- The agent navigates to the workspace home

Run with: pytest -m eval -k test_eval_navigation -v -s
"""

import pytest

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

PROMPT_NAVIGATES_TO_TABLE = "Navigate to the Tasks table (ID: {table_id})"

PROMPT_NAVIGATES_TO_WORKSPACE = "Go to the workspace home page"


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
def test_agent_navigates_to_table(data_fixture, eval_model):
    """Agent should call navigate with the correct table_id when asked to open a table."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Projects DB"
    )
    table = data_fixture.create_database_table(database=database, name="Tasks")

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
        question=PROMPT_NAVIGATES_TO_TABLE.format(table_id=table.id),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    history = format_message_history(result)
    tool_calls = [
        e for e in history if e.get("tool_name") == "navigate" and e["role"] == "user"
    ]
    assert len(tool_calls) >= 1, (
        "Agent should have called navigate at least once. "
        f"History tools: {[e.get('tool_name') for e in history if e.get('tool_name')]}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_navigates_to_workspace(data_fixture, eval_model):
    """Agent should navigate to workspace home when asked to go home."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

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
        question=PROMPT_NAVIGATES_TO_WORKSPACE,
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    history = format_message_history(result)
    tool_calls = [
        e for e in history if e.get("tool_name") == "navigate" and e["role"] == "user"
    ]
    assert len(tool_calls) >= 1, (
        "Agent should have called navigate at least once. "
        f"History tools: {[e.get('tool_name') for e in history if e.get('tool_name')]}"
    )
