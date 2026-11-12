from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

import pytest

from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.database.table.actions import CreateTableActionType
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.exceptions import PermissionException
from baserow.core.service import CoreService


@pytest.mark.django_db
@pytest.mark.parametrize("is_template", [True, False], ids=["template", "private"])
def test_shared_read_layers_preserve_anonymous_template_boundaries(
    data_fixture, is_template
):
    workspace = data_fixture.create_workspace()
    if is_template:
        data_fixture.create_template(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    anonymous = AnonymousUser()

    # These shared services explicitly accept AnonymousUser for template reads;
    # ToolContext itself remains restricted to a User or Identity.
    if is_template:
        # The API authorizes the workspace before passing it into list services.
        authorized_workspace = CoreService().get_workspace(anonymous, workspace.id)
        applications = CoreService().list_applications_in_workspace(
            anonymous, authorized_workspace
        )
        assert {app.id for app in applications} == {database.id, automation.id}
        assert list(
            TableHandler()
            .list_workspace_tables(anonymous, authorized_workspace)
            .values_list("id", flat=True)
        ) == [table.id]
        assert [item.id for item in ViewHandler().list_views(anonymous, table)] == [
            view.id
        ]
        assert ViewHandler().get_view_as_user(anonymous, view.id).id == view.id
        assert [
            node.id for node in AutomationNodeService().get_nodes(anonymous, workflow)
        ] == [workflow.get_trigger().id]
    else:
        with pytest.raises(PermissionException):
            CoreService().get_workspace(anonymous, workspace.id)
        with pytest.raises(PermissionException):
            ViewHandler().get_view_as_user(anonymous, view.id)
        with pytest.raises(PermissionException):
            AutomationNodeService().get_nodes(anonymous, workflow)

    with pytest.raises(PermissionException):
        CreateTableActionType.do(anonymous, database, "Unauthorized")
    assert list(database.table_set.values_list("id", flat=True)) == [table.id]


@pytest.mark.django_db
@pytest.mark.parametrize("is_template", [True, False], ids=["template", "private"])
def test_anonymous_automation_node_api_is_read_only_for_templates(
    api_client, data_fixture, is_template
):
    workflow = data_fixture.create_automation_workflow()
    if is_template:
        data_fixture.create_template(workspace=workflow.automation.workspace)
    trigger = workflow.get_trigger()
    url = reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id})

    response = api_client.get(url)
    assert response.status_code == (200 if is_template else 401)
    if is_template:
        assert [node["id"] for node in response.json()] == [trigger.id]

    response = api_client.post(
        url,
        {"type": "core_smtp_email", "reference_node_id": trigger.id},
        format="json",
    )
    assert response.status_code == 401
    assert workflow.automation_workflow_nodes.count() == 1
