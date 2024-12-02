"""
Test the CollectionElementTypeMixin class.
"""
import json
from io import BytesIO

import pytest

from baserow.contrib.builder.elements.mixins import CollectionElementTypeMixin
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig

MODULE_PATH = "baserow.contrib.builder.elements.collection_field_types"


@pytest.mark.django_db
def test_import_context_addition_sets_schema_property(data_fixture):
    """
    Test the import_context_addition() method.

    Ensure that the data_source_id and schema_property are set when applicable.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )
    outer_repeat = data_fixture.create_builder_repeat_element(
        data_source=data_source, page=page
    )
    inner_repeat = data_fixture.create_builder_repeat_element(
        page=page,
        data_source=None,
        parent_element_id=outer_repeat.id,
        schema_property="field_123",
    )
    assert CollectionElementTypeMixin().import_context_addition(outer_repeat) == {
        "data_source_id": data_source.id,
    }
    assert CollectionElementTypeMixin().import_context_addition(inner_repeat) == {
        "data_source_id": data_source.id,
        "schema_property": "field_123",
    }


@pytest.mark.django_db(transaction=True)
def test_import_export_collection_element_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    trashed_multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, trashed=True
    )
    data_fixture.create_select_option(
        field=trashed_multiple_select_field, value="A", color="blue"
    )
    element = data_fixture.create_builder_table_element(
        page=page,
        fields=[
            {
                "name": "Name",
                "type": "text",
                "config": {"value": f"'foobar'"},
            },
        ],
    )
    element.property_options.create(schema_property="id", sortable=True)
    element.property_options.create(schema_property=field.db_column, sortable=True)
    element.property_options.create(
        schema_property=trashed_multiple_select_field.db_column, sortable=True
    )

    config = ImportExportConfig(include_permission_data=False)
    exported_applications = CoreHandler().export_workspace_applications(
        workspace, BytesIO(), config
    )

    # Ensure the values are json serializable
    try:
        json.dumps(exported_applications)
    except Exception as e:
        pytest.fail(f"Exported applications are not json serializable: {e}")

    imported_applications, _ = CoreHandler().import_applications_to_workspace(
        workspace, exported_applications, BytesIO(), config, None
    )
    imported_database, imported_builder = imported_applications

    # Pluck out the imported database records.
    imported_table = imported_database.table_set.get()
    imported_field = imported_table.field_set.get()

    # Pluck out the imported builder records.
    imported_page = imported_builder.page_set.exclude(path="__shared__")[0]
    imported_element = imported_page.element_set.get()

    imported_property_options = [
        {"schema_property": option.schema_property, "sortable": option.sortable}
        for option in imported_element.property_options.all()
    ]
    assert imported_property_options == [
        {"schema_property": "id", "sortable": True},
        {"schema_property": imported_field.db_column, "sortable": True},
    ]
