from io import BytesIO

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    CoreSMTPEmailWorkflowAction,
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
        field=copy_field,
        value="get('a_provider_from_the_future.1.value')",
        enabled=True,
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

    assert mapping.value["formula"] == "get('a_provider_from_the_future.1.value')"


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


@pytest.mark.django_db
def test_duplicate_table_remaps_a_previous_action_reference(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    button_field = data_fixture.create_button_field(table=table, name="btn")

    create_row = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = create_row.service.specific
    service.table = table
    service.save()

    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={
            "formula": (
                f"get('previous_action.{create_row.id}.field_{text_field.id}')"
            ),
            "mode": "simple",
        },
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (duplicated_create_row,) = LocalBaserowCreateRowWorkflowAction.objects.filter(
        field=duplicated_field
    )
    (duplicated_open_url,) = OpenUrlWorkflowAction.objects.filter(
        field=duplicated_field
    )
    new_text_field_id = (
        duplicated_table.field_set.exclude(id=duplicated_field.id).get().id
    )

    assert duplicated_open_url.url["formula"] == (
        f"get('previous_action.{duplicated_create_row.id}.field_{new_text_field_id}')"
    )


@pytest.mark.django_db(transaction=True)
def test_a_previous_action_reference_survives_an_application_export_import(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    button_field = data_fixture.create_button_field(table=table, name="btn")
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    create_row = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=service
    )
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={
            "formula": (
                f"get('previous_action.{create_row.id}.field_{name_field.id}')"
            ),
            "mode": "simple",
        },
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
    (imported_create_row,) = LocalBaserowCreateRowWorkflowAction.objects.filter(
        field=imported_button
    )
    (imported_open_url,) = OpenUrlWorkflowAction.objects.filter(field=imported_button)

    assert imported_create_row.id != create_row.id
    assert imported_name_field.id != name_field.id
    assert imported_open_url.url["formula"] == (
        f"get('previous_action.{imported_create_row.id}"
        f".field_{imported_name_field.id}')"
    )


@pytest.mark.django_db
def test_duplicate_table_remaps_a_previous_action_reference_in_a_mapping(data_fixture):
    """A mapping's `value` is a formula the service does not remap itself, so a
    reference inside one needs both the action id and the field id it names to
    be carried over."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    copy_field = data_fixture.create_text_field(table=table, name="Copy")
    button_field = data_fixture.create_button_field(table=table, name="btn")

    first_service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    create_row = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=first_service
    )

    second_service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    second_service.field_mappings.create(
        field=copy_field,
        value=f"get('previous_action.{create_row.id}.field_{name_field.id}')",
        enabled=True,
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=second_service
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_name_field = duplicated_table.field_set.get(name="Name")
    duplicated_button = duplicated_table.field_set.get(name="btn").specific
    duplicated_create_row, duplicated_second = (
        LocalBaserowCreateRowWorkflowAction.objects.filter(
            field=duplicated_button
        ).order_by("order", "id")
    )
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=duplicated_second.service_id
    )

    assert duplicated_create_row.id != create_row.id
    assert duplicated_name_field.id != name_field.id
    assert mapping.value["formula"] == (
        f"get('previous_action.{duplicated_create_row.id}"
        f".field_{duplicated_name_field.id}')"
    )


@pytest.mark.django_db(transaction=True)
def test_a_previous_action_reference_in_a_mapping_survives_an_import(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    copy_field = data_fixture.create_text_field(table=table, name="Copy")
    button_field = data_fixture.create_button_field(table=table, name="btn")

    first_service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    create_row = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=first_service
    )

    second_service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    second_service.field_mappings.create(
        field=copy_field,
        value=f"get('previous_action.{create_row.id}.field_{name_field.id}')",
        enabled=True,
    )
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field, service=second_service
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
    imported_create_row, imported_second = (
        LocalBaserowCreateRowWorkflowAction.objects.filter(
            field=imported_button
        ).order_by("order", "id")
    )
    (mapping,) = LocalBaserowTableServiceFieldMapping.objects.filter(
        service_id=imported_second.service_id
    )

    assert imported_create_row.id != create_row.id
    assert imported_name_field.id != name_field.id
    assert mapping.value["formula"] == (
        f"get('previous_action.{imported_create_row.id}"
        f".field_{imported_name_field.id}')"
    )


@pytest.mark.django_db
def test_a_previous_action_reference_outside_the_import_is_left_alone(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, name="btn")
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"formula": "get('previous_action.999999.id')", "mode": "simple"},
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (action,) = OpenUrlWorkflowAction.objects.filter(field=duplicated_field)

    assert action.url["formula"] == "get('previous_action.999999.id')"


@pytest.mark.django_db
def test_duplicating_a_reference_to_an_unconfigured_action(data_fixture):
    """`BrokenChain` in the e2e suite: the referenced action has no table, so
    its service can offer nothing to remap the rest of the path with."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, name="btn")

    unconfigured = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={
            "formula": f"get('previous_action.{unconfigured.id}.id')",
            "mode": "simple",
        },
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (duplicated_unconfigured,) = LocalBaserowCreateRowWorkflowAction.objects.filter(
        field=duplicated_field
    )
    (duplicated_open_url,) = OpenUrlWorkflowAction.objects.filter(
        field=duplicated_field
    )

    assert duplicated_open_url.url["formula"] == (
        f"get('previous_action.{duplicated_unconfigured.id}.id')"
    )


@pytest.mark.django_db
def test_duplicating_a_forward_reference(data_fixture):
    """`Stale` in the e2e suite: the reference points at an action that runs
    after it, which the editor marks but does not refuse to save."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, name="btn")

    later = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = later.service.specific
    service.table = table
    service.save()
    earlier = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"formula": f"get('previous_action.{later.id}.id')", "mode": "simple"},
    )
    # Ordered so the URL action runs first, as a reorder would leave it.
    earlier.order = 1
    earlier.save()
    later.order = 2
    later.save()

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_field = duplicated_table.field_set.get(name="btn").specific
    (duplicated_later,) = LocalBaserowCreateRowWorkflowAction.objects.filter(
        field=duplicated_field
    )
    (duplicated_open_url,) = OpenUrlWorkflowAction.objects.filter(
        field=duplicated_field
    )

    assert duplicated_open_url.url["formula"] == (
        f"get('previous_action.{duplicated_later.id}.id')"
    )


@pytest.mark.django_db
def test_export_leaves_behind_what_a_click_remembered(data_fixture):
    """
    An export travels to snapshots, duplicates and templates, and what a click
    remembered of an external response describes this installation's data.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    service = data_fixture.create_core_http_request_service(integration=None)
    service.sample_data = {"data": {"body": {"secret": "tKn-123"}}, "status": 200}
    service.save()
    data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field, service=service
    )

    exported = field_type_registry.get_by_model(button_field).export_serialized(
        button_field
    )

    exported_service = exported["workflow_actions"][0]["service"]
    assert "sample_data" not in exported_service
    assert "tKn-123" not in str(exported)


