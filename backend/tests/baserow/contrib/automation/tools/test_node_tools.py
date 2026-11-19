"""Tests for add_nodes, update_nodes and delete_nodes, shared by MCP and Kuma."""

from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest
from pydantic import ValidationError as PydanticValidationError

from baserow.api.sessions import get_untrusted_client_session_id
from baserow.contrib.automation.action_scopes import WorkflowActionScopeType
from baserow.contrib.automation.nodes.actions import (
    DeleteAutomationNodeActionType,
    UpdateAutomationNodeActionType,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.nodes.trash_types import (
    AutomationNodeTrashableItemType,
)
from baserow.contrib.automation.tools.nodes import (
    add_nodes,
    delete_nodes,
    list_nodes,
    update_nodes,
)
from baserow.contrib.automation.tools.types import (
    ActionNodeCreate,
    NodeRefs,
    NodeUpdate,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.cache import local_cache
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.trash.handler import TrashHandler

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
    workflow.refresh_from_db()
    graph = workflow.graph
    assert graph[str(trigger.id)]["next"][""] == [first["id"]]
    assert graph[str(first["id"])]["next"][""] == [second["id"]]
    (error,) = result["formula_errors"]
    assert (error["node_id"], error["field"]) == (second["id"], "subject")


@pytest.mark.django_db
def test_add_nodes_before_an_existing_node_keeps_it_and_reports_it(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]

    result = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="slack",
                label="Ping",
                type="slack_write_message",
                previous_node_ref=str(trigger.id),
                channel="sales",
                text="New lead",
            ),
            _email(ref="log", previous="slack", label="Log"),
        ],
    )

    slack, log = result["created_nodes"]
    assert result["shifted_nodes"] == [
        {
            "id": email["id"],
            "label": email["label"],
            "type": "smtp_email",
            "previous_node_ref": str(log["id"]),
        }
    ]
    assert [node["id"] for node in list_nodes(ctx, workflow.id)["nodes"]] == [
        trigger.id,
        slack["id"],
        log["id"],
        email["id"],
    ]
    service = AutomationNode.objects.get(id=email["id"]).service.specific
    assert service.subject["formula"] == "'Hi'"


@pytest.mark.django_db
def test_add_nodes_before_a_node_on_a_router_branch(automation_ctx):
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
    (email,) = add_nodes(
        ctx, workflow.id, [_email(previous=str(router.id), router_edge_label="Big")]
    )["created_nodes"]

    result = add_nodes(
        ctx,
        workflow.id,
        [_email(ref="log", previous=str(router.id), router_edge_label="Big")],
    )

    (log,) = result["created_nodes"]
    graph = workflow.get_graph().graph
    assert graph[str(router.id)]["next"][big] == [log["id"]]
    assert graph[str(log["id"])]["next"][""] == [email["id"]]
    (shifted,) = result["shifted_nodes"]
    assert shifted["id"] == email["id"]
    assert shifted["previous_node_ref"] == str(log["id"])
    assert "router_edge_label" not in shifted


@pytest.mark.django_db
def test_add_nodes_router_before_a_node_moves_it_onto_the_named_branch(
    automation_ctx,
):
    ctx, automation, table, name = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    (after,) = add_nodes(
        ctx, workflow.id, [_email(ref="after", previous=str(email["id"]))]
    )["created_nodes"]
    before = deepcopy(workflow.get_graph().graph)

    result = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[
                    {
                        "label": "acme.com",
                        "condition": f"contains(get('previous_node.{trigger.id}"
                        f".0.field_{name.id}'), 'acme.com')",
                    }
                ],
                shifted_node_edge_label="ACME.com",
            )
        ],
    )

    (router,) = result["created_nodes"]
    (shifted,) = result["shifted_nodes"]
    assert (shifted["id"], shifted["router_edge_label"]) == (email["id"], "acme.com")
    (edge,) = AutomationNode.objects.get(id=router["id"]).service.specific.edges.all()
    graph = workflow.get_graph().graph
    # The email runs on the branch, and the node after it still follows it.
    assert graph[str(router["id"])]["next"] == {str(edge.uid): [email["id"]]}
    assert graph[str(email["id"])]["next"][""] == [after["id"]]

    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)
    ActionHandler.undo(ctx.user, scope, session)
    workflow.reload_graph()
    assert workflow.graph == before

    ActionHandler.redo(ctx.user, scope, session)
    workflow.reload_graph()
    assert workflow.graph[str(router["id"])]["next"] == {str(edge.uid): [email["id"]]}


