"""Kuma-automation eval dataset: Automation workflow creation.

All 7 cases run in ``AgentMode.DATABASE`` — the legacy tests never set
``deps.mode`` before running automation prompts, so the agent operated in
DATABASE mode even while doing automation work. That is preserved here
unchanged rather than "fixed", since fixing it would change agent behaviour
and invalidate any existing baseline.
"""

from __future__ import annotations

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.harness import tool_called
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.scenarios import build_database_ui_context
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)

# Names the automation instead of a live DB id, since prompts are fixed before creation.
PROMPT_LISTS_WORKFLOWS = "List the workflows in automation '{automation_name}'."

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

# ---------------------------------------------------------------------------
# Local helpers — args inspection over output.messages (assistant-side entries)
# ---------------------------------------------------------------------------


def _get_create_workflows_args(output: EvalRunOutput) -> list[dict]:
    """Return the parsed ``args`` dicts of every ``create_workflows`` call."""

    return [
        e["args"]
        for e in output.messages
        if e["role"] == "assistant"
        and e.get("tool_name") == "create_workflows"
        and "args" in e
    ]


def _get_workflow_nodes(
    automation: Automation,
) -> tuple[AutomationWorkflow | None, AutomationNode | None, list[AutomationNode]]:
    """Return (workflow, trigger, action_nodes) for the first workflow, or Nones."""

    workflow = AutomationWorkflow.objects.filter(automation=automation).first()
    if workflow is None:
        return None, None, []
    trigger = workflow.get_trigger()
    action_nodes = list(
        workflow.automation_workflow_nodes.exclude(id=trigger.id).order_by("id")
    )
    return workflow, trigger, action_nodes


# ---------------------------------------------------------------------------
# Lists workflows
# ---------------------------------------------------------------------------


@register_scenario("automation-lists-workflows")
def _lists_workflows_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    automation = fx.create_automation_application(
        workspace=workspace, name="My Automation"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"automation": automation},
    )


def _check_lists_workflows(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    return [
        CheckResult(
            "called list_workflows", tool_called(output, "list_workflows") >= 1
        ),
    ]


register_case(
    EvalCase(
        id="automation/lists-workflows",
        dataset="kuma-automation",
        prompt=PROMPT_LISTS_WORKFLOWS.format(automation_name="My Automation"),
        scenario="automation-lists-workflows",
        checks=_check_lists_workflows,
        max_iters=10,
    )
)

# ---------------------------------------------------------------------------
# Creates workflow (rows_created trigger + update_row action)
# ---------------------------------------------------------------------------


@register_scenario("automation-creates-workflow")
def _creates_workflow_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    table = fx.create_database_table(database=database, name="Orders")
    fx.create_text_field(table=table, name="Order ID", primary=True)
    fx.create_text_field(table=table, name="Status")
    automation = fx.create_automation_application(
        workspace=workspace, name="Order Processing"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"automation": automation, "table": table},
    )


