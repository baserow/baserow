"""Saved workflow checks tolerate rejected and repaired model requests."""

from types import SimpleNamespace

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFieldMapping,
)
from baserow_enterprise.assistant.evals.datasets import automation
from baserow_enterprise.assistant.evals.harness import format_message_history
from baserow_enterprise.assistant.evals.types import EvalRunOutput


def _output(workflow, rejected_first=True):
    rejected = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    "create_workflows",
                    {"workflows": [{"name": "Rejected", "nodes": None}]},
                    tool_call_id="rejected",
                )
            ]
        ),
        ModelRequest(
            parts=[
                RetryPromptPart(
                    "Invalid nodes",
                    tool_name="create_workflows",
                    tool_call_id="rejected",
                )
            ]
        ),
    ]
    # InlineRefs repairs this payload before execution without changing the
    # original ToolCallPart. The return identifies the actually saved workflow.
    repaired = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    "create_workflows",
                    {
                        "workflows": [
                            {"name": "Uncorrected", "trigger": None, "nodes": [None]}
                        ]
                    },
                    tool_call_id="repaired",
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    "create_workflows",
                    {"created_workflows": [{"id": workflow.id, "name": workflow.name}]},
                    tool_call_id="repaired",
                )
            ]
        ),
    ]
    messages = rejected + repaired if rejected_first else repaired + rejected
    return EvalRunOutput(
        answer="Created the workflow.",
        messages=format_message_history(SimpleNamespace(all_messages=lambda: messages)),
        tool_calls=["create_workflows", "create_workflows"],
        tool_error_count=1,
        tool_error_hint="Invalid nodes",
        sources=[],
        request_count=1,
        duration_s=0,
    )


def _save_workflow(data_fixture, scenario, kind):
    automation_app = scenario.refs["automation"]
    table = scenario.refs.get("table") or scenario.refs.get("source_table")
    schedule = {
        "interval": "WEEK",
        "day_of_week": 1,
        "hour": 9,
        "minute": 0,
        "timezone": "UTC",
    }
    workflow = data_fixture.create_automation_workflow(
        automation=automation_app,
        trigger_type="periodic"
        if kind == "weekly_slack_reminder"
        else "rows_updated"
        if kind == "update_row_workflow"
        else "rows_created",
        trigger_service_kwargs=schedule
        if kind == "weekly_slack_reminder"
        else {"table": table},
    )
    trigger = workflow.get_trigger()
    if kind == "weekly_slack_reminder":
        data_fixture.create_automation_node(
            workflow=workflow,
            type="slack_write_message",
            service_kwargs={
                "channel": "general",
                "text": "'Is there anything to demo this week?'",
            },
        )
    elif kind == "email_notification_workflow":
        data_fixture.create_automation_node(
            workflow=workflow,
            type="smtp_email",
            service_kwargs={
                "to_emails": "'admin@example.com'",
                "subject": "'New Order'",
                "body": "'A new order has been placed'",
            },
        )
    elif kind == "router_workflow":
        router = data_fixture.create_automation_node(workflow=workflow, type="router")
        router.service.specific.edges.all().delete()
        priority = table.field_set.get(name="Priority")
        high = data_fixture.create_core_router_service_edge(
            service=router.service.specific,
            label="High",
            order=1,
            condition=f"if(equal(get('previous_node.{trigger.id}[0].{priority.db_column}.value'), 'High'), 'true', 'false')",
            skip_output_node=True,
        )
        data_fixture.create_core_router_service_edge(
            service=router.service.specific,
            label="Low",
            order=2,
            condition=f"equal(get('previous_node.{trigger.id}[0].{priority.db_column}.value'), 'Low')",
            skip_output_node=True,
        )
        data_fixture.create_automation_node(
            workflow=workflow,
            type="slack_write_message",
            reference_node=router,
            output=high.uid,
            service_kwargs={
                "channel": "urgent",
                "text": "'High priority ticket created'",
            },
        )
    else:
        creating = kind == "row_with_field_values"
        target = scenario.refs["log_table"] if creating else table
        node = data_fixture.create_automation_node(
            workflow=workflow,
            type="create_row" if creating else "update_row",
            service_kwargs={
                "table": target,
                "row_id": ""
                if creating
                else f"get('previous_node.{trigger.id}[0].id')",
            },
        )
        values = {"Status": "'Processing'"}
        if creating:
            name = table.field_set.get(name="Name")
            values = {
                "Entry": f"get('previous_node.{trigger.id}[0].{name.db_column}')",
                "Source": "'automation'",
            }
        elif kind == "update_row_workflow":
            values = {
                "Status": "'Reviewed'",
                "Notes": "'Automatically reviewed by automation'",
            }
        for name, formula in values.items():
            LocalBaserowTableServiceFieldMapping.objects.create(
                service=node.service,
                field=target.field_set.get(name=name),
                value=formula,
            )
    return workflow


