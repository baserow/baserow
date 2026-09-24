from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.database.fields.field_types import ButtonFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    CoreSMTPEmailWorkflowAction,
    DatabaseWorkflowServiceAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
    SlackWriteMessageWorkflowAction,
)
from baserow.contrib.database.workflow_actions.reconfiguration import (
    button_fields_depending_on,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowIntegration,
    LocalBaserowUpsertRow,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.service import IntegrationService
from baserow.core.trash.handler import TrashHandler


def _requires_reconfiguration(button_field):
    """
    Reads the flag both ways a button field is loaded, and fails if they
    disagree, so every case below also pins the annotation to the fallback.
    It also reads each action's own flag both ways, and fails unless the
    field's flag is whether any action has it.
    """

    annotated = (
        ButtonFieldType()
        .enhance_field_queryset_for_serialization(
            ButtonField.objects.filter(id=button_field.id), None
        )
        .get()
        .requires_reconfiguration
    )
    fallback = ButtonField.objects.get(id=button_field.id).requires_reconfiguration
    assert annotated == fallback, "The annotation and the fallback disagree."

    user = button_field.table.database.workspace.users.first()
    listed = [
        action
        for action in DatabaseWorkflowActionService().get_workflow_actions(
            user, button_field
        )
        if isinstance(action, DatabaseWorkflowServiceAction)
    ]
    per_action = [action.requires_reconfiguration for action in listed]
    per_action_fallback = [
        type(action).objects.get(pk=action.pk).requires_reconfiguration
        for action in listed
    ]
    assert per_action == per_action_fallback, "An action's flag disagrees."
    assert any(per_action) == annotated, "The field isn't any of its actions."
    return annotated


def _row_action(data_fixture, model_class, button_field, table, row_id="'1'"):
    """
    A row action on this table. An update is given a row id, since one without
    fails every click and needs reconfiguring on its own.
    """

    action = data_fixture.create_database_workflow_action(
        model_class, field=button_field
    )
    service = action.service.specific
    service.table = table
    if model_class is LocalBaserowUpdateRowWorkflowAction:
        service.row_id = row_id
    service.save()
    return action, service


def _slack_action(data_fixture, button_field, integration):
    action = data_fixture.create_database_workflow_action(
        SlackWriteMessageWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.integration = integration
    service.save()
    return action, service


@pytest.fixture
def setup(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="People",
        # Two fields, so "Name" isn't the (undeletable) primary field.
        fields=[("Id", "text", {}), ("Name", "text", {})],
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    return user, database, table, name_field, button_field


@pytest.mark.django_db
def test_a_button_without_actions_does_not_need_reconfiguring(setup):
    *_, button_field = setup

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class",
    [LocalBaserowCreateRowWorkflowAction, LocalBaserowUpdateRowWorkflowAction],
)
def test_a_mapping_on_a_trashed_field_needs_reconfiguring_until_restored(
    data_fixture, setup, model_class
):
    user, _, table, name_field, button_field = setup
    _, service = _row_action(data_fixture, model_class, button_field, table)
    service.field_mappings.create(field=name_field, value="'x'", enabled=True)

    assert _requires_reconfiguration(button_field) is False

    FieldHandler().delete_field(user, name_field)

    assert _requires_reconfiguration(button_field) is True

    TrashHandler.restore_item(user, "field", name_field.id)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
@pytest.mark.parametrize("row_id", ["", "   "])
def test_an_update_row_without_a_row_id_needs_reconfiguring(
    data_fixture, setup, row_id
):
    """Every click on it is refused (`UpdateRowRequiresRowIdMixin`), so it is
    no different to the person clicking than a target in the trash."""

    _, _, table, _, button_field = setup
    _, service = _row_action(
        data_fixture,
        LocalBaserowUpdateRowWorkflowAction,
        button_field,
        table,
        row_id=row_id,
    )

    assert _requires_reconfiguration(button_field) is True

    service.row_id = "'1'"
    service.save()

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_create_row_without_a_row_id_does_not_need_reconfiguring(data_fixture, setup):
    """A create makes the row, so it never names one."""

    _, _, table, _, button_field = setup
    _row_action(data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_disabled_mapping_on_a_trashed_field_does_not_count(data_fixture, setup):
    user, _, table, name_field, button_field = setup
    _, service = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table
    )
    service.field_mappings.create(field=name_field, value="'x'", enabled=False)

    FieldHandler().delete_field(user, name_field)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_trashed_mapping_with_an_integration_does_not_count(data_fixture, setup):
    """With an integration the dispatch drops the mapping rather than failing."""

    user, database, table, name_field, button_field = setup
    _, service = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table
    )
    service.integration = data_fixture.create_local_baserow_integration(
        application=database, user=user
    )
    service.save()
    service.field_mappings.create(field=name_field, value="'x'", enabled=True)

    FieldHandler().delete_field(user, name_field)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class",
    [
        LocalBaserowCreateRowWorkflowAction,
        LocalBaserowUpdateRowWorkflowAction,
        LocalBaserowDeleteRowWorkflowAction,
    ],
)
def test_a_row_action_without_a_table_needs_reconfiguring(
    data_fixture, setup, model_class
):
    *_, button_field = setup
    _row_action(data_fixture, model_class, button_field, None)

    assert _requires_reconfiguration(button_field) is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class",
    [LocalBaserowCreateRowWorkflowAction, LocalBaserowDeleteRowWorkflowAction],
)
def test_a_trashed_target_table_needs_reconfiguring_until_restored(
    data_fixture, setup, model_class
):
    user, database, _, _, button_field = setup
    target = data_fixture.create_database_table(user=user, database=database)
    _row_action(data_fixture, model_class, button_field, target)

    TableHandler().delete_table(user, target)

    assert _requires_reconfiguration(button_field) is True

    TrashHandler.restore_item(user, "table", target.id)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_target_table_in_a_trashed_database_needs_reconfiguring(data_fixture, setup):
    user, database, _, _, button_field = setup
    other_database = data_fixture.create_database_application(
        user=user, workspace=database.workspace
    )
    target = data_fixture.create_database_table(user=user, database=other_database)
    _row_action(data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, target)

    CoreHandler().delete_application(user, other_database)

    assert _requires_reconfiguration(button_field) is True

    TrashHandler.restore_item(user, "application", other_database.id)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_target_table_in_a_trashed_workspace_needs_reconfiguring(data_fixture, setup):
    """An action can target a table of any workspace its editor is in."""

    user, _, _, _, button_field = setup
    other_workspace = data_fixture.create_workspace(user=user)
    other_database = data_fixture.create_database_application(
        user=user, workspace=other_workspace
    )
    target = data_fixture.create_database_table(user=user, database=other_database)
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        database_workflow_action_type_registry.get("local_baserow_create_row"),
        button_field,
        service={"table_id": target.id},
    )

    assert _requires_reconfiguration(button_field) is False

    CoreHandler().delete_workspace(user, other_workspace)

    assert _requires_reconfiguration(button_field) is True

    TrashHandler.restore_item(user, "workspace", other_workspace.id)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_trashed_integration_needs_reconfiguring_until_restored(data_fixture, setup):
    """The dispatch refuses a service whose integration is in the trash."""

    user, database, *_, button_field = setup
    bot = data_fixture.create_slack_bot_integration(application=database, user=user)
    _slack_action(data_fixture, button_field, bot)

    assert _requires_reconfiguration(button_field) is False

    IntegrationService().delete_integration(user, bot)

    assert _requires_reconfiguration(button_field) is True

    TrashHandler.restore_item(user, "integration", bot.id)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_an_action_missing_the_integration_it_needs_needs_reconfiguring(
    data_fixture, setup
):
    """The dispatch refuses a Slack action with no bot picked."""

    *_, button_field = setup
    _slack_action(data_fixture, button_field, None)

    assert _requires_reconfiguration(button_field) is True


