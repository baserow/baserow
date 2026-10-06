import pytest

from baserow.core.formula.types import (
    BASEROW_FORMULA_FORMAT_MARKDOWN,
    BASEROW_FORMULA_FORMAT_PLAIN,
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormulaMinified,
    BaserowFormulaObject,
)


@pytest.mark.parametrize("formula_format", [None, BASEROW_FORMULA_FORMAT_PLAIN])
def test_baserow_formula_object_create_omits_plain_format(formula_format):
    """
    A missing `format` means plain, so an object created with a plain (or no)
    format must be identical to the objects created before formats existed.
    """

    formula_object = BaserowFormulaObject.create(
        formula="'foo'",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version="0.1",
        format=formula_format,
    )

    assert formula_object == {
        "formula": "'foo'",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": "0.1",
    }
    assert "format" not in formula_object


def test_baserow_formula_object_create_keeps_markdown_format():
    formula_object = BaserowFormulaObject.create(
        formula="'**foo**'",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version="0.1",
        format=BASEROW_FORMULA_FORMAT_MARKDOWN,
    )

    assert formula_object == {
        "formula": "'**foo**'",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": "0.1",
        "format": BASEROW_FORMULA_FORMAT_MARKDOWN,
    }


@pytest.mark.parametrize("formula_format", [None, BASEROW_FORMULA_FORMAT_PLAIN])
def test_baserow_formula_minified_create_omits_plain_format(formula_format):
    """
    `fmt: "plain"` is never written to the database: a stored formula without
    `fmt` is plain, so every plain row keeps the shape written before formats
    existed.
    """

    minified = BaserowFormulaMinified.create(
        formula="'foo'",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version="0.1",
        format=formula_format,
    )

    assert minified == {"f": "'foo'", "m": BASEROW_FORMULA_MODE_SIMPLE, "v": "0.1"}
    assert "fmt" not in minified


def test_baserow_formula_minified_create_keeps_markdown_format():
    minified = BaserowFormulaMinified.create(
        formula="'**foo**'",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version="0.1",
        format=BASEROW_FORMULA_FORMAT_MARKDOWN,
    )

    assert minified == {
        "f": "'**foo**'",
        "m": BASEROW_FORMULA_MODE_SIMPLE,
        "v": "0.1",
        "fmt": BASEROW_FORMULA_FORMAT_MARKDOWN,
    }
