from unittest.mock import patch

from django.urls import reverse

import pytest

from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.core.handler import CoreHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.fixture
def workflow_on_a_secret_table(enterprise_data_fixture):
    """
    A workflow whose trigger reads a table with a "Salary" field, and a user who
    may build the workflow but has no access to the table's database.
    """

    fixture = enterprise_data_fixture
    admin, admin_token = fixture.create_user_and_token()
    workspace = fixture.create_workspace(user=admin)
    automation = fixture.create_automation_application(workspace=workspace)
    table = fixture.create_database_table(
        database=fixture.create_database_application(workspace=workspace)
    )
    salary = fixture.create_single_select_field(table=table, name="Salary")
    fixture.create_select_option(field=salary, value="Over 100k")
    workflow = AutomationWorkflowService().create_workflow(admin, automation.id, "Flow")
    trigger = AutomationNodeService().create_node(
        admin,
        automation_node_type_registry.get("local_baserow_rows_created"),
        workflow,
        service={"table_id": table.id},
    )

    restricted, restricted_token = fixture.create_user_and_token()
    fixture.create_user_workspace(
        user=restricted, workspace=workspace, permissions="NO_ACCESS"
    )
    RoleAssignmentHandler().assign_role(
        restricted,
        workspace,
        role=Role.objects.get(uid="BUILDER"),
        scope=automation.application_ptr,
    )
    return admin, workflow, trigger, admin_token, restricted_token


def _assert_hides_the_table(response, node):
    assert "Salary" not in response.content.decode()
    assert "Over 100k" not in response.content.decode()
    service = node["service"]
    assert service["table_accessible"] is False
    assert service["schema"] is None
    assert service["context_data"] is None
    assert service["context_data_schema"] is None


@pytest.mark.django_db
def test_listing_nodes_hides_the_fields_of_a_table_the_user_cannot_see(
    api_client, workflow_on_a_secret_table
):
    _, workflow, trigger, admin_token, restricted_token = workflow_on_a_secret_table
    url = reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {restricted_token}")

    assert response.status_code == 200
    (node,) = response.json()
    assert node["id"] == trigger.id
    _assert_hides_the_table(response, node)

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {admin_token}")

    assert response.status_code == 200
    (node,) = response.json()
    properties = node["service"]["schema"]["items"]["properties"]
    assert "Salary" in [prop["title"] for prop in properties.values()]
    assert "Over 100k" in response.content.decode()
    assert node["service"]["table_accessible"] is True


@pytest.mark.django_db
def test_updating_a_node_hides_the_fields_of_a_table_the_user_cannot_see(
    api_client, workflow_on_a_secret_table
):
    _, _, trigger, _, restricted_token = workflow_on_a_secret_table

    response = api_client.patch(
        reverse("api:automation:nodes:item", kwargs={"node_id": trigger.id}),
        {"label": "Renamed"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["label"] == "Renamed"
    _assert_hides_the_table(response, response.json())


@pytest.mark.django_db
def test_listing_nodes_checks_each_table_once(api_client, workflow_on_a_secret_table):
    admin, workflow, trigger, _, restricted_token = workflow_on_a_secret_table
    table_id = trigger.service.specific.table_id
    previous = trigger
    for _ in range(3):
        previous = AutomationNodeService().create_node(
            admin,
            automation_node_type_registry.get("local_baserow_create_row"),
            workflow,
            reference_node_id=previous.id,
            service={"table_id": table_id},
        )
    url = reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id})

    with patch.object(
        CoreHandler, "check_permissions", wraps=CoreHandler().check_permissions
    ) as check:
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {restricted_token}")

    assert response.status_code == 200
    assert len(response.json()) == 4
    assert all(node["service"]["schema"] is None for node in response.json())
    table_checks = [
        call
        for call in check.call_args_list
        if call.args[1] == ListFieldsOperationType.type
    ]
    assert len(table_checks) == 1