@pytest.mark.django_db
def test_an_email_action_without_an_integration_does_not_need_reconfiguring(
    data_fixture, setup
):
    """A button's email action always sends through the instance's server."""

    *_, button_field = setup
    action = data_fixture.create_database_workflow_action(
        CoreSMTPEmailWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.use_instance_smtp_settings = True
    service.save()

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class", [OpenUrlWorkflowAction, CoreHTTPRequestWorkflowAction]
)
def test_other_action_types_never_need_reconfiguring(data_fixture, setup, model_class):
    *_, button_field = setup
    data_fixture.create_database_workflow_action(model_class, field=button_field)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_cached_table_model_serves_no_stale_flag(data_fixture, setup):
    """
    A table's model is cached until its own schema changes, and trashing what
    a button points at in another table doesn't change it.
    """

    user, database, table, _, button_field = setup
    target = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="Target",
        fields=[("Id", "text", {}), ("Name", "text", {})],
    )
    target_field = target.field_set.get(name="Name")
    _, service = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, target
    )
    service.field_mappings.create(field=target_field, value="'x'", enabled=True)

    def button_from_model():
        return table._get_model()._field_objects[button_field.id]["field"]

    assert button_from_model().requires_reconfiguration is False

    FieldHandler().delete_field(user, target_field)

    assert button_from_model().requires_reconfiguration is True


