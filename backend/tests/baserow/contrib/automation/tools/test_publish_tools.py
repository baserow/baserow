"""Tests for publish_workflow and pause_workflow, shared by MCP and Kuma."""

from threading import Thread
from unittest.mock import patch

from django.db import connection, transaction

import pytest

from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.tools import workflows as workflows_tools
from baserow.contrib.automation.tools.automations import create_automation
from baserow.contrib.automation.tools.nodes import update_nodes
from baserow.contrib.automation.tools.types import NodeUpdate, WorkflowCreate
from baserow.contrib.automation.tools.workflows import (
    create_workflows,
    describe_workflow,
    pause_workflow,
    publish_workflow,
)
from baserow.contrib.automation.workflows.actions import (
    UpdateAutomationWorkflowActionType,
)
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.operations import (
    PublishAutomationWorkflowOperationType,
    UpdateAutomationWorkflowOperationType,
)
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError

from .conftest import create_node, create_workflow


class Built:
    """Orders and Log tables, and a draft workflow that logs every new order."""

    def __init__(self, data_fixture):
        user = data_fixture.create_user()
        workspace = data_fixture.create_workspace(user=user)
        self.ctx = ToolContext(user=user, workspace=workspace)
        database = data_fixture.create_database_application(workspace=workspace)
        self.orders = data_fixture.create_database_table(
            database=database, name="Orders"
        )
        self.orders_name = data_fixture.create_text_field(
            table=self.orders, name="Name", primary=True
        )
        self.log = data_fixture.create_database_table(database=database, name="Log")
        self.log_name = data_fixture.create_text_field(
            table=self.log, name="Name", primary=True
        )
        automation_id = create_automation(self.ctx, "Flows")["created_automation"]["id"]
        self.automation = Automation.objects.get(id=automation_id)
        (self.workflow,) = self.create(
            "Log new orders",
            {
                "ref": "log",
                "label": "Log it",
                "type": "create_row",
                "previous_node_ref": "trigger",
                "table_id": self.log.id,
                "values": [{"field_id": self.log_name.id, "value": "Written"}],
            },
        )["created_workflows"]

    @property
    def user(self):
        return self.ctx.user

    def create(self, name, *nodes):
        return create_workflows(
            self.ctx,
            self.automation.id,
            [
                WorkflowCreate.model_validate(
                    {
                        "name": name,
                        "trigger": {
                            "ref": "trigger",
                            "label": "Order created",
                            "type": "rows_created",
                            "rows_triggers_settings": {"table_id": self.orders.id},
                        },
                        "nodes": list(nodes),
                    }
                )
            ],
        )

    def node(self, label, workflow_id=None):
        return AutomationNode.objects.get(
            workflow_id=workflow_id or self.workflow["id"], label=label
        )

    def order(self):
        RowHandler().create_rows(
            self.user, self.orders, [{self.orders_name.db_column: "go"}]
        )

    def logged(self):
        rows = self.log.get_model().objects.order_by("id")
        return [getattr(row, self.log_name.db_column) for row in rows]


def _published(workflow_id):
    return AutomationWorkflow.objects.filter(automation__published_from=workflow_id)


def _state(workflow_id):
    workflow = AutomationWorkflow.objects.get(id=workflow_id)
    return describe_workflow(workflow)["state"]


@pytest.mark.django_db(transaction=True)
def test_edits_reach_the_live_workflow_only_after_publishing_again(data_fixture):
    built = Built(data_fixture)
    workflow_id = built.workflow["id"]
    publish_workflow(built.ctx, workflow_id)

    update_nodes(
        built.ctx,
        workflow_id,
        [
            NodeUpdate.model_validate(
                {
                    "node_id": built.node("Log it").id,
                    "values": [{"field_id": built.log_name.id, "value": "Edited"}],
                }
            )
        ],
    )

    built.order()
    assert built.logged() == ["Written"]

    publish_workflow(built.ctx, workflow_id)
    assert _state(workflow_id) == "live"

    built.order()
    assert built.logged() == ["Written", "Edited"]