@pytest.mark.django_db
@pytest.mark.parametrize("rejected_first", [False, True])
@pytest.mark.parametrize(
    "kind",
    [
        "workflow",
        "update_row_workflow",
        "router_workflow",
        "email_notification_workflow",
        "row_with_field_values",
        "weekly_slack_reminder",
    ],
)
def test_complete_workflow_survives_earlier_draft_and_rejected_or_repaired_history(
    data_fixture, kind, rejected_first
):
    scenario = getattr(automation, f"_creates_{kind}_scenario")(data_fixture)
    data_fixture.create_automation_workflow(
        automation=scenario.refs["automation"], name="Incomplete draft"
    )
    workflow = _save_workflow(data_fixture, scenario, kind)
    checks = getattr(automation, f"_check_creates_{kind}")(
        None, scenario, _output(workflow, rejected_first)
    )
    assert all(check.passed for check in checks), checks


@pytest.mark.django_db
def test_checks_do_not_combine_two_incomplete_workflows(data_fixture):
    scenario = automation._creates_weekly_slack_reminder_scenario(data_fixture)
    data_fixture.create_automation_workflow(
        automation=scenario.refs["automation"],
        trigger_type="periodic",
        trigger_service_kwargs={
            "interval": "WEEK",
            "day_of_week": 1,
            "hour": 9,
            "minute": 0,
            "timezone": "UTC",
        },
    )
    second = _save_workflow(data_fixture, scenario, "weekly_slack_reminder")
    periodic = second.get_trigger().service.specific
    periodic.day_of_week = 2
    periodic.save()
    checks = automation._check_creates_weekly_slack_reminder(
        None, scenario, _output(second)
    )
    assert not all(check.passed for check in checks), checks


@pytest.mark.django_db
@pytest.mark.parametrize(
    "defect", ["wrong_table", "disabled_status", "swapped_fields", "missing_notes"]
)
def test_update_checks_require_saved_named_mappings_and_target(data_fixture, defect):
    scenario = automation._creates_update_row_workflow_scenario(data_fixture)
    workflow = _save_workflow(data_fixture, scenario, "update_row_workflow")
    node = workflow.automation_workflow_nodes.get(
        content_type__model="localbaserowupdaterowactionnode"
    )
    service = node.service.specific
    if defect == "wrong_table":
        service.table = data_fixture.create_database_table(
            database=scenario.refs["table"].database
        )
        service.save()
    elif defect == "disabled_status":
        service.field_mappings.filter(field__name="Status").update(enabled=False)
    elif defect == "missing_notes":
        service.field_mappings.filter(field__name="Notes").delete()
    else:
        status, notes = [
            service.field_mappings.get(field__name=name) for name in ("Status", "Notes")
        ]
        status.value, notes.value = notes.value, status.value
        status.save()
        notes.save()
    checks = automation._check_creates_update_row_workflow(
        None, scenario, _output(workflow)
    )
    assert not all(check.passed for check in checks), checks


@pytest.mark.django_db
@pytest.mark.parametrize(
    "defect",
    [
        "reversed_condition",
        "malformed_later_edge",
        "low_branch_action",
        "channel",
        "message",
    ],
)
def test_router_check_uses_saved_conditions_and_branch_message(data_fixture, defect):
    scenario = automation._creates_router_workflow_scenario(data_fixture)
    workflow = _save_workflow(data_fixture, scenario, "router_workflow")
    router = workflow.automation_workflow_nodes.get(
        content_type__model="corerouteractionnode"
    )
    slack = workflow.automation_workflow_nodes.get(
        content_type__model="slackwritemessageactionnode"
    ).service.specific
    if defect == "reversed_condition":
        edge = router.service.specific.edges.get(label="High")
        edge.condition = "false"
        edge.save()
    elif defect == "malformed_later_edge":
        data_fixture.create_core_router_service_edge(
            service=router.service.specific,
            label="Invalid later condition",
            order=3,
            condition="invalid_function()",
            skip_output_node=True,
        )
    elif defect == "low_branch_action":
        edge = router.service.specific.edges.get(label="Low")
        data_fixture.create_automation_node(
            workflow=workflow,
            type="slack_write_message",
            reference_node=router,
            output=edge.uid,
        )
    else:
        if defect == "channel":
            slack.channel = "urgent-other"
        else:
            slack.text = "'An unrelated message'"
        slack.save()
    checks = automation._check_creates_router_workflow(
        None, scenario, _output(workflow)
    )
    assert not all(check.passed for check in checks), checks


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [
        ("to_emails", "other@example.com"),
        ("subject", "Other order"),
        ("body", "The order was cancelled"),
    ],
)
def test_email_check_uses_saved_recipient_subject_and_body(data_fixture, field, value):
    scenario = automation._creates_email_notification_workflow_scenario(data_fixture)
    workflow = _save_workflow(data_fixture, scenario, "email_notification_workflow")
    service = workflow.automation_workflow_nodes.get(
        content_type__model="coresmtpemailactionnode"
    ).service.specific
    setattr(service, field, repr(value))
    service.save()
    checks = automation._check_creates_email_notification_workflow(
        None, scenario, _output(workflow)
    )
    assert not all(check.passed for check in checks), checks
