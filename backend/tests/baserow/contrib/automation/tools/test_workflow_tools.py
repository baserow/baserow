"""Tests for create_workflows, shared by MCP and Kuma."""

from unittest.mock import patch

from django.core.exceptions import ValidationError as DjangoValidationError

import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.tools.types import WorkflowCreate
from baserow.contrib.automation.tools.workflows import create_workflows
from baserow.contrib.automation.workflows.actions import (
    CreateAutomationWorkflowActionType,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.database.table.models import Table
from baserow.core.action.models import Action
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED

from .conftest import create_workflow


def _workflow(table, *nodes, name="Orders"):
    return WorkflowCreate(
        name=name,
        trigger={
            "ref": "trigger",
            "type": "rows_created",
            "rows_triggers_settings": {"table_id": table.id},
        },
        nodes=list(nodes),
    )


def _email(ref="mail", previous="trigger", **values):
    return {
        "ref": ref,
        "type": "smtp_email",
        "previous_node_ref": previous,
        "to_emails": "team@example.com",
        "subject": "New order",
        "body": "Hello",
        **values,
    }


def _nodes(workflow_id):
    return {
        node.label: node.specific
        for node in AutomationNode.objects.filter(workflow_id=workflow_id)
    }


@pytest.mark.django_db
def test_create_workflows_stores_literals_and_raw_formulas(automation_ctx):
    ctx, automation, table, name = automation_ctx
    condition = f"greater_than(get('previous_node.1.0.field_{name.id}'), 10)"
    workflow = _workflow(
        table,
        {
            "ref": "router",
            "type": "router",
            "label": "Route",
            "previous_node_ref": "trigger",
            "edges": [{"label": "Big", "condition": condition}],
        },
        _email(
            previous="router",
            router_edge_label="Big",
            label="Mail",
            subject="concat('Order ', get('previous_node.1.0.id'))",
        ),
    )

    result = create_workflows(ctx, automation.id, [workflow])

    (created,) = result["created_workflows"]
    assert "formula_errors" not in result
    assert [node["ref"] for node in created["nodes"]] == ["trigger", "router", "mail"]
    nodes = _nodes(created["id"])
    edge = nodes["Route"].service.specific.edges.get()
    assert edge.label == "Big"
    assert edge.condition["formula"] == condition
    assert edge.condition["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    mail = nodes["Mail"].service.specific
    assert mail.to_emails["formula"] == "'team@example.com'"
    assert mail.subject["formula"] == "concat('Order ', get('previous_node.1.0.id'))"
    assert mail.body["formula"] == "'Hello'"
    graph = AutomationWorkflow.objects.get(id=created["id"]).get_graph().graph
    assert graph[str(nodes["Route"].id)]["next"][str(edge.uid)] == [nodes["Mail"].id]
    # Each change is in the undo history, as in the editor.
    assert Action.objects.filter(user=ctx.user).count() == 4


@pytest.mark.django_db
def test_an_invalid_formula_leaves_its_value_empty(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow = _workflow(
        table, _email(label="Mail", subject="concat(", body="$formula: the name")
    )

    result = create_workflows(ctx, automation.id, [workflow])

    mail = _nodes(result["created_workflows"][0]["id"])["Mail"]
    assert result["formula_errors"] == [
        {
            "node_id": mail.id,
            "node_label": "Mail",
            "field": "subject",
            "formula": "concat(",
            "error": result["formula_errors"][0]["error"],
        },
        {
            "node_id": mail.id,
            "node_label": "Mail",
            "field": "body",
            "formula": "$formula: the name",
            "error": "'body' needs a formula, not a description. Write it in "
            "Baserow formula syntax.",
        },
    ]
    assert "syntax" in result["formula_errors"][0]["error"].lower()
    service = mail.service.specific
    assert service.subject["formula"] == ""
    assert service.body["formula"] == ""
    assert service.to_emails["formula"] == "'team@example.com'"


@pytest.mark.django_db
def test_an_empty_router_condition_is_reported(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow = _workflow(
        table,
        {
            "ref": "router",
            "type": "router",
            "label": "Route",
            "previous_node_ref": "trigger",
            "edges": [{"label": "Big", "condition": " "}],
        },
    )

    result = create_workflows(ctx, automation.id, [workflow])

    (error,) = result["formula_errors"]
    assert error["field"] == "condition"
    assert error["edge_label"] == "Big"
    assert error["error"] == "'condition' needs a formula."


@pytest.mark.django_db
def test_an_unknown_ref_writes_nothing(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    first = _workflow(table, _email(), name="First")
    second = _workflow(table, _email(previous="nope"), name="Second")

    with pytest.raises(DjangoValidationError, match="previous_node_ref 'nope'"):
        create_workflows(ctx, automation.id, [first, second])

    assert not AutomationWorkflow.objects.filter(automation=automation).exists()


@pytest.mark.django_db
def test_an_unknown_router_branch_writes_nothing(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow = _workflow(
        table,
        {
            "ref": "router",
            "type": "router",
            "previous_node_ref": "trigger",
            "edges": [{"label": "Big", "condition": "true"}],
        },
        _email(previous="router", router_edge_label="Small"),
    )

    with pytest.raises(DjangoValidationError, match="'Small' is not a branch"):
        create_workflows(ctx, automation.id, [workflow])

    assert not AutomationWorkflow.objects.filter(automation=automation).exists()


@pytest.mark.django_db
def test_a_router_branch_label_matches_without_case(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow = _workflow(
        table,
        {
            "ref": "router",
            "type": "router",
            "label": "Route",
            "previous_node_ref": "trigger",
            "edges": [{"label": "Big", "condition": "true"}],
        },
        _email(previous="router", router_edge_label="big", label="Mail"),
    )

    result = create_workflows(ctx, automation.id, [workflow])

    nodes = _nodes(result["created_workflows"][0]["id"])
    edge = nodes["Route"].service.specific.edges.get()
    graph = AutomationWorkflow.objects.get(automation=automation).get_graph().graph
    assert graph[str(nodes["Route"].id)]["next"][str(edge.uid)] == [nodes["Mail"].id]


@pytest.mark.django_db
def test_a_table_in_another_workspace_is_not_found(data_fixture, automation_ctx):
    ctx, automation, _, _ = automation_ctx
    elsewhere = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=data_fixture.create_workspace(user=ctx.user)
        )
    )

    with pytest.raises(Table.DoesNotExist):
        create_workflows(ctx, automation.id, [_workflow(elsewhere, _email())])

    assert not AutomationWorkflow.objects.filter(automation=automation).exists()


@pytest.mark.django_db
def test_a_field_of_another_table_is_not_mapped(data_fixture, automation_ctx):
    ctx, automation, table, name = automation_ctx
    other = data_fixture.create_text_field(
        table=data_fixture.create_database_table(database=table.database)
    )
    workflow = _workflow(
        table,
        {
            "ref": "store",
            "type": "create_row",
            "label": "Store",
            "previous_node_ref": "trigger",
            "table_id": table.id,
            "values": [
                {"field_id": name.id, "value": "get('previous_node.1.0.id')"},
                {"field_id": other.id, "value": "x"},
            ],
        },
    )

    result = create_workflows(ctx, automation.id, [workflow])

    store = _nodes(result["created_workflows"][0]["id"])["Store"]
    mappings = list(store.service.specific.field_mappings.all())
    assert [(m.field_id, m.value["formula"]) for m in mappings] == [
        (name.id, "get('previous_node.1.0.id')")
    ]
    assert result["errors"] == [
        f"Node {store.id} (Store): Field {other.id} is not in table {table.id}, "
        "so its value was not set."
    ]


@pytest.mark.django_db
def test_duplicate_names_merge_or_conflict(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    same = _workflow(table, _email())

    result = create_workflows(ctx, automation.id, [same, _workflow(table, _email())])
    assert len(result["created_workflows"]) == 1

    with pytest.raises(DjangoValidationError, match="same name: Other"):
        create_workflows(
            ctx,
            automation.id,
            [
                _workflow(table, _email(), name="Other"),
                _workflow(table, _email(subject="Changed"), name="Other"),
            ],
        )


@pytest.mark.django_db
def test_an_existing_name_is_reused_unchanged(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    existing, trigger = create_workflow(ctx.user, automation, "Orders", table)

    result = create_workflows(ctx, automation.id, [_workflow(table, _email())])

    assert result["created_workflows"] == []
    (reused,) = result["reused_workflows"]
    assert reused["id"] == existing.id
    assert [node["id"] for node in reused["nodes"]] == [trigger.id]
    assert AutomationNode.objects.filter(workflow=existing).count() == 1


@pytest.mark.django_db
def test_an_empty_list_is_rejected(automation_ctx):
    ctx, automation, *_ = automation_ctx

    with pytest.raises(DjangoValidationError, match="at least one workflow"):
        create_workflows(ctx, automation.id, [])


@pytest.mark.django_db
def test_a_formula_can_name_an_earlier_node_by_its_ref(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow = _workflow(
        table, _email(label="Mail", subject="get('previous_node.trigger.0.id')")
    )

    result = create_workflows(ctx, automation.id, [workflow])

    created = result["created_workflows"][0]
    trigger_id = created["nodes"][0]["id"]
    mail = _nodes(created["id"])["Mail"].service.specific
    assert mail.subject["formula"] == f"get('previous_node.{trigger_id}.0.id')"


@pytest.mark.django_db
def test_router_branches_need_their_own_labels():
    with pytest.raises(ValueError, match="its own label"):
        WorkflowCreate(
            name="X",
            trigger={
                "ref": "t",
                "type": "periodic",
                "periodic_interval": {"interval": "DAY"},
            },
            nodes=[
                {
                    "ref": "r",
                    "type": "router",
                    "previous_node_ref": "t",
                    "edges": [
                        {"label": "A", "condition": "true"},
                        {"label": "a", "condition": "true"},
                    ],
                }
            ],
        )


def test_labels_and_names_have_the_database_limits():
    with pytest.raises(ValueError, match="75"):
        WorkflowCreate(
            name="X",
            trigger={
                "ref": "t",
                "type": "periodic",
                "periodic_interval": {"interval": "DAY"},
            },
            nodes=[{**_email(), "label": "x" * 76}],
        )
    with pytest.raises(ValueError, match="255"):
        WorkflowCreate(
            name="x" * 256,
            trigger={
                "ref": "t",
                "type": "periodic",
                "periodic_interval": {"interval": "DAY"},
            },
        )


@pytest.mark.django_db
def test_a_workflow_that_fails_keeps_the_ones_saved_before(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    first = _workflow(table, _email(subject="$formula: the id"), name="First")
    second = _workflow(table, _email(), name="Second")
    do = CreateAutomationWorkflowActionType.do

    def fail_second(user, automation_id, data):
        if data["name"] == "Second":
            raise DjangoValidationError("No more workflows.")
        return do(user, automation_id, data)

    with patch.object(
        CreateAutomationWorkflowActionType, "do", side_effect=fail_second
    ):
        result = create_workflows(ctx, automation.id, [first, second])

    assert [w["name"] for w in result["created_workflows"]] == ["First"]
    assert result["errors"] == [
        "Workflow Second was not created: Invalid value. No more workflows."
    ]
    assert result["formula_errors"][0]["field"] == "subject"


@pytest.mark.django_db
def test_the_email_body_type_is_stored_as_a_choice(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow = _workflow(table, _email(label="Mail", body_type="html"))

    result = create_workflows(ctx, automation.id, [workflow])

    mail = _nodes(result["created_workflows"][0]["id"])["Mail"].service.specific
    assert mail.body_type == "html"
