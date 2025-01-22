import pytest

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import RollupField
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.import_export_workspace
@pytest.mark.django_db()
def test_import_export_works_with_invalid_rollup_field(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    rollup_field = FieldHandler().create_field(
        user,
        table_a,
        "rollup",
        name="rollup_field",
        through_field_name=link_a_to_b.name,
        target_field_id=table_b.get_primary_field().id,
        rollup_function="min",
    )

    TableHandler().delete_table(user, table_b)
    rollup_field.refresh_from_db()
    assert rollup_field.formula_type == "invalid"

    import_export_config = ImportExportConfig(
        include_permission_data=False, reduce_disk_space_usage=True
    )
    exported_db = DatabaseApplicationType().export_serialized(
        table_a.database, import_export_config
    )

    assert (
        "references the deleted or unknown field"
        in exported_db["tables"][0]["fields"][1]["error"]
    )

    imported_app = DatabaseApplicationType().import_serialized(
        table_a.database.workspace, exported_db, import_export_config, {}
    )

    imported_field = RollupField.objects.get(table=imported_app.table_set.first())
    assert imported_field.formula_type == "invalid"
    assert "references the deleted or unknown field" in imported_field.error
