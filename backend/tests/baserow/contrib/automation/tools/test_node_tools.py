"""Tests for add_nodes, update_nodes and delete_nodes, shared by MCP and Kuma."""

from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError

import pytest

from baserow.contrib.automation.nodes.actions import UpdateAutomationNodeActionType
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.tools.nodes import (
    add_nodes,
    delete_nodes,
    update_nodes,
)
from baserow.contrib.automation.tools.types import ActionNodeCreate, NodeUpdate
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED

from .conftest import create_node, create_workflow


def _email(ref="mail", previous="trigger", **values):
    return ActionNodeCreate(
        **{
            "ref": ref,
            "type": "smtp_email",
            "previous_node_ref": previous,
            "to_emails": "team@example.com",
            "subject": "Hi",
            "body": "Hello",
            **values,
        }
    )


def _email_node(ctx, workflow, previous, label):
    return create_node(
        ctx.user,
        workflow,
        "smtp_email",
        label=label,
        reference_node_id=previous.id,
        service={"subject": "'Before'"},
    )


@pytest.mark.django_db
def test_add_nodes_after_an_existing_node_and_each_other(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    result = add_nodes(
        ctx,
        workflow.id,
        [
            _email(ref="first", previous=str(trigger.id), label="First"),
            _email(ref="second", previous="first", label="Second", subject="concat("),
        ],
    )

    first, second = result["created_nodes"]
    assert (first["ref"], second["ref"]) == ("first", "second")
    graph = workflow.get_graph().graph
    assert graph[str(trigger.id)]["next"][""] == [first["id"]]
    assert graph[str(first["id"])]["next"][""] == [second["id"]]
    (error,) = result["formula_errors"]
    assert (error["node_id"], error["field"]) == (second["id"], "subject")


@pytest.mark.django_db
def test_add_nodes_reports_values_a_row_node_type_takes_no(automation_ctx):
    ctx, automation, table, name = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    result = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="store",
                type="create_row",
                previous_node_ref=str(trigger.id),
                table_id=table.id,
                row_id="5",
                values=[{"field_id": name.id, "value": "done"}],
            ),
            ActionNodeCreate(
                ref="remove",
                type="delete_row",
                previous_node_ref="store",
                table_id=table.id,
                row_id="5",
                values=[{"field_id": name.id, "value": "done"}],
            ),
        ],
    )

    store, remove = result["created_nodes"]
    assert result["errors"] == [
        f"Node {store['id']} ({store['label']}): A create_row node takes no row_id.",
        f"Node {remove['id']} ({remove['label']}): A delete_row node takes no values.",
    ]
    service = AutomationNode.objects.get(id=store["id"]).service.specific
    assert not service.row_id["formula"]
    assert service.field_mappings.get(field=name).value["formula"] == "'done'"
    service = AutomationNode.objects.get(id=remove["id"]).service.specific
    assert not service.field_mappings.exists()


