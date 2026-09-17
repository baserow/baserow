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
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler


def _requires_reconfiguration(button_field):
    """
    Reads the flag both ways a button field is loaded, and fails if they
    disagree, so every case below also pins the annotation to the fallback.
    """

    annotated = (
        ButtonFieldType()
        .enhance_field_queryset(ButtonField.objects.filter(id=button_field.id), None)
        .get()
        .requires_reconfiguration
    )
    fallback = ButtonField.objects.get(id=button_field.id).requires_reconfiguration
    assert annotated == fallback, "The annotation and the fallback disagree."
    return annotated


def _row_action(data_fixture, model_class, button_field, table):
    action = data_fixture.create_database_workflow_action(
        model_class, field=button_field
    )
    service = action.service.specific
    service.table = table
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
@pytest.mark.parametrize(
    "model_class", [OpenUrlWorkflowAction, CoreHTTPRequestWorkflowAction]
)
def test_other_action_types_never_need_reconfiguring(data_fixture, setup, model_class):
    *_, button_field = setup
    data_fixture.create_database_workflow_action(model_class, field=button_field)

    assert _requires_reconfiguration(button_field) is False


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


def _upsert_row_scans(sql, params=None):
    """
    Plans `sql` with sequential scans discouraged, as they would be on tables
    of real size, and returns every scan of an upsert row service in the plan.
    """

    def walk(node):
        if node.get("Relation Name") == "integrations_localbaserowupsertrow":
            yield node
        for child in node.get("Plans", []):
            yield from walk(child)

    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql, params)
        plan = cursor.fetchone()[0]
        cursor.execute("SET LOCAL enable_seqscan = on")
    return list(walk(plan[0]["Plan"]))


@pytest.mark.django_db
def test_the_check_only_reads_the_buttons_own_services(data_fixture, setup):
    """
    Upsert row services are shared with the builder and automations, so the
    check must look up a button's own services rather than scan them all.
    """

    user, database, table, name_field, button_field = setup
    _, service = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table
    )
    service.field_mappings.create(field=name_field, value="'x'", enabled=True)
    for _ in range(20):
        unrelated = data_fixture.create_local_baserow_upsert_row_service(table=table)
        unrelated.field_mappings.create(field=name_field, value="'x'", enabled=True)

    annotated = ButtonFieldType().enhance_field_queryset(
        ButtonField.objects.filter(id=button_field.id), None
    )
    with CaptureQueriesContext(connection) as captured:
        ButtonField.objects.get(id=button_field.id).requires_reconfiguration
    fallback_sql = captured.captured_queries[-1]["sql"]

    for scans in [
        _upsert_row_scans(*annotated.query.sql_with_params()),
        _upsert_row_scans(fallback_sql),
    ]:
        assert scans
        for scan in scans:
            assert "Index Cond" in scan, scan
            rows_read = scan["Actual Rows"] + scan.get("Rows Removed by Filter", 0)
            assert rows_read <= 1, scan
