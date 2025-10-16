from io import BytesIO
from tempfile import tempdir

from django.core.files.storage import FileSystemStorage

import pytest

from baserow.contrib.builder.pages.service import PageService
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE, BaserowFormulaObject
from baserow.core.user_files.handler import UserFileHandler


@pytest.mark.django_db
@pytest.mark.parametrize(
    "storage",
    [None, FileSystemStorage(location=str(tempdir), base_url="http://localhost")],
)
def test_import_export_image_collection_field_type(data_fixture, fake, storage):
    """
    Ensure that the ImageCollectionField's formulas are exported correctly
    with the updated data sources.
    """

    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    # Create a database table with a "files" column
    image_file = UserFileHandler().upload_user_file(
        user,
        "test.jpg",
        BytesIO(fake.image()),
        storage=storage,
    )
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Images", "file")],
        rows=[[[image_file.serialize()]]],
    )

    # Create a new builder table element and connect it to the previous
    # created database table
    data_source_1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source_1,
        fields=[
            {
                "name": "Images",
                "type": "image",
                "config": {
                    "src": f"get('data_source.{data_source_1.id}.*.{fields[0].db_column}.url')",
                    "alt": f"get('data_source.{data_source_1.id}.*.{fields[0].db_column}.name')",
                },
            },
        ],
    )

    # Duplicate the page and create a second data source
    duplicated_page = PageService().duplicate_page(user, page)
    data_source_2 = duplicated_page.datasource_set.first()
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}

    # Export the table element and import it, applying the id mapping of the
    # second data source created
    exported = table_element.get_type().export_serialized(table_element)
    imported_table_element = table_element.get_type().import_serialized(
        page, exported, id_mapping
    )

    images = imported_table_element.fields.get(name="Images")
    assert images.config == {
        "src": BaserowFormulaObject(
            formula=f"get('data_source.{data_source_2.id}.*.{fields[0].db_column}.url')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "alt": BaserowFormulaObject(
            formula=f"get('data_source.{data_source_2.id}.*.{fields[0].db_column}.name')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
    }
