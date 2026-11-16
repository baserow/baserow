from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.nodes.signals import automation_node_updated
from baserow.contrib.automation.tools.nodes import list_nodes, update_nodes
from baserow.contrib.automation.tools.types import NodeUpdate
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.core.handler import CoreHandler
from baserow.core.tools import ToolContext
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.fixture
def workflow_on_a_secret_table(enterprise_data_fixture):
    """
    A workflow whose trigger reads a table with a "Salary" field and has the rows
    of a test run, and a user who may build the workflow but has no access to the
    table's database.
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
    # As a test run stores the rows: keyed by field name.
    trigger.service.sample_data = {"data": [{"id": 1, "Salary": "Paid 250k"}]}
    trigger.service.save()

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


TABLE_DERIVED_KEYS = ("schema", "context_data", "context_data_schema", "sample_data")


def _assert_hides_the_table(response, node):
    assert "Salary" not in response.content.decode()
    assert "Over 100k" not in response.content.decode()
    assert "Paid 250k" not in response.content.decode()
    service = node["service"]
    assert service["table_accessible"] is False
    assert service["sample_data"] is None
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
    assert "Paid 250k" in response.content.decode()
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
    if event_type == "updated":
        assert "Paid 250k" in str(full)
    assert full["node"]["service"]["table_accessible"] is True
    assert full["node"]["service"]["schema"] is not None

    assert "Salary" not in str(hidden)
    assert "Over 100k" not in str(hidden)
    assert "Paid 250k" not in str(hidden)
    assert hidden["node"]["service"]["table_accessible"] is False
    for key in TABLE_DERIVED_KEYS:
        assert hidden["node"]["service"][key] is None
    # Everything else is what the users who may see the table get.
    assert {
        key: value
        for key, value in hidden["node"]["service"].items()
        if key not in TABLE_DERIVED_KEYS
    } == {
        key: value
        for key, value in full["node"]["service"].items()
        if key not in TABLE_DERIVED_KEYS
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


@broadcast_node_events
@pytest.mark.django_db(transaction=True)
def test_node_events_check_the_table_in_its_own_workspace(
    django_capture_on_commit_callbacks, enterprise_data_fixture
):
    """
    The table of a node's service is checked in the table's workspace, so an
    admin of the automation's workspace isn't shown a table of another one.
    """

    fixture = enterprise_data_fixture
    admin = fixture.create_user()
    workspace = fixture.create_workspace(user=admin)
    workflow = fixture.create_automation_workflow(
        automation=fixture.create_automation_application(workspace=workspace),
        trigger_type="local_baserow_rows_created",
    )
    elsewhere = fixture.create_database_table(
        database=fixture.create_database_application(
            workspace=fixture.create_workspace()
        )
    )
    fixture.create_text_field(table=elsewhere, name="Salary")
    trigger = workflow.get_trigger()
    service = trigger.service.specific
    service.table = elsewhere
    service.save()

    # Sent directly: the service handlers refuse a table of another workspace.
    sent = _broadcast_node_events(
        django_capture_on_commit_callbacks,
        lambda: automation_node_updated.send(None, user=None, node=trigger),
    )

    (event,) = sent[admin.id]
    assert event["node"]["service"]["table_accessible"] is False
    assert "Salary" not in str(event)


def _formula(formula):
    return {"formula": formula, "mode": "simple", "version": "0.1"}


def _add_node(admin, workflow, node_type, after, sample_data=None, **values):
    """A node after another, with the given service values and test run data."""

    node = AutomationNodeService().create_node(
        admin,
        automation_node_type_registry.get(node_type),
        workflow,
        reference_node_id=after.id,
        service={},
    )
    service = node.service.specific
    for name, value in values.items():
        setattr(service, name, value)
    service.sample_data = sample_data
    service.save()
    return node


@pytest.fixture
def nodes_after_a_secret_trigger(workflow_on_a_secret_table):
    """
    An iterator over the rows of the trigger, an email that reads a value of the
    trigger's row, and an email that reads nothing of the trigger. The test run
    data of the first two holds the trigger's rows.
    """

    admin, workflow, trigger, _, _, _ = workflow_on_a_secret_table
    iterator = _add_node(
        admin,
        workflow,
        "iterator",
        trigger,
        source=_formula(f"get('previous_node.{trigger.id}')"),
        sample_data={"data": {"results": [{"id": 1, "Salary": "Paid 250k"}]}},
    )
    email = _add_node(
        admin,
        workflow,
        "smtp_email",
        iterator,
        body=_formula(f"get('current_iteration.{iterator.id}.item.Salary')"),
        sample_data={"data": {"body": "Paid 250k"}},
    )
    unrelated = _add_node(
        admin,
        workflow,
        "smtp_email",
        email,
        body=_formula("'Weekly report'"),
        sample_data={"data": {"body": "Weekly report"}},
    )
    return iterator, email, unrelated


@pytest.mark.django_db
def test_nodes_reading_a_secret_table_are_hidden_too(
    api_client, workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    _, workflow, _, admin_token, restricted_token, _ = workflow_on_a_secret_table
    iterator, email, unrelated = nodes_after_a_secret_trigger
    url = reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {restricted_token}")

    assert response.status_code == 200
    assert "Paid 250k" not in response.content.decode()
    services = {node["id"]: node["service"] for node in response.json()}
    for node in (iterator, email):
        # They have no table of their own: only the data they read is hidden.
        assert services[node.id]["table_accessible"] is True
        assert services[node.id]["sample_data"] is None
    # The iterator's schema is built from its test run data.
    assert services[iterator.id]["schema"] is None
    # The email's schema is its own.
    assert services[email.id]["schema"]["properties"]["success"]
    assert services[unrelated.id]["table_accessible"] is True
    assert services[unrelated.id]["sample_data"] == {"data": {"body": "Weekly report"}}

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {admin_token}")

    services = {node["id"]: node["service"] for node in response.json()}
    assert services[iterator.id]["schema"]["items"]["properties"]["Salary"]
    assert services[email.id]["sample_data"] == {"data": {"body": "Paid 250k"}}
    assert all(service["table_accessible"] for service in services.values())


@pytest.mark.django_db
def test_list_nodes_tool_hides_nodes_reading_a_secret_table(
    workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    _, workflow, _, _, _, restricted = workflow_on_a_secret_table
    iterator, email, unrelated = nodes_after_a_secret_trigger
    ctx = ToolContext(user=restricted, workspace=workflow.automation.workspace)

    outputs = {
        node["id"]: node["output_schema"]
        for node in list_nodes(ctx, workflow.id)["nodes"]
    }

    assert outputs[iterator.id]["reads_hidden_data"] is True
    assert outputs[iterator.id]["properties"] == {}
    assert outputs[email.id]["reads_hidden_data"] is True
    assert outputs[email.id]["properties"]["success"]
    assert "reads_hidden_data" not in outputs[unrelated.id]


@pytest.mark.django_db
def test_a_formula_reading_a_secret_table_is_refused_without_naming_its_fields(
    workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    admin, workflow, trigger, _, _, restricted = workflow_on_a_secret_table
    _, _, unrelated = nodes_after_a_secret_trigger
    formula = f"get('previous_node.{trigger.id}.0.nonexistent')"

    def update_as(user):
        ctx = ToolContext(user=user, workspace=workflow.automation.workspace)
        return update_nodes(
            ctx, workflow.id, [NodeUpdate(node_id=unrelated.id, subject=formula)]
        )

    (error,) = update_as(restricted)["formula_errors"]
    assert error["error"] == (
        f"Node {trigger.id} shows a table you can't access, so this formula "
        "can't read it."
    )
    unrelated.service.specific.refresh_from_db()
    assert unrelated.service.specific.subject["formula"] != formula

    # A user who may see the table is told what the node outputs.
    (error,) = update_as(admin)["formula_errors"]
    assert "Salary" in error["error"]


@pytest.mark.django_db
def test_run_results_of_nodes_reading_a_secret_table_are_hidden(
    api_client,
    enterprise_data_fixture,
    workflow_on_a_secret_table,
    nodes_after_a_secret_trigger,
):
    _, workflow, trigger, admin_token, restricted_token, _ = workflow_on_a_secret_table
    iterator, email, unrelated = nodes_after_a_secret_trigger
    run = enterprise_data_fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow
    )
    results = {}
    for node, result in (
        (trigger, {"results": [{"id": 1, "Salary": "Paid 250k"}]}),
        (iterator, {"results": [{"id": 1, "Salary": "Paid 250k"}]}),
        (email, {"body": "Paid 250k"}),
        (unrelated, {"body": "Weekly report"}),
    ):
        node_history = enterprise_data_fixture.create_automation_node_history(
            workflow_history=run, node=node
        )
        enterprise_data_fixture.create_automation_node_result(
            node_history=node_history, result=result
        )
        results[node.id] = node_history.id

    def result_of(node, token):
        response = api_client.get(
            reverse(
                "api:automation:history:node_result",
                kwargs={"node_history_id": results[node.id]},
            ),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == 200, response.json()
        return response.json()["result"]

    for node in (trigger, iterator, email):
        assert result_of(node, restricted_token) is None
        assert "Paid 250k" in str(result_of(node, admin_token))
    assert result_of(unrelated, restricted_token) == {"body": "Weekly report"}


@broadcast_node_events
@pytest.mark.django_db(transaction=True)
def test_node_events_of_nodes_reading_a_secret_table_are_hidden(
    django_capture_on_commit_callbacks,
    workflow_on_a_secret_table,
    nodes_after_a_secret_trigger,
):
    admin, _, _, _, _, restricted = workflow_on_a_secret_table
    _, email, unrelated = nodes_after_a_secret_trigger

    def rename(node):
        return _broadcast_node_events(
            django_capture_on_commit_callbacks,
            lambda: AutomationNodeService().update_node(admin, node.id, label="New"),
        )

    sent = rename(email)
    (full,) = sent[admin.id]
    (hidden,) = sent[restricted.id]
    assert full["node"]["service"]["sample_data"] == {"data": {"body": "Paid 250k"}}
    assert "Paid 250k" not in str(hidden)
    assert hidden["node"]["service"]["sample_data"] is None
    # The email has no table of its own.
    assert hidden["node"]["service"]["table_accessible"] is True

    sent = rename(unrelated)
    assert sent[restricted.id] == sent[admin.id]
    assert sent[restricted.id][0]["node"]["service"]["table_accessible"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "get( 'previous_node.{trigger}.0.Salary')",
        "get(('previous_node.{trigger}.0.Salary'))",
        "get('previous_node.{trigger_underscored}.0.Salary')",
        "get(concat('previous_node.', '{trigger}', '.0.Salary'))",
    ],
)
def test_reads_of_a_secret_table_are_found_however_written(
    api_client, workflow_on_a_secret_table, nodes_after_a_secret_trigger, path
):
    """
    The paths are read as the runtime reads them, and a path the formula builds
    can read any node.
    """

    admin, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
    _, _, unrelated = nodes_after_a_secret_trigger
    trigger_id = str(trigger.id)
    formula = path.format(
        trigger=trigger_id,
        trigger_underscored=trigger_id[0] + "_" + trigger_id[1:]
        if len(trigger_id) > 1
        else "0_" + trigger_id,
    )
    service = unrelated.service.specific
    service.body = _formula(formula)
    service.sample_data = {"data": {"body": "Paid 250k"}}
    service.save()

    response = api_client.get(
        reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id}),
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )

    assert response.status_code == 200
    assert "Paid 250k" not in response.content.decode()


@pytest.mark.django_db
def test_a_get_without_a_path_reads_nothing(
    api_client, workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    _, workflow, _, _, restricted_token, _ = workflow_on_a_secret_table
    _, _, unrelated = nodes_after_a_secret_trigger
    service = unrelated.service.specific
    service.body = _formula("concat(get(), 'x')")
    service.save()

    response = api_client.get(
        reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id}),
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )

    assert response.status_code == 200
    services = {node["id"]: node["service"] for node in response.json()}
    assert services[unrelated.id]["sample_data"] == {"data": {"body": "Weekly report"}}


@pytest.mark.django_db
def test_a_row_action_on_a_visible_table_keeps_its_fields_when_it_reads_a_secret_one(
    api_client, enterprise_data_fixture, workflow_on_a_secret_table
):
    """
    Reading a value of a table the user may not see hides the data read, not the
    table the action writes to, which the user may see.
    """

    admin, workflow, trigger, _, restricted_token, restricted = (
        workflow_on_a_secret_table
    )
    workspace = workflow.automation.workspace
    public = enterprise_data_fixture.create_database_table(
        database=enterprise_data_fixture.create_database_application(
            workspace=workspace
        )
    )
    note = enterprise_data_fixture.create_text_field(table=public, name="Note")
    RoleAssignmentHandler().assign_role(
        restricted, workspace, role=Role.objects.get(uid="EDITOR"), scope=public
    )
    create_row = AutomationNodeService().create_node(
        admin,
        automation_node_type_registry.get("local_baserow_create_row"),
        workflow,
        reference_node_id=trigger.id,
        service={"table_id": public.id},
    )
    service = create_row.service.specific
    service.field_mappings.create(
        field=note, value=_formula(f"get('previous_node.{trigger.id}.0.Salary')")
    )
    service.sample_data = {"data": {"id": 1, "Note": "Paid 250k"}}
    service.save()

    response = api_client.get(
        reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id}),
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )

    (node,) = [node for node in response.json() if node["id"] == create_row.id]
    assert node["service"]["table_accessible"] is True
    assert "Note" in str(node["service"]["schema"])
    assert node["service"]["context_data"] is not None
    assert node["service"]["sample_data"] is None
    assert "Paid 250k" not in response.content.decode()


@pytest.mark.django_db
def test_a_formula_reading_a_hidden_iterator_is_refused(
    workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    _, workflow, _, _, _, restricted = workflow_on_a_secret_table
    iterator, _, unrelated = nodes_after_a_secret_trigger
    ctx = ToolContext(user=restricted, workspace=workflow.automation.workspace)

    result = update_nodes(
        ctx,
        workflow.id,
        [
            NodeUpdate(
                node_id=unrelated.id,
                subject=f"get('current_iteration.{iterator.id}.item.nonexistent')",
            )
        ],
    )

    (error,) = result["formula_errors"]
    assert error["error"] == (
        f"Node {iterator.id} reads data of a table you can't access, so this "
        "formula can't read it."
    )


@pytest.mark.django_db
def test_a_built_path_is_refused_when_a_node_shows_a_secret_table(
    workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    _, workflow, trigger, _, _, restricted = workflow_on_a_secret_table
    _, _, unrelated = nodes_after_a_secret_trigger
    ctx = ToolContext(user=restricted, workspace=workflow.automation.workspace)

    result = update_nodes(
        ctx,
        workflow.id,
        [
            NodeUpdate(
                node_id=unrelated.id,
                subject=f"get(concat('previous_node.', '{trigger.id}', '.0.x'))",
            )
        ],
    )

    (error,) = result["formula_errors"]
    assert "builds" in error["error"]


@pytest.mark.django_db
def test_run_messages_of_nodes_reading_a_secret_table_are_hidden(
    api_client,
    enterprise_data_fixture,
    workflow_on_a_secret_table,
    nodes_after_a_secret_trigger,
):
    _, workflow, trigger, admin_token, restricted_token, _ = workflow_on_a_secret_table
    _, email, unrelated = nodes_after_a_secret_trigger
    run = enterprise_data_fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow
    )
    for node, message in (
        (trigger, "Salary: 'Paid 250k' is invalid"),
        (email, "Paid 250k is not an email"),
        (unrelated, "Weekly report failed"),
    ):
        enterprise_data_fixture.create_automation_node_history(
            workflow_history=run, node=node, message=message
        )
    url = reverse(
        "api:automation:history:node_histories",
        kwargs={"workflow_history_id": run.id},
    )

    def messages(token):
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == 200, response.json()
        return {entry["node"]: entry["message"] for entry in response.json()}

    seen = messages(restricted_token)
    assert seen[trigger.id] == seen[email.id] == ""
    assert seen[unrelated.id] == "Weekly report failed"
    assert messages(admin_token)[email.id] == "Paid 250k is not an email"


@pytest.mark.django_db
def test_run_result_of_a_trashed_node_is_checked_for_its_table(
    api_client, enterprise_data_fixture, workflow_on_a_secret_table
):
    _, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
    run = enterprise_data_fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow
    )
    node_history = enterprise_data_fixture.create_automation_node_history(
        workflow_history=run, node=trigger
    )
    enterprise_data_fixture.create_automation_node_result(
        node_history=node_history, result={"results": [{"Salary": "Paid 250k"}]}
    )
    AutomationNode.objects_and_trash.filter(id=trigger.id).update(trashed=True)

    response = api_client.get(
        reverse(
            "api:automation:history:node_result",
            kwargs={"node_history_id": node_history.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["result"] is None


def test_serializer_without_access_shows_no_table():
    from baserow.contrib.automation.api.nodes.serializers import (
        AutomationServiceSerializer,
    )

    class Service:
        id = 1
        table_id = 1

        @property
        def specific(self):
            return self

    serializer = AutomationServiceSerializer(context={})

    assert serializer.get_table_accessible(Service()) is False


@pytest.mark.django_db
def test_listing_nodes_reads_the_workflow_once(
    api_client, workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    _, workflow, _, admin_token, restricted_token, _ = workflow_on_a_secret_table
    url = reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id})

    for token in (admin_token, restricted_token):
        with patch.object(
            AutomationNodeHandler,
            "get_nodes",
            autospec=True,
            side_effect=AutomationNodeHandler.get_nodes,
        ) as get_nodes:
            response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

        assert response.status_code == 200
        assert get_nodes.call_count == 1