@pytest.mark.django_db
def test_duplicating_a_field_leaves_the_remembered_answer_behind(data_fixture):
    """
    Duplicating goes through the same export and import as a snapshot, so a
    copy must arrive with the request configured and with nothing this
    installation's endpoint happened to answer.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    service = data_fixture.create_core_http_request_service(
        integration=None, url="'http://example.notexist/'"
    )
    service.sample_data = {"data": {"body": {"secret": "tKn-123"}}, "status": 200}
    service.save()
    data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field, service=service
    )

    copy, _ = FieldHandler().duplicate_field(user, button_field)

    copied_actions = list(
        DatabaseWorkflowActionHandler().get_workflow_actions(copy.specific)
    )
    assert len(copied_actions) == 1
    copied_service = copied_actions[0].service.specific
    assert copied_service.url["formula"] == "'http://example.notexist/'"
    assert copied_service.sample_data is None


def _button_with_authorized_request(data_fixture, table):
    button_field = data_fixture.create_button_field(table=table)
    service = data_fixture.create_core_http_request_service(
        integration=None, url="'http://example.notexist/'"
    )
    service.headers.create(
        key="Authorization", value={"formula": "'Bearer sk-SUPERSECRET'"}
    )
    service.query_params.create(key="token", value={"formula": "'qp-SUPERSECRET'"})
    service.form_data.create(key="secret", value={"formula": "'fd-SUPERSECRET'"})
    service.body_type = "raw"
    service.body_content = {"formula": "'body-SUPERSECRET'"}
    service.save()
    data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field, service=service
    )
    return button_field


@pytest.mark.django_db
def test_an_export_does_not_carry_the_key_a_request_sends(data_fixture):
    """
    An HTTP action has no integration, so its key lives in the service's own
    headers and query parameters. Without stripping it travels wherever the
    export goes: snapshots, workspace exports, templates.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = _button_with_authorized_request(data_fixture, table)

    exported = field_type_registry.get_by_model(button_field).export_serialized(
        button_field,
        import_export_config=ImportExportConfig(
            include_permission_data=False, exclude_sensitive_data=True
        ),
    )

    # Every placement a credential can take, not only the header the review
    # found it in.
    for secret in ("sk-", "qp-", "fd-", "body-"):
        assert f"{secret}SUPERSECRET" not in str(exported)
    exported_service = exported["workflow_actions"][0]["service"]
    assert exported_service["form_data"] == [{"key": "secret", "value": None}]
    assert exported_service["body_content"] is None
    # The names stay, so an import says what has to be entered again. Blanking
    # the whole list would take the headers that hold no secret with it.
    assert exported_service["headers"] == [{"key": "Authorization", "value": None}]
    assert exported_service["query_params"] == [{"key": "token", "value": None}]
    # The request itself still travels; only what authorizes it is left behind.
    assert exported_service["url"]["formula"] == "'http://example.notexist/'"