@pytest.mark.django_db
def test_undo_router_insert_keeps_a_node_added_on_its_default_output(
    automation_ctx,
):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    (after,) = add_nodes(
        ctx, workflow.id, [_email(ref="after", previous=str(email["id"]))]
    )["created_nodes"]
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="Big",
            )
        ],
    )["created_nodes"]
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)

    # Another session adds a node on the router's default output.
    workflow.reload_graph()
    other = _email_node(
        ctx, workflow, AutomationNode.objects.get(id=router["id"]), "Other"
    )
    graph = workflow.get_graph().graph
    assert graph[str(router["id"])]["next"][""] == [other.id]

    ActionHandler.undo(ctx.user, scope, session)

    workflow.reload_graph()
    graph = workflow.graph
    assert str(router["id"]) not in graph
    assert graph["0"] == trigger.id
    assert graph[str(trigger.id)]["next"] == {"": [email["id"]]}
    assert graph[str(email["id"])]["next"] == {"": [after["id"]]}
    assert graph[str(after["id"])]["next"] == {"": [other.id]}
    assert not Action.objects.filter(error__isnull=False).exists()

    ActionHandler.redo(ctx.user, scope, session)

    # Other is back on the router's default output, not after the branch.
    (edge,) = AutomationNode.objects.get(id=router["id"]).service.specific.edges.all()
    workflow.reload_graph()
    graph = workflow.graph
    assert graph[str(router["id"])]["next"] == {
        str(edge.uid): [email["id"]],
        "": [other.id],
    }
    assert graph[str(email["id"])]["next"] == {"": [after["id"]]}
    assert not graph[str(after["id"])].get("next", {}).get("")

    ActionHandler.undo(ctx.user, scope, session)

    workflow.reload_graph()
    graph = workflow.graph
    assert str(router["id"]) not in graph
    assert graph[str(trigger.id)]["next"] == {"": [email["id"]]}
    assert graph[str(email["id"])]["next"] == {"": [after["id"]]}
    assert graph[str(after["id"])]["next"] == {"": [other.id]}
    assert not Action.objects.filter(error__isnull=False).exists()


@pytest.mark.django_db
def test_restore_from_trash_after_undo_puts_the_nodes_back_on_the_branch(
    automation_ctx,
):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Match", "condition": "true"}],
                shifted_node_edge_label="Match",
            )
        ],
    )["created_nodes"]
    workflow.reload_graph()
    fallback = _email_node(
        ctx, workflow, AutomationNode.objects.get(id=router["id"]), "Fallback"
    )
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)
    ActionHandler.undo(ctx.user, scope, session)

    # Restored from the trash instead of with redo.
    TrashHandler.restore_item(
        ctx.user, AutomationNodeTrashableItemType.type, router["id"]
    )

    (edge,) = AutomationNode.objects.get(id=router["id"]).service.specific.edges.all()
    workflow.reload_graph()
    assert workflow.graph[str(router["id"])]["next"] == {
        str(edge.uid): [email["id"]],
        "": [fallback.id],
    }
    assert not workflow.graph[str(email["id"])].get("next", {}).get("")


@pytest.mark.django_db
def test_redo_router_insert_keeps_default_nodes_when_the_first_one_is_deleted(
    automation_ctx,
):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="Big",
            )
        ],
    )["created_nodes"]
    workflow.reload_graph()
    first = _email_node(
        ctx, workflow, AutomationNode.objects.get(id=router["id"]), "First"
    )
    workflow.reload_graph()
    second = _email_node(ctx, workflow, first, "Second")
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)
    ActionHandler.undo(ctx.user, scope, session)
    # Another session deletes the first node that was on the default output.
    AutomationNodeService().delete_node(ctx.user, first.id)

    ActionHandler.redo(ctx.user, scope, session)

    (edge,) = AutomationNode.objects.get(id=router["id"]).service.specific.edges.all()
    workflow.reload_graph()
    assert workflow.graph[str(router["id"])]["next"] == {
        str(edge.uid): [email["id"]],
        "": [second.id],
    }
    assert not workflow.graph[str(email["id"])].get("next", {}).get("")