def _delete_node(user, node_id):
    try:
        with transaction.atomic():
            AutomationNodeService().delete_node(user, node_id)
    finally:
        connection.close()


def _update_node(user, node_id, **values):
    try:
        with transaction.atomic():
            AutomationNodeService().update_node(user, node_id, **values)
    finally:
        connection.close()


def _while_publishing(target, *args, **kwargs):
    """
    Runs `target` from another connection when the publication starts, after
    anything the tool checks on the draft beforehand.
    """

    publish = AutomationWorkflowService.publish
    other = Thread(target=target, args=args, kwargs=kwargs)

    def publish_after_the_other_request(self, *publish_args, **kwargs):
        other.start()
        other.join(timeout=5)
        return publish(self, *publish_args, **kwargs)

    return other, patch.object(
        AutomationWorkflowService, "publish", publish_after_the_other_request
    )


@pytest.mark.django_db(transaction=True)
def test_an_action_deleted_while_publishing_waits_for_the_publication(data_fixture):
    built = Built(data_fixture)
    log_node = built.node("Log it")
    check = workflows_tools.check_workflow_can_run
    deletion = Thread(target=_delete_node, args=(built.user, log_node.id))
    waited = []

    def check_then_delete(ctx, published):
        warnings = check(ctx, published)
        # Another request deletes the action after the checks ran.
        deletion.start()
        deletion.join(timeout=2)
        waited.append(deletion.is_alive())
        return warnings

    with patch.object(workflows_tools, "check_workflow_can_run", check_then_delete):
        with transaction.atomic():
            publish_workflow(built.ctx, built.workflow["id"])
    deletion.join(timeout=30)

    assert waited == [True]
    assert not AutomationNode.objects.filter(id=log_node.id).exists()
    built.order()
    assert built.logged() == ["Written"]


@pytest.mark.django_db(transaction=True)
def test_a_row_id_cleared_while_publishing_is_reported(data_fixture):
    built = Built(data_fixture)
    (workflow,) = built.create(
        "Change row",
        {
            "ref": "change",
            "label": "Change it",
            "type": "update_row",
            "previous_node_ref": "trigger",
            "table_id": built.log.id,
            "row_id": "1",
            "values": [{"field_id": built.log_name.id, "value": "Changed"}],
        },
    )["created_workflows"]
    node = built.node("Change it", workflow["id"])
    # An edit of the node's service only, as the editor sends it.
    other, patched = _while_publishing(
        _update_node, built.user, node.id, service={"row_id": ""}
    )

    with patched:
        with transaction.atomic():
            result = publish_workflow(built.ctx, workflow["id"])
    other.join(timeout=30)

    published = AutomationNode.objects.get(
        workflow__automation__published_from_id=workflow["id"], label="Change it"
    )
    assert published.service.specific.row_id["formula"] == ""
    assert result["published_workflow"]["state"] == "live"
    assert result["warnings"] == [
        f"Node {node.id} (Change it): A row ID is required to update a row. "
        "Every run fails here."
    ]


@pytest.mark.django_db(transaction=True)
def test_a_refused_publication_leaves_the_live_copy_running(data_fixture):
    built = Built(data_fixture)
    workflow_id = built.workflow["id"]
    publish_workflow(built.ctx, workflow_id)
    (live,) = _published(workflow_id)
    log_node = built.node("Log it")
    other, patched = _while_publishing(_delete_node, built.user, log_node.id)

    with patched, pytest.raises(ToolInputError, match="no action after its trigger"):
        with transaction.atomic():
            publish_workflow(built.ctx, workflow_id)
    other.join(timeout=30)

    assert not AutomationNode.objects.filter(id=log_node.id).exists()
    assert list(_published(workflow_id)) == [live]
    live.refresh_from_db()
    assert live.state == WorkflowState.LIVE
    built.order()
    assert built.logged() == ["Written"]


