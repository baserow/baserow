"""
Test the ButtonCollectionFieldType class.
"""

from unittest.mock import patch

import pytest

from baserow.contrib.builder.elements.collection_field_types import (
    ButtonCollectionFieldType,
)
from baserow.contrib.builder.pages.service import PageService
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE

MODULE_PATH = "baserow.contrib.builder.elements.collection_field_types"


def test_class_properties_are_set():
    """
    Test that the properties of the class are correctly set.

    Ensure the type, allowed_fields, serializer_field_names, and
    simple_formula_fields properties are set to the correct values.
    """

    field_type = ButtonCollectionFieldType()

    assert field_type.type == "button"
    assert field_type.allowed_fields == ["label"]
    assert field_type.serializer_field_names == ["label"]
    assert field_type.simple_formula_fields == ["label"]


def test_serializer_field_overrides_returns_expected_value():
    """
    Ensure the serializer_field_overrides() method returns the expected value.
    """

    result = ButtonCollectionFieldType().serializer_field_overrides
    field = result["label"]

    assert type(field) is FormulaSerializerField
    assert isinstance(field.default, dict)
    assert field.required is False
    assert field.help_text == "The string value."


@patch(f"{MODULE_PATH}.CollectionFieldType.deserialize_property")
@pytest.mark.parametrize(
    "prop_name,data_source_id",
    [
        ("", 1),
        (" ", 1),
        ("", None),
        (" ", None),
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

    mock_value = "'foo'"
    mock_super_deserialize.return_value = mock_value
    value = "'foo'"
    id_mapping = {}

    result = ButtonCollectionFieldType().deserialize_property(
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
def test_import_export_button_collection_field_type(data_fixture):
    """
    Ensure that the ButtonCollectionField's formulas are exported correctly
    with the updated Data Sources.
    """

    user, _ = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["Foo"],
        ],
    )
    text_field = fields[0]
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Foo Button",
                "type": "button",
                "config": {
                    "label": f"get('data_source.{data_source.id}.0.{text_field.db_column}')"
                },
            },
        ],
    )

    duplicated_page = PageService().duplicate_page(user, page)
    data_source2 = duplicated_page.datasource_set.first()

    id_mapping = {"builder_data_sources": {data_source.id: data_source2.id}}

    exported = table_element.get_type().export_serialized(table_element)
    imported_table_element = table_element.get_type().import_serialized(
        page, exported, id_mapping
    )

    imported_field = imported_table_element.fields.get(name="Foo Button")
    assert imported_field.config == {
        "label": BaserowFormulaObject(
            formula=f"get('data_source.{data_source2.id}.0.{text_field.db_column}')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        )
    }