def _check_creates_workflow(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    automation = scenario.refs["automation"]
    table = scenario.refs["table"]

    workflows = AutomationWorkflow.objects.filter(automation=automation)

    call_args_list = _get_create_workflows_args(output)
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
        _, trigger_node, action_nodes = _get_workflow_nodes(automation)
        db_trigger_type = trigger_node.service.get_type().type
        db_update_actions = [
            n
            for n in action_nodes
            if n.service.get_type().type == "local_baserow_upsert_row"
        ]
    else:
        db_trigger_type = None
        db_update_actions = []

    return [
        CheckResult(
            "called create_workflows", tool_called(output, "create_workflows") >= 1
        ),
        CheckResult("workflow created in DB", db_ok),
        CheckResult(
            "trigger is rows_created",
            trigger_args.get("type") == "rows_created",
            hint=f"got {trigger_args.get('type')}",
        ),
        CheckResult(
            "trigger table is Orders",
            trigger_table_id == table.id,
            hint=f"got table_id={trigger_table_id}, expected={table.id}",
        ),
        CheckResult(
            "update_row node in args",
            len(update_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        ),
        CheckResult(
            "update_row sets field to 'Processing'",
            ur_has_processing,
            hint=f"values: {ur_values}",
        ),
        CheckResult(
            "DB trigger is rows_created",
            db_trigger_type == "local_baserow_rows_created",
            hint=f"got {db_trigger_type}",
        ),
        CheckResult("update_row action in DB", len(db_update_actions) >= 1),
    ]


register_case(
    EvalCase(
        id="automation/creates-workflow",
        dataset="kuma-automation",
        prompt=PROMPT_CREATES_WORKFLOW.format(
            automation_name="Order Processing", table_name="Orders"
        ),
        scenario="automation-creates-workflow",
        checks=_check_creates_workflow,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Weekly Slack reminder (periodic trigger + slack_write_message action)
# ---------------------------------------------------------------------------


@register_scenario("automation-creates-weekly-slack-reminder")
def _creates_weekly_slack_reminder_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    automation = fx.create_automation_application(
        workspace=workspace, name="Team Reminders"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"automation": automation},
    )


def _check_creates_weekly_slack_reminder(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    automation = scenario.refs["automation"]

    call_args_list = _get_create_workflows_args(output)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    trigger_args = wf_args.get("trigger", {})
    interval_args = trigger_args.get("periodic_interval", {})
    nodes_args = wf_args.get("nodes", [])
    slack_nodes_args = [n for n in nodes_args if n.get("type") == "slack_write_message"]

    db_ok = AutomationWorkflow.objects.filter(automation=automation).exists()
    if db_ok:
        # Deliberately trigger_node.get_type() here (not .service.get_type()),
        # unlike every other case in this dataset — ported as-is from the legacy test.
        _, trigger_node, action_nodes = _get_workflow_nodes(automation)
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

    return [
        CheckResult("called create_workflows", len(call_args_list) >= 1),
        CheckResult(
            "trigger type is periodic",
            trigger_args.get("type") == "periodic",
            hint=f"got {trigger_args.get('type')}",
        ),
        CheckResult(
            "interval is WEEK",
            interval_args.get("interval") == "WEEK",
            hint=f"got {interval_args.get('interval')}",
        ),
        CheckResult(
            "day_of_week is 1 (Tuesday)",
            interval_args.get("day_of_week") == 1,
            hint=f"got {interval_args.get('day_of_week')}",
        ),
        CheckResult(
            "slack_write_message node in args",
            len(slack_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        ),
        CheckResult(
            "workflow created in DB with periodic trigger",
            db_trigger_type == "periodic",
            hint=f"got {db_trigger_type}",
        ),
        CheckResult("Slack action exists in DB", len(db_slack_actions) >= 1),
        CheckResult(
            "Slack channel is #general",
            "general" in slack_channel.lower(),
            hint=f"got channel: '{slack_channel}'",
        ),
        CheckResult(
            "Slack message mentions demo",
            "demo" in slack_text.lower(),
            hint=f"got text: '{slack_text}'",
        ),
    ]


register_case(
    EvalCase(
        id="automation/creates-weekly-slack-reminder",
        dataset="kuma-automation",
        prompt=PROMPT_CREATES_WEEKLY_SLACK_REMINDER.format(
            automation_name="Team Reminders"
        ),
        scenario="automation-creates-weekly-slack-reminder",
        checks=_check_creates_weekly_slack_reminder,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Router workflow (branching + slack_write_message action)
# ---------------------------------------------------------------------------


@register_scenario("automation-creates-router-workflow")
def _creates_router_workflow_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    table = fx.create_database_table(database=database, name="Tickets")
    fx.create_text_field(table=table, name="Title", primary=True)
    priority_field = fx.create_single_select_field(table=table, name="Priority")
    fx.create_select_option(field=priority_field, value="High", order=0)
    fx.create_select_option(field=priority_field, value="Low", order=1)
    automation = fx.create_automation_application(
        workspace=workspace, name="Ticket Router"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"automation": automation, "table": table},
    )


def _check_creates_router_workflow(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    automation = scenario.refs["automation"]
    table = scenario.refs["table"]

    call_args_list = _get_create_workflows_args(output)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    nodes_args = wf_args.get("nodes", [])
    router_nodes_args = [n for n in nodes_args if n.get("type") == "router"]
    router_edges_args = (
        router_nodes_args[0].get("edges", []) if router_nodes_args else []
    )

    db_ok = AutomationWorkflow.objects.filter(automation=automation).exists()
    if db_ok:
        _, trigger_node, action_nodes = _get_workflow_nodes(automation)
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

    return [
        CheckResult("called create_workflows", len(call_args_list) >= 1),
        CheckResult(
            "trigger is rows_created",
            trigger_args.get("type") == "rows_created",
            hint=f"got {trigger_args.get('type')}",
        ),
        CheckResult(
            "trigger table is Tickets",
            trigger_table_id == table.id,
            hint=f"got table_id={trigger_table_id}, expected={table.id}",
        ),
        CheckResult(
            "router node in args",
            len(router_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        ),
        CheckResult(
            "router has >=2 edges in args",
            len(router_edges_args) >= 2,
            hint=f"got {len(router_edges_args)}",
        ),
        CheckResult("router node in DB", len(db_router_actions) >= 1),
        CheckResult(
            "router has >=2 edges in DB",
            db_edges_count >= 2,
            hint=f"got {db_edges_count}",
        ),
        CheckResult(
            "Slack node exists for High branch",
            len(slack_nodes_in_nodes) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        ),
        CheckResult(
            "Slack channel is #urgent",
            "urgent" in slack_channel.lower(),
            hint=f"got channel: '{slack_channel}'",
        ),
    ]


register_case(
    EvalCase(
        id="automation/creates-router-workflow",
        dataset="kuma-automation",
        prompt=PROMPT_CREATES_ROUTER_WORKFLOW.format(
            automation_name="Ticket Router", table_name="Tickets"
        ),
        scenario="automation-creates-router-workflow",
        checks=_check_creates_router_workflow,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Create-row workflow with mapped field values
# ---------------------------------------------------------------------------


@register_scenario("automation-creates-row-with-field-values")
def _creates_row_with_field_values_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    source_table = fx.create_database_table(database=database, name="Contacts")
    fx.create_text_field(table=source_table, name="Name", primary=True)
    fx.create_email_field(table=source_table, name="Email")
    log_table = fx.create_database_table(database=database, name="Log")
    fx.create_text_field(table=log_table, name="Entry", primary=True)
    fx.create_text_field(table=log_table, name="Source")
    automation = fx.create_automation_application(
        workspace=workspace, name="Contact Logger"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, source_table),
        refs={
            "automation": automation,
            "source_table": source_table,
            "log_table": log_table,
        },
    )


def _check_creates_row_with_field_values(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    automation = scenario.refs["automation"]
    source_table = scenario.refs["source_table"]
    log_table = scenario.refs["log_table"]

    call_args_list = _get_create_workflows_args(output)
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
        _, trigger_node, action_nodes = _get_workflow_nodes(automation)
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

    return [
        CheckResult("called create_workflows", len(call_args_list) >= 1),
        CheckResult(
            "trigger is rows_created",
            trigger_args.get("type") == "rows_created",
            hint=f"got {trigger_args.get('type')}",
        ),
        CheckResult(
            "trigger table is Contacts (source_table)",
            trigger_table_id == source_table.id,
            hint=f"got table_id={trigger_table_id}, expected={source_table.id}",
        ),
        CheckResult(
            "create_row node in args",
            len(create_row_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        ),
        CheckResult(
            "create_row targets Log table",
            cr_table_id == log_table.id,
            hint=f"got table_id={cr_table_id}, expected={log_table.id}",
        ),
        CheckResult(
            "create_row has >=1 field value",
            len(cr_values) >= 1,
            hint=f"got {len(cr_values)}",
        ),
        CheckResult(
            "create_row has 'automation' literal value (Source field)",
            cr_has_literal_automation,
            hint=f"values: {cr_values}",
        ),
        CheckResult(
            "DB trigger is rows_created",
            db_trigger_type == "local_baserow_rows_created",
            hint=f"got {db_trigger_type}",
        ),
        CheckResult("create_row action in DB", len(db_create_actions) >= 1),
    ]


register_case(
    EvalCase(
        id="automation/creates-row-with-field-values",
        dataset="kuma-automation",
        prompt=PROMPT_CREATES_ROW_WITH_FIELD_VALUES.format(
            automation_name="Contact Logger",
            source_table_name="Contacts",
            log_table_name="Log",
        ),
        scenario="automation-creates-row-with-field-values",
        checks=_check_creates_row_with_field_values,
        max_iters=20,
        max_tool_errors=1,
    )
)

# ---------------------------------------------------------------------------
# Update-row workflow (rows_updated trigger, references trigger row)
# ---------------------------------------------------------------------------


@register_scenario("automation-creates-update-row-workflow")
def _creates_update_row_workflow_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    table = fx.create_database_table(database=database, name="Tasks")
    fx.create_text_field(table=table, name="Task", primary=True)
    fx.create_text_field(table=table, name="Status")
    fx.create_long_text_field(table=table, name="Notes")
    automation = fx.create_automation_application(
        workspace=workspace, name="Task Processor"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"automation": automation, "table": table},
    )


def _check_creates_update_row_workflow(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    automation = scenario.refs["automation"]
    table = scenario.refs["table"]

    call_args_list = _get_create_workflows_args(output)
    args = call_args_list[0] if call_args_list else {}
    wf_args = args.get("workflows", [{}])[0] if args.get("workflows") else {}
    trigger_args = wf_args.get("trigger", {})
    nodes_args = wf_args.get("nodes", [])
    update_nodes_args = [n for n in nodes_args if n.get("type") == "update_row"]
    ur = update_nodes_args[0] if update_nodes_args else {}

    db_ok = AutomationWorkflow.objects.filter(automation=automation).exists()
    if db_ok:
        _, trigger_node, action_nodes = _get_workflow_nodes(automation)
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

    return [
        CheckResult("called create_workflows", len(call_args_list) >= 1),
        CheckResult(
            "trigger is rows_updated",
            trigger_args.get("type") == "rows_updated",
            hint=f"got {trigger_args.get('type')}",
        ),
        CheckResult(
            "trigger table is Tasks",
            trigger_table_id == table.id,
            hint=f"got table_id={trigger_table_id}, expected={table.id}",
        ),
        CheckResult(
            "update_row node in args",
            len(update_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        ),
        CheckResult("update_row has >=1 field value", len(ur_values) >= 1),
        CheckResult("update_row has row_id", bool(ur.get("row_id"))),
        CheckResult(
            "update_row sets Status to 'Reviewed'",
            ur_has_reviewed,
            hint=f"values: {ur_values}",
        ),
        CheckResult(
            "update_row sets Notes (automation/reviewed text)",
            ur_has_notes,
            hint=f"values: {ur_values}",
        ),
        CheckResult(
            "DB trigger is rows_updated",
            db_trigger_type == "local_baserow_rows_updated",
            hint=f"got {db_trigger_type}",
        ),
        CheckResult("update_row action in DB", len(db_update_actions) >= 1),
    ]


register_case(
    EvalCase(
        id="automation/creates-update-row-workflow",
        dataset="kuma-automation",
        prompt=PROMPT_CREATES_UPDATE_ROW_WORKFLOW.format(
            automation_name="Task Processor", table_name="Tasks"
        ),
        scenario="automation-creates-update-row-workflow",
        checks=_check_creates_update_row_workflow,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Email notification workflow (smtp_email action)
# ---------------------------------------------------------------------------


@register_scenario("automation-creates-email-notification-workflow")
def _creates_email_notification_workflow_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    table = fx.create_database_table(database=database, name="Orders")
    fx.create_text_field(table=table, name="Order ID", primary=True)
    fx.create_text_field(table=table, name="Customer Email")
    automation = fx.create_automation_application(
        workspace=workspace, name="Order Notifications"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"automation": automation, "table": table},
    )


def _check_creates_email_notification_workflow(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    automation = scenario.refs["automation"]
    table = scenario.refs["table"]

    call_args_list = _get_create_workflows_args(output)
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
        _, trigger_node, action_nodes = _get_workflow_nodes(automation)
        db_email_actions = [
            n for n in action_nodes if n.service.get_type().type == "smtp_email"
        ]
    else:
        db_email_actions = []

    return [
        CheckResult("called create_workflows", len(call_args_list) >= 1),
        CheckResult(
            "trigger is rows_created",
            trigger_args.get("type") == "rows_created",
            hint=f"got {trigger_args.get('type')}",
        ),
        CheckResult(
            "trigger table is Orders",
            trigger_table_id == table.id,
            hint=f"got table_id={trigger_table_id}, expected={table.id}",
        ),
        CheckResult(
            "smtp_email node in args",
            len(email_nodes_args) >= 1,
            hint=f"node types: {[n.get('type') for n in nodes_args]}",
        ),
        CheckResult(
            "email to admin@example.com",
            "admin@example.com" in email_to,
            hint=f"got to: '{email_to}'",
        ),
        CheckResult(
            "email subject mentions 'Order'",
            "order" in email_subject.lower(),
            hint=f"got subject: '{email_subject}'",
        ),
        CheckResult(
            "email body mentions order being placed",
            "order" in email_body.lower() or "placed" in email_body.lower(),
            hint=f"got body: '{email_body}'",
        ),
        CheckResult("workflow created in DB", db_ok),
        CheckResult("smtp_email action in DB", len(db_email_actions) >= 1),
    ]


register_case(
    EvalCase(
        id="automation/creates-email-notification-workflow",
        dataset="kuma-automation",
        prompt=PROMPT_CREATES_EMAIL_NOTIFICATION_WORKFLOW.format(
            automation_name="Order Notifications", table_name="Orders"
        ),
        scenario="automation-creates-email-notification-workflow",
        checks=_check_creates_email_notification_workflow,
        max_iters=20,
    )
)