def _deny(operation_type):
    check_permissions = CoreHandler.check_permissions

    def deny(self, actor, operation_name, *args, **kwargs):
        if operation_name == operation_type:
            raise PermissionException(actor)
        return check_permissions(self, actor, operation_name, *args, **kwargs)

    return patch.object(CoreHandler, "check_permissions", deny)


@pytest.mark.django_db
def test_publish_needs_the_publish_permission(automation_ctx):
    ctx, automation, _, _ = automation_ctx
    workflow, _ = create_workflow(ctx.user, automation)

    with _deny(PublishAutomationWorkflowOperationType.type):
        with pytest.raises(PermissionException):
            publish_workflow(ctx, workflow.id)

    assert not _published(workflow.id).exists()


@pytest.mark.django_db
def test_publish_refuses_a_workflow_of_another_workspace(data_fixture, automation_ctx):
    ctx, _, _, _ = automation_ctx
    # The user is a member of the other workspace too.
    other = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=ctx.user)
    )
    workflow, _ = create_workflow(ctx.user, other)

    with pytest.raises(AutomationWorkflowDoesNotExist):
        publish_workflow(ctx, workflow.id)

    assert not _published(workflow.id).exists()


@pytest.mark.django_db
def test_publish_refuses_the_published_copy_itself(data_fixture):
    built = Built(data_fixture)
    publish_workflow(built.ctx, built.workflow["id"])
    copy = _published(built.workflow["id"]).get()

    with pytest.raises(AutomationWorkflowDoesNotExist):
        publish_workflow(built.ctx, copy.id)


def _add_create_row_node(user, workflow, reference_node):
    """An action node after the reference node, with no table."""

    return create_node(
        user,
        workflow,
        "local_baserow_create_row",
        service={},
        reference_node_id=reference_node.id,
    )


@pytest.mark.django_db
def test_publish_refuses_untrusted_content_like_the_api(automation_ctx):
    ctx, automation, _, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation)
    _add_create_row_node(ctx.user, workflow, trigger)
    workflow.untrusted_content = True
    workflow.save(update_fields=["untrusted_content"])

    with pytest.raises(ToolInputError) as error:
        publish_workflow(ctx, workflow.id)

    assert str(error.value) == (
        "Review and trust the imported content before publishing."
    )
    assert not _published(workflow.id).exists()


@pytest.mark.django_db
def test_publish_refuses_a_workflow_without_a_trigger(data_fixture, automation_ctx):
    ctx, automation, _, _ = automation_ctx
    workflow = data_fixture.create_automation_workflow(
        user=ctx.user, automation=automation, create_trigger=False
    )

    with pytest.raises(ToolInputError) as error:
        publish_workflow(ctx, workflow.id)

    assert str(error.value) == (
        "This workflow has no trigger, so it would never run. Nothing was published."
    )
    assert not _published(workflow.id).exists()


@pytest.mark.django_db
def test_publish_refuses_a_workflow_with_nothing_after_its_trigger(automation_ctx):
    ctx, automation, _, _ = automation_ctx
    workflow, _ = create_workflow(ctx.user, automation)

    with pytest.raises(ToolInputError) as error:
        publish_workflow(ctx, workflow.id)

    assert str(error.value) == (
        "This workflow has no action after its trigger, so it would do nothing. "
        "Nothing was published."
    )
    assert not _published(workflow.id).exists()


@pytest.mark.django_db
def test_publish_refuses_a_workflow_whose_nodes_were_all_deleted(data_fixture):
    built = Built(data_fixture)
    workflow_id = built.workflow["id"]
    nodes = AutomationNode.objects.filter(workflow_id=workflow_id)
    for node in nodes.order_by("-id"):
        AutomationNodeService().delete_node(built.user, node.id)

    with pytest.raises(ToolInputError, match="no trigger"):
        publish_workflow(built.ctx, workflow_id)

    assert not _published(workflow_id).exists()


