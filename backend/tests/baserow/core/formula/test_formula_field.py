import json

import pytest

from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import (
    BASEROW_FORMULA_VERSION_INITIAL,
    FormulaField,
    JSONFormulaField,
)
from baserow.core.formula.types import (
    BASEROW_FORMULA_FORMAT_MARKDOWN,
    BASEROW_FORMULA_FORMAT_PLAIN,
    BASEROW_FORMULA_MODE_SIMPLE,
)


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
    Legacy rows written before the formula-object migration can hold `null` at
    a formula path, and older write paths could persist a null `f`. These must
    be read back as `formula: ""`, never `formula: None`, because clients expect
    a string. A missing mode or version is deliberately not defaulted.
    """

    field = JSONFormulaField(properties=["value"])
    expected = {
        "formula": "",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
    }
    minified_with_null_formula = {
        "f": None,
        "m": BASEROW_FORMULA_MODE_SIMPLE,
        "v": BASEROW_FORMULA_VERSION_INITIAL,
    }

    assert field._transform_db_property(None) == expected
    assert field._transform_db_property(minified_with_null_formula) == expected


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
    expected = [
        {
            "name": "id",
            "value": {
                "f": "",
                "m": BASEROW_FORMULA_MODE_SIMPLE,
                "v": BASEROW_FORMULA_VERSION_INITIAL,
            },
        }
    ]
    object_with_null_formula = {
        "formula": None,
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
    }

    assert field.get_prep_value([{"name": "id", "value": None}]) == expected
    assert (
        field.get_prep_value([{"name": "id", "value": object_with_null_formula}])
        == expected
    )


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


def test_formula_field_get_prep_value_stores_markdown_format_as_fmt():
    field = FormulaField()
    formula_object = {
        "formula": "'**foo**'",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
        "format": BASEROW_FORMULA_FORMAT_MARKDOWN,
    }

    prepped = field.get_prep_value(formula_object)

    assert json.loads(prepped) == {
        "f": "'**foo**'",
        "m": BASEROW_FORMULA_MODE_SIMPLE,
        "v": BASEROW_FORMULA_VERSION_INITIAL,
        "fmt": BASEROW_FORMULA_FORMAT_MARKDOWN,
    }


@pytest.mark.parametrize(
    "formula_object",
    [
        {
            "formula": "'foo'",
            "mode": BASEROW_FORMULA_MODE_SIMPLE,
            "version": BASEROW_FORMULA_VERSION_INITIAL,
        },
        {
            "formula": "'foo'",
            "mode": BASEROW_FORMULA_MODE_SIMPLE,
            "version": BASEROW_FORMULA_VERSION_INITIAL,
            "format": BASEROW_FORMULA_FORMAT_PLAIN,
        },
    ],
)
def test_formula_field_get_prep_value_never_stores_plain_format(formula_object):
    """
    A plain format is never written to the database, so every plain formula,
    old or new, keeps the exact shape stored before formats existed.
    """

    field = FormulaField()

    prepped = field.get_prep_value(formula_object)

    assert json.loads(prepped) == {
        "f": "'foo'",
        "m": BASEROW_FORMULA_MODE_SIMPLE,
        "v": BASEROW_FORMULA_VERSION_INITIAL,
    }


def test_formula_field_transform_db_value_reads_fmt_as_format():
    field = FormulaField()

    result = field._transform_db_value_to_dict(
        '{"m": "simple", "v": "0.1", "f": "\'**foo**\'", "fmt": "markdown"}'
    )

    assert result == {
        "formula": "'**foo**'",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
        "format": BASEROW_FORMULA_FORMAT_MARKDOWN,
    }


@pytest.mark.parametrize(
    "stored_value",
    [
        '{"m": "simple", "v": "0.1", "f": "\'foo\'"}',
        # Never written, but a stored plain format still reads as no format.
        '{"m": "simple", "v": "0.1", "f": "\'foo\'", "fmt": "plain"}',
    ],
)
def test_formula_field_transform_db_value_omits_plain_format(stored_value):
    field = FormulaField()

    result = field._transform_db_value_to_dict(stored_value)

    assert result == {
        "formula": "'foo'",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
    }
    assert "format" not in result


def test_formula_field_to_python_keeps_format_of_in_memory_object():
    """
    After a save, the model keeps the in-memory `BaserowFormulaObject` and runs
    it through `to_python` again, which must not lose its format.
    """

    field = FormulaField()
    formula_object = BaserowFormulaObject.create(
        formula="'**foo**'",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version=BASEROW_FORMULA_VERSION_INITIAL,
        format=BASEROW_FORMULA_FORMAT_MARKDOWN,
    )

    assert field.to_python(formula_object) == formula_object


def test_formula_field_round_trips_markdown_format():
    field = FormulaField()
    formula_object = BaserowFormulaObject.create(
        formula="'**foo**'",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version=BASEROW_FORMULA_VERSION_INITIAL,
        format=BASEROW_FORMULA_FORMAT_MARKDOWN,
    )

    assert field.from_db_value(field.get_prep_value(formula_object)) == formula_object


def test_json_formula_field_get_prep_value_stores_markdown_format_as_fmt():
    field = JSONFormulaField(properties=["value"])
    config = {
        "value": {
            "formula": "'**foo**'",
            "mode": BASEROW_FORMULA_MODE_SIMPLE,
            "version": BASEROW_FORMULA_VERSION_INITIAL,
            "format": BASEROW_FORMULA_FORMAT_MARKDOWN,
        }
    }

    assert field.get_prep_value(config) == {
        "value": {
            "f": "'**foo**'",
            "m": BASEROW_FORMULA_MODE_SIMPLE,
            "v": BASEROW_FORMULA_VERSION_INITIAL,
            "fmt": BASEROW_FORMULA_FORMAT_MARKDOWN,
        }
    }


def test_json_formula_field_get_prep_value_never_stores_plain_format():
    field = JSONFormulaField(properties=["value"])
    config = {
        "value": {
            "formula": "'foo'",
            "mode": BASEROW_FORMULA_MODE_SIMPLE,
            "version": BASEROW_FORMULA_VERSION_INITIAL,
            "format": BASEROW_FORMULA_FORMAT_PLAIN,
        }
    }

    assert field.get_prep_value(config) == {
        "value": {
            "f": "'foo'",
            "m": BASEROW_FORMULA_MODE_SIMPLE,
            "v": BASEROW_FORMULA_VERSION_INITIAL,
        }
    }


@pytest.mark.parametrize(
    "value",
    [
        # The minified form read from the database.
        {"f": "'**foo**'", "m": "simple", "v": "0.1", "fmt": "markdown"},
        # The full form `to_python` receives after a save.
        {
            "formula": "'**foo**'",
            "mode": "simple",
            "version": "0.1",
            "format": "markdown",
        },
    ],
)
def test_json_formula_field_transform_db_property_keeps_markdown_format(value):
    field = JSONFormulaField(properties=["value"])

    assert field._transform_db_property(value) == {
        "formula": "'**foo**'",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
        "format": BASEROW_FORMULA_FORMAT_MARKDOWN,
    }


@pytest.mark.parametrize(
    "value",
    [
        {"f": "'foo'", "m": "simple", "v": "0.1"},
        {"f": "'foo'", "m": "simple", "v": "0.1", "fmt": "plain"},
        {"formula": "'foo'", "mode": "simple", "version": "0.1", "format": "plain"},
    ],
)
def test_json_formula_field_transform_db_property_omits_plain_format(value):
    field = JSONFormulaField(properties=["value"])

    result = field._transform_db_property(value)

    assert result == {
        "formula": "'foo'",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
    }
    assert "format" not in result


def test_json_formula_field_round_trips_markdown_format_in_list():
    """
    Collection fields store their formulas in a list of configs, the shape the
    table element uses. The format must survive the trip to and from the
    database at that path too.
    """

    field = JSONFormulaField(properties=["value"])
    fields = [
        {
            "name": "Name",
            "value": {
                "formula": "'**foo**'",
                "mode": BASEROW_FORMULA_MODE_SIMPLE,
                "version": BASEROW_FORMULA_VERSION_INITIAL,
                "format": BASEROW_FORMULA_FORMAT_MARKDOWN,
            },
        }
    ]

    prepped = field.get_prep_value(fields)

    assert prepped == [
        {
            "name": "Name",
            "value": {
                "f": "'**foo**'",
                "m": BASEROW_FORMULA_MODE_SIMPLE,
                "v": BASEROW_FORMULA_VERSION_INITIAL,
                "fmt": BASEROW_FORMULA_FORMAT_MARKDOWN,
            },
        }
    ]
    assert field._transform_db_properties(prepped) == fields
