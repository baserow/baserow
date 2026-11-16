from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
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
    return admin, workflow, trigger, admin_token, restricted_token, restricted


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
    _, workflow, trigger, admin_token, restricted_token, _ = workflow_on_a_secret_table
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
    _, _, trigger, _, restricted_token, _ = workflow_on_a_secret_table

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
    admin, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
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


# The node events are broadcast with one of these, by whether the node uses a table.
broadcast_node_events = pytest.mark.enable_signals(
    "baserow.ws.tasks.broadcast_to_permitted_users.delay",
    "baserow.contrib.automation.nodes.ws.tasks."
    "broadcast_node_event_to_permitted_users.delay",
)


def _broadcast_node_events(django_capture_on_commit_callbacks, change):
    """
    Makes the change and returns the node events each user is sent, by user id.
    """

    with (
        patch("baserow.ws.tasks.broadcast_to_users") as send_to_users,
        django_capture_on_commit_callbacks(execute=True),
    ):
        change()

    sent = {}
    for call in send_to_users.call_args_list:
        user_ids, payload = call.args
        if payload["type"].startswith("automation_node_"):
            for user_id in user_ids:
                sent.setdefault(user_id, []).append(payload)
    return sent


@broadcast_node_events
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("event_type", ["created", "updated"])
def test_node_events_hide_the_fields_of_a_table_the_user_cannot_see(
    django_capture_on_commit_callbacks, workflow_on_a_secret_table, event_type
):
    admin, workflow, trigger, _, _, restricted = workflow_on_a_secret_table
    table_id = trigger.service.specific.table_id

    def change():
        if event_type == "created":
            AutomationNodeService().create_node(
                admin,
                automation_node_type_registry.get("local_baserow_create_row"),
                workflow,
                reference_node_id=trigger.id,
                service={"table_id": table_id},
            )
        else:
            AutomationNodeService().update_node(admin, trigger.id, label="Renamed")

    sent = _broadcast_node_events(django_capture_on_commit_callbacks, change)

    (full,) = sent[admin.id]
    (hidden,) = sent[restricted.id]
    assert full["type"] == hidden["type"] == f"automation_node_{event_type}"
    assert full["node"]["id"] == hidden["node"]["id"]
    assert "Salary" in str(full)
    assert full["node"]["service"]["table_accessible"] is True
    assert full["node"]["service"]["schema"] is not None

    assert "Salary" not in str(hidden)
    assert "Over 100k" not in str(hidden)
    assert hidden["node"]["service"]["table_accessible"] is False
    for key in ("schema", "context_data", "context_data_schema"):
        assert hidden["node"]["service"][key] is None
    # Everything else is what the users who may see the table get.
    assert {
        key: value
        for key, value in hidden["node"]["service"].items()
        if key not in ("schema", "context_data", "context_data_schema")
    } == {
        key: value
        for key, value in full["node"]["service"].items()
        if key not in ("schema", "context_data", "context_data_schema")
    } | {"table_accessible": False}
    assert {k: v for k, v in hidden["node"].items() if k != "service"} == {
        k: v for k, v in full["node"].items() if k != "service"
    }


@broadcast_node_events
@pytest.mark.django_db(transaction=True)
def test_node_events_cost_the_same_queries_for_more_users(
    django_capture_on_commit_callbacks,
    enterprise_data_fixture,
    workflow_on_a_secret_table,
):
    admin, workflow, trigger, _, _, restricted = workflow_on_a_secret_table
    workspace = workflow.automation.workspace

    def broadcast():
        with CaptureQueriesContext(connection) as queries:
            sent = _broadcast_node_events(
                django_capture_on_commit_callbacks,
                lambda: AutomationNodeService().update_node(
                    admin, trigger.id, label="Renamed"
                ),
            )
        return len(queries), sent

    queries, sent = broadcast()
    assert set(sent) == {admin.id, restricted.id}
    for _ in range(3):
        user = enterprise_data_fixture.create_user()
        enterprise_data_fixture.create_user_workspace(
            user=user, workspace=workspace, permissions="NO_ACCESS"
        )
        RoleAssignmentHandler().assign_role(
            user,
            workspace,
            role=Role.objects.get(uid="BUILDER"),
            scope=workflow.automation.application_ptr,
        )

    more_queries, sent = broadcast()
    assert len(sent) == 5
    assert more_queries == queries
