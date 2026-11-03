"""Tests for the workflow read tools shared by MCP and Kuma."""

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.automation.tools.workflows import (
    get_workflow_in_workspace,
    list_workflows,
)
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.tools import ToolContext

from .conftest import create_workflow


@pytest.mark.django_db
def test_list_workflows_without_an_id_lists_every_automation(
    data_fixture, automation_ctx
):
    ctx, automation, table, _ = automation_ctx
    second = data_fixture.create_automation_application(
        workspace=ctx.workspace, name="Second"
    )
    first_flow, _ = create_workflow(ctx.user, automation, "First flow", table)
    second_flow, _ = create_workflow(ctx.user, automation, "Second flow", table)
    # In another workspace of the same user.
    other = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=ctx.user)
    )
    create_workflow(ctx.user, other, "Elsewhere")

    result = list_workflows(ctx)

    assert result == {
        "automations": [
            {
                "id": automation.id,
                "name": automation.name,
                "workflows": [
                    {"id": first_flow.id, "name": "First flow", "state": "draft"},
                    {"id": second_flow.id, "name": "Second flow", "state": "draft"},
                ],
            },
            {"id": second.id, "name": "Second", "workflows": []},
        ]
    }


@pytest.mark.django_db
def test_list_workflows_of_one_automation(data_fixture, automation_ctx):
    ctx, automation, table, _ = automation_ctx
    data_fixture.create_automation_application(workspace=ctx.workspace)
    flow, _ = create_workflow(ctx.user, automation, "Flow", table)

    result = list_workflows(ctx, automation.id)

    assert result["automations"] == [
        {
            "id": automation.id,
            "name": automation.name,
            "workflows": [{"id": flow.id, "name": "Flow", "state": "draft"}],
        }
    ]


@pytest.mark.django_db
def test_list_workflows_of_an_automation_elsewhere_is_not_found(
    data_fixture, automation_ctx
):
    ctx, *_ = automation_ctx
    member_of = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=ctx.user)
    )
    not_member_of = data_fixture.create_automation_application()

    for automation_id in (member_of.id, not_member_of.id, 999999):
        with pytest.raises(ApplicationDoesNotExist):
            list_workflows(ctx, automation_id)


@pytest.mark.django_db
def test_get_workflow_in_workspace_hides_other_workspaces(data_fixture, automation_ctx):
    ctx, automation, table, _ = automation_ctx
    flow, _ = create_workflow(ctx.user, automation, "Flow", table)
    member_of = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=ctx.user)
    )
    member_flow, _ = create_workflow(ctx.user, member_of)
    stranger = data_fixture.create_user()
    stranger_flow, _ = create_workflow(
        stranger, data_fixture.create_automation_application(user=stranger)
    )

    assert get_workflow_in_workspace(ctx, flow.id) == flow
    for workflow_id in (member_flow.id, stranger_flow.id, 999999):
        with pytest.raises(AutomationWorkflowDoesNotExist):
            get_workflow_in_workspace(ctx, workflow_id)


@pytest.mark.django_db
def test_list_workflows_skips_trashed_workflows(data_fixture, automation_ctx):
    ctx, automation, table, _ = automation_ctx
    flow, _ = create_workflow(ctx.user, automation, "Flow", table)
    flow.trashed = True
    flow.save()

    assert list_workflows(ctx, automation.id)["automations"][0]["workflows"] == []
    with pytest.raises(AutomationWorkflowDoesNotExist):
        get_workflow_in_workspace(ToolContext(ctx.user, ctx.workspace), flow.id)


def _publish(workflow):
    with transaction.atomic():
        return AutomationWorkflowHandler().publish(workflow)


def _states(ctx):
    (automation,) = list_workflows(ctx)["automations"]
    return {flow["name"]: flow["state"] for flow in automation["workflows"]}


@pytest.mark.django_db
def test_list_workflows_tells_a_draft_from_a_live_one(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    live, _ = create_workflow(ctx.user, automation, "Live", table)
    create_workflow(ctx.user, automation, "Draft", table)

    _publish(live)

    assert _states(ctx) == {"Live": "live", "Draft": "draft"}


@pytest.mark.django_db
@pytest.mark.parametrize("state", [WorkflowState.PAUSED, WorkflowState.DISABLED])
def test_list_workflows_reports_the_state_of_the_published_version(
    automation_ctx, state
):
    ctx, automation, table, _ = automation_ctx
    workflow, _ = create_workflow(ctx.user, automation, "Flow", table)
    published = _publish(workflow)
    published.state = state
    published.save(update_fields=["state"])

    assert _states(ctx) == {"Flow": state.value}


@pytest.mark.django_db
def test_list_workflows_keeps_a_test_run_copy_a_draft(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, _ = create_workflow(ctx.user, automation, "Flow", table)

    AutomationWorkflowHandler()._ensure_published_for_run(workflow)

    assert _states(ctx) == {"Flow": "draft"}


@pytest.mark.django_db
def test_list_workflows_runs_no_query_per_workflow(automation_ctx):
    ctx, automation, table, _ = automation_ctx
    workflow, _ = create_workflow(ctx.user, automation, "First", table)
    _publish(workflow)
    # The first call fills caches, which would hide an extra query.
    list_workflows(ctx)
    with CaptureQueriesContext(connection) as one_workflow:
        list_workflows(ctx)

    for name in ("Second", "Third", "Fourth"):
        workflow, _ = create_workflow(ctx.user, automation, name, table)
        _publish(workflow)
    with CaptureQueriesContext(connection) as four_workflows:
        list_workflows(ctx)

    assert len(four_workflows) == len(one_workflow)
