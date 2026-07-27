from io import BytesIO

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    CreateRowWorkflowAction,
    DatabaseWorkflowAction,
    DeleteRowWorkflowAction,
)
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_export_includes_the_actions(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )

    exported = field_type_registry.get_by_model(button_field).export_serialized(
        button_field
    )

    assert len(exported["workflow_actions"]) == 1
    assert exported["workflow_actions"][0]["type"] == "create_row"
    assert exported["workflow_actions"][0]["service"]["table_id"] == table.id


@pytest.mark.django_db
def test_duplicating_the_table_remaps_the_action_target(data_fixture):
    """The service targets a table in the same database, the hard case in ADR 006."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_field)

    assert action.specific.service.specific.table_id == duplicated_table.id
    assert action.specific.service.specific.table_id != table.id


@pytest.mark.django_db
@pytest.mark.xfail(
    reason="ADR 006 section 8 promises actions and services are duplicated with the "
    "field, but `FieldHandler.duplicate_field` passes the exported values through "
    "`create_field`, where `extract_allowed` drops `workflow_actions`. Fixing it "
    "needs a per-type duplication hook on `FieldType`, which is a separate design "
    "decision. Delete this marker once that hook exists.",
    strict=True,
)
def test_duplicating_a_single_field_copies_its_actions(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_field, _ = FieldHandler().duplicate_field(user, button_field)

    actions = list(DatabaseWorkflowAction.objects.filter(field=duplicated_field))
    assert [a.specific.get_type().type for a in actions] == ["create_row"]
    assert actions[0].specific.service.specific.table_id == table.id


@pytest.mark.django_db(transaction=True)
def test_actions_survive_an_application_export_import(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )
    data_fixture.create_database_workflow_action(
        DeleteRowWorkflowAction, field=button_field
    )

    config = ImportExportConfig(include_permission_data=False)
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    imported_table = imported[0].table_set.get(name=table.name)
    imported_field = imported_table.field_set.get(name="btn").specific
    actions = list(
        DatabaseWorkflowAction.objects.filter(field=imported_field).order_by("order")
    )

    assert [a.specific.get_type().type for a in actions] == ["create_row", "delete_row"]
    assert actions[0].specific.service.specific.table_id == imported_table.id
    assert actions[0].specific.service.specific.table_id != table.id
