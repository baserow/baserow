from unittest.mock import patch

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.tools.nodes import list_nodes, update_nodes
from baserow.contrib.automation.tools.types import NodeUpdate
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.services.registries import service_type_registry
from baserow.core.tools import ToolContext
from baserow.core.trash.handler import TrashHandler
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


def _add_row_nodes(admin, workflow, trigger, table_ids):
    """A create row node on each of the tables, one after the other."""

    previous = trigger
    for table_id in table_ids:
        previous = AutomationNodeService().create_node(
            admin,
            automation_node_type_registry.get("local_baserow_create_row"),
            workflow,
            reference_node_id=previous.id,
            service={"table_id": table_id},
        )
    return previous


@pytest.mark.django_db
def test_listing_nodes_costs_the_same_queries_for_more_nodes_on_a_table(
    api_client,
    django_assert_num_queries,
    workflow_on_a_secret_table,
):
    admin, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
    table_id = trigger.service.specific.table_id
    url = reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id})

    def list_nodes_as_restricted():
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {restricted_token}")
        assert response.status_code == 200
        assert all(node["service"]["schema"] is None for node in response.json())
        return response

    last = _add_row_nodes(admin, workflow, trigger, [table_id])
    list_nodes_as_restricted()  # Warms the caches.
    with CaptureQueriesContext(connection) as queries:
        list_nodes_as_restricted()
    _add_row_nodes(admin, workflow, last, [table_id] * 3)

    # Each table is checked once, however many nodes use it.
    with django_assert_num_queries(len(queries)):
        response = list_nodes_as_restricted()
    assert len(response.json()) == 5


@pytest.mark.django_db
def test_listing_nodes_costs_a_fixed_number_of_queries_for_each_table(
    api_client,
    enterprise_data_fixture,
    django_assert_num_queries,
    workflow_on_a_secret_table,
):
    admin, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
    url = reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id})
    workspace = workflow.automation.workspace

    def list_nodes_as_restricted():
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {restricted_token}")
        assert response.status_code == 200
        return response

    # The trigger's table is the one table of the workflow.
    one = _add_row_nodes(admin, workflow, trigger, [trigger.service.specific.table_id])
    list_nodes_as_restricted()  # Warms the caches.
    with CaptureQueriesContext(connection) as one_table:
        list_nodes_as_restricted()

    tables = [
        enterprise_data_fixture.create_database_table(
            database=enterprise_data_fixture.create_database_application(
                workspace=workspace
            )
        ).id
        for _ in range(2)
    ]
    last = _add_row_nodes(admin, workflow, one, tables)
    with CaptureQueriesContext(connection) as three_tables:
        list_nodes_as_restricted()

    # More nodes on those tables cost nothing more.
    _add_row_nodes(admin, workflow, last, tables)
    with django_assert_num_queries(len(three_tables)):
        response = list_nodes_as_restricted()
    assert len(response.json()) == 6
    per_table = (len(three_tables) - len(one_table)) / 2
    assert per_table == int(per_table)
    assert per_table <= 4


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


@pytest.mark.django_db
def test_serializer_without_access_shows_no_table(workflow_on_a_secret_table):
    from baserow.contrib.automation.api.nodes.serializers import (
        AutomationServiceSerializer,
    )

    _, _, trigger, _, _, _ = workflow_on_a_secret_table
    service = trigger.service.specific
    serializer = AutomationServiceSerializer(context={})

    assert serializer.get_table_accessible(service) is False
    data = serializer.to_representation(service)
    assert data["sample_data"] is None
    assert data["schema"] is None


