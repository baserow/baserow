import pytest

from baserow.core.registries import ImportExportConfig, application_type_registry


@pytest.mark.django_db
@pytest.mark.parametrize("same_workspace", [True, False])
def test_copied_rows_keep_identity_attribution_only_in_its_workspace(
    data_fixture, same_workspace
):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    identity = data_fixture.create_identity(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True)
    table.get_model().objects.create(created_by=identity, last_modified_by=identity)
    target = workspace if same_workspace else data_fixture.create_workspace(user=admin)
    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=False)
    serialized = database_type.export_serialized(database, config)

    copy = database_type.import_serialized(target, serialized, config, {}, None, None)

    row = copy.table_set.get().get_model().objects.get()
    expected = identity.id if same_workspace else None
    assert (row.created_by_id, row.last_modified_by_id) == (expected, expected)