@pytest.mark.django_db
def test_an_export_that_may_keep_secrets_keeps_them(data_fixture):
    """
    Duplicating a field and snapshotting a database stay inside the
    installation, so the copy has to keep working.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = _button_with_authorized_request(data_fixture, table)

    copy, _ = FieldHandler().duplicate_field(user, button_field)

    copied_action = DatabaseWorkflowActionHandler().get_workflow_actions(copy.specific)[
        0
    ]
    copied_service = copied_action.service.specific
    assert [h.key for h in copied_service.headers.all()] == ["Authorization"]
    assert copied_service.headers.get().value["formula"] == "'Bearer sk-SUPERSECRET'"
    assert copied_service.query_params.get().key == "token"


@pytest.mark.django_db(transaction=True)
def test_a_workspace_export_strips_the_key_and_still_imports(data_fixture):
    """
    The whole path, the way a workspace export really runs it: the config has
    to reach the field, and the import has to read a stripped header list as
    "none of them" rather than fall over.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    button_field = _button_with_authorized_request(data_fixture, table)
    button_field.name = "btn"
    button_field.save()

    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(
        workspace,
        BytesIO(),
        ImportExportConfig(include_permission_data=False, exclude_sensitive_data=True),
    )

    for secret in ("sk-", "qp-", "fd-", "body-"):
        assert f"{secret}SUPERSECRET" not in str(exported)

    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace,
        exported,
        BytesIO(),
        ImportExportConfig(include_permission_data=False),
        None,
    )

    imported_field = (
        imported[0].table_set.get(name=table.name).field_set.get(name="btn").specific
    )
    (action,) = DatabaseWorkflowAction.objects.filter(field=imported_field)
    imported_service = action.specific.service.specific
    # The rows survive with their names and an empty value, so the button says
    # what it needs rather than quietly sending a different request.
    assert [h.key for h in imported_service.headers.all()] == ["Authorization"]
    assert not imported_service.headers.get().value.get("formula")
    assert [q.key for q in imported_service.query_params.all()] == ["token"]
    assert not imported_service.query_params.get().value.get("formula")
    # The request still travels; only what authorizes it is left behind.
    assert imported_service.url["formula"] == "'http://example.notexist/'"


def _button_that_sends_email(data_fixture, table, name_field, button_name="btn"):
    """A button whose email names a field of its own table in every formula."""

    button_field = data_fixture.create_button_field(table=table, name=button_name)
    service = data_fixture.create_core_smtp_email_service(
        integration=None,
        use_instance_smtp_settings=True,
        to_emails=f"get('row.field_{name_field.id}')",
        subject=f"concat('Hello ', get('row.field_{name_field.id}'))",
        body=f"get('row.field_{name_field.id}')",
    )
    data_fixture.create_database_workflow_action(
        CoreSMTPEmailWorkflowAction, field=button_field, service=service
    )
    return button_field


