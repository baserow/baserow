"""Kuma-automation eval dataset: creating workflows and changing existing ones.

All cases run in ``AgentMode.DATABASE`` — the legacy tests never set
``deps.mode`` before running automation prompts, so the agent operated in
DATABASE mode even while doing automation work. That is preserved here
unchanged rather than "fixed", since fixing it would change agent behaviour
and invalidate any existing baseline.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.cache import local_cache
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
)
from baserow.core.formula.validator import ensure_boolean
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
from baserow_enterprise.assistant.tools.automation.agents import AssistantFormulaContext

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

PROMPT_EDITS_EMAIL_SUBJECT = (
    "In automation '{automation_name}', change the subject of the email in "
    "workflow '{workflow_name}' to 'New order from ' followed by the order's "
    "Customer name."
)

PROMPT_ADDS_SLACK_TO_ROUTER_BRANCH = (
    "In automation '{automation_name}', workflow '{workflow_name}': add a step on "
    "the router's High branch that sends a Slack message to #urgent saying "
    "'High priority ticket'."
)

PROMPT_CHANGES_ROUTER_CONDITION = (
    "In automation '{automation_name}', workflow '{workflow_name}': change the "
    "router's High branch so it also matches tickets whose Priority is 'Urgent'."
)

PROMPT_DELETES_NODE = (
    "In automation '{automation_name}', remove the Slack step from workflow "
    "'{workflow_name}'. Keep the email."
)

# ---------------------------------------------------------------------------
# Local helpers — inspect saved configuration, including repaired tool calls.
# ---------------------------------------------------------------------------


def _check_saved_workflows(
    automation: Automation,
    output: EvalRunOutput,
    check: Callable[[AutomationNode | None, list[AutomationNode]], list[CheckResult]],
) -> list[CheckResult]:
    """Score one whole workflow, allowing an earlier incomplete draft to remain."""

    candidates = []
    # Read graph relationships fresh after the agent's mutations.
    with local_cache.context():
        for workflow in AutomationWorkflow.objects.filter(automation=automation):
            trigger = workflow.get_trigger()
            actions = list(
                workflow.automation_workflow_nodes.exclude(
                    id=trigger.id if trigger else None
                )
            )
            candidates.append(check(trigger, actions))
    # Keep useful partial-failure details, but never combine checks from different
    # workflows into a passing result.
    best = (
        max(candidates, key=lambda checks: sum(c.passed for c in checks))
        if candidates
        else check(None, [])
    )
    return [
        CheckResult(
            "called create_workflows", bool(tool_called(output, "create_workflows"))
        ),
        CheckResult("workflow created in DB", bool(candidates)),
        *best,
    ]


_UNRESOLVED = object()


def _resolve_saved_formula(formula, trigger=None, row=None):
    context = AssistantFormulaContext()
    if trigger is not None and row is not None:
        context.add_node_context(trigger.id, [row])
    try:
        return resolve_formula(formula, formula_runtime_function_registry, context)
    except Exception:
        return _UNRESOLVED


def _row_values_match(service, trigger, samples, *, update: bool) -> bool:
    """Check row identity and named mappings against two different trigger rows."""

    if trigger is None:
        return False
    mappings = {
        mapping.field_id: mapping.value
        for mapping in service.field_mappings.filter(enabled=True)
    }
    for row, expected in samples:
        row_id = _resolve_saved_formula(service.row_id, trigger, row)
        if row_id not in ((row["id"], str(row["id"])) if update else (None, "")):
            return False
        if any(
            field_id not in mappings
            or _resolve_saved_formula(mappings[field_id], trigger, row) != value
            for field_id, value in expected.items()
        ):
            return False
    return True


def _check_updates_trigger_row(scenario, output, trigger_type, values):
    table = scenario.refs["table"]
    expected = {
        table.field_set.get(name=name).id: value for name, value in values.items()
    }
    samples = [({"id": row_id}, expected) for row_id in (101, 202)]

    def check(trigger, actions):
        service = trigger.service.specific if trigger else None
        updates = [
            node.service.specific
            for node in actions
            if node.get_type().type == "local_baserow_update_row"
        ]
        targets = [service for service in updates if service.table_id == table.id]
        return [
            CheckResult(
                f"DB trigger is {trigger_type}",
                service is not None
                and service.get_type().type == f"local_baserow_{trigger_type}",
            ),
            CheckResult(
                f"trigger table is {table.name}",
                service is not None and getattr(service, "table_id", None) == table.id,
            ),
            CheckResult("update_row action in DB", bool(updates)),
            CheckResult(f"update_row targets {table.name} table", bool(targets)),
            CheckResult(
                "saved update targets the trigger row with the requested field values",
                any(
                    _row_values_match(service, trigger, samples, update=True)
                    for service in targets
                ),
                hint=f"expected field values: {values}",
            ),
        ]

    return _check_saved_workflows(scenario.refs["automation"], output, check)


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
    return _check_updates_trigger_row(
        scenario, output, "rows_created", {"Status": "Processing"}
    )


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
    def check(trigger, actions):
        periodic = (
            trigger.service.specific
            if trigger and trigger.get_type().type == "periodic"
            else None
        )
        slack = [
            node.service.specific
            for node in actions
            if node.service.get_type().type == "slack_write_message"
        ]
        targets = [
            service for service in slack if service.channel.lstrip("#") == "general"
        ]
        checks = [
            CheckResult("workflow created with periodic trigger", periodic is not None),
            CheckResult("Slack action exists in DB", bool(slack)),
            CheckResult("Slack channel is #general", bool(targets)),
            CheckResult(
                "Slack action sends the exact requested message to #general",
                any(
                    _resolve_saved_formula(service.text)
                    == "Is there anything to demo this week?"
                    for service in targets
                ),
            ),
        ]
        for name, expected in (
            ("interval", "WEEK"),
            ("day_of_week", 1),
            ("hour", 9),
            ("minute", 0),
            ("timezone", "UTC"),
        ):
            actual = getattr(periodic, name, None)
            checks.append(
                CheckResult(
                    f"saved {name} is {expected}",
                    actual == expected,
                    hint=f"got {actual}",
                )
            )
        return checks

    return _check_saved_workflows(scenario.refs["automation"], output, check)


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
    table = scenario.refs["table"]
    priority = table.field_set.get(name="Priority")
    options = {
        option.value: {"id": option.id, "value": option.value, "color": option.color}
        for option in priority.select_options.all()
    }

    def branches_match(router, trigger):
        if trigger is None:
            return False
        edges = list(router.service.specific.edges.all())
        selected = {}
        for value in ("High", "Low"):
            row = {priority.db_column: options[value]}
            # Runtime resolves every condition before choosing the first match.
            resolved = [
                _resolve_saved_formula(edge.condition, trigger, row) for edge in edges
            ]
            if any(result is _UNRESOLVED for result in resolved):
                return False
            selected[value] = next(
                (
                    str(edge.uid)
                    for edge, result in zip(edges, resolved)
                    if ensure_boolean(result, False)
                ),
                "",
            )
        if selected["High"] == selected["Low"]:
            return False
        high_nodes = router.get_next_points(selected["High"])
        low_nodes = router.get_next_points(selected["Low"])
        return not low_nodes and any(
            node.service.get_type().type == "slack_write_message"
            and node.service.specific.channel.lstrip("#") == "urgent"
            and _resolve_saved_formula(node.service.specific.text)
            == "High priority ticket created"
            for node in high_nodes
        )

    def check(trigger, actions):
        service = trigger.service.specific if trigger else None
        routers = [node for node in actions if node.service.get_type().type == "router"]
        return [
            CheckResult(
                "trigger is rows_created",
                service is not None
                and service.get_type().type == "local_baserow_rows_created",
            ),
            CheckResult(
                "trigger table is Tickets",
                service is not None and getattr(service, "table_id", None) == table.id,
            ),
            CheckResult("router node in DB", bool(routers)),
            CheckResult(
                "saved High branch sends the requested Slack message; Low does nothing",
                any(branches_match(router, trigger) for router in routers),
            ),
        ]

    return _check_saved_workflows(scenario.refs["automation"], output, check)


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
    source_table = scenario.refs["source_table"]
    log_table = scenario.refs["log_table"]
    name_field = source_table.field_set.get(name="Name")
    entry_field = log_table.field_set.get(name="Entry")
    source_field = log_table.field_set.get(name="Source")
    samples = [
        (
            {"id": row_id, name_field.db_column: name},
            {entry_field.id: name, source_field.id: "automation"},
        )
        for row_id, name in ((101, "Ada Lovelace"), (202, "Grace Hopper"))
    ]

    def check(trigger, actions):
        service = trigger.service.specific if trigger else None
        creates = [
            node.service.specific
            for node in actions
            if node.get_type().type == "local_baserow_create_row"
        ]
        targets = [service for service in creates if service.table_id == log_table.id]
        return [
            CheckResult(
                "DB trigger is rows_created",
                service is not None
                and service.get_type().type == "local_baserow_rows_created",
            ),
            CheckResult(
                "DB trigger table is Contacts",
                service is not None
                and getattr(service, "table_id", None) == source_table.id,
            ),
            CheckResult("create_row action in DB", bool(creates)),
            CheckResult("create_row targets Log table", bool(targets)),
            CheckResult(
                "saved Entry follows trigger Name and Source is automation",
                any(
                    _row_values_match(service, trigger, samples, update=False)
                    for service in targets
                ),
            ),
        ]

    return _check_saved_workflows(scenario.refs["automation"], output, check)


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
    return _check_updates_trigger_row(
        scenario,
        output,
        "rows_updated",
        {"Status": "Reviewed", "Notes": "Automatically reviewed by automation"},
    )


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
    table = scenario.refs["table"]

    def check(trigger, actions):
        service = trigger.service.specific if trigger else None
        emails = [
            node.service.specific
            for node in actions
            if node.service.get_type().type == "smtp_email"
        ]
        return [
            CheckResult(
                "trigger is rows_created",
                service is not None
                and service.get_type().type == "local_baserow_rows_created",
            ),
            CheckResult(
                "trigger table is Orders",
                service is not None and getattr(service, "table_id", None) == table.id,
            ),
            CheckResult("smtp_email action in DB", bool(emails)),
            CheckResult(
                "saved email has the requested recipient, subject and body",
                any(
                    _resolve_saved_formula(email.to_emails) == "admin@example.com"
                    and _resolve_saved_formula(email.subject) == "New Order"
                    and _resolve_saved_formula(email.body)
                    == "A new order has been placed"
                    for email in emails
                ),
            ),
        ]

    return _check_saved_workflows(scenario.refs["automation"], output, check)


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

# ---------------------------------------------------------------------------
# Changing existing workflows. Each scenario builds the workflow the prompt
# names through the node service, the way the editor does.
# ---------------------------------------------------------------------------


def _create_node(user, workflow, node_type: str, **kwargs) -> AutomationNode:
    return AutomationNodeService().create_node(
        user, automation_node_type_registry.get(node_type), workflow, **kwargs
    )


def _orders_workflow(fx: Fixtures, workflow_name: str) -> dict:
    """An Orders table and a workflow that emails the team on a new order."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    table = fx.create_database_table(database=database, name="Orders")
    fx.create_text_field(table=table, name="Order ID", primary=True)
    fx.create_text_field(table=table, name="Customer")
    automation = fx.create_automation_application(
        workspace=workspace, name="Order Notifications"
    )
    workflow = AutomationWorkflowService().create_workflow(
        user, automation.id, workflow_name
    )
    trigger = _create_node(
        user,
        workflow,
        "local_baserow_rows_created",
        label="Order created",
        service={"table_id": table.id},
    )
    email = _create_node(
        user,
        workflow,
        "smtp_email",
        label="Notify team",
        reference_node_id=trigger.id,
        service={
            "to_emails": "'team@example.com'",
            "subject": "'New order'",
            "body": "'A new order arrived'",
        },
    )
    return {
        "user": user,
        "workspace": workspace,
        "database": database,
        "table": table,
        "automation": automation,
        "workflow": workflow,
        "trigger": trigger,
        "email": email,
    }