@pytest.mark.django_db
def test_add_nodes_to_an_existing_router_branch(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    big = str(uuid4())
    router = create_node(
        ctx.user,
        workflow,
        "router",
        reference_node_id=trigger.id,
        service={"edges": [{"uid": big, "label": "Big"}]},
    )

    result = add_nodes(
        ctx, workflow.id, [_email(previous=str(router.id), router_edge_label="Big")]
    )

    (created,) = result["created_nodes"]
    assert workflow.get_graph().graph[str(router.id)]["next"][big] == [created["id"]]


@pytest.mark.django_db
def test_add_nodes_with_an_unknown_ref_writes_nothing(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    with pytest.raises(DjangoValidationError, match="previous_node_ref 'nope'"):
        add_nodes(
            ctx,
            workflow.id,
            [_email(ref="a", previous=str(trigger.id)), _email(previous="nope")],
        )

    assert AutomationNode.objects.filter(workflow=workflow).count() == 1


@pytest.mark.django_db
def test_add_nodes_cannot_follow_a_node_of_another_workflow(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, _ = create_workflow(ctx.user, automation, "Flow", table)
    _, other_trigger = create_workflow(ctx.user, automation, "Other", table)

    with pytest.raises(DjangoValidationError, match=str(other_trigger.id)):
        add_nodes(ctx, workflow.id, [_email(previous=str(other_trigger.id))])


@pytest.mark.django_db
def test_update_nodes_only_updates_nodes_of_the_workflow(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    other, other_trigger = create_workflow(ctx.user, automation, "Other", table)
    elsewhere = _email_node(ctx, other, other_trigger, "Elsewhere")

    result = update_nodes(
        ctx, workflow.id, [NodeUpdate(node_id=elsewhere.id, label="Moved")]
    )

    assert result["updated_nodes"] == []
    assert result["errors"] == [
        f"Error updating node {elsewhere.id}: Not found in this workspace."
    ]
    elsewhere.refresh_from_db()
    assert elsewhere.label == "Elsewhere"


@pytest.mark.django_db
def test_update_nodes_saves_each_node_in_a_savepoint(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    first = _email_node(ctx, workflow, trigger, "First")
    second = _email_node(ctx, workflow, first, "Second")
    third = _email_node(ctx, workflow, second, "Third")
    do = UpdateAutomationNodeActionType.do

    def fail_second(user, node_id, data):
        if node_id == second.id:
            # A real database error, so the transaction is broken until the
            # savepoint is rolled back.
            AutomationNode.objects.create(id=trigger.id, workflow=workflow)
        return do(user, node_id, data)

    with patch.object(UpdateAutomationNodeActionType, "do", side_effect=fail_second):
        result = update_nodes(
            ctx,
            workflow.id,
            [
                NodeUpdate(node_id=n.id, subject="Changed")
                for n in (first, second, third)
            ],
        )

    assert [node["node_id"] for node in result["updated_nodes"]] == [first.id, third.id]
    assert len(result["errors"]) == 1
    assert result["errors"][0].startswith(f"Error updating node {second.id}:")
    for node, subject in (
        (first, "'Changed'"),
        (second, "'Before'"),
        (third, "'Changed'"),
    ):
        node.refresh_from_db()
        assert node.service.specific.subject["formula"] == subject


@pytest.mark.django_db
def test_update_nodes_checks_formulas(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    mail = _email_node(ctx, workflow, trigger, "Mail")

    result = update_nodes(
        ctx,
        workflow.id,
        [
            NodeUpdate(
                node_id=mail.id,
                subject="get('previous_node.1.0.id')",
                body="$formula: the name",
            )
        ],
    )

    (error,) = result["formula_errors"]
    assert (error["node_id"], error["field"]) == (mail.id, "body")
    service = mail.service.specific
    service.refresh_from_db()
    assert service.subject["formula"] == "get('previous_node.1.0.id')"
    assert service.body["formula"] == ""


@pytest.mark.django_db
def test_update_nodes_sets_a_router_condition(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    big = str(uuid4())
    router = create_node(
        ctx.user,
        workflow,
        "router",
        reference_node_id=trigger.id,
        service={"edges": [{"uid": big, "label": "Big"}]},
    )
    add_nodes(
        ctx, workflow.id, [_email(previous=str(router.id), router_edge_label="Big")]
    )

    result = update_nodes(
        ctx,
        workflow.id,
        [
            NodeUpdate(
                node_id=router.id,
                edges=[
                    {"label": "big", "condition": "equal(1, 1)"},
                    {"label": "Small", "condition": "true"},
                ],
            )
        ],
    )

    edge = router.service.specific.edges.get()
    assert str(edge.uid) == big
    assert edge.condition["formula"] == "equal(1, 1)"
    assert edge.condition["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    assert result["errors"] == [
        f"Node {router.id} ({router.label}): 'Small' is not a branch of node "
        f"{router.id}, so its condition was not set. Its branches: 'Big'."
    ]


@pytest.mark.django_db
def test_update_nodes_merges_row_values(automation_ctx, data_fixture):
    ctx, automation, table, name = automation_ctx
    other = data_fixture.create_text_field(table=table, name="Other")
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    store = create_node(
        ctx.user,
        workflow,
        "local_baserow_create_row",
        reference_node_id=trigger.id,
        service={
            "table_id": table.id,
            "field_mappings": [{"field_id": name.id, "value": "'A'", "enabled": True}],
        },
    )

    update_nodes(
        ctx,
        workflow.id,
        [NodeUpdate(node_id=store.id, values=[{"field_id": other.id, "value": "B"}])],
    )

    mappings = store.service.specific.field_mappings.order_by("field_id")
    assert [(m.field_id, m.value["formula"]) for m in mappings] == [
        (name.id, "'A'"),
        (other.id, "'B'"),
    ]


@pytest.mark.django_db
def test_delete_nodes_hides_whether_a_node_exists(data_fixture, automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    mail = _email_node(ctx, workflow, trigger, "Mail")
    member_of = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=ctx.user)
    )
    _, member_trigger = create_workflow(ctx.user, member_of)
    stranger = data_fixture.create_user()
    _, stranger_trigger = create_workflow(
        stranger, data_fixture.create_automation_application(user=stranger)
    )
    ids = [member_trigger.id, stranger_trigger.id, 999999]

    result = delete_nodes(ctx, [mail.id, *ids])

    assert result["deleted_node_ids"] == [mail.id]
    assert result["errors"] == [
        f"Error deleting node {node_id}: Not found in this workspace."
        for node_id in ids
    ]
    assert AutomationNode.objects.filter(id__in=ids[:2]).count() == 2


@pytest.mark.django_db
def test_delete_nodes_reports_a_router_with_nodes_on_a_branch(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    big = str(uuid4())
    router = create_node(
        ctx.user,
        workflow,
        "router",
        reference_node_id=trigger.id,
        service={"edges": [{"uid": big, "label": "Big"}]},
    )
    add_nodes(
        ctx, workflow.id, [_email(previous=str(router.id), router_edge_label="Big")]
    )

    result = delete_nodes(ctx, [router.id])

    assert result["deleted_node_ids"] == []
    (error,) = result["errors"]
    assert error.startswith(f"Error deleting node {router.id}: ")
    assert "branch" in error.lower() or "output" in error.lower()
    assert AutomationNode.objects.filter(id=router.id).exists()


@pytest.mark.django_db
def test_update_nodes_reports_values_for_a_row_node_without_a_table(automation_ctx):
    ctx, automation, table, name = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    store = create_node(
        ctx.user, workflow, "local_baserow_create_row", reference_node_id=trigger.id
    )

    result = update_nodes(
        ctx,
        workflow.id,
        [NodeUpdate(node_id=store.id, values=[{"field_id": name.id, "value": "B"}])],
    )

    assert result["errors"] == [
        f"Node {store.id} ({store.label}): The node has no table, so its values "
        "were not set. Give a table_id with them."
    ]
    assert not store.service.specific.field_mappings.exists()


@pytest.mark.django_db
def test_add_nodes_refuses_a_ref_that_names_another_node(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    for refs in ([str(trigger.id)], ["a", "a"]):
        nodes = [_email(ref=ref, previous=str(trigger.id)) for ref in refs]
        with pytest.raises(DjangoValidationError, match="already the ref or ID"):
            add_nodes(ctx, workflow.id, nodes)

    assert AutomationNode.objects.filter(workflow=workflow).count() == 1


@pytest.mark.django_db
def test_delete_nodes_rejects_an_empty_list(automation_ctx):
    ctx, *_ = automation_ctx

    with pytest.raises(DjangoValidationError, match="at least one node ID"):
        delete_nodes(ctx, [])


@pytest.mark.django_db
def test_update_nodes_explains_a_deactivated_node_type(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    mail = _email_node(ctx, workflow, trigger, "Mail")

    with patch.object(type(mail.get_type()), "is_deactivated", return_value=True):
        result = update_nodes(
            ctx, workflow.id, [NodeUpdate(node_id=mail.id, label="Renamed")]
        )

    assert result["errors"] == [
        f"Error updating node {mail.id}: This automation node type is deactivated."
    ]


@pytest.mark.django_db
def test_update_nodes_keeps_a_value_whose_new_formula_is_invalid(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    mail = _email_node(ctx, workflow, trigger, "Mail")

    result = update_nodes(
        ctx, workflow.id, [NodeUpdate(node_id=mail.id, subject="concat(")]
    )

    assert result["formula_errors"][0]["field"] == "subject"
    service = mail.service.specific
    service.refresh_from_db()
    assert service.subject["formula"] == "'Before'"


@pytest.mark.django_db
def test_update_nodes_refuses_values_a_row_node_does_not_take(automation_ctx):
    ctx, automation, table, name = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    store = create_node(
        ctx.user,
        workflow,
        "local_baserow_create_row",
        reference_node_id=trigger.id,
        service={"table_id": table.id},
    )
    remove = create_node(
        ctx.user,
        workflow,
        "local_baserow_delete_row",
        reference_node_id=store.id,
        service={"table_id": table.id},
    )

    result = update_nodes(
        ctx,
        workflow.id,
        [
            NodeUpdate(node_id=store.id, row_id="5"),
            NodeUpdate(node_id=remove.id, values=[{"field_id": name.id, "value": "x"}]),
        ],
    )

    assert result["errors"] == [
        f"Node {store.id} ({store.label}): A create_row node takes no row_id.",
        f"Node {remove.id} ({remove.label}): A delete_row node takes no values.",
    ]
    store.service.specific.refresh_from_db()
    assert not store.service.specific.row_id["formula"]


@pytest.mark.django_db
def test_update_nodes_hides_a_node_the_user_cannot_read(automation_ctx):
    from baserow.contrib.automation.tools import nodes as nodes_module
    from baserow.core.exceptions import PermissionException

    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    hidden = _email_node(ctx, workflow, trigger, "Hidden")
    check = nodes_module.CoreHandler.check_permissions

    def deny_hidden(self, actor, operation, workspace=None, context=None, **kwargs):
        if getattr(context, "id", None) == hidden.id:
            raise PermissionException()
        return check(
            self, actor, operation, workspace=workspace, context=context, **kwargs
        )

    with patch.object(nodes_module.CoreHandler, "check_permissions", deny_hidden):
        result = update_nodes(
            ctx, workflow.id, [NodeUpdate(node_id=hidden.id, label="X")]
        )

    assert result["errors"] == [
        f"Error updating node {hidden.id}: Not found in this workspace."
    ]


@pytest.mark.django_db
def test_update_nodes_refuses_a_label_that_names_several_branches(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    router = create_node(
        ctx.user,
        workflow,
        "router",
        reference_node_id=trigger.id,
        service={
            "edges": [
                {"uid": str(uuid4()), "label": "Yes"},
                {"uid": str(uuid4()), "label": "Yes"},
            ]
        },
    )

    result = update_nodes(
        ctx,
        workflow.id,
        [NodeUpdate(node_id=router.id, edges=[{"label": "Yes", "condition": "true"}])],
    )

    assert "names several branches" in result["errors"][0]


@pytest.mark.django_db
def test_update_nodes_stores_the_email_body_type_as_a_choice(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    mail = _email_node(ctx, workflow, trigger, "Mail")

    update_nodes(ctx, workflow.id, [NodeUpdate(node_id=mail.id, body_type="html")])

    service = mail.service.specific
    service.refresh_from_db()
    assert service.body_type == "html"