@pytest.mark.django_db
def test_undo_router_insert_refuses_to_hang_default_nodes_on_a_router(
    automation_ctx,
):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router2",
                type="router",
                previous_node_ref=str(email["id"]),
                edges=[{"label": "Small", "condition": "true"}],
            )
        ],
    )
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="Big",
            )
        ],
    )["created_nodes"]
    workflow.reload_graph()
    other = _email_node(
        ctx, workflow, AutomationNode.objects.get(id=router["id"]), "Other"
    )
    workflow.reload_graph()
    before = deepcopy(workflow.graph)
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)

    # On the branch, the chain ends in a router: Other would then run only when
    # none of its branches match, so the undo is refused.
    (action,) = ActionHandler.undo(ctx.user, scope, session)

    assert "AutomationNodeNotDeletable" in action.error
    workflow.reload_graph()
    assert workflow.graph == before
    assert AutomationNode.objects.filter(id=other.id).exists()


@pytest.mark.django_db
def test_undo_router_insert_refuses_to_hang_default_nodes_on_a_router_mid_chain(
    automation_ctx,
):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router2",
                type="router",
                previous_node_ref=str(email["id"]),
                edges=[{"label": "Small", "condition": "true"}],
            ),
            _email(ref="r2_default", previous="router2"),
        ],
    )
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="Big",
            )
        ],
    )["created_nodes"]
    workflow.reload_graph()
    other = _email_node(
        ctx, workflow, AutomationNode.objects.get(id=router["id"]), "Other"
    )
    workflow.reload_graph()
    before = deepcopy(workflow.graph)
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)

    # The chain on the branch ends in a node on Router2's default branch: Other
    # would then run only when none of Router2's branches match.
    (action,) = ActionHandler.undo(ctx.user, scope, session)

    assert "AutomationNodeNotDeletable" in action.error
    assert "This step can't be undone" in action.error
    workflow.reload_graph()
    assert workflow.graph == before
    assert AutomationNode.objects.filter(id=other.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("at_head", [True, False])
def test_undo_router_insert_refuses_when_another_node_joined_the_branch(
    automation_ctx, at_head
):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Match", "condition": "true"}],
                shifted_node_edge_label="Match",
            )
        ],
    )["created_nodes"]
    (edge,) = AutomationNode.objects.get(id=router["id"]).service.specific.edges.all()
    # Another editor adds a step on the branch, so it runs only on a match.
    workflow.reload_graph()
    slack = create_node(
        ctx.user,
        workflow,
        "smtp_email",
        label="Slack",
        reference_node_id=router["id"] if at_head else email["id"],
        output=str(edge.uid) if at_head else "",
    )
    workflow.reload_graph()
    before = deepcopy(workflow.graph)
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)

    (action,) = ActionHandler.undo(ctx.user, scope, session)

    assert "AutomationNodeNotDeletable" in action.error
    assert f"node {slack.id}" in action.error
    workflow.reload_graph()
    assert workflow.graph == before


def _undo_router_insert_queries(ctx, automation, table, length):
    workflow, trigger = create_workflow(ctx.user, automation, f"Flow {length}", table)
    add_nodes(
        ctx,
        workflow.id,
        [_email(ref="e0", previous=str(trigger.id))]
        + [_email(ref=f"e{i}", previous=f"e{i - 1}") for i in range(1, length)],
    )
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="Big",
            )
        ],
    )["created_nodes"]
    workflow.reload_graph()
    _email_node(ctx, workflow, AutomationNode.objects.get(id=router["id"]), "Other")
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)
    with CaptureQueriesContext(connection) as queries:
        (action,) = ActionHandler.undo(ctx.user, scope, session)
    assert not action.error
    return len(queries)


@pytest.mark.django_db
def test_undo_router_insert_checks_the_chain_in_a_fixed_number_of_queries(
    automation_ctx,
):
    ctx, automation, table, _ = automation_ctx

    short = _undo_router_insert_queries(ctx, automation, table, 2)
    long = _undo_router_insert_queries(ctx, automation, table, 10)

    assert long == short