@pytest.mark.django_db
def test_publish_warns_about_a_row_trigger_and_action_with_no_table(automation_ctx):
    ctx, automation, _, _ = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation)
    action = _add_create_row_node(ctx.user, workflow, trigger)

    result = publish_workflow(ctx, workflow.id)

    assert result["published_workflow"]["state"] == "live"
    assert result["warnings"] == [
        f"Node {trigger.id} ({trigger.label}): No table is selected. It never fires.",
        f"Node {action.id} ({action.label}): No table is selected. "
        "Every run fails here.",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_type,warning",
    [
        ("update_row", "A row ID is required to update a row. Every run fails here."),
        # A delete with no row ID deletes nothing, it doesn't fail.
        ("delete_row", "No row ID is set, so every run deletes nothing."),
    ],
)
def test_publish_warns_about_a_row_id_left_empty_by_a_bad_formula(
    data_fixture, node_type, warning
):
    built = Built(data_fixture)
    values = (
        {"values": [{"field_id": built.log_name.id, "value": "Changed"}]}
        if node_type == "update_row"
        else {}
    )
    created = built.create(
        "Bad row",
        {
            "ref": "change",
            "label": "Change it",
            "type": node_type,
            "previous_node_ref": "trigger",
            "table_id": built.log.id,
            "row_id": "get('previous_node.nothing.0.id')",
            **values,
        },
    )
    (workflow,) = created["created_workflows"]
    assert created["formula_errors"][0]["field"] == "row_id"
    node = built.node("Change it", workflow["id"])

    result = publish_workflow(built.ctx, workflow["id"])

    assert result["warnings"] == [f"Node {node.id} (Change it): {warning}"]


@pytest.mark.django_db
@pytest.mark.parametrize("empty_row_id", ["", "''"])
def test_publish_warns_about_a_row_id_emptied_by_an_update(data_fixture, empty_row_id):
    built = Built(data_fixture)
    (workflow,) = built.create(
        "Emptied row",
        {
            "ref": "change",
            "label": "Change it",
            "type": "update_row",
            "previous_node_ref": "trigger",
            "table_id": built.log.id,
            "row_id": "1",
            "values": [{"field_id": built.log_name.id, "value": "Changed"}],
        },
    )["created_workflows"]
    node = built.node("Change it", workflow["id"])
    update_nodes(
        built.ctx,
        workflow["id"],
        [NodeUpdate.model_validate({"node_id": node.id, "row_id": empty_row_id})],
    )
    node = AutomationNode.objects.get(id=node.id).specific
    assert node.service.specific.row_id["formula"] == ""

    result = publish_workflow(built.ctx, workflow["id"])

    assert result["warnings"] == [
        f"Node {node.id} (Change it): A row ID is required to update a row. "
        "Every run fails here."
    ]


@pytest.mark.django_db
def test_create_workflows_reports_the_state_of_a_reused_live_workflow(data_fixture):
    built = Built(data_fixture)
    publish_workflow(built.ctx, built.workflow["id"])

    result = built.create("Log new orders")

    assert result["reused_workflows"][0]["state"] == "live"


@pytest.mark.django_db(transaction=True)
def test_pause_stops_a_live_workflow_until_it_is_published_again(data_fixture):
    built = Built(data_fixture)
    workflow_id = built.workflow["id"]
    publish_workflow(built.ctx, workflow_id)
    built.order()
    assert built.logged() == ["Written"]
    runs = AutomationWorkflowHistory.objects.filter(original_workflow=workflow_id)
    assert runs.count() == 1

    result = pause_workflow(built.ctx, workflow_id)

    assert result == {
        "paused_workflow": {
            "id": workflow_id,
            "name": "Log new orders",
            "state": "paused",
        },
        "changed": True,
    }
    assert _state(workflow_id) == "paused"

    # An event neither starts a run nor writes a row.
    built.order()
    assert built.logged() == ["Written"]
    assert runs.count() == 1

    republished = publish_workflow(built.ctx, workflow_id)
    assert republished["published_workflow"]["state"] == "live"
    assert _state(workflow_id) == "live"

    built.order()
    assert built.logged() == ["Written", "Written"]


