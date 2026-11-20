import pytest

from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.fixture
def tables(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(
        workspace=integration.application.workspace
    )
    return (
        user,
        integration,
        data_fixture.create_database_table(user=user, database=database),
        data_fixture.create_database_table(user=user, database=database),
    )


@pytest.mark.django_db
def test_a_dispatch_context_does_not_know_what_a_sample_was_built_from(tables):
    assert FakeDispatchContext().get_sample_data_table_ids(None) is None


@pytest.mark.django_db
def test_a_service_type_tells_the_tables_it_reads(data_fixture, tables):
    _, integration, table, _ = tables
    rows = data_fixture.create_local_baserow_list_rows_service(
        integration=integration, table=table
    )
    no_table = data_fixture.create_local_baserow_list_rows_service(
        integration=integration, table=None
    )

    rows_type = service_type_registry.get("local_baserow_list_rows")
    assert rows_type.get_table_ids(rows) == {table.id}
    assert rows_type.get_table_ids(no_table) == set()
    smtp = data_fixture.create_service(
        service_type_registry.get("smtp_email").model_class
    )
    assert smtp.get_type().get_table_ids(smtp) == set()


@pytest.mark.django_db
def test_the_tables_a_sample_was_built_from_are_exported_and_remapped_on_import(
    data_fixture, tables
):
    _, integration, table, other_table = tables
    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        table=table,
        sample_data={"data": {"results": []}},
        sample_data_table_ids=[table.id, other_table.id, 0],
    )
    service_type = service.get_type()

    serialized = service_type.export_serialized(service)
    assert serialized["sample_data_table_ids"] == [table.id, other_table.id, 0]

    # A table the import doesn't hold keeps its ID, so the sample stays hidden
    # from whoever may not see that table.
    imported = service_type.import_serialized(
        integration,
        serialized,
        {"database_tables": {table.id: other_table.id}},
    )
    assert imported.table_id == other_table.id
    assert imported.sample_data_table_ids == [other_table.id, other_table.id, 0]

    # Unknown ones aren't exported, nor does importing them make any up.
    service.sample_data_table_ids = None
    serialized = service_type.export_serialized(service)
    assert "sample_data_table_ids" not in serialized
    no_ids = service_type.import_serialized(
        integration, serialized, {"database_tables": {table.id: other_table.id}}
    )
    assert no_ids.sample_data_table_ids is None
