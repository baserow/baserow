import pytest

from baserow.contrib.automation.workflows.models import AutomationWorkflow

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

PROMPT_LISTS_WORKFLOWS = "List the workflows in automation ID {automation_id}"

PROMPT_CREATES_WORKFLOW = (
    "Create a workflow in automation {automation_name} that "
    "triggers when a row is created in table '{table_name}', "
    "and updates the Status field to 'Processing'."
)

PROMPT_CREATES_WEEKLY_SLACK_REMINDER = (
    "In automation '{automation_name}', create a workflow that sends a "
    "Slack message to #general every Tuesday at 9am UTC asking "
    "'Is there anything to demo this week?'"
)

PROMPT_CREATES_ROUTER_WORKFLOW = (
    "In automation '{automation_name}', create a workflow that "
    "triggers when a row is created in table '{table_name}'. "
    "Add a router: if Priority is 'High', send a Slack message to "
    "#urgent saying 'High priority ticket created'. "
    "If Priority is 'Low', do nothing (just the router branch is fine)."
)

PROMPT_CREATES_ROW_WITH_FIELD_VALUES = (
    "In automation '{automation_name}', create a workflow that "
    "triggers when a row is created in '{source_table_name}'. "
    "Then create a row in '{log_table_name}' with Entry set to "
    "the new contact's Name and Source set to 'automation'."
)

PROMPT_CREATES_UPDATE_ROW_WORKFLOW = (
    "In automation '{automation_name}', create a workflow that "
    "triggers when a row is updated in '{table_name}'. "
    "Then update the same row: set Status to 'Reviewed' and "
    "Notes to 'Automatically reviewed by automation'."
)

PROMPT_CREATES_EMAIL_NOTIFICATION_WORKFLOW = (
    "In automation '{automation_name}', create a workflow that "
    "triggers when a row is created in '{table_name}'. "
    "Send an email to admin@example.com with subject 'New Order' "
    "and body 'A new order has been placed'."
)


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


def _get_create_workflows_args(result) -> list[dict]:
    """Return the parsed ``args`` dicts of every ``create_workflows`` tool call
    the agent made (assistant-side entries have ``args``)."""

    history = format_message_history(result)
    return [
        e["args"]
        for e in history
        if e["role"] == "assistant"
        and e.get("tool_name") == "create_workflows"
        and "args" in e
    ]


def _get_workflow_nodes(automation):
    """Return (workflow, trigger, action_nodes) for the first workflow."""

    workflow = AutomationWorkflow.objects.filter(automation=automation).first()
    assert workflow is not None, "No workflow was created"
    trigger = workflow.get_trigger()
    action_nodes = list(
        workflow.automation_workflow_nodes.exclude(id=trigger.id).order_by("id")
    )
    return workflow, trigger, action_nodes


# ---------------------------------------------------------------------------
# Existing evals
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_lists_workflows(data_fixture, eval_model):
    """Agent should call list_workflows when asked about automation workflows."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    automation = data_fixture.create_automation_application(
        workspace=workspace, name="My Automation"
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
        question=PROMPT_LISTS_WORKFLOWS.format(automation_id=automation.id),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "list_workflows" and e["role"] == "user"
    ]
    assert len(tool_calls) >= 1, (
        "Agent should have called list_workflows. "
        f"Tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_workflow(data_fixture, eval_model):
    """Agent should create a workflow when asked to automate a process."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=table, name="Order ID", primary=True)
    data_fixture.create_text_field(table=table, name="Status")

    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Order Processing"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, table)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_WORKFLOW.format(
            automation_name=automation.name, table_name=table.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "create_workflows" and e["role"] == "user"
    ]
    assert len(tool_calls) >= 1, (
        "Agent should have called create_workflows. "
        f"Tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}"
    )

    # Verify a workflow was actually created
    workflows = AutomationWorkflow.objects.filter(automation=automation)
    assert workflows.exists(), "No workflow was created in the automation"