@broadcast_node_events
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("formula", ["get('')", "field('a')"])
def test_formulas_that_cant_be_read_hide_the_node_instead_of_failing(
    api_client,
    django_capture_on_commit_callbacks,
    enterprise_data_fixture,
    workflow_on_a_secret_table,
    nodes_after_a_secret_trigger,
    formula,
):
    """
    A formula that can't be read, like one imported broken, could read any node,
    so it hides the node from a user who may not see a table of the workflow.
    """

    admin, workflow, _, admin_token, restricted_token, restricted = (
        workflow_on_a_secret_table
    )
    _, _, unrelated = nodes_after_a_secret_trigger
    service = unrelated.service.specific
    service.body = _formula(formula)
    service.save()
    url = reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {restricted_token}")
    assert response.status_code == 200
    (node,) = [node for node in response.json() if node["id"] == unrelated.id]
    assert node["service"]["sample_data"] is None

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {admin_token}")
    assert response.status_code == 200

    ctx = ToolContext(user=restricted, workspace=workflow.automation.workspace)
    outputs = {
        node["id"]: node["output_schema"]
        for node in list_nodes(ctx, workflow.id)["nodes"]
    }
    assert outputs[unrelated.id]["reads_hidden_data"] is True

    run = enterprise_data_fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow
    )
    node_history = enterprise_data_fixture.create_automation_node_history(
        workflow_history=run, node=unrelated
    )
    enterprise_data_fixture.create_automation_node_result(
        node_history=node_history, result={"body": "Weekly report"}
    )
    response = api_client.get(
        reverse(
            "api:automation:history:node_result",
            kwargs={"node_history_id": node_history.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )
    assert response.status_code == 200
    assert response.json()["result"] is None

    sent = _broadcast_node_events(
        django_capture_on_commit_callbacks,
        lambda: AutomationNodeService().update_node(admin, unrelated.id, label="New"),
    )
    assert sent[restricted.id][0]["node"]["service"]["sample_data"] is None


@pytest.mark.django_db
def test_run_results_stay_hidden_when_the_node_they_read_is_trashed(
    api_client,
    enterprise_data_fixture,
    workflow_on_a_secret_table,
    nodes_after_a_secret_trigger,
):
    admin, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
    _, _, unrelated = nodes_after_a_secret_trigger
    # A list of the secret rows, which a later email reads.
    rows = AutomationNodeService().create_node(
        admin,
        automation_node_type_registry.get("local_baserow_list_rows"),
        workflow,
        reference_node_id=unrelated.id,
        service={"table_id": trigger.service.specific.table_id},
    )
    email = _add_node(
        admin,
        workflow,
        "smtp_email",
        rows,
        body=_formula(f"get('previous_node.{rows.id}.0.Salary')"),
    )
    run = enterprise_data_fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow
    )
    node_history = enterprise_data_fixture.create_automation_node_history(
        workflow_history=run, node=email, message="Paid 250k is not an email"
    )
    enterprise_data_fixture.create_automation_node_result(
        node_history=node_history, result={"body": "Paid 250k"}
    )
    # The node the email read is trashed after the run.
    AutomationNodeService().delete_node(admin, rows.id)

    result = api_client.get(
        reverse(
            "api:automation:history:node_result",
            kwargs={"node_history_id": node_history.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )
    histories = api_client.get(
        reverse(
            "api:automation:history:node_histories",
            kwargs={"workflow_history_id": run.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )

    assert result.status_code == histories.status_code == 200
    assert result.json()["result"] is None
    assert histories.json()[0]["message"] == ""
    assert "Paid 250k" not in histories.content.decode()


@pytest.mark.django_db
def test_list_nodes_tool_counts_nodes_no_path_reaches(
    enterprise_data_fixture, workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    """
    A node can read a node that no path of the workflow reaches, which is still
    in the workflow.
    """

    admin, workflow, trigger, _, _, restricted = workflow_on_a_secret_table
    _, _, unrelated = nodes_after_a_secret_trigger
    list_rows_type = automation_node_type_registry.get("local_baserow_list_rows")
    unreachable = AutomationNodeHandler().create_node(
        list_rows_type,
        workflow=workflow,
        service=enterprise_data_fixture.create_service(
            service_type_registry.get(list_rows_type.service_type).model_class,
            table=trigger.service.specific.table,
            integration_args={"application": workflow.automation},
        ),
    )
    service = unrelated.service.specific
    service.body = _formula(f"get('previous_node.{unreachable.id}.0.Salary')")
    service.save()
    ctx = ToolContext(user=restricted, workspace=workflow.automation.workspace)

    outputs = {
        node["id"]: node["output_schema"]
        for node in list_nodes(ctx, workflow.id)["nodes"]
    }

    assert unreachable.id not in outputs
    assert outputs[unrelated.id]["reads_hidden_data"] is True


@pytest.mark.django_db
def test_listing_run_nodes_costs_the_same_queries_for_more_nodes(
    api_client, enterprise_data_fixture, workflow_on_a_secret_table
):
    admin, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table

    def queries_for(node_count):
        previous = trigger
        nodes = [trigger]
        for _ in range(node_count - 1):
            previous = _add_node(
                admin,
                workflow,
                "smtp_email",
                previous,
                body=_formula(f"get('previous_node.{trigger.id}.0.Salary')"),
            )
            nodes.append(previous)
        run = enterprise_data_fixture.create_automation_workflow_history(
            workflow=workflow, original_workflow=workflow
        )
        for node in nodes:
            enterprise_data_fixture.create_automation_node_history(
                workflow_history=run, node=node, message="Failed"
            )
        url = reverse(
            "api:automation:history:node_histories",
            kwargs={"workflow_history_id": run.id},
        )
        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {restricted_token}")
        assert response.status_code == 200
        assert all(entry["message"] == "" for entry in response.json())
        return [query["sql"] for query in queries.captured_queries]

    few = queries_for(2)
    many = queries_for(6)

    # The nodes of the run are read once, whatever their number.
    assert len(many) <= len(few)


SECRET_ROWS = {"results": [{"id": 1, "Salary": "Paid 250k"}], "has_next_page": False}


def _test_run(fixture, workflow, node, event_payload=None):
    """
    Dispatches the nodes up to the given one as a test run until it does, which
    stores the test run data of the node.
    """

    run = fixture.create_automation_workflow_history(
        workflow=workflow,
        original_workflow=workflow,
        simulate_until_node=node,
        event_payload=event_payload or SECRET_ROWS,
    )
    for before in sorted(node.get_previous_points(), key=lambda n: n.id):
        AutomationNodeHandler().dispatch_node(before.id, history_id=run.id)
    AutomationNodeHandler().dispatch_node(node.id, history_id=run.id)
    node.service.specific.refresh_from_db()
    return node


def _nodes_as(api_client, workflow, token):
    response = api_client.get(
        reverse("api:automation:nodes:list", kwargs={"workflow_id": workflow.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    return response, {node["id"]: node["service"] for node in response.json()}


@pytest.fixture
def test_run_nodes(enterprise_data_fixture, workflow_on_a_secret_table):
    """
    The trigger on the secret table, an iterator over its rows and an email that
    reads one, each with the test run data a real test run stored.
    """

    admin, workflow, trigger, _, _, _ = workflow_on_a_secret_table
    fixture = enterprise_data_fixture
    trigger.service.specific.integration = fixture.create_local_baserow_integration(
        user=admin, application=workflow.automation
    )
    trigger.service.specific.sample_data = None
    trigger.service.specific.save()
    iterator = _add_node(
        admin,
        workflow,
        "iterator",
        trigger,
        source=_formula(f"get('previous_node.{trigger.id}')"),
    )
    email = _add_node(
        admin,
        workflow,
        "smtp_email",
        iterator,
        use_instance_smtp_settings=True,
        from_email=_formula("'from@example.com'"),
        to_emails=_formula("'to@example.com'"),
        subject=_formula("'Report'"),
        body=_formula(f"get('previous_node.{trigger.id}.0.Salary')"),
    )
    for node in (trigger, iterator, email):
        _test_run(fixture, workflow, node)
    return trigger, iterator, email


@pytest.mark.django_db
def test_test_run_data_remembers_the_tables_it_was_built_from(
    workflow_on_a_secret_table, test_run_nodes
):
    _, _, trigger, _, _, _ = workflow_on_a_secret_table
    table_id = trigger.service.specific.table_id

    for node in test_run_nodes:
        assert node.service.specific.sample_data
        assert node.service.specific.sample_data_table_ids == [table_id]


@pytest.mark.django_db
def test_test_run_data_is_hidden_after_the_formula_reading_the_table_is_edited(
    api_client, workflow_on_a_secret_table, test_run_nodes
):
    _, workflow, _, admin_token, restricted_token, _ = workflow_on_a_secret_table
    _, iterator, email = test_run_nodes
    _, services = _nodes_as(api_client, workflow, restricted_token)
    assert services[iterator.id]["sample_data"] is None

    response = api_client.patch(
        reverse("api:automation:nodes:item", kwargs={"node_id": iterator.id}),
        {"service": {"source": _formula("'nothing'")}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )
    assert response.status_code == 200, response.json()
    assert "Paid 250k" not in response.content.decode()
    response, services = _nodes_as(api_client, workflow, restricted_token)

    assert "Paid 250k" not in response.content.decode()
    assert services[iterator.id]["sample_data"] is None
    assert services[iterator.id]["schema"] is None
    # The email read the iterator's rows, whatever the iterator reads now.
    assert services[email.id]["sample_data"] is None
    _, services = _nodes_as(api_client, workflow, admin_token)
    assert "Paid 250k" in str(services[iterator.id]["sample_data"])


@pytest.fixture
def test_run_rows_and_iterator(enterprise_data_fixture, workflow_on_a_secret_table):
    """
    A list of the secret table's rows, with a note in the row, and an iterator
    over them, each with the test run data a real test run stored.
    """

    admin, workflow, trigger, _, _, _ = workflow_on_a_secret_table
    fixture = enterprise_data_fixture
    table = trigger.service.specific.table
    note = fixture.create_text_field(table=table, name="Note")
    table.get_model().objects.create(**{f"field_{note.id}": "Paid 250k"})
    integration = fixture.create_local_baserow_integration(
        user=admin, application=workflow.automation
    )
    rows = _add_node(
        admin,
        workflow,
        "local_baserow_list_rows",
        trigger,
        table=table,
        integration=integration,
    )
    iterator = _add_node(
        admin,
        workflow,
        "iterator",
        rows,
        source=_formula(f"get('previous_node.{rows.id}')"),
    )
    trigger.service.specific.integration = integration
    trigger.service.specific.save()
    _test_run(fixture, workflow, iterator)
    assert "Paid 250k" in str(iterator.service.specific.sample_data)
    return rows, iterator


@pytest.mark.django_db
def test_test_run_data_is_hidden_after_the_node_between_is_deleted(
    api_client, workflow_on_a_secret_table, test_run_rows_and_iterator
):
    _, workflow, _, admin_token, restricted_token, _ = workflow_on_a_secret_table
    rows, iterator = test_run_rows_and_iterator
    _, services = _nodes_as(api_client, workflow, restricted_token)
    assert services[iterator.id]["sample_data"] is None

    response = api_client.delete(
        reverse("api:automation:nodes:item", kwargs={"node_id": rows.id}),
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == 204
    response, services = _nodes_as(api_client, workflow, restricted_token)

    assert "Paid 250k" not in response.content.decode()
    assert services[iterator.id]["sample_data"] is None
    assert services[iterator.id]["schema"] is None
    _, services = _nodes_as(api_client, workflow, admin_token)
    assert "Paid 250k" in str(services[iterator.id]["sample_data"])


@broadcast_node_events
@pytest.mark.django_db(transaction=True)
def test_node_events_are_hidden_after_the_node_between_is_deleted(
    django_capture_on_commit_callbacks,
    workflow_on_a_secret_table,
    test_run_rows_and_iterator,
):
    admin, _, _, _, _, restricted = workflow_on_a_secret_table
    rows, iterator = test_run_rows_and_iterator
    AutomationNodeService().delete_node(admin, rows.id)

    sent = _broadcast_node_events(
        django_capture_on_commit_callbacks,
        lambda: AutomationNodeService().update_node(admin, iterator.id, label="New"),
    )

    (full,) = sent[admin.id]
    (hidden,) = sent[restricted.id]
    assert "Paid 250k" in str(full["node"]["service"]["sample_data"])
    assert "Paid 250k" not in str(hidden)
    assert hidden["node"]["service"]["sample_data"] is None


@pytest.mark.django_db
def test_test_run_data_is_hidden_after_the_table_is_permanently_deleted(
    api_client, workflow_on_a_secret_table, test_run_nodes
):
    admin, workflow, trigger, admin_token, restricted_token, _ = (
        workflow_on_a_secret_table
    )
    _, iterator, email = test_run_nodes
    table = trigger.service.specific.table
    TrashHandler.trash(
        admin,
        workflow.automation.workspace,
        table.database,
        table,
    )
    TrashHandler.permanently_delete(table)
    trigger.service.specific.refresh_from_db()
    assert trigger.service.specific.table_id is None

    response, services = _nodes_as(api_client, workflow, restricted_token)

    assert "Paid 250k" not in response.content.decode()
    for node in (trigger, iterator, email):
        assert services[node.id]["sample_data"] is None
    assert services[iterator.id]["schema"] is None
    # Who may see a table that is gone can't be told, so nobody sees its data.
    response, services = _nodes_as(api_client, workflow, admin_token)
    assert "Paid 250k" not in response.content.decode()
    assert services[iterator.id]["sample_data"] is None


@pytest.mark.django_db
def test_run_messages_of_a_failed_node_on_a_secret_table_are_hidden(
    api_client,
    enterprise_data_fixture,
    workflow_on_a_secret_table,
):
    admin, workflow, trigger, admin_token, restricted_token, _ = (
        workflow_on_a_secret_table
    )
    fixture = enterprise_data_fixture
    table = trigger.service.specific.table
    bonus = fixture.create_number_field(table=table, name="Bonus")
    integration = fixture.create_local_baserow_integration(
        user=admin, application=workflow.automation
    )
    trigger.service.specific.integration = integration
    trigger.service.specific.save()
    create_row = _add_node(
        admin,
        workflow,
        "local_baserow_create_row",
        trigger,
        table=table,
        integration=integration,
    )
    create_row.service.specific.field_mappings.create(
        field=bonus, value=_formula("'a lot'"), enabled=True
    )
    run = fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow, event_payload=SECRET_ROWS
    )
    for node in (trigger, create_row):
        AutomationNodeHandler().dispatch_node(node.id, history_id=run.id)
    run.refresh_from_db()
    assert "Bonus" in run.message
    url = reverse(
        "api:automation:workflows:history", kwargs={"workflow_id": workflow.id}
    )

    def run_message(token):
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == 200, response.json()
        (entry,) = response.json()["results"]
        return entry["message"]

    assert run_message(restricted_token) == ""
    assert "Bonus" in run_message(admin_token)


@pytest.mark.django_db
def test_run_message_of_a_failed_node_the_user_may_see_is_shown(
    api_client, enterprise_data_fixture, workflow_on_a_secret_table
):
    admin, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
    unrelated = _add_node(
        admin,
        workflow,
        "smtp_email",
        trigger,
        use_instance_smtp_settings=True,
        from_email=_formula("'from@example.com'"),
        to_emails=_formula("''"),
        subject=_formula("'Report'"),
        body=_formula("'Weekly report'"),
    )
    run = enterprise_data_fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow, event_payload=SECRET_ROWS
    )
    trigger.service.specific.integration = (
        enterprise_data_fixture.create_local_baserow_integration(
            user=admin, application=workflow.automation
        )
    )
    trigger.service.specific.save()
    for node in (trigger, unrelated):
        AutomationNodeHandler().dispatch_node(node.id, history_id=run.id)
    run.refresh_from_db()
    assert run.message

    response = api_client.get(
        reverse(
            "api:automation:workflows:history", kwargs={"workflow_id": workflow.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )

    (entry,) = response.json()["results"]
    assert entry["message"] == run.message


@pytest.mark.django_db
def test_a_retry_condition_reading_a_secret_table_hides_the_data_of_the_node(
    api_client, workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    """
    For test run data stored before the tables it was built from were kept, the
    formulas of the node decide, its retry condition included.
    """

    _, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
    _, _, unrelated = nodes_after_a_secret_trigger
    AutomationNode.objects.filter(id=unrelated.id).update(
        retry_condition=_formula(f"get('previous_node.{trigger.id}.0.Salary')")
    )

    _, services = _nodes_as(api_client, workflow, restricted_token)

    assert services[unrelated.id]["sample_data"] is None


@pytest.mark.django_db
def test_history_serializers_show_nothing_without_a_node_access(
    enterprise_data_fixture, workflow_on_a_secret_table, nodes_after_a_secret_trigger
):
    from baserow.contrib.automation.api.history.serializers import (
        AutomationNodeHistorySerializer,
        AutomationNodeResultSerializer,
    )
    from baserow.contrib.automation.api.workflows.serializers import (
        AutomationWorkflowHistorySerializer,
    )

    _, workflow, _, _, _, _ = workflow_on_a_secret_table
    _, _, unrelated = nodes_after_a_secret_trigger
    run = enterprise_data_fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow, message="Paid 250k"
    )
    node_history = enterprise_data_fixture.create_automation_node_history(
        workflow_history=run, node=unrelated, message="Paid 250k"
    )
    result = enterprise_data_fixture.create_automation_node_result(
        node_history=node_history, result={"body": "Paid 250k"}
    )

    assert AutomationNodeHistorySerializer(node_history).data["message"] == ""
    assert AutomationNodeResultSerializer(result).data["result"] is None
    assert AutomationWorkflowHistorySerializer(run).data["message"] == ""


def _run_results(workflow):
    """
    The node history with a result of each node of the workflow, as the test runs
    of `test_run_nodes` stored them.
    """

    from baserow.contrib.automation.history.models import AutomationNodeHistory

    return {
        history.node_id: history
        for history in AutomationNodeHistory.objects.filter(
            workflow_history__workflow=workflow, node_results__isnull=False
        ).order_by("id")
    }


def _result_as(api_client, node_history, token):
    response = api_client.get(
        reverse(
            "api:automation:history:node_result",
            kwargs={"node_history_id": node_history.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    return response.json()["result"]


@pytest.mark.django_db
def test_run_history_remembers_the_tables_each_node_read(
    workflow_on_a_secret_table, test_run_nodes
):
    _, workflow, trigger, _, _, _ = workflow_on_a_secret_table
    _, iterator, email = test_run_nodes
    table_id = trigger.service.specific.table_id

    histories = _run_results(workflow)

    assert histories[trigger.id].read_table_ids == [table_id]
    assert histories[iterator.id].read_table_ids == [table_id]


@pytest.mark.django_db
def test_past_run_results_stay_hidden_after_the_formula_reading_the_table_is_edited(
    api_client, workflow_on_a_secret_table, test_run_nodes
):
    admin, workflow, _, admin_token, restricted_token, _ = workflow_on_a_secret_table
    _, iterator, _ = test_run_nodes
    histories = _run_results(workflow)
    assert _result_as(api_client, histories[iterator.id], restricted_token) is None

    AutomationNodeService().update_node(
        admin, iterator.id, service={"source": _formula("'nothing'")}
    )

    assert _result_as(api_client, histories[iterator.id], restricted_token) is None
    assert "Paid 250k" in str(
        _result_as(api_client, histories[iterator.id], admin_token)
    )


@pytest.mark.django_db
def test_past_run_results_stay_hidden_after_the_table_is_permanently_deleted(
    api_client, workflow_on_a_secret_table, test_run_nodes
):
    admin, workflow, trigger, admin_token, restricted_token, _ = (
        workflow_on_a_secret_table
    )
    _, iterator, _ = test_run_nodes
    histories = _run_results(workflow)
    table = trigger.service.specific.table
    TrashHandler.trash(admin, workflow.automation.workspace, table.database, table)
    TrashHandler.permanently_delete(table)

    for node in (trigger, iterator):
        assert _result_as(api_client, histories[node.id], restricted_token) is None
        assert _result_as(api_client, histories[node.id], admin_token) is None


def _forget_stored_tables(workflow):
    """
    Leaves the test run data and the run history of the workflow as they were
    stored before the tables they were built from were kept.
    """

    from baserow.contrib.automation.history.models import AutomationNodeHistory
    from baserow.core.services.models import Service

    Service.objects.filter(
        id__in=AutomationNode.objects_and_trash.filter(workflow=workflow).values(
            "service_id"
        )
    ).update(sample_data_table_ids=None)
    AutomationNodeHistory.objects.filter(workflow_history__workflow=workflow).update(
        read_table_ids=None
    )


@pytest.mark.django_db
def test_data_stored_before_the_tables_were_kept_stays_hidden_after_an_edit(
    api_client, workflow_on_a_secret_table, test_run_nodes
):
    from baserow.contrib.automation.nodes.backfill import fill_missing_table_ids

    admin, workflow, _, admin_token, restricted_token, _ = workflow_on_a_secret_table
    _, iterator, _ = test_run_nodes
    histories = _run_results(workflow)
    _forget_stored_tables(workflow)

    assert fill_missing_table_ids() == 1
    AutomationNodeService().update_node(
        admin, iterator.id, service={"source": _formula("'nothing'")}
    )

    response, services = _nodes_as(api_client, workflow, restricted_token)
    assert "Paid 250k" not in response.content.decode()
    assert services[iterator.id]["sample_data"] is None
    assert _result_as(api_client, histories[iterator.id], restricted_token) is None
    _, services = _nodes_as(api_client, workflow, admin_token)
    assert "Paid 250k" in str(services[iterator.id]["sample_data"])
    assert "Paid 250k" in str(
        _result_as(api_client, histories[iterator.id], admin_token)
    )


@pytest.mark.django_db
def test_filling_the_tables_keeps_those_already_stored(
    workflow_on_a_secret_table, test_run_nodes
):
    from baserow.contrib.automation.nodes.backfill import fill_missing_table_ids

    _, workflow, _, _, _, _ = workflow_on_a_secret_table
    _, iterator, _ = test_run_nodes
    service = iterator.service.specific
    service.sample_data_table_ids = [999]
    service.save()

    assert fill_missing_table_ids() == 0

    service.refresh_from_db()
    assert service.sample_data_table_ids == [999]


@pytest.mark.django_db
def test_a_test_run_after_the_iterator_is_edited_keeps_its_rows_hidden(
    api_client, enterprise_data_fixture, workflow_on_a_secret_table, test_run_nodes
):
    """
    The nodes before the tested one answer with their stored test run data, so
    the run history and the test run data built from it keep its tables.
    """

    from baserow.contrib.automation.history.models import AutomationNodeHistory

    _, workflow, _, admin_token, restricted_token, _ = workflow_on_a_secret_table
    _, iterator, email = test_run_nodes
    service = email.service.specific
    service.body = _formula(f"get('previous_node.{iterator.id}')")
    service.save()
    response = api_client.patch(
        reverse("api:automation:nodes:item", kwargs={"node_id": iterator.id}),
        {"service": {"source": _formula("'nothing'")}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {restricted_token}",
    )
    assert response.status_code == 200, response.json()
    last_history = AutomationNodeHistory.objects.order_by("-id").first().id

    _test_run(enterprise_data_fixture, workflow, email)

    replayed = AutomationNodeHistory.objects.get(
        id__gt=last_history, node=iterator, node_results__isnull=False
    )
    assert _result_as(api_client, replayed, restricted_token) is None
    assert "Paid 250k" in str(_result_as(api_client, replayed, admin_token))
    response, services = _nodes_as(api_client, workflow, restricted_token)
    assert "Paid 250k" not in response.content.decode()
    assert services[email.id]["sample_data"] is None
    _, services = _nodes_as(api_client, workflow, admin_token)
    assert services[email.id]["sample_data"] is not None


@pytest.mark.django_db
def test_the_error_of_a_failed_test_run_keeps_its_tables(
    api_client, enterprise_data_fixture, workflow_on_a_secret_table, test_run_nodes
):
    admin, workflow, trigger, _, restricted_token, _ = workflow_on_a_secret_table
    failing = _add_node(
        admin,
        workflow,
        "smtp_email",
        trigger,
        use_instance_smtp_settings=True,
        from_email=_formula("'from@example.com'"),
        to_emails=_formula("''"),
        subject=_formula("'Report'"),
        body=_formula(f"get('previous_node.{trigger.id}.0.Salary')"),
    )
    _test_run(enterprise_data_fixture, workflow, failing)
    assert "_error" in failing.service.specific.sample_data

    AutomationNodeService().update_node(
        admin, failing.id, service={"body": _formula("'Weekly report'")}
    )

    _, services = _nodes_as(api_client, workflow, restricted_token)
    assert services[failing.id]["sample_data"] is None


@pytest.mark.django_db
def test_a_built_path_is_refused_when_only_the_stored_tables_are_hidden(
    workflow_on_a_secret_table, test_run_nodes
):
    admin, workflow, trigger, _, _, restricted = workflow_on_a_secret_table
    _, iterator, email = test_run_nodes
    # The trigger is the only node on the table, and reads of it are gone.
    AutomationNodeService().update_node(
        admin, iterator.id, service={"source": _formula("'nothing'")}
    )
    AutomationNodeService().update_node(
        admin, email.id, service={"body": _formula("'Weekly report'")}
    )
    table = trigger.service.specific.table
    TrashHandler.trash(admin, workflow.automation.workspace, table.database, table)
    TrashHandler.permanently_delete(table)
    ctx = ToolContext(user=restricted, workspace=workflow.automation.workspace)

    result = update_nodes(
        ctx,
        workflow.id,
        [
            NodeUpdate(
                node_id=email.id,
                subject=f"get(concat('previous_node.', '{iterator.id}', '.0.x'))",
            )
        ],
    )

    (error,) = result["formula_errors"]
    assert "builds" in error["error"]


@broadcast_node_events
@pytest.mark.django_db(transaction=True)
def test_node_events_show_nobody_the_data_of_a_deleted_table(
    django_capture_on_commit_callbacks, workflow_on_a_secret_table, test_run_nodes
):
    admin, workflow, trigger, _, _, restricted = workflow_on_a_secret_table
    _, iterator, _ = test_run_nodes
    table = trigger.service.specific.table
    with transaction.atomic():
        TrashHandler.trash(admin, workflow.automation.workspace, table.database, table)
        TrashHandler.permanently_delete(table)

    sent = _broadcast_node_events(
        django_capture_on_commit_callbacks,
        lambda: AutomationNodeService().update_node(admin, iterator.id, label="New"),
    )

    for user in (admin, restricted):
        (payload,) = sent[user.id]
        assert "Paid 250k" not in str(payload)
        assert payload["node"]["service"]["sample_data"] is None


@pytest.mark.django_db
def test_a_node_waiting_for_another_run_keeps_the_tables_that_run_read(
    api_client, enterprise_data_fixture, workflow_on_a_secret_table
):
    """
    A start workflow node returns what the run it started answered, which is
    built from the tables that run read.
    """

    fixture = enterprise_data_fixture
    admin, workflow, trigger, admin_token, restricted_token, _ = (
        workflow_on_a_secret_table
    )
    start = _add_node(admin, workflow, "start_workflow", trigger)
    run = fixture.create_automation_workflow_history(
        workflow=workflow, original_workflow=workflow
    )
    waiting = fixture.create_automation_node_history(
        workflow_history=run, node=start, read_table_ids=[]
    )
    other_workflow = AutomationWorkflowService().create_workflow(
        admin, workflow.automation.id, "Other"
    )
    started = fixture.create_automation_workflow_history(
        workflow=other_workflow, original_workflow=other_workflow
    )
    fixture.create_automation_node_history(
        workflow_history=started,
        node=trigger,
        read_table_ids=[trigger.service.specific.table_id],
    )

    AutomationNodeHandler().complete_deferred_node(
        waiting.id, started.id, "", timed_out=True
    )

    waiting.refresh_from_db()
    assert waiting.read_table_ids == [trigger.service.specific.table_id]
    assert _result_as(api_client, waiting, restricted_token) is None
    assert _result_as(api_client, waiting, admin_token) is not None


@pytest.mark.django_db
def test_the_tables_are_filled_after_the_migrate_that_adds_them(
    workflow_on_a_secret_table, test_run_nodes
):
    from baserow.contrib.automation.nodes.backfill import (
        fill_missing_table_ids_after_migrate,
    )

    _, workflow, trigger, _, _, _ = workflow_on_a_secret_table
    _, iterator, _ = test_run_nodes
    _forget_stored_tables(workflow)

    class Migration:
        def __init__(self, app_label, name):
            self.app_label, self.name = app_label, name

    other = Migration(
        "automation", "0045_automationworkflowhistory_triggered_by_user_type"
    )
    fill_missing_table_ids_after_migrate(plan=[(other, False)])
    iterator.service.specific.refresh_from_db()
    assert iterator.service.specific.sample_data_table_ids is None

    adding = Migration("automation", "0046_node_history_read_table_ids")
    fill_missing_table_ids_after_migrate(plan=[(adding, False)])
    iterator.service.specific.refresh_from_db()
    assert iterator.service.specific.sample_data_table_ids == [
        trigger.service.specific.table_id
    ]
