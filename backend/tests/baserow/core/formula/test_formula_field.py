from baserow.core.formula.field import FormulaField


def test_deserialize_baserow_object_valid():
    field = FormulaField()

    valid_json = '{"m": "simple", "v": "0.1", "f": "test formula"}'
    result = field._deserialize_baserow_object(valid_json)

    assert result == {"m": "simple", "v": "0.1", "f": "test formula"}


def test_deserialize_baserow_object_invalid():
    field = FormulaField()

    invalid_json = "{foo}"
    result = field._deserialize_baserow_object(invalid_json)

    assert result is None
