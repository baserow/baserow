from io import BytesIO

import pytest

from baserow.contrib.builder.elements.element_types import RecordSelectorElementType
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_record_selector_element_extract_properties(data_fixture):
    user = data_fixture.create_user()
    element_type = RecordSelectorElementType()

    # If the record selector has no data source, then the formula properties are empty
    element = data_fixture.create_builder_record_selector_element(data_source=None)
    properties = element_type.extract_properties(element)
    assert properties == {}

    # If the record selector has a data source *without* a table then the
    # formula properties just include "id"
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source()
    element = data_fixture.create_builder_record_selector_element(
        data_source=data_source
    )
    properties = element_type.extract_properties(element)
    assert properties == {element.data_source.service_id: ["id"]}

    # If the record selector has a data source *with* a table that does not
    # define a name property, then the formula properties just include "id"
    table = data_fixture.create_database_table(user=user)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table
    )
    element = data_fixture.create_builder_record_selector_element(
        data_source=data_source
    )
    properties = element_type.extract_properties(element)
    assert properties == {data_source.service_id: ["id"]}

    # If the record selector has a data source whose table defines a name property
    # then the formula properties includes the "id" and the field name
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(name="Name", table=table, primary=True)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table
    )
    element = data_fixture.create_builder_record_selector_element(
        data_source=data_source
    )
    properties = element_type.extract_properties(element)
    assert properties == {data_source.service_id: ["id", field.db_column]}


@pytest.mark.django_db(transaction=True)
def test_export_import_record_selector_element(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user()

    # Setup database data
    database = data_fixture.create_database_application(workspace=workspace)
    table, fields, _ = data_fixture.build_table(
        database=database,
        user=user,
        columns=[("Name", "text"), ("Color", "text")],
        rows=[["BMW", "Blue"]],
    )

    # Setup application builder page with a record selector element
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    element = data_fixture.create_builder_record_selector_element(
        page=page,
        data_source=data_source,
        option_name_suffix=f"get('current_record.field_{fields[-1].id}')",
    )
    option_name_suffix_field_id = str(fields[-1].id)

    # Export the current workspace and import it into a new one
    handler = CoreHandler()
    config = ImportExportConfig(include_permission_data=False)
    imported_apps, id_mapping = handler.import_applications_to_workspace(
        workspace=data_fixture.create_workspace(),
        exported_applications=handler.export_workspace_applications(
            workspace=workspace,
            files_buffer=BytesIO(),
            import_export_config=config,
        ),
        files_buffer=BytesIO(),
        import_export_config=config,
    )
    imported_builder = imported_apps[-1]
    imported_element = (
        imported_builder.visible_pages.first().element_set.first().specific
    )

    # Check that the formula for option name suffix was updated with the new mapping
    import_option_name_suffix = imported_element.option_name_suffix["formula"]
    import_option_name_suffix_field_id = str(
        id_mapping["database_fields"][fields[-1].id]
    )
    assert import_option_name_suffix == element.option_name_suffix["formula"].replace(
        option_name_suffix_field_id, import_option_name_suffix_field_id
    )