@pytest.mark.django_db
def test_generating_a_table_model_does_not_compute_the_flags(setup):
    """Nothing in a table's model reads them, and each costs subqueries."""

    *_, table, _, _ = setup

    with CaptureQueriesContext(connection) as captured:
        table._get_model(use_cache=False)

    sql = " ".join(query["sql"] for query in captured.captured_queries)
    assert "database_databaseworkflowaction" not in sql


@pytest.mark.django_db
def test_listing_actions_does_not_query_per_mapping(api_client, data_fixture):
    """`trashed` reads the mapped field, which must not cost a query each."""

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    _, service = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table
    )
    url = reverse(
        "api:database:workflow_actions:list", kwargs={"field_id": button_field.id}
    )

    def list_actions():
        with CaptureQueriesContext(connection) as captured:
            response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
            assert response.status_code == 200, response.json()
        return response.json(), len(captured)

    service.field_mappings.create(
        field=data_fixture.create_text_field(table=table), value="'a'", enabled=True
    )
    list_actions()
    _, one_mapping_queries = list_actions()

    for _ in range(3):
        service.field_mappings.create(
            field=data_fixture.create_text_field(table=table),
            value="'a'",
            enabled=True,
        )

    # Adding fields bumps the table's schema version, so the first list call
    # after that pays a one-off cost rebuilding the cached table model. Warm
    # that up the same way the one-mapping baseline above does, so the
    # comparison below isolates the per-mapping cost this test is about.
    list_actions()
    payload, four_mapping_queries = list_actions()

    assert all("trashed" in m for m in payload[0]["service"]["field_mappings"])
    assert four_mapping_queries == one_mapping_queries


