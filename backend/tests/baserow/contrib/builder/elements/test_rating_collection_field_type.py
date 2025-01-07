"""
Test the RatingCollectionFieldType class.
"""

from unittest.mock import patch

import pytest

from baserow.contrib.builder.elements.collection_field_types import (
    RatingCollectionFieldType,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.pages.service import PageService

MODULE_PATH = "baserow.contrib.builder.elements.collection_field_types"


def test_class_properties_are_set():
    """
    Test that the properties of the class are correctly set.
    """

    field_type = RatingCollectionFieldType()

    assert field_type.type == "rating"
    assert field_type.allowed_fields == ["value", "color", "style", "max_value"]
    assert field_type.serializer_field_names == ["value", "color", "style", "max_value"]
    assert field_type.simple_formula_fields == ["value"]


@patch(f"{MODULE_PATH}.CollectionFieldType.deserialize_property")
@pytest.mark.parametrize(
    "prop_name,data_source_id",
    [
        ("", 1),
        (" ", 1),
        ("", None),
        (" ", None),
        ("invalid_prop", 1),
    ],
)
def test_deserialize_property_returns_value_from_super_method(
    mock_super_deserialize,
    prop_name,
    data_source_id,
):
    """
    Ensure that the value is returned by calling the parent class's
    deserialize_property() method.
    """

    mock_value = "5"
    mock_super_deserialize.return_value = mock_value
    value = "5"
    id_mapping = {}

    result = RatingCollectionFieldType().deserialize_property(
        prop_name,
        value,
        id_mapping,
        {},
        data_source_id=data_source_id,
    )

    assert result == mock_value
    mock_super_deserialize.assert_called_once_with(
        prop_name,
        value,
        id_mapping,
        {},
        data_source_id=data_source_id,
    )


@pytest.mark.django_db
def test_import_export_rating_collection_field_type(data_fixture):
    """
    Ensure that the RatingCollectionField's formulas are exported correctly
    with the updated Data Sources.
    """

    user, _ = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Rating", "rating"),
        ],
        rows=[
            [3],
        ],
    )
    rating_field = fields[0]
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Rating Field",
                "type": "rating",
                "config": {
                    "value": f"get('data_source.{data_source.id}.0.{rating_field.db_column}')",
                    "max_value": 5,
                    "style": "star",
                    "color": "",
                },
            },
        ],
    )

    # Create a duplicate page to get a new data source
    duplicated_page = PageService().duplicate_page(user, page)
    data_source2 = duplicated_page.datasource_set.first()

    # Create ID mapping for the data sources
    id_mapping = {"builder_data_sources": {data_source.id: data_source2.id}}

    # Export the element
    serialized = element_type_registry.get_by_model(table_element).export_serialized(
        table_element
    )

    # Delete the element
    table_element.delete()

    # Import it back
    imported_element = element_type_registry.get_by_model(
        table_element
    ).import_serialized(
        page,
        serialized,
        id_mapping,
        None,
    )

    # The imported element should have the same field configuration
    # with updated data source ID
    imported_field = imported_element.fields.get(name="Rating Field")
    assert imported_field.config == {
        "value": f"get('data_source.{data_source2.id}.0.{rating_field.db_column}')",
        "max_value": 5,
        "style": "star",
        "color": "",
    }
