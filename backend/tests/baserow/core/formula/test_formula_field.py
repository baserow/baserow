from baserow.core.formula.field import (
    BASEROW_FORMULA_VERSION_INITIAL,
    FormulaField,
    JSONFormulaField,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE


def test_json_formula_field_get_prep_value_does_not_mutate_input():
    """
    Regression: `get_prep_value` minifies the formula paths in a config, but it
    must NOT mutate the value it is given — that value is the model instance's
    in-memory `config` attribute, and mutating it as a side effect of preparing
    the DB value is unsafe.

    Why it matters (the silk-driven bug): django-silk (enabled in the dev env)
    wraps `SQLCompiler.execute_sql` and compiles each UPDATE twice — once to log
    the query, once to actually run it — so `get_prep_value` runs twice on the
    *same* config object within a single save. Before the deepcopy fix the first
    call minified the config in place (`{"formula": ...}` -> `{"f": ...}`) and the
    second call re-minified the already-minified form; `_transform_python_property`
    reads the "formula" key (absent after minify), so it wrote back `{"f": ""}` and
    the formula was silently blanked. This is what made table-element duplication
    lose every field formula when silk was on. Keeping `get_prep_value` free of
    side effects makes it idempotent regardless of how many times it runs.
    """

    field = JSONFormulaField(properties=["value"])
    config = {
        "value": {
            "formula": "get('current_record.field_5')",
            "mode": "simple",
            "version": "0.1",
        }
    }

    prepped = field.get_prep_value(config)

    # 1. The input (the model's in-memory config) must be untouched — still full.
    assert config == {
        "value": {
            "formula": "get('current_record.field_5')",
            "mode": "simple",
            "version": "0.1",
        }
    }
    # 2. It returns the correct minified DB representation.
    assert prepped == {
        "value": {"f": "get('current_record.field_5')", "m": "simple", "v": "0.1"}
    }

    # 3. Running it again on the SAME object (silk's second compile) must still
    #    produce the correct minified value, not a blanked one.
    prepped_again = field.get_prep_value(config)
    assert prepped_again == {
        "value": {"f": "get('current_record.field_5')", "m": "simple", "v": "0.1"}
    }


def test_json_formula_field_transform_db_property_coerces_null_formula():
    """
    Legacy rows written before the formula-object migration can hold `null`
    (or dicts with missing/null keys) at a formula path. These must be read
    back as `formula: ""`, never `formula: None`, because clients expect a string.
    """

    field = JSONFormulaField(properties=["value"])
    expected = {
        "formula": "",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
    }

    assert field._transform_db_property(None) == expected
    assert field._transform_db_property({}) == expected
    assert field._transform_db_property({"f": None, "m": None, "v": None}) == expected


def test_json_formula_field_transform_db_properties_coerces_legacy_null_value():
    field = JSONFormulaField(properties=["value"])

    result = field._transform_db_properties([{"name": "id", "value": None}])

    assert result == [
        {
            "name": "id",
            "value": {
                "formula": "",
                "mode": BASEROW_FORMULA_MODE_SIMPLE,
                "version": BASEROW_FORMULA_VERSION_INITIAL,
            },
        }
    ]


def test_json_formula_field_get_prep_value_coerces_null_formula():
    """
    Non-serializer write paths (direct ORM saves, application import) must not
    be able to persist a null formula.
    """

    field = JSONFormulaField(properties=["value"])

    prepped = field.get_prep_value([{"name": "id", "value": None}])

    assert prepped == [
        {
            "name": "id",
            "value": {
                "f": "",
                "m": BASEROW_FORMULA_MODE_SIMPLE,
                "v": BASEROW_FORMULA_VERSION_INITIAL,
            },
        }
    ]


def test_formula_field_transform_db_value_coerces_null_formula():
    field = FormulaField()

    result = field._transform_db_value_to_dict('{"m": "simple", "v": "0.1", "f": null}')

    assert result == {
        "formula": "",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
    }


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
