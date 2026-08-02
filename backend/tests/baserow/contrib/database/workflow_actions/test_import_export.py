from io import BytesIO

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    CreateRowWorkflowAction,
    DatabaseWorkflowAction,
    DeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFieldMapping,
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
def test_duplicating_a_single_field_copies_its_actions(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    target_table = data_fixture.create_database_table(user=user, database=database)
    button_field = data_fixture.create_button_field(table=table, name="btn", label="Go")
    target_field = data_fixture.create_text_field(table=target_table)
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=target_table
    )
    service.field_mappings.create(field=target_field, value="'hi'", enabled=True)
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_field, _ = FieldHandler().duplicate_field(user, button_field)

    actions = list(DatabaseWorkflowAction.objects.filter(field=duplicated_field))
    assert [a.specific.get_type().type for a in actions] == ["create_row"]
    assert actions[0].specific.service_id != service.id, (
        "The duplicate must own its own service, not share the original's."
    )
    duplicated_service = actions[0].specific.service.specific
    assert duplicated_service.table_id == target_table.id, (
        "The duplicated action must still point at the original target table. "
        "An id_mapping that maps the table to nothing nulls it, which produces "
        "a copy that looks correct and does nothing."
    )
    # Queried fresh: the service instance carries the mappings it was created
    # with, whose in-memory `value` isn't converted back into a formula object.
    duplicated_mappings = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=duplicated_service.id
    )
    assert [(m.field_id, m.value["formula"]) for m in duplicated_mappings] == [
        (target_field.id, "'hi'")
    ], (
        "The field mappings must keep pointing at the fields of the target "
        "table, which an id_mapping without them would drop."
    )


@pytest.mark.django_db
def test_duplicate_table_remaps_open_url_action_field_references(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    button_field = data_fixture.create_button_field(table=table, name="btn")
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={
            "formula": f"get('fields.field_{text_field.id}')",
            "mode": "simple",
        },
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = OpenUrlWorkflowAction.objects.filter(field=duplicated_field)
    new_text_field_id = (
        duplicated_table.field_set.exclude(id=duplicated_field.id).get().id
    )

    assert action.url["formula"] == f"get('fields.field_{new_text_field_id}')"
    assert action.url["mode"] == "simple"


@pytest.mark.django_db
def test_duplicate_table_keeps_raw_open_url_action_formula_working(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, name="btn")
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"formula": "https://example.com?x=(1", "mode": "raw"},
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = OpenUrlWorkflowAction.objects.filter(field=duplicated_field)

    # A raw formula is literal text that is never parsed. Downgrading it to
    # `simple` would make this unparseable and break the duplicated action.
    assert action.url["mode"] == "raw"
    assert action.url["formula"] == "https://example.com?x=(1"


@pytest.mark.django_db
def test_duplicate_table_keeps_open_url_action_broken_references(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, name="btn")
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={
            "formula": "concat('test:',get('fields.field_0'))",
            "mode": "simple",
        },
    )

    # A reference to a field missing from the id mapping must not fail the
    # duplication; the reference is left pointing where it was. The formula is
    # re-rendered from its parse tree, so casing and spacing may be normalised.
    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = OpenUrlWorkflowAction.objects.filter(field=duplicated_field)

    assert action.url["formula"] == "concat('test:',get('fields.field_0'))"


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


@pytest.mark.django_db
def test_duplicate_table_remaps_a_field_mapping_formula(data_fixture):
    """The `field_id` of a mapping is remapped by the service, its `value` is
    not, so a formula in it needs the import pass of ADR 006 section 6."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    copy_field = data_fixture.create_text_field(table=table, name="Copy")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    service.field_mappings.create(
        field=copy_field, value=f"get('row.field_{name_field.id}')", enabled=True
    )
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_name_field = duplicated_table.field_set.get(name="Name")
    duplicated_copy_field = duplicated_table.field_set.get(name="Copy")
    duplicated_button = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_button)
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=action.specific.service_id
    )

    assert duplicated_name_field.id != name_field.id
    assert mapping.field_id == duplicated_copy_field.id
    # Left pointing at the original field, the copy would silently read the
    # source table's value instead of its own row's.
    assert mapping.value["formula"] == f"get('row.field_{duplicated_name_field.id}')"


@pytest.mark.django_db
def test_duplicate_table_remaps_a_row_id_formula(data_fixture):
    """`row_id` is a formula on the service itself rather than on a mapping."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(table=table, name="Target")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_delete_row_service(
        integration=None, table=table, row_id=f"get('row.field_{number_field.id}')"
    )
    data_fixture.create_database_workflow_action(
        DeleteRowWorkflowAction, field=button_field, service=service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_number_field = duplicated_table.field_set.get(name="Target")
    duplicated_button = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_button)

    assert duplicated_number_field.id != number_field.id
    assert (
        action.specific.service.specific.row_id["formula"]
        == f"get('row.field_{duplicated_number_field.id}')"
    )


@pytest.mark.django_db
def test_duplicate_table_keeps_an_unimportable_field_mapping_formula(data_fixture):
    """Nothing to remap must leave the formula's meaning and its references
    alone, rather than fail the duplication. The formula is re-rendered from
    its parse tree, so casing and spacing may be normalised."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    copy_field = data_fixture.create_text_field(table=table, name="Copy")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    # A trashed field, which is never exported, so the mapping has no entry.
    service.field_mappings.create(
        field=copy_field, value="concat('x:',get('row.field_0'))", enabled=True
    )
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_button = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_button)
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=action.specific.service_id
    )

    assert mapping.value["formula"] == "concat('x:',get('row.field_0'))"


@pytest.mark.django_db
def test_duplicate_table_keeps_a_formula_naming_an_unknown_data_provider(data_fixture):
    """An export written by a version that has a provider this one doesn't must
    still import; the reference is left alone rather than blowing up."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    copy_field = data_fixture.create_text_field(table=table, name="Copy")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    service.field_mappings.create(
        field=copy_field, value="get('previous_action.1.value')", enabled=True
    )
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_button = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_button)
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=action.specific.service_id
    )

    assert mapping.value["formula"] == "get('previous_action.1.value')"


@pytest.mark.django_db(transaction=True)
def test_a_field_mapping_formula_survives_an_application_export_import(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    copy_field = data_fixture.create_text_field(table=table, name="Copy")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    service.field_mappings.create(
        field=copy_field, value=f"get('row.field_{name_field.id}')", enabled=True
    )
    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field, service=service
    )

    config = ImportExportConfig(include_permission_data=False)
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    imported_table = imported[0].table_set.get(name=table.name)
    imported_name_field = imported_table.field_set.get(name="Name")
    imported_button = imported_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=imported_button)
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=action.specific.service_id
    )

    assert imported_name_field.id != name_field.id
    assert mapping.value["formula"] == f"get('row.field_{imported_name_field.id}')"