# ---------------------------------------------------------------------------
# Periodic trigger + Slack message
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_weekly_slack_reminder(data_fixture, eval_model):
    """Agent should create a periodic-WEEK trigger firing on Tuesday with a
    Slack message node asking about demos."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Team Reminders"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_WEEKLY_SLACK_REMINDER.format(
            automation_name=automation.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Agent called create_workflows
    call_args_list = _get_create_workflows_args(result)
    assert len(call_args_list) >= 1, "Agent should have called create_workflows"

    # Inspect the args: expect periodic trigger + slack_write_message node
    args = call_args_list[0]
    workflows = args.get("workflows", [])
    assert len(workflows) >= 1, f"Expected at least 1 workflow, got {len(workflows)}"
    wf = workflows[0]

    trigger = wf.get("trigger", {})
    assert trigger.get("type") == "periodic", (
        f"Expected periodic trigger, got {trigger.get('type')}"
    )
    interval = trigger.get("periodic_interval", {})
    assert interval.get("interval") == "WEEK", (
        f"Expected WEEK interval, got {interval.get('interval')}"
    )
    assert interval.get("day_of_week") == 1, (
        f"Expected day_of_week=1 (Tuesday), got {interval.get('day_of_week')}"
    )

    nodes = wf.get("nodes", [])
    slack_nodes = [n for n in nodes if n.get("type") == "slack_write_message"]
    assert len(slack_nodes) >= 1, (
        f"Expected a slack_write_message node, got types: "
        f"{[n.get('type') for n in nodes]}"
    )

    # Verify the workflow was actually created in DB
    workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
    assert trigger_node.get_type().type == "periodic"
    slack_actions = [
        n for n in action_nodes if n.service.get_type().type == "slack_write_message"
    ]
    assert len(slack_actions) >= 1, "Slack node should exist in the created workflow"


# ---------------------------------------------------------------------------
# Router node
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_router_workflow(data_fixture, eval_model):
    """Agent should create a workflow with a router node that branches
    based on a condition."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tickets")
    data_fixture.create_text_field(table=table, name="Title", primary=True)
    priority_field = data_fixture.create_single_select_field(
        table=table, name="Priority"
    )
    data_fixture.create_select_option(field=priority_field, value="High", order=0)
    data_fixture.create_select_option(field=priority_field, value="Low", order=1)

    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Ticket Router"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, table)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_ROUTER_WORKFLOW.format(
            automation_name=automation.name, table_name=table.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Agent called create_workflows
    call_args_list = _get_create_workflows_args(result)
    assert len(call_args_list) >= 1, "Agent should have called create_workflows"

    # Inspect: expect a router node in the workflow
    args = call_args_list[0]
    workflows = args.get("workflows", [])
    assert len(workflows) >= 1
    wf = workflows[0]

    nodes = wf.get("nodes", [])
    router_nodes = [n for n in nodes if n.get("type") == "router"]
    assert len(router_nodes) >= 1, (
        f"Expected a router node, got types: {[n.get('type') for n in nodes]}"
    )

    # Router should have at least 2 edges
    router = router_nodes[0]
    edges = router.get("edges", [])
    assert len(edges) >= 2, f"Router should have at least 2 edges, got {len(edges)}"

    # Verify the workflow was created in DB with a router node
    workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
    router_actions = [n for n in action_nodes if n.service.get_type().type == "router"]
    assert len(router_actions) >= 1, "Router node should exist in the created workflow"

    # Router should have edges in DB
    router_service = router_actions[0].service.specific
    db_edges = router_service.edges.all()
    assert db_edges.count() >= 2, (
        f"Router should have at least 2 edges in DB, got {db_edges.count()}"
    )