@pytest.mark.django_db
def test_an_export_that_leaves_the_instance_carries_no_message(data_fixture):
    """
    The table schema handed to formula AI is serialized this way and then sent
    to a third-party model. Reading a formula field needs far less permission
    than configuring a button, so who the button writes to and what it says
    must not travel with it.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    button_field = _button_that_sends_email(data_fixture, table, name_field)
    action = DatabaseWorkflowAction.objects.get(field=button_field).specific
    service = action.service.specific
    service.from_email = "'billing@example.com'"
    service.to_emails = "'someone@example.com'"
    service.cc_emails = "'cc@example.com'"
    service.bcc_emails = "'bcc@example.com'"
    service.subject = "'Your invoice'"
    service.body = "'Account 1234 is overdue'"
    service.save()

    exported = field_type_registry.get_by_model(button_field).export_serialized(
        button_field,
        import_export_config=ImportExportConfig(
            include_permission_data=False, exclude_sensitive_data=True
        ),
    )

    for literal in (
        "billing@",
        "someone@",
        "cc@",
        "bcc@",
        "Your invoice",
        "overdue",
    ):
        assert literal not in str(exported)

    exported_action = exported["workflow_actions"][0]
    exported_service = exported_action["service"]
    for prop_name in (
        "from_email",
        "to_emails",
        "cc_emails",
        "bcc_emails",
        "subject",
        "body",
    ):
        assert exported_service[prop_name] is None
    # The action still says what it is, so a schema built from this is useful.
    assert exported_action["type"] == "smtp_email"
    assert exported_service["body_type"] == "plain"


@pytest.mark.django_db(transaction=True)
def test_a_workspace_export_carries_no_message(data_fixture):
    """
    The whole path, the way a workspace export really runs it: an export file
    leaves the instance, and the import has to read a blanked message as
    "nothing was set" rather than fall over.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    button_field = _button_that_sends_email(data_fixture, table, name_field)
    action = DatabaseWorkflowAction.objects.get(field=button_field).specific
    service = action.service.specific
    service.to_emails = "'someone@example.com'"
    service.subject = "'Your invoice'"
    service.body = "'Account 1234 is overdue'"
    service.save()

    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(
        workspace,
        BytesIO(),
        ImportExportConfig(include_permission_data=False),
    )

    for literal in ("someone@", "Your invoice", "overdue"):
        assert literal not in str(exported)

    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace,
        exported,
        BytesIO(),
        ImportExportConfig(include_permission_data=False),
        None,
    )

    imported_button = (
        imported[0].table_set.get(name=table.name).field_set.get(name="btn").specific
    )
    (imported_action,) = DatabaseWorkflowAction.objects.filter(field=imported_button)
    imported_service = imported_action.specific.service.specific
    assert not imported_service.to_emails.get("formula")
    assert not imported_service.body.get("formula")
    # How it sends still travels, so only the message has to be written again.
    assert imported_service.use_instance_smtp_settings is True
    assert imported_service.body_type == "plain"


@pytest.mark.django_db
def test_duplicate_table_remaps_the_field_an_email_reads(data_fixture):
    """
    Recipient, subject and body are formulas on the service itself. Left
    pointing at the original table's field, the copy would send whatever the
    source row holds (ADR 006 section 6).
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    _button_that_sends_email(data_fixture, table, name_field)

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_name_field = duplicated_table.field_set.get(name="Name")
    duplicated_button = duplicated_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=duplicated_button)
    service = action.specific.service.specific

    assert duplicated_name_field.id != name_field.id
    reference = f"get('row.field_{duplicated_name_field.id}')"
    assert service.to_emails["formula"] == reference
    assert service.body["formula"] == reference
    # Reprinted from the parsed formula, so the space after the comma goes.
    assert service.subject["formula"] == f"concat('Hello ',{reference})"
    # A copy sends through the instance server too, since a database action
    # has no integration to send through.
    assert service.use_instance_smtp_settings is True


@pytest.mark.django_db(transaction=True)
def test_an_email_action_survives_an_application_export_import(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    _button_that_sends_email(data_fixture, table, name_field)

    # Keeping the message, the way a snapshot and a duplicate do. An export
    # that leaves the instance drops it, which
    # `test_a_workspace_export_carries_no_message` covers.
    config = ImportExportConfig(
        include_permission_data=False, exclude_sensitive_data=False
    )
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    imported_table = imported[0].table_set.get(name=table.name)
    imported_name_field = imported_table.field_set.get(name="Name")
    imported_button = imported_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=imported_button)
    service = action.specific.service.specific

    assert imported_name_field.id != name_field.id
    assert service.to_emails["formula"] == f"get('row.field_{imported_name_field.id}')"
    assert service.subject["formula"] == (
        f"concat('Hello ',get('row.field_{imported_name_field.id}'))"
    )
    assert service.use_instance_smtp_settings is True
    assert service.integration_id is None


@pytest.mark.django_db(transaction=True)
def test_an_email_action_is_imported_even_where_it_cannot_send(data_fixture, settings):
    """
    An export travels between installations, and whether one can send is a
    deploy setting rather than something the export carries. The action is kept
    as configured and refused where it is used, so moving the copy to an
    installation with a mail server needs no repair.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    _button_that_sends_email(data_fixture, table, name_field)

    config = ImportExportConfig(include_permission_data=False)
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = False
    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    imported_table = imported[0].table_set.get(name=table.name)
    imported_button = imported_table.field_set.get(name="btn").specific
    (action,) = DatabaseWorkflowAction.objects.filter(field=imported_button)

    assert action.specific.get_type().type == "smtp_email"
    assert action.specific.get_type().is_deactivated(imported_workspace) is True