@pytest.mark.django_db
def test_the_action_list_says_which_actions_need_reconfiguring(
    api_client, data_fixture
):
    """The editor names the action behind the button's flag."""

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    target = data_fixture.create_database_table(user=user, database=database)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    trashed_target_action, _ = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, target
    )
    _row_action(data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table)
    bot = data_fixture.create_slack_bot_integration(application=database, user=user)
    _slack_action(data_fixture, button_field, bot)
    data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    list_url = reverse(
        "api:database:workflow_actions:list", kwargs={"field_id": button_field.id}
    )

    def flags():
        response = api_client.get(list_url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == 200, response.json()
        return [action["requires_reconfiguration"] for action in response.json()]

    assert flags() == [False, False, False, False]

    TableHandler().delete_table(user, target)
    IntegrationService().delete_integration(user, bot)

    assert flags() == [True, False, True, False]

    # An action saved on its own is answered for without the list's annotation.
    response = api_client.patch(
        reverse(
            "api:database:workflow_actions:item",
            kwargs={"workflow_action_id": trashed_target_action.id},
        ),
        {"type": "local_baserow_create_row"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["requires_reconfiguration"] is True


@pytest.mark.django_db
def test_listing_actions_does_not_query_per_action_for_the_flag(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    url = reverse(
        "api:database:workflow_actions:list", kwargs={"field_id": button_field.id}
    )

    def list_actions():
        with CaptureQueriesContext(connection) as captured:
            response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
            assert response.status_code == 200, response.json()
        return response.json(), len(captured)

    # No table, so each of them needs reconfiguring.
    _row_action(data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, None)
    list_actions()
    _, one_action_queries = list_actions()

    for _ in range(3):
        _row_action(
            data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, None
        )
    payload, four_action_queries = list_actions()

    assert [action["requires_reconfiguration"] for action in payload] == [True] * 4
    assert four_action_queries == one_action_queries


SERVICE_TABLES = {
    "integrations_localbaserowupsertrow",
    "core_service",
    "core_integration",
}


def _fill_service_tables(application, table, count=10000):
    """
    Adds `count` unrelated integrations, services and upsert row services, as
    the builder and automations would. On a few thousand rows the planner may
    rightly hash a whole table rather than look up one row per action.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH integrations AS (
                INSERT INTO core_integration
                    (trashed, name, "order", application_id, content_type_id)
                SELECT false, '', n, %s, %s FROM generate_series(1, %s) AS n
                RETURNING id
            ), services AS (
                INSERT INTO core_service (trashed, content_type_id, integration_id)
                SELECT false, %s, id FROM integrations
                RETURNING id
            )
            INSERT INTO integrations_localbaserowupsertrow (service_ptr_id, table_id)
            SELECT id, %s FROM services
            """,
            [
                application.id,
                ContentType.objects.get_for_model(LocalBaserowIntegration).id,
                count,
                ContentType.objects.get_for_model(LocalBaserowUpsertRow).id,
                table.id,
            ],
        )


def _service_scans(sql, params=None):
    """
    Plans `sql` with sequential scans discouraged, as they would be on tables
    of real size, and returns every scan of a service or integration in the plan.
    The tables are analyzed first and the costs pinned to Postgres' defaults, so
    the plan depends neither on whether autovacuum analyzed them during an
    earlier test nor on how the database was started: the dev database lowers
    `random_page_cost`, which makes an index lookup look cheaper than on CI.
    """

    def walk(node):
        if node.get("Relation Name") in SERVICE_TABLES:
            yield node
        for child in node.get("Plans", []):
            yield from walk(child)

    with connection.cursor() as cursor:
        for service_table in sorted(SERVICE_TABLES):
            cursor.execute(f"ANALYZE {service_table}")
        cursor.execute("SET LOCAL random_page_cost = 4")
        cursor.execute("SET LOCAL work_mem = '4MB'")
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql, params)
        plan = cursor.fetchone()[0]
        cursor.execute("SET LOCAL enable_seqscan = on")
        cursor.execute("RESET random_page_cost")
        cursor.execute("RESET work_mem")
    return list(walk(plan[0]["Plan"]))


@pytest.mark.django_db
def test_the_check_only_reads_the_buttons_own_services(data_fixture, setup):
    """
    Services and integrations are shared with the builder and automations, so
    the check must look up a button's own services rather than scan them all.
    """

    user, database, table, name_field, button_field = setup
    _, service = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table
    )
    service.field_mappings.create(field=name_field, value="'x'", enabled=True)
    _slack_action(
        data_fixture,
        button_field,
        data_fixture.create_slack_bot_integration(application=database, user=user),
    )
    for _ in range(20):
        unrelated = data_fixture.create_local_baserow_upsert_row_service(table=table)
        unrelated.field_mappings.create(field=name_field, value="'x'", enabled=True)
        data_fixture.create_slack_write_message_service()
    _fill_service_tables(database, table)

    annotated = ButtonFieldType().enhance_field_queryset_for_serialization(
        ButtonField.objects.filter(id=button_field.id), None
    )
    with CaptureQueriesContext(connection) as captured:
        ButtonField.objects.get(id=button_field.id).requires_reconfiguration
    fallback_sql = captured.captured_queries[-1]["sql"]

    for scans in [
        _service_scans(*annotated.query.sql_with_params()),
        _service_scans(fallback_sql),
    ]:
        assert {scan["Relation Name"] for scan in scans} == SERVICE_TABLES
        for scan in scans:
            assert "Index Cond" in scan, scan
            rows_read = scan["Actual Rows"] + scan.get("Rows Removed by Filter", 0)
            assert rows_read <= 1, scan


@pytest.mark.django_db
def test_the_realtime_lookup_keeps_the_services_in_a_subquery(data_fixture, setup):
    """
    A table can be the target of many builder and automation services, so their
    ids are not read into Python only to be sent back.
    """

    *_, table, _, button_field = setup
    _row_action(data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table)
    for _ in range(3):
        data_fixture.create_local_baserow_upsert_row_service(table=table)

    with CaptureQueriesContext(connection) as captured:
        assert list(button_fields_depending_on(table_ids=[table.id])) == [button_field]

    check, buttons = captured.captured_queries
    # Asks whether there is one rather than reading them all, and a UNION
    # without ALL would read them all to drop duplicates.
    assert check["sql"].endswith("LIMIT 1")
    assert "UNION ALL" in check["sql"]
    assert "integrations_localbaserowupsertrow" in buttons["sql"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lookup,service_table,action_count",
    [
        ("field_ids", "integrations_localbaserowtableservicefieldmapping", 2),
        ("table_ids", "integrations_localbaserowupsertrow", 2),
        ("table_ids", "integrations_localbaserowdeleterow", 1),
    ],
)
def test_the_realtime_lookup_pairs_each_service_with_its_actions(
    data_fixture, setup, lookup, service_table, action_count
):
    """
    Mappings and upserts only back create and update row actions, and a delete
    row service only a delete row action.
    """

    *_, table, name_field, _ = setup
    service = data_fixture.create_local_baserow_upsert_row_service(table=table)
    service.field_mappings.create(field=name_field, value="'x'", enabled=True)
    ids = {"field_ids": [name_field.id], "table_ids": [table.id]}[lookup]

    sql = str(button_fields_depending_on(**{lookup: ids}).query)

    assert sql.count(f'FROM "{service_table}"') == action_count


@pytest.mark.django_db
def test_updating_an_action_does_not_query_per_mapping(api_client, data_fixture):
    """Neither saving the mappings nor sending them back costs a query each."""

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    fields = [data_fixture.create_text_field(table=table) for _ in range(10)]
    button_field = data_fixture.create_button_field(table=table, label="Go")
    action, _ = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table
    )
    url = reverse(
        "api:database:workflow_actions:item",
        kwargs={"workflow_action_id": action.id},
    )

    def update_mappings(mapped_fields):
        payload = {
            "type": "local_baserow_create_row",
            "service": {
                "type": "local_baserow_upsert_row",
                "table_id": table.id,
                "field_mappings": [
                    {"field_id": field.id, "value": "'a'", "enabled": True}
                    for field in mapped_fields
                ],
            },
        }
        with CaptureQueriesContext(connection) as captured:
            response = api_client.patch(
                url, payload, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
            )
            assert response.status_code == 200, response.json()
        return response.json(), len(captured)

    update_mappings(fields[:1])
    _, one_mapping_queries = update_mappings(fields[:1])
    update_mappings(fields)
    payload, ten_mapping_queries = update_mappings(fields)

    assert len(payload["service"]["field_mappings"]) == 10
    assert all(m["trashed"] is False for m in payload["service"]["field_mappings"])
    assert ten_mapping_queries == one_mapping_queries


@pytest.mark.django_db
def test_a_lookup_no_action_model_can_use_matches_no_button(data_fixture, setup):
    """
    With no action model to pair the integration's services with, the lookup
    matches no button rather than every one.
    """

    user, database, table, _, button_field = setup
    bot = data_fixture.create_slack_bot_integration(application=database, user=user)
    _slack_action(data_fixture, button_field, bot)
    other_button = data_fixture.create_button_field(table=table, label="Other")
    _row_action(data_fixture, LocalBaserowCreateRowWorkflowAction, other_button, table)

    with patch(
        "baserow.contrib.database.workflow_actions.reconfiguration."
        "_unusable_integration_by_action_model",
        return_value={},
    ):
        assert list(button_fields_depending_on(integration_ids=[bot.id])) == []