def _tickets_workflow(fx: Fixtures, workflow_name: str, with_slack: bool) -> dict:
    """A Tickets table and a workflow whose router splits on Priority."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    table = fx.create_database_table(database=database, name="Tickets")
    fx.create_text_field(table=table, name="Title", primary=True)
    priority = fx.create_single_select_field(table=table, name="Priority")
    for order, value in enumerate(("High", "Low", "Urgent")):
        fx.create_select_option(field=priority, value=value, order=order)
    automation = fx.create_automation_application(
        workspace=workspace, name="Ticket Router"
    )
    workflow = AutomationWorkflowService().create_workflow(
        user, automation.id, workflow_name
    )
    trigger = _create_node(
        user,
        workflow,
        "local_baserow_rows_created",
        label="Ticket created",
        service={"table_id": table.id},
    )
    path = f"previous_node.{trigger.id}.0.{priority.db_column}.value"
    edges = [
        {
            "uid": str(uuid4()),
            "label": value,
            "condition": BaserowFormulaObject.create(
                f"equal(get('{path}'), '{value}')", BASEROW_FORMULA_MODE_ADVANCED
            ),
        }
        for value in ("High", "Low")
    ]
    router = _create_node(
        user,
        workflow,
        "router",
        label="Route by priority",
        reference_node_id=trigger.id,
        service={"edges": edges},
    )
    slack = None
    if with_slack:
        slack = _create_node(
            user,
            workflow,
            "slack_write_message",
            label="Alert on-call",
            reference_node_id=router.id,
            output=edges[0]["uid"],
            service={"channel": "urgent", "text": "'High priority ticket'"},
        )
    return {
        "user": user,
        "workspace": workspace,
        "database": database,
        "table": table,
        "automation": automation,
        "workflow": workflow,
        "trigger": trigger,
        "router": router,
        "slack": slack,
        "priority": priority,
    }


def _scenario(refs: dict) -> EvalScenario:
    return EvalScenario(
        user=refs["user"],
        workspace=refs["workspace"],
        ui_context=build_database_ui_context(
            refs["user"], refs["workspace"], refs["database"], refs["table"]
        ),
        refs=refs,
    )


def _select_row(priority, value: str) -> dict:
    option = priority.select_options.get(value=value)
    return {
        "id": 1,
        priority.db_column: {
            "id": option.id,
            "value": option.value,
            "color": option.color,
        },
    }


def _branch_taken(router, trigger, row) -> str | None:
    """The uid of the branch the router takes for a trigger row, as at runtime."""

    edges = list(router.service.specific.edges.all())
    resolved = [_resolve_saved_formula(edge.condition, trigger, row) for edge in edges]
    if any(result is _UNRESOLVED for result in resolved):
        return None
    return next(
        (
            str(edge.uid)
            for edge, result in zip(edges, resolved)
            if ensure_boolean(result, False)
        ),
        "",
    )


def _follows(node, previous) -> bool:
    """Whether the saved workflow runs ``node`` right after ``previous``."""

    with local_cache.context():
        previous = AutomationNode.objects.filter(id=previous.id).first()
        return previous is not None and any(
            point.id == node.id for point in previous.get_next_points()
        )


# ---------------------------------------------------------------------------
# Edits an email subject (list_nodes + update_nodes, formula from the trigger)
# ---------------------------------------------------------------------------


@register_scenario("automation-edits-email-subject")
def _edits_email_subject_scenario(fx: Fixtures) -> EvalScenario:
    return _scenario(_orders_workflow(fx, "New order"))


def _check_edits_email_subject(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    refs = scenario.refs
    customer = refs["table"].field_set.get(name="Customer")
    email = AutomationNode.objects.filter(id=refs["email"].id).first()
    service = email.service.specific if email else None
    subjects = [
        _resolve_saved_formula(
            service.subject, refs["trigger"], {"id": 1, customer.db_column: name}
        )
        if service
        else None
        for name in ("Ada Lovelace", "Grace Hopper")
    ]
    return [
        CheckResult("called update_nodes", bool(tool_called(output, "update_nodes"))),
        CheckResult("the email node is kept", service is not None),
        CheckResult(
            "the email still runs after the trigger",
            _follows(refs["email"], refs["trigger"]),
        ),
        CheckResult(
            "saved subject follows the trigger's Customer",
            subjects == ["New order from Ada Lovelace", "New order from Grace Hopper"],
            hint=f"resolved subjects: {subjects}",
        ),
        CheckResult(
            "recipient and body are unchanged",
            service is not None
            and _resolve_saved_formula(service.to_emails) == "team@example.com"
            and _resolve_saved_formula(service.body) == "A new order arrived",
        ),
    ]


register_case(
    EvalCase(
        id="automation/edits-email-subject",
        dataset="kuma-automation",
        prompt=PROMPT_EDITS_EMAIL_SUBJECT.format(
            automation_name="Order Notifications", workflow_name="New order"
        ),
        scenario="automation-edits-email-subject",
        checks=_check_edits_email_subject,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Adds a Slack step on a router branch (add_nodes with router_edge_label)
# ---------------------------------------------------------------------------


@register_scenario("automation-adds-slack-to-router-branch")
def _adds_slack_to_router_branch_scenario(fx: Fixtures) -> EvalScenario:
    return _scenario(_tickets_workflow(fx, "Ticket triage", with_slack=False))


def _check_adds_slack_to_router_branch(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    refs = scenario.refs
    with local_cache.context():
        router = AutomationNode.objects.filter(id=refs["router"].id).first()
        edges = (
            {edge.label: str(edge.uid) for edge in router.service.specific.edges.all()}
            if router
            else {}
        )
        high = router.get_next_points(edges["High"]) if "High" in edges else []
        low = router.get_next_points(edges["Low"]) if "Low" in edges else []
    return [
        CheckResult("called add_nodes", bool(tool_called(output, "add_nodes"))),
        CheckResult(
            "the router keeps its branches",
            router is not None and set(edges) == {"High", "Low"},
        ),
        CheckResult(
            "saved High branch sends the requested Slack message",
            any(
                node.service.get_type().type == "slack_write_message"
                and node.service.specific.channel.lstrip("#") == "urgent"
                and _resolve_saved_formula(node.service.specific.text)
                == "High priority ticket"
                for node in high
            ),
        ),
        CheckResult("Low branch still does nothing", not low),
        CheckResult(
            "no second workflow",
            AutomationWorkflow.objects.filter(automation=refs["automation"]).count()
            == 1,
        ),
    ]


register_case(
    EvalCase(
        id="automation/adds-slack-to-router-branch",
        dataset="kuma-automation",
        prompt=PROMPT_ADDS_SLACK_TO_ROUTER_BRANCH.format(
            automation_name="Ticket Router", workflow_name="Ticket triage"
        ),
        scenario="automation-adds-slack-to-router-branch",
        checks=_check_adds_slack_to_router_branch,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Changes a router condition (update_nodes edges)
# ---------------------------------------------------------------------------


@register_scenario("automation-changes-router-condition")
def _changes_router_condition_scenario(fx: Fixtures) -> EvalScenario:
    return _scenario(_tickets_workflow(fx, "Ticket triage", with_slack=True))


def _check_changes_router_condition(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    refs = scenario.refs
    priority = refs["priority"]
    with local_cache.context():
        router = AutomationNode.objects.filter(id=refs["router"].id).first()
        edges = (
            {edge.label: str(edge.uid) for edge in router.service.specific.edges.all()}
            if router
            else {}
        )
        taken = (
            {
                value: _branch_taken(
                    router, refs["trigger"], _select_row(priority, value)
                )
                for value in ("High", "Urgent", "Low")
            }
            if router
            else {}
        )
        slack = AutomationNode.objects.filter(id=refs["slack"].id).first()
        high_nodes = router.get_next_points(edges["High"]) if "High" in edges else []
    return [
        CheckResult("called update_nodes", bool(tool_called(output, "update_nodes"))),
        CheckResult(
            "the router keeps its branches",
            router is not None and set(edges) == {"High", "Low"},
        ),
        CheckResult(
            "High and Urgent tickets take the High branch, Low the Low branch",
            bool(edges)
            and taken.get("High") == edges["High"]
            and taken.get("Urgent") == edges["High"]
            and taken.get("Low") == edges["Low"],
            hint=f"branches taken: {taken}, branches: {edges}",
        ),
        CheckResult(
            "the Slack step stays on the High branch",
            slack is not None and any(node.id == slack.id for node in high_nodes),
        ),
    ]


register_case(
    EvalCase(
        id="automation/changes-router-condition",
        dataset="kuma-automation",
        prompt=PROMPT_CHANGES_ROUTER_CONDITION.format(
            automation_name="Ticket Router", workflow_name="Ticket triage"
        ),
        scenario="automation-changes-router-condition",
        checks=_check_changes_router_condition,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Deletes a node (delete_nodes)
# ---------------------------------------------------------------------------


@register_scenario("automation-deletes-node")
def _deletes_node_scenario(fx: Fixtures) -> EvalScenario:
    refs = _orders_workflow(fx, "Order flow")
    refs["slack"] = _create_node(
        refs["user"],
        refs["workflow"],
        "slack_write_message",
        label="Post to #orders",
        reference_node_id=refs["email"].id,
        service={"channel": "orders", "text": "'New order'"},
    )
    return _scenario(refs)


def _check_deletes_node(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    refs = scenario.refs
    remaining = set(
        AutomationNode.objects.filter(workflow=refs["workflow"]).values_list(
            "id", flat=True
        )
    )
    return [
        CheckResult("called delete_nodes", bool(tool_called(output, "delete_nodes"))),
        CheckResult("the Slack step is deleted", refs["slack"].id not in remaining),
        CheckResult(
            "the trigger and the email are kept",
            {refs["trigger"].id, refs["email"].id} <= remaining,
        ),
        CheckResult(
            "the email still runs after the trigger",
            _follows(refs["email"], refs["trigger"]),
        ),
    ]


register_case(
    EvalCase(
        id="automation/deletes-node",
        dataset="kuma-automation",
        prompt=PROMPT_DELETES_NODE.format(
            automation_name="Order Notifications", workflow_name="Order flow"
        ),
        scenario="automation-deletes-node",
        checks=_check_deletes_node,
        max_iters=20,
    )
)
