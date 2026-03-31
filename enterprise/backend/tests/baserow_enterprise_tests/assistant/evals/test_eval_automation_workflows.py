import pytest

from baserow.contrib.automation.workflows.models import AutomationWorkflow

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
    err_count, err_hint = count_tool_errors(result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "list_workflows" and e["role"] == "user"
    ]

    with EvalChecklist("lists workflows") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called list_workflows",
            len(tool_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
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
    err_count, err_hint = count_tool_errors(result)

    history = format_message_history(result)
    tool_calls = [
        e
        for e in history
        if e.get("tool_name") == "create_workflows" and e["role"] == "user"
    ]
    workflows = AutomationWorkflow.objects.filter(automation=automation)

    call_args_list = _get_create_workflows_args(result)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    trigger_args = wf_args.get("trigger", {})
    nodes_args = wf_args.get("nodes", [])
    trigger_table_id = trigger_args.get("rows_triggers_settings", {}).get("table_id")
    update_nodes_args = [n for n in nodes_args if n.get("type") == "update_row"]
    ur_values = update_nodes_args[0].get("values", []) if update_nodes_args else []
    ur_has_processing = any(
        "processing" in str(v.get("value", "")).lower() for v in ur_values
    )

    db_ok = workflows.exists()
    if db_ok:
        workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
        db_trigger_type = trigger_node.service.get_type().type
        db_update_actions = [
            n
            for n in action_nodes
            if n.service.get_type().type == "local_baserow_upsert_row"
        ]
    else:
        db_trigger_type = None
        db_update_actions = []

    with EvalChecklist("creates workflow") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called create_workflows",
            len(tool_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            "workflow created in DB",
            db_ok,
        )
        checks.check(
            "trigger is rows_created",
            trigger_args.get("type") == "rows_created",
            hint=f"got {trigger_args.get('type')}",
        )
        checks.check(
            "trigger table is Orders",
            trigger_table_id == table.id,
            hint=f"got table_id={trigger_table_id}, expected={table.id}",
        )
        checks.check(
            "update_row node in args",
            len(update_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        )
        checks.check(
            "update_row sets field to 'Processing'",
            ur_has_processing,
            hint=f"values: {ur_values}",
        )
        checks.check(
            "DB trigger is rows_created",
            db_trigger_type == "local_baserow_rows_created",
            hint=f"got {db_trigger_type}",
        )
        checks.check(
            "update_row action in DB",
            len(db_update_actions) >= 1,
        )


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
    err_count, err_hint = count_tool_errors(result)

    call_args_list = _get_create_workflows_args(result)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    trigger_args = wf_args.get("trigger", {})
    interval_args = trigger_args.get("periodic_interval", {})
    nodes_args = wf_args.get("nodes", [])
    slack_nodes_args = [n for n in nodes_args if n.get("type") == "slack_write_message"]

    db_ok = AutomationWorkflow.objects.filter(automation=automation).exists()
    if db_ok:
        workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
        db_trigger_type = trigger_node.get_type().type
        db_slack_actions = [
            n
            for n in action_nodes
            if n.service.get_type().type == "slack_write_message"
        ]
    else:
        db_trigger_type = None
        db_slack_actions = []

    slack_node = slack_nodes_args[0] if slack_nodes_args else {}
    slack_channel = slack_node.get("channel", "")
    slack_text = slack_node.get("text", "")

    with EvalChecklist("creates weekly Slack reminder") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called create_workflows",
            len(call_args_list) >= 1,
        )
        checks.check(
            "trigger type is periodic",
            trigger_args.get("type") == "periodic",
            hint=f"got {trigger_args.get('type')}",
        )
        checks.check(
            "interval is WEEK",
            interval_args.get("interval") == "WEEK",
            hint=f"got {interval_args.get('interval')}",
        )
        checks.check(
            "day_of_week is 1 (Tuesday)",
            interval_args.get("day_of_week") == 1,
            hint=f"got {interval_args.get('day_of_week')}",
        )
        checks.check(
            "slack_write_message node in args",
            len(slack_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        )
        checks.check(
            "workflow created in DB with periodic trigger",
            db_trigger_type == "periodic",
            hint=f"got {db_trigger_type}",
        )
        checks.check(
            "Slack action exists in DB",
            len(db_slack_actions) >= 1,
        )
        checks.check(
            "Slack channel is #general",
            "general" in slack_channel.lower(),
            hint=f"got channel: '{slack_channel}'",
        )
        checks.check(
            "Slack message mentions demo",
            "demo" in slack_text.lower(),
            hint=f"got text: '{slack_text}'",
        )


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
    err_count, err_hint = count_tool_errors(result)

    call_args_list = _get_create_workflows_args(result)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    nodes_args = wf_args.get("nodes", [])
    router_nodes_args = [n for n in nodes_args if n.get("type") == "router"]
    router_edges_args = (
        router_nodes_args[0].get("edges", []) if router_nodes_args else []
    )

    db_ok = AutomationWorkflow.objects.filter(automation=automation).exists()
    if db_ok:
        workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
        db_router_actions = [
            n for n in action_nodes if n.service.get_type().type == "router"
        ]
        db_edges_count = (
            db_router_actions[0].service.specific.edges.count()
            if db_router_actions
            else 0
        )
    else:
        db_router_actions = []
        db_edges_count = 0

    trigger_args = wf_args.get("trigger", {})
    trigger_table_id = trigger_args.get("rows_triggers_settings", {}).get("table_id")
    slack_nodes_in_nodes = [
        n for n in nodes_args if n.get("type") == "slack_write_message"
    ]
    slack_channel = (
        slack_nodes_in_nodes[0].get("channel", "") if slack_nodes_in_nodes else ""
    )

    with EvalChecklist("creates router workflow") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check("called create_workflows", len(call_args_list) >= 1)
        checks.check(
            "trigger is rows_created",
            trigger_args.get("type") == "rows_created",
            hint=f"got {trigger_args.get('type')}",
        )
        checks.check(
            "trigger table is Tickets",
            trigger_table_id == table.id,
            hint=f"got table_id={trigger_table_id}, expected={table.id}",
        )
        checks.check(
            "router node in args",
            len(router_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        )
        checks.check(
            "router has >=2 edges in args",
            len(router_edges_args) >= 2,
            hint=f"got {len(router_edges_args)}",
        )
        checks.check(
            "router node in DB",
            len(db_router_actions) >= 1,
        )
        checks.check(
            "router has >=2 edges in DB",
            db_edges_count >= 2,
            hint=f"got {db_edges_count}",
        )
        checks.check(
            "Slack node exists for High branch",
            len(slack_nodes_in_nodes) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        )
        checks.check(
            "Slack channel is #urgent",
            "urgent" in slack_channel.lower(),
            hint=f"got channel: '{slack_channel}'",
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
    err_count, err_hint = count_tool_errors(result)

    call_args_list = _get_create_workflows_args(result)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    trigger_args = wf_args.get("trigger", {})
    nodes_args = wf_args.get("nodes", [])
    create_row_nodes_args = [n for n in nodes_args if n.get("type") == "create_row"]
    cr_values = (
        create_row_nodes_args[0].get("values", []) if create_row_nodes_args else []
    )

    db_ok = AutomationWorkflow.objects.filter(automation=automation).exists()
    if db_ok:
        workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
        db_trigger_type = trigger_node.service.get_type().type
        db_create_actions = [
            n
            for n in action_nodes
            if n.service.get_type().type == "local_baserow_upsert_row"
        ]
    else:
        db_trigger_type = None
        db_create_actions = []

    trigger_table_id = trigger_args.get("rows_triggers_settings", {}).get("table_id")
    cr_node = create_row_nodes_args[0] if create_row_nodes_args else {}
    cr_table_id = cr_node.get("table_id")
    cr_has_literal_automation = any(
        "automation" in str(v.get("value", "")).lower() for v in cr_values
    )

    with EvalChecklist("creates row with field values") as checks:
        checks.check("<=1 tool errors", err_count <= 1, hint=err_hint)
        checks.check("called create_workflows", len(call_args_list) >= 1)
        checks.check(
            "trigger is rows_created",
            trigger_args.get("type") == "rows_created",
            hint=f"got {trigger_args.get('type')}",
        )
        checks.check(
            "trigger table is Contacts (source_table)",
            trigger_table_id == source_table.id,
            hint=f"got table_id={trigger_table_id}, expected={source_table.id}",
        )
        checks.check(
            "create_row node in args",
            len(create_row_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        )
        checks.check(
            "create_row targets Log table",
            cr_table_id == log_table.id,
            hint=f"got table_id={cr_table_id}, expected={log_table.id}",
        )
        checks.check(
            "create_row has >=1 field value",
            len(cr_values) >= 1,
            hint=f"got {len(cr_values)}",
        )
        checks.check(
            "create_row has 'automation' literal value (Source field)",
            cr_has_literal_automation,
            hint=f"values: {cr_values}",
        )
        checks.check(
            "DB trigger is rows_created",
            db_trigger_type == "local_baserow_rows_created",
            hint=f"got {db_trigger_type}",
        )
        checks.check(
            "create_row action in DB",
            len(db_create_actions) >= 1,
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
    err_count, err_hint = count_tool_errors(result)

    call_args_list = _get_create_workflows_args(result)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    trigger_args = wf_args.get("trigger", {})
    nodes_args = wf_args.get("nodes", [])
    update_nodes_args = [n for n in nodes_args if n.get("type") == "update_row"]
    ur = update_nodes_args[0] if update_nodes_args else {}

    db_ok = AutomationWorkflow.objects.filter(automation=automation).exists()
    if db_ok:
        workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
        db_trigger_type = trigger_node.service.get_type().type
        db_update_actions = [
            n
            for n in action_nodes
            if n.service.get_type().type == "local_baserow_upsert_row"
        ]
    else:
        db_trigger_type = None
        db_update_actions = []

    ur_values = ur.get("values", [])
    ur_has_reviewed = any(
        "reviewed" in str(v.get("value", "")).lower() for v in ur_values
    )
    ur_has_notes = any(
        "automation" in str(v.get("value", "")).lower()
        or "review" in str(v.get("value", "")).lower()
        for v in ur_values
    )
    trigger_table_id = trigger_args.get("rows_triggers_settings", {}).get("table_id")

    with EvalChecklist("creates update-row workflow") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check("called create_workflows", len(call_args_list) >= 1)
        checks.check(
            "trigger is rows_updated",
            trigger_args.get("type") == "rows_updated",
            hint=f"got {trigger_args.get('type')}",
        )
        checks.check(
            "trigger table is Tasks",
            trigger_table_id == table.id,
            hint=f"got table_id={trigger_table_id}, expected={table.id}",
        )
        checks.check(
            "update_row node in args",
            len(update_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        )
        checks.check(
            "update_row has >=1 field value",
            len(ur_values) >= 1,
        )
        checks.check(
            "update_row has row_id",
            bool(ur.get("row_id")),
        )
        checks.check(
            "update_row sets Status to 'Reviewed'",
            ur_has_reviewed,
            hint=f"values: {ur_values}",
        )
        checks.check(
            "update_row sets Notes (automation/reviewed text)",
            ur_has_notes,
            hint=f"values: {ur_values}",
        )
        checks.check(
            "DB trigger is rows_updated",
            db_trigger_type == "local_baserow_rows_updated",
            hint=f"got {db_trigger_type}",
        )
        checks.check(
            "update_row action in DB",
            len(db_update_actions) >= 1,
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
    err_count, err_hint = count_tool_errors(result)

    call_args_list = _get_create_workflows_args(result)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    trigger_args = wf_args.get("trigger", {})
    trigger_table_id = trigger_args.get("rows_triggers_settings", {}).get("table_id")
    nodes_args = wf_args.get("nodes", [])
    email_nodes_args = [n for n in nodes_args if n.get("type") == "smtp_email"]
    email_node = email_nodes_args[0] if email_nodes_args else {}
    email_to = email_node.get("to_emails", "")
    email_subject = email_node.get("subject", "")
    email_body = email_node.get("body", "")

    db_ok = AutomationWorkflow.objects.filter(automation=automation).exists()
    if db_ok:
        workflow, trigger_node, action_nodes = _get_workflow_nodes(automation)
        db_email_actions = [
            n for n in action_nodes if n.service.get_type().type == "smtp_email"
        ]
    else:
        db_email_actions = []

    with EvalChecklist("creates email notification workflow") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check("called create_workflows", len(call_args_list) >= 1)
        checks.check(
            "trigger is rows_created",
            trigger_args.get("type") == "rows_created",
            hint=f"got {trigger_args.get('type')}",
        )
        checks.check(
            "trigger table is Orders",
            trigger_table_id == table.id,
            hint=f"got table_id={trigger_table_id}, expected={table.id}",
        )
        checks.check(
            "smtp_email node in args",
            len(email_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        )
        checks.check(
            "email to admin@example.com",
            "admin@example.com" in email_to,
            hint=f"got to: '{email_to}'",
        )
        checks.check(
            "email subject mentions 'Order'",
            "order" in email_subject.lower(),
            hint=f"got subject: '{email_subject}'",
        )
        checks.check(
            "email body mentions order being placed",
            "order" in email_body.lower() or "placed" in email_body.lower(),
            hint=f"got body: '{email_body}'",
        )
        checks.check("workflow created in DB", db_ok)
        checks.check(
            "smtp_email action in DB",
            len(db_email_actions) >= 1,
        )
