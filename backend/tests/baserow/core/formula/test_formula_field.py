import pytest

from baserow.core.formula.field import FormulaField


@pytest.mark.django_db
def test_value_is_serialized_object_valid(data_fixture):
    field = FormulaField()

    valid_json = '{"m": "simple", "v": "0.1", "f": "test formula"}'
    result = field._value_is_serialized_object(valid_json)

    assert result == {"m": "simple", "v": "0.1", "f": "test formula"}


@pytest.mark.django_db
def test_value_is_serialized_object_invalid(data_fixture):
    field = FormulaField()

    invalid_json = "{foo}"
    result = field._value_is_serialized_object(invalid_json)

    assert result is None
