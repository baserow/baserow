from io import BytesIO

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFieldMapping,
)
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress


@pytest.mark.django_db
def test_export_includes_the_actions(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )

    exported = field_type_registry.get_by_model(button_field).export_serialized(
        button_field
    )

    assert len(exported["workflow_actions"]) == 1
    assert exported["workflow_actions"][0]["type"] == "local_baserow_create_row"
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
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_field)

    assert action.specific.service.specific.table_id == duplicated_table.id
    assert action.specific.service.specific.table_id != table.id


@pytest.mark.django_db
def test_duplicating_the_table_keeps_a_target_outside_it(data_fixture):
    """The duplicated table is the only one in the id mapping, so a service
    pointing anywhere else finds no mapping for its target. A duplicate stays in
    the same workspace, so the original table is still the right one to keep."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    other_database = data_fixture.create_database_application(user=user)
    other_table = data_fixture.create_database_table(user=user, database=other_database)
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=other_table
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_field)

    assert action.specific.service.specific.table_id == other_table.id


@pytest.mark.django_db
def test_duplicating_the_table_keeps_the_mappings_of_a_target_outside_it(data_fixture):
    """A kept target table's fields are outside the duplicated scope too, so
    dropping them left the action on the right table with nothing to write."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    other_database = data_fixture.create_database_application(user=user)
    other_table = data_fixture.create_database_table(user=user, database=other_database)
    other_field = data_fixture.create_text_field(table=other_table, name="Name")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=other_table
    )
    service.field_mappings.create(field=other_field, value="'x'", enabled=True)
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_field)
    duplicated_service = action.specific.service.specific

    assert duplicated_service.table_id == other_table.id
    assert [m.field_id for m in duplicated_service.field_mappings.all()] == [
        other_field.id
    ], "The action keeps its target table, so it must keep what it writes there."


@pytest.mark.django_db
def test_duplicating_the_table_drops_a_mapping_whose_field_was_trashed(data_fixture):
    """A trashed field is unmapped for the same reason an out of scope one is,
    so keeping every unmapped id would resurrect this against the source."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    doomed_field = data_fixture.create_text_field(table=table, name="Doomed")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    service.field_mappings.create(field=doomed_field, value="'x'", enabled=True)
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )
    FieldHandler().delete_field(user, doomed_field)

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_field)
    duplicated_service = action.specific.service.specific

    assert duplicated_service.table_id == duplicated_table.id
    assert list(duplicated_service.field_mappings.all()) == []


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
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated_field, _ = FieldHandler().duplicate_field(user, button_field)

    actions = list(DatabaseWorkflowAction.objects.filter(field=duplicated_field))
    assert [a.specific.get_type().type for a in actions] == ["local_baserow_create_row"]
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
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
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

    assert [a.specific.get_type().type for a in actions] == [
        "local_baserow_create_row",
        "local_baserow_delete_row",
    ]
    assert actions[0].specific.service.specific.table_id == imported_table.id
    assert actions[0].specific.service.specific.table_id != table.id


@pytest.mark.django_db(transaction=True)
def test_an_action_targeting_another_database_survives_the_import(data_fixture):
    """Applications are imported one at a time, so when the button's database is
    imported the other one does not exist yet. Without deferring the action
    import, the target table is nulled and the field mappings are dropped."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    # `order` decides the import order, so the button's database goes first.
    database_a = data_fixture.create_database_application(
        workspace=workspace, name="A", order=1
    )
    database_b = data_fixture.create_database_application(
        workspace=workspace, name="B", order=2
    )
    table_a = data_fixture.create_database_table(database=database_a, name="TA")
    table_b = data_fixture.create_database_table(database=database_b, name="TB")
    source_field = data_fixture.create_text_field(table=table_a, name="Source")
    target_field = data_fixture.create_text_field(table=table_b, name="Target")
    button_field = data_fixture.create_button_field(table=table_a, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table_b
    )
    service.field_mappings.create(
        field=target_field, value=f"get('row.field_{source_field.id}')", enabled=True
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )

    config = ImportExportConfig(include_permission_data=False)
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    imported_by_name = {application.name: application for application in imported}
    imported_a = imported_by_name["A"].table_set.get(name="TA")
    imported_b = imported_by_name["B"].table_set.get(name="TB")
    imported_source = imported_a.field_set.get(name="Source")
    imported_target = imported_b.field_set.get(name="Target")
    imported_button = imported_a.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=imported_button)
    imported_service = action.specific.service.specific
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=imported_service.id
    )

    assert imported_b.id != table_b.id
    assert imported_service.table_id == imported_b.id
    assert mapping.field_id == imported_target.id
    # The formula names the clicked row, which is in the button's own database.
    assert mapping.value["formula"] == f"get('row.field_{imported_source.id}')"


@pytest.mark.django_db
def test_actions_survive_a_duplicated_application(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="db")
    table = data_fixture.create_database_table(database=database, name="T")
    name_field = data_fixture.create_text_field(table=table, name="Name")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    service.field_mappings.create(
        field=name_field, value=f"get('row.field_{name_field.id}')", enabled=True
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )

    duplicated = CoreHandler().duplicate_application(user, database)

    duplicated_table = duplicated.table_set.get(name="T")
    duplicated_name_field = duplicated_table.field_set.get(name="Name")
    duplicated_button = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_button)
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=action.specific.service_id
    )

    assert action.specific.service.specific.table_id == duplicated_table.id
    assert mapping.field_id == duplicated_name_field.id
    assert mapping.value["formula"] == f"get('row.field_{duplicated_name_field.id}')"


@pytest.mark.django_db
def test_actions_survive_a_snapshot_and_its_restore(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, order=1)
    table = data_fixture.create_database_table(database=database, name="T")
    name_field = data_fixture.create_text_field(table=table, name="Name")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    service.field_mappings.create(
        field=name_field, value=f"get('row.field_{name_field.id}')", enabled=True
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=database, name="snap", created_by=user
    )

    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    restored = SnapshotHandler().perform_restore(snapshot, Progress(total=100))

    restored_table = restored.table_set.get(name="T")
    restored_name_field = restored_table.field_set.get(name="Name")
    restored_button = restored_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=restored_button)
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=action.specific.service_id
    )

    assert action.specific.service.specific.table_id == restored_table.id
    assert mapping.field_id == restored_name_field.id
    assert mapping.value["formula"] == f"get('row.field_{restored_name_field.id}')"


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
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
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
        LocalBaserowDeleteRowWorkflowAction, field=button_field, service=service
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
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
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
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
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
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
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