@pytest.mark.django_db(transaction=True)
def test_pause_acts_on_the_latest_published_version(data_fixture):
    built = Built(data_fixture)
    workflow_id = built.workflow["id"]
    for _ in range(2):
        publish_workflow(built.ctx, workflow_id)

    pause_workflow(built.ctx, workflow_id)

    built.order()
    assert built.logged() == []
    assert not _published(workflow_id).filter(state=WorkflowState.LIVE).exists()


@pytest.mark.django_db
def test_pause_of_a_paused_workflow_changes_nothing(data_fixture):
    built = Built(data_fixture)
    workflow_id = built.workflow["id"]
    publish_workflow(built.ctx, workflow_id)
    pause_workflow(built.ctx, workflow_id)

    with patch.object(UpdateAutomationWorkflowActionType, "do") as update:
        result = pause_workflow(built.ctx, workflow_id)

    update.assert_not_called()
    assert result["changed"] is False
    assert result["paused_workflow"]["state"] == "paused"


def _pause_survives_cleanup(built):
    AutomationWorkflowHandler().clear_old_history()

    assert _state(built.workflow["id"]) == "paused"
    with patch.object(UpdateAutomationWorkflowActionType, "do") as update:
        result = pause_workflow(built.ctx, built.workflow["id"])
    update.assert_not_called()
    assert result["changed"] is False


@pytest.mark.django_db
def test_a_paused_workflow_survives_the_history_cleanup(data_fixture):
    built = Built(data_fixture)
    publish_workflow(built.ctx, built.workflow["id"])
    pause_workflow(built.ctx, built.workflow["id"])

    _pause_survives_cleanup(built)


@pytest.mark.django_db(transaction=True)
def test_a_paused_workflow_with_an_older_run_survives_the_history_cleanup(
    data_fixture,
):
    built = Built(data_fixture)
    workflow_id = built.workflow["id"]
    publish_workflow(built.ctx, workflow_id)
    built.order()
    assert built.logged() == ["Written"]
    publish_workflow(built.ctx, workflow_id)
    pause_workflow(built.ctx, workflow_id)

    _pause_survives_cleanup(built)

    # It can be made live again from the update the UI uses.
    AutomationWorkflowHandler().update_workflow(
        AutomationWorkflow.objects.get(id=workflow_id), state=WorkflowState.LIVE
    )
    assert _state(workflow_id) == "live"


@pytest.mark.django_db
def test_pause_refuses_a_workflow_never_published(automation_ctx):
    ctx, automation, _, _ = automation_ctx
    workflow, _ = create_workflow(ctx.user, automation)

    with pytest.raises(ToolInputError) as error:
        pause_workflow(ctx, workflow.id)

    assert str(error.value) == (
        "This workflow has never been published, so it isn't running and there is "
        "nothing to pause."
    )


@pytest.mark.django_db
def test_pause_leaves_a_disabled_workflow_disabled(data_fixture):
    built = Built(data_fixture)
    workflow_id = built.workflow["id"]
    publish_workflow(built.ctx, workflow_id)
    _published(workflow_id).update(state=WorkflowState.DISABLED)

    with pytest.raises(ToolInputError) as error:
        pause_workflow(built.ctx, workflow_id)

    assert str(error.value) == (
        "This workflow was disabled after too many failed runs, so it isn't running "
        "and stays disabled. Publishing it again makes it live."
    )
    assert _state(workflow_id) == "disabled"


@pytest.mark.django_db
def test_pause_refuses_a_workflow_of_another_workspace(data_fixture, automation_ctx):
    ctx, _, _, _ = automation_ctx
    other = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=ctx.user)
    )
    workflow, _ = create_workflow(ctx.user, other)

    with pytest.raises(AutomationWorkflowDoesNotExist):
        pause_workflow(ctx, workflow.id)


@pytest.mark.django_db
def test_pause_needs_the_update_permission(automation_ctx):
    ctx, automation, _, _ = automation_ctx
    workflow, _ = create_workflow(ctx.user, automation)

    with _deny(UpdateAutomationWorkflowOperationType.type):
        with pytest.raises(PermissionException):
            pause_workflow(ctx, workflow.id)
