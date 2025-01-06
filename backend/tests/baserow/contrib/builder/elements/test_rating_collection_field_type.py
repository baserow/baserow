"""
Test the RatingCollectionFieldType class.
"""

import pytest
from unittest.mock import patch

from baserow.contrib.builder.elements.collection_field_types import (
    RatingCollectionFieldType,
)
from baserow.contrib.builder.elements.models import RatingStyles
from baserow.core.formula.serializers import FormulaSerializerField

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
    Ensure that the RatingCollectionField's properties are exported correctly
    with the updated Data Sources.
    """
    pass
