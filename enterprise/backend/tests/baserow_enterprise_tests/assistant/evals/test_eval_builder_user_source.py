import pytest

from baserow.core.user_sources.handler import UserSourceHandler
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
# UI context helper
# ---------------------------------------------------------------------------


def build_builder_ui_context(user, workspace, builder) -> str:
    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        application=ApplicationUIContext(id=str(builder.id), name=builder.name),
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_NEW_TABLE = (
    "In builder '{builder_name}', set up a user source called 'App Users' "
    "so users can log in with roles: Admin and Viewer."
)

PROMPT_EXISTING_TABLE = (
    "In builder '{builder_name}', set up a user source called 'Members' "
    "using the existing table '{table_name}'."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    deps.tool_helpers.request_context["ui_context"] = ui_context

    from baserow_enterprise.assistant.deps import AgentMode

    deps.mode = AgentMode.APPLICATION

    return agent.run_sync(
        user_prompt=question,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )


def _filter_tool_calls(result, tool_names):
    history = format_message_history(result)
    calls = [e for e in history if e["role"] == "assistant" and "args" in e]
    if isinstance(tool_names, str):
        tool_names = {tool_names}
    else:
        tool_names = set(tool_names)
    return [e for e in calls if e.get("tool_name") in tool_names]


# ---------------------------------------------------------------------------
# Evals
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_eval_setup_user_source_new_table(data_fixture, eval_model):
    """Agent creates a user source with a brand-new users table."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="My DB"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_NEW_TABLE.format(
            builder_name=builder.name, database_name=database.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    setup_calls = _filter_tool_calls(result, "setup_user_source")
    user_sources = UserSourceHandler().get_user_sources(builder)

    with EvalChecklist("user source new table") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called setup_user_source",
            len(setup_calls) >= 1,
            hint=f"calls: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}",
        )
        checks.check(
            "user source created",
            len(user_sources) >= 1,
            hint=f"found {len(user_sources)} user sources",
        )
        if user_sources:
            us = user_sources[0]
            roles = us.get_type().get_roles(us)
            checks.check(
                "has Admin role",
                "Admin" in roles,
                hint=f"roles: {roles}",
            )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_eval_setup_user_source_existing_table(data_fixture, eval_model):
    """Agent creates a user source using an existing table."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="My DB"
    )
    table = data_fixture.create_database_table(
        database=database, name="Members", user=user
    )
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_email_field(table=table, name="Email")
    data_fixture.create_password_field(table=table, name="Password")
    data_fixture.create_single_select_field(table=table, name="Role")

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_EXISTING_TABLE.format(
            builder_name=builder.name,
            table_name=table.name,
            table_id=table.id,
            database_name=database.name,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    setup_calls = _filter_tool_calls(result, "setup_user_source")
    user_sources = UserSourceHandler().get_user_sources(builder)

    with EvalChecklist("user source existing table") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called setup_user_source",
            len(setup_calls) >= 1,
            hint=f"calls: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}",
        )
        checks.check(
            "user source created",
            len(user_sources) >= 1,
            hint=f"found {len(user_sources)} user sources",
        )
        if user_sources:
            us = user_sources[0]
            checks.check(
                "uses correct table",
                us.specific.table_id == table.id,
                hint=f"expected table {table.id}, got {us.specific.table_id}",
            )