@pytest.mark.django_db
def test_undo_router_insert_checks_the_chain_under_the_graph_lock(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="Big",
            )
        ],
    )["created_nodes"]
    workflow.reload_graph()
    other = _email_node(
        ctx, workflow, AutomationNode.objects.get(id=router["id"]), "Other"
    )
    workflow.reload_graph()
    stale = deepcopy(workflow.graph)
    # Another session adds a router with branches at the end of the Big chain
    # after the undo read the graph, but before it took the lock.
    router2 = create_node(
        ctx.user,
        workflow,
        "router",
        reference_node_id=email["id"],
        service={"edges": [{"uid": str(uuid4()), "label": "Small"}]},
    )
    workflow.reload_graph()
    before = deepcopy(workflow.graph)
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)
    get_node = AutomationNodeHandler.get_node

    stale_reads = [router["id"]]

    def get_node_reading_stale_graph(self, node_id, *args, **kwargs):
        node = get_node(self, node_id, *args, **kwargs)
        if node_id in stale_reads:
            stale_reads.remove(node_id)
            node.workflow.reload_graph()
            node.workflow.graph.clear()
            node.workflow.graph.update(deepcopy(stale))
        return node

    with patch.object(AutomationNodeHandler, "get_node", get_node_reading_stale_graph):
        (action,) = ActionHandler.undo(ctx.user, scope, session)

    assert not stale_reads
    assert action.error and "AutomationNodeNotDeletable" in action.error
    workflow.reload_graph()
    assert workflow.graph == before
    assert workflow.graph[str(email["id"])]["next"] == {"": [router2.id]}
    assert AutomationNode.objects.filter(id=other.id).exists()


@pytest.mark.django_db
def test_redo_router_insert_broadcasts_the_final_graph_once(
    automation_ctx, django_capture_on_commit_callbacks
):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    (router,) = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="Big",
            )
        ],
    )["created_nodes"]
    scope = [WorkflowActionScopeType.value(workflow.id)]
    session = get_untrusted_client_session_id(ctx.user)
    ActionHandler.undo(ctx.user, scope, session)

    with patch(
        "baserow.contrib.automation.workflows.ws.signals.broadcast_to_permitted_users"
    ) as broadcast:
        with django_capture_on_commit_callbacks(execute=True):
            ActionHandler.redo(ctx.user, scope, session)

    updates = [
        call.args[4]["workflow"]
        for call in broadcast.delay.call_args_list
        if call.args[4]["type"] == "automation_workflow_updated"
    ]
    (update,) = updates
    assert list(update["graph"][str(router["id"])]["next"].values()) == [[email["id"]]]


@pytest.mark.django_db
def test_add_nodes_router_at_the_end_keeps_no_branch_for_undo(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="router",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="Big",
            )
        ],
    )

    # Nothing moved onto the branch, so undo and redo leave it alone.
    assert Action.objects.latest("id").params["next_output"] == ""


@pytest.mark.django_db
def test_add_nodes_reads_the_graph_a_cached_handler_missed(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    stale = deepcopy(workflow.get_graph().graph)
    (other,) = add_nodes(
        ctx, workflow.id, [_email(ref="other", previous=str(email["id"]))]
    )["created_nodes"]
    # As in a Kuma run, where an earlier call's handler stays cached after
    # another session changed the graph.
    cached = workflow.get_graph().graph
    cached.clear()
    cached.update(stale)

    (log,) = add_nodes(ctx, workflow.id, [_email(ref="log", previous=str(trigger.id))])[
        "created_nodes"
    ]

    assert [node["id"] for node in list_nodes(ctx, workflow.id)["nodes"]] == [
        trigger.id,
        log["id"],
        email["id"],
        other["id"],
    ]


@pytest.mark.django_db
def test_add_nodes_router_before_a_node_needs_its_branch_chosen(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    (email,) = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])[
        "created_nodes"
    ]
    before = deepcopy(workflow.get_graph().graph)
    router = {
        "type": "router",
        "previous_node_ref": str(trigger.id),
        "edges": [{"label": "Big", "condition": "true"}],
    }

    with pytest.raises(DjangoValidationError, match="'Big' or 'default'"):
        add_nodes(
            ctx,
            workflow.id,
            # The first node is fine; the router after it is not.
            [
                _email(ref="log", previous=str(trigger.id)),
                ActionNodeCreate(ref="r", **{**router, "previous_node_ref": "log"}),
            ],
        )

    workflow.reload_graph()
    assert workflow.graph == before
    assert AutomationNode.objects.filter(workflow=workflow).count() == 2

    result = add_nodes(
        ctx,
        workflow.id,
        [ActionNodeCreate(ref="r", shifted_node_edge_label="Default", **router)],
    )

    (created,) = result["created_nodes"]
    assert workflow.get_graph().graph[str(created["id"])]["next"] == {"": [email["id"]]}