# ---------------------------------------------------------------------------
# Create-row / update-row with field value formulas
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_row_with_field_values(data_fixture, eval_model):
    """Agent should create a workflow with a create_row node that maps
    specific field values (including formula-style references)."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    source_table = data_fixture.create_database_table(
        database=database, name="Contacts"
    )
    data_fixture.create_text_field(table=source_table, name="Name", primary=True)
    data_fixture.create_email_field(table=source_table, name="Email")

    log_table = data_fixture.create_database_table(database=database, name="Log")
    data_fixture.create_text_field(table=log_table, name="Entry", primary=True)
    data_fixture.create_text_field(table=log_table, name="Source")

    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Contact Logger"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, source_table)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_ROW_WITH_FIELD_VALUES.format(
            automation_name=automation.name,
            source_table_name=source_table.name,
            log_table_name=log_table.name,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Agent called create_workflows
    call_args_list = _get_create_workflows_args(result)
    assert len(call_args_list) >= 1, "Agent should have called create_workflows"

    # Inspect: expect rows_created trigger + create_row node with values
    args = call_args_list[0]
    workflows = args.get("workflows", [])
    assert len(workflows) >= 1
    wf = workflows[0]

    trigger = wf.get("trigger", {})
    assert trigger.get("type") == "rows_created", (
        f"Expected rows_created trigger, got {trigger.get('type')}"
    )

    nodes = wf.get("nodes", [])
    create_row_nodes = [n for n in nodes if n.get("type") == "create_row"]
    assert len(create_row_nodes) >= 1, (
        f"Expected a create_row node, got types: {[n.get('type') for n in nodes]}"
    )

    # The create_row node should have values referencing fields
    cr = create_row_nodes[0]
    values = cr.get("values", [])
    assert len(values) >= 1, (
        f"create_row should have at least 1 field value mapping, got {len(values)}"
    )

    # Verify workflow was created in DB
    workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
    assert trigger_node.service.get_type().type == "local_baserow_rows_created"
    create_actions = [
        n
        for n in action_nodes
        if n.service.get_type().type == "local_baserow_upsert_row"
    ]
    assert len(create_actions) >= 1, (
        "create_row action should exist in the created workflow"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_update_row_workflow(data_fixture, eval_model):
    """Agent should create a workflow with an update_row node that references
    field values from the trigger."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    table = data_fixture.create_database_table(database=database, name="Tasks")
    data_fixture.create_text_field(table=table, name="Task", primary=True)
    data_fixture.create_text_field(table=table, name="Status")
    data_fixture.create_long_text_field(table=table, name="Notes")

    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Task Processor"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, table)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_UPDATE_ROW_WORKFLOW.format(
            automation_name=automation.name, table_name=table.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Agent called create_workflows
    call_args_list = _get_create_workflows_args(result)
    assert len(call_args_list) >= 1, "Agent should have called create_workflows"

    args = call_args_list[0]
    workflows = args.get("workflows", [])
    assert len(workflows) >= 1
    wf = workflows[0]

    # Trigger should be rows_updated
    trigger = wf.get("trigger", {})
    assert trigger.get("type") == "rows_updated", (
        f"Expected rows_updated trigger, got {trigger.get('type')}"
    )

    # Should have an update_row node with values
    nodes = wf.get("nodes", [])
    update_nodes = [n for n in nodes if n.get("type") == "update_row"]
    assert len(update_nodes) >= 1, (
        f"Expected an update_row node, got types: {[n.get('type') for n in nodes]}"
    )

    ur = update_nodes[0]
    values = ur.get("values", [])
    assert len(values) >= 1, "update_row should have field value mappings"

    # row_id should be set (referencing the trigger row)
    assert ur.get("row_id"), "update_row should have a row_id"

    # Verify in DB
    workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
    assert trigger_node.service.get_type().type == "local_baserow_rows_updated"
    update_actions = [
        n
        for n in action_nodes
        if n.service.get_type().type == "local_baserow_upsert_row"
    ]
    assert len(update_actions) >= 1, (
        "update_row action should exist in the created workflow"
    )


# ---------------------------------------------------------------------------
# Send email node
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_email_notification_workflow(data_fixture, eval_model):
    """Agent should create a workflow with an smtp_email node."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=table, name="Order ID", primary=True)
    data_fixture.create_text_field(table=table, name="Customer Email")

    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Order Notifications"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, table)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_EMAIL_NOTIFICATION_WORKFLOW.format(
            automation_name=automation.name, table_name=table.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    call_args_list = _get_create_workflows_args(result)
    assert len(call_args_list) >= 1, "Agent should have called create_workflows"

    args = call_args_list[0]
    workflows = args.get("workflows", [])
    assert len(workflows) >= 1
    wf = workflows[0]

    nodes = wf.get("nodes", [])
    email_nodes = [n for n in nodes if n.get("type") == "smtp_email"]
    assert len(email_nodes) >= 1, (
        f"Expected an smtp_email node, got types: {[n.get('type') for n in nodes]}"
    )

    # Verify in DB
    workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
    email_actions = [
        n for n in action_nodes if n.service.get_type().type == "smtp_email"
    ]
    assert len(email_actions) >= 1, (
        "smtp_email action should exist in the created workflow"
    )
