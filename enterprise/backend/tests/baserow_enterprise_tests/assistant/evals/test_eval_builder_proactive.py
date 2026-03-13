"""
Eval: the agent should ask the user when implied resources don't exist.

When the user says "create an app showing projects", the agent should look for
a "projects" table, and if none exists, ask the user which table to use rather
than creating a new table and building everything on top of it.

When a matching table IS found the agent should proceed to build the app.

Run with: pytest -m eval -k test_eval_builder_proactive -v -s
"""

import pytest

from baserow.contrib.builder.pages.models import Page
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.types import (
    ApplicationUIContext,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)

from .eval_utils import (
    EvalChecklist,
    count_tool_errors,
    create_eval_assistant,
    format_message_history,
    print_message_history,
)

# ---------------------------------------------------------------------------
# Eval prompts — one per test, easy to scan for coverage
# ---------------------------------------------------------------------------

PROMPT_CREATE_PROJECTS_APP = (
    "Create an app showing projects in a list with cards showing "
    "project name and status."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_builder_ui_context(user, workspace, builder=None) -> str:
    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        application=ApplicationUIContext(id=str(builder.id), name=builder.name)
        if builder
        else None,
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    deps.tool_helpers.request_context["ui_context"] = ui_context

    ctx = UIContext.model_validate_json(ui_context)
    if ctx.application or ctx.page:
        deps.mode = AgentMode.APPLICATION
    elif ctx.automation or ctx.workflow:
        deps.mode = AgentMode.AUTOMATION
    else:
        deps.mode = AgentMode.DATABASE

    return agent.run_sync(
        user_prompt=question,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )


def _get_tool_calls(result, tool_name):
    history = format_message_history(result)
    return [
        e
        for e in history
        if e["role"] == "assistant" and e.get("tool_name") == tool_name and "args" in e
    ]


# ---------------------------------------------------------------------------
# Evals
# ---------------------------------------------------------------------------


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

    # Create an unrelated table so list_tables returns something meaningful
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Finance"
    )
    table = data_fixture.create_database_table(
        user=user, database=database, name="Invoices"
    )
    data_fixture.create_text_field(table=table, name="Invoice Number", primary=True)

    # Provide a builder context so the agent starts in APPLICATION mode
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = _build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATE_PROJECTS_APP,
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    history = format_message_history(result)
    create_table_calls = _get_tool_calls(result, "create_tables")
    list_table_calls = _get_tool_calls(result, "list_tables")
    create_page_calls = _get_tool_calls(result, "create_pages")
    setup_page_calls = _get_tool_calls(result, "setup_page")

    last_assistant_entries = [e for e in history if e["role"] == "assistant"]
    last_assistant = last_assistant_entries[-1] if last_assistant_entries else {}
    final_text = last_assistant.get("content", "")

    with EvalChecklist("asks when implied table missing") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called list_tables to search for 'projects'",
            len(list_table_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            "did NOT call create_tables",
            len(create_table_calls) == 0,
            hint=f"create_tables args: {[c.get('args') for c in create_table_calls]}",
        )
        checks.check(
            "did NOT create app pages (no matching table found)",
            len(create_page_calls) + len(setup_page_calls) == 0,
            hint=f"create_pages/setup_page args: {[c.get('args') for c in create_page_calls + setup_page_calls]}",
        )
        checks.check(
            "agent ended with a text response (asked the user)",
            last_assistant.get("type") == "TextPart",
            hint=f"last assistant entry type: {last_assistant.get('type')}",
        )
        checks.check(
            "response asks about projects or requests clarification",
            any(
                kw in final_text.lower()
                for kw in (
                    "project",
                    "which table",
                    "clarif",
                    "don't see",
                    "no table",
                    "exist",
                    "could you",
                    "please",
                )
            ),
            hint=f"response: {final_text[:300]}",
        )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_app_when_table_exists(data_fixture, eval_model):
    """
    When a matching 'Projects' table exists the agent should build the app
    without asking for clarification.

    Expected:
    - does NOT call create_tables (reuses existing)
    - creates a page
    - creates a data source pointing to the Projects table
    - creates at least one collection or display element
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Work"
    )
    projects_table = data_fixture.create_database_table(
        user=user, database=database, name="Projects"
    )
    data_fixture.create_text_field(table=projects_table, name="Name", primary=True)
    data_fixture.create_text_field(table=projects_table, name="Status")

    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Project Tracker"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=25, model=eval_model
    )
    ui_context = _build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATE_PROJECTS_APP,
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    history = format_message_history(result)
    create_table_calls = _get_tool_calls(result, "create_tables")
    create_page_calls = _get_tool_calls(result, "create_pages")
    setup_page_calls = _get_tool_calls(result, "setup_page")
    ds_calls = _get_tool_calls(result, "create_data_sources")

    pages = Page.objects.filter(builder=builder, shared=False)

    # Collect data source table_ids from args
    ds_table_ids = []
    for call in ds_calls:
        for ds in call.get("args", {}).get("data_sources", []):
            if ds.get("table_id"):
                ds_table_ids.append(ds["table_id"])

    # Collect all element types created
    _ELEMENT_TOOLS = {
        "create_display_elements",
        "create_collection_elements",
        "create_layout_elements",
        "create_form_elements",
    }
    el_calls = [
        e
        for e in history
        if e["role"] == "assistant"
        and e.get("tool_name") in _ELEMENT_TOOLS
        and "args" in e
    ]
    all_element_types = []
    for call in el_calls:
        all_element_types.extend(
            e.get("type") for e in call.get("args", {}).get("elements", [])
        )

    with EvalChecklist("creates app when projects table exists") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "did NOT call create_tables (used existing Projects table)",
            len(create_table_calls) == 0,
            hint=f"create_tables args: {[c.get('args') for c in create_table_calls]}",
        )
        checks.check(
            "created at least one page",
            len(create_page_calls) + len(setup_page_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            "page exists in DB",
            pages.exists(),
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        )
        checks.check(
            "data source targets Projects table",
            projects_table.id in ds_table_ids,
            hint=f"data source table_ids: {ds_table_ids}, expected: {projects_table.id}",
        )
        checks.check(
            "at least one element created",
            len(all_element_types) >= 1,
            hint=f"element tools called: {[c.get('tool_name') for c in el_calls]}",
        )