@pytest.mark.django_db
def test_add_nodes_router_before_a_node_of_the_call_names_it_by_ref(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    with pytest.raises(DjangoValidationError, match="before node 'a'"):
        add_nodes(
            ctx,
            workflow.id,
            [
                _email(ref="a", previous=str(trigger.id)),
                ActionNodeCreate(
                    ref="r",
                    type="router",
                    previous_node_ref=str(trigger.id),
                    edges=[{"label": "Big", "condition": "true"}],
                    shifted_node_edge_label="",
                ),
            ],
        )

    assert AutomationNode.objects.filter(workflow=workflow).count() == 1


@pytest.mark.django_db
def test_add_nodes_router_at_the_end_takes_an_empty_shifted_label(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    result = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="r",
                type="router",
                previous_node_ref=str(trigger.id),
                edges=[{"label": "Big", "condition": "true"}],
                shifted_node_edge_label="",
            ),
            _email(ref="after", previous="r", router_edge_label="default"),
        ],
    )

    router, after = result["created_nodes"]
    graph = workflow.get_graph().graph
    assert graph[str(router["id"])]["next"] == {"": [after["id"]]}


def test_add_nodes_rejects_a_shifted_node_edge_label_the_router_lacks():
    with pytest.raises(PydanticValidationError, match="'Big' is not a branch"):
        ActionNodeCreate(
            ref="router",
            type="router",
            previous_node_ref="1",
            edges=[{"label": "Small", "condition": "true"}],
            shifted_node_edge_label="Big",
        )


@pytest.mark.parametrize("shifted", ["default", "Default"])
def test_add_nodes_rejects_default_when_a_branch_is_named_default(shifted):
    # A branch named Default would hide the default branch: there would be no way
    # left to shift the node onto the default branch.
    with pytest.raises(PydanticValidationError, match="Rename that branch"):
        ActionNodeCreate(
            ref="router",
            type="router",
            previous_node_ref="1",
            edges=[{"label": "Default", "condition": "true"}],
            shifted_node_edge_label=shifted,
        )


@pytest.mark.django_db
def test_add_nodes_after_the_last_node_shifts_nothing(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    result = add_nodes(ctx, workflow.id, [_email(previous=str(trigger.id))])

    assert "shifted_nodes" not in result


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
    workflow.refresh_from_db()
    assert workflow.graph[str(router.id)]["next"][big] == [created["id"]]


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
                subject=f"get('previous_node.{trigger.id}.0.id')",
                body="$formula: the name",
            )
        ],
    )

    (error,) = result["formula_errors"]
    assert (error["node_id"], error["field"]) == (mail.id, "body")
    service = mail.service.specific
    service.refresh_from_db()
    assert service.subject["formula"] == f"get('previous_node.{trigger.id}.0.id')"
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
def test_delete_nodes_keeps_a_node_whose_deletion_failed_in_the_graph(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    first = _email_node(ctx, workflow, trigger, "First")
    second = _email_node(ctx, workflow, first, "Second")
    register_action = DeleteAutomationNodeActionType.register_action
    calls = []

    def fail_first(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("lock timeout")
        return register_action(*args, **kwargs)

    with (
        local_cache.context(),
        patch.object(DeleteAutomationNodeActionType, "register_action", fail_first),
    ):
        result = delete_nodes(ctx, [first.id, second.id])

    assert result["deleted_node_ids"] == [second.id]
    with local_cache.context():
        trigger = AutomationNode.objects.get(id=trigger.id)
        assert [node.id for node in trigger.get_next_points()] == [first.id]


@pytest.mark.django_db
def test_update_nodes_rejects_a_node_given_twice(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    mail = _email_node(ctx, workflow, trigger, "Mail")

    with pytest.raises(DjangoValidationError, match=f"Node {mail.id} is given more"):
        update_nodes(
            ctx,
            workflow.id,
            [
                NodeUpdate(node_id=mail.id, subject="concat("),
                NodeUpdate(node_id=mail.id, subject="After"),
            ],
        )

    assert mail.service.specific.subject["formula"] == "'Before'"


@pytest.mark.django_db
def test_add_nodes_reports_nothing_for_an_html_email(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    result = add_nodes(
        ctx, workflow.id, [_email(previous=str(trigger.id), body_type="html")]
    )

    assert "errors" not in result
    node = AutomationNode.objects.get(id=result["created_nodes"][0]["id"])
    assert node.service.specific.body_type == "html"


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


@pytest.mark.django_db
def test_add_nodes_maps_a_field_given_twice_once(automation_ctx):
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
                values=[
                    {"field_id": name.id, "value": "first"},
                    {"field_id": name.id, "value": "second"},
                ],
            )
        ],
    )

    service = AutomationNode.objects.get(
        id=result["created_nodes"][0]["id"]
    ).service.specific
    assert [m.value["formula"] for m in service.field_mappings.all()] == ["'second'"]


@pytest.mark.django_db
def test_add_nodes_reports_values_the_node_type_takes_no(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)

    result = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="slack",
                type="slack_write_message",
                previous_node_ref=str(trigger.id),
                channel="general",
                text="Hi",
                subject="Ignored",
                table_id=999999,
            )
        ],
    )

    (slack,) = result["created_nodes"]
    assert result["errors"] == [
        f"Node {slack['id']} ({slack['label']}): A slack_write_message node takes "
        "no subject, table_id, so they were not set."
    ]


@pytest.mark.django_db
def test_update_nodes_reports_values_the_node_type_takes_no(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    mail = _email_node(ctx, workflow, trigger, "Mail")

    result = update_nodes(ctx, workflow.id, [NodeUpdate(node_id=mail.id, text="Hi")])

    assert result == {
        "updated_nodes": [],
        "errors": [
            f"Node {mail.id} (Mail): A smtp_email node takes no text, so it was not "
            "set."
        ],
    }


@pytest.mark.django_db
def test_update_nodes_lists_only_nodes_that_changed(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    mail = _email_node(ctx, workflow, trigger, "Mail")
    other = _email_node(ctx, workflow, mail, "Other")

    result = update_nodes(
        ctx,
        workflow.id,
        [
            NodeUpdate(node_id=mail.id, subject="concat("),
            NodeUpdate(node_id=other.id, subject="New"),
        ],
    )

    assert result["updated_nodes"] == [{"node_id": other.id, "label": "Other"}]
    assert result["formula_errors"][0]["node_id"] == mail.id


@pytest.mark.django_db
def test_update_nodes_leaves_a_router_alone_when_no_condition_is_valid(
    automation_ctx,
):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    router = create_node(
        ctx.user,
        workflow,
        "router",
        reference_node_id=trigger.id,
        service={"edges": [{"uid": str(uuid4()), "label": "Big"}]},
    )
    actions = Action.objects.count()

    result = update_nodes(
        ctx,
        workflow.id,
        [NodeUpdate(node_id=router.id, edges=[{"label": "Big", "condition": "if("}])],
    )

    assert result["updated_nodes"] == []
    assert result["formula_errors"][0]["edge_label"] == "Big"
    assert Action.objects.count() == actions


@pytest.mark.django_db
def test_list_nodes_names_the_container_of_a_child(automation_ctx, data_fixture):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow, reference_node=trigger
    )
    child = data_fixture.create_automation_node(
        workflow=workflow, reference_node=iterator, position="child"
    )

    nodes = {node["id"]: node for node in list_nodes(ctx, workflow.id)["nodes"]}

    assert nodes[child.id]["parent_node_id"] == iterator.id
    assert "previous_node_ref" not in nodes[child.id]
    assert nodes[iterator.id]["previous_node_ref"] == str(trigger.id)


@pytest.mark.django_db
def test_update_nodes_keeps_a_branch_listed_without_a_condition(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    router = create_node(
        ctx.user,
        workflow,
        "router",
        reference_node_id=trigger.id,
        service={
            "edges": [
                {"uid": str(uuid4()), "label": "Big"},
                {"uid": str(uuid4()), "label": "Small"},
            ]
        },
    )

    result = update_nodes(
        ctx,
        workflow.id,
        [
            NodeUpdate(
                node_id=router.id,
                edges=[{"label": "Big", "condition": "true"}, {"label": "Small"}],
            )
        ],
    )

    assert result == {"updated_nodes": [{"node_id": router.id, "label": router.label}]}
    edges = {
        edge.label: edge.condition["formula"]
        for edge in router.service.specific.edges.all()
    }
    assert edges == {"Big": "true", "Small": ""}


def test_node_refs_refuses_default_when_two_branches_match_it():
    refs = NodeRefs()
    refs.add("router", 1, {"Default": "uid1", "DEFAULT": "uid2"})

    assert refs.resolve("router", "Default") == (1, "uid1")
    with pytest.raises(
        DjangoValidationError,
        match="matches several branches.*or leave router_edge_label out",
    ):
        refs.resolve("router", "default")
    refs.add("yes", 3, {"Yes": "uid4", "YES": "uid5"})
    with pytest.raises(DjangoValidationError) as error:
        refs.resolve("yes", "yes")
    assert "matches several branches" in str(error.value)
    assert "leave router_edge_label out" not in str(error.value)
    refs.add("plain", 2, {"Big": "uid3"})
    assert refs.resolve("plain", "default") == (2, "")
