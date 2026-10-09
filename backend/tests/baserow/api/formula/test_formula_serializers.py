import pytest
from rest_framework.exceptions import ValidationError

from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.serializers import (
    BaserowFormulaObjectSerializer,
    FormulaSerializerField,
)
from baserow.core.formula.types import (
    BASEROW_FORMULA_FORMAT_MARKDOWN,
    BASEROW_FORMULA_FORMAT_PLAIN,
    BASEROW_FORMULA_MODE_RAW,
    BASEROW_FORMULA_MODE_SIMPLE,
)


@pytest.mark.parametrize("context", [None, {}, {"application_type": None}])
def test_formula_serializer_field_without_context(context):
    with pytest.raises(ValidationError) as exc:
        field = FormulaSerializerField()
        field._context = context
        field.to_internal_value(
            {
                "formula": "get('data_source.123.field_456')",
                "version": BASEROW_FORMULA_VERSION_INITIAL,
                "mode": BASEROW_FORMULA_MODE_SIMPLE,
            }
        )
    assert str(exc.value.detail[0]) == (
        "The formula serializer field requires "
        "an application type context to validate the formula arguments."
    )


def test_formula_serializer_field_allows_only_plain_by_default():
    field = FormulaSerializerField(help_text="The label.")

    assert field.allowed_formats == [BASEROW_FORMULA_FORMAT_PLAIN]
    # A field with a single format doesn't mention formats in the API docs.
    assert field.help_text == "The label."


def test_formula_serializer_field_lists_allowed_formats_in_help_text():
    field = FormulaSerializerField(
        help_text="The label.",
        allowed_formats=[BASEROW_FORMULA_FORMAT_PLAIN, BASEROW_FORMULA_FORMAT_MARKDOWN],
    )

    assert field.allowed_formats == [
        BASEROW_FORMULA_FORMAT_PLAIN,
        BASEROW_FORMULA_FORMAT_MARKDOWN,
    ]
    assert field.help_text == "The label. Accepted `format` values: plain, markdown."


def test_formula_serializer_field_help_text_without_a_base_help_text():
    field = FormulaSerializerField(
        allowed_formats=[BASEROW_FORMULA_FORMAT_PLAIN, BASEROW_FORMULA_FORMAT_MARKDOWN]
    )

    assert field.help_text == "Accepted `format` values: plain, markdown."


def test_formula_serializer_field_rejects_a_format_that_is_not_allowed():
    field = FormulaSerializerField()

    with pytest.raises(ValidationError) as exc:
        field.to_internal_value(
            {"formula": "'**foo**'", "format": BASEROW_FORMULA_FORMAT_MARKDOWN}
        )

    assert exc.value.detail[0].code == "invalid_format"
    assert str(exc.value.detail[0]) == (
        "The format 'markdown' is not allowed for this formula. Allowed formats: plain."
    )


def test_formula_serializer_field_rejects_an_unknown_format():
    field = FormulaSerializerField(
        allowed_formats=[BASEROW_FORMULA_FORMAT_PLAIN, BASEROW_FORMULA_FORMAT_MARKDOWN]
    )

    with pytest.raises(ValidationError) as exc:
        field.to_internal_value({"formula": "'foo'", "format": "html"})

    assert exc.value.detail["format"][0].code == "invalid_choice"


@pytest.mark.parametrize(
    "data",
    [
        {"formula": "", "mode": BASEROW_FORMULA_MODE_SIMPLE},
        {
            "formula": "",
            "mode": BASEROW_FORMULA_MODE_SIMPLE,
            "format": BASEROW_FORMULA_FORMAT_PLAIN,
        },
    ],
)
def test_formula_serializer_field_never_keeps_a_plain_format(data):
    """
    A missing `format` means plain, so the validated object must not carry the
    key, whether the client left it out or sent plain explicitly.
    """

    field = FormulaSerializerField(
        allowed_formats=[BASEROW_FORMULA_FORMAT_PLAIN, BASEROW_FORMULA_FORMAT_MARKDOWN]
    )

    assert field.to_internal_value(data) == {
        "formula": "",
        "mode": BASEROW_FORMULA_MODE_SIMPLE,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
    }


def test_formula_serializer_field_keeps_an_allowed_markdown_format():
    field = FormulaSerializerField(
        allowed_formats=[BASEROW_FORMULA_FORMAT_PLAIN, BASEROW_FORMULA_FORMAT_MARKDOWN]
    )

    # A raw formula skips the argument validation, which needs a context.
    result = field.to_internal_value(
        {
            "formula": "**foo**",
            "mode": BASEROW_FORMULA_MODE_RAW,
            "format": BASEROW_FORMULA_FORMAT_MARKDOWN,
        }
    )

    assert result == {
        "formula": "**foo**",
        "mode": BASEROW_FORMULA_MODE_RAW,
        "version": BASEROW_FORMULA_VERSION_INITIAL,
        "format": BASEROW_FORMULA_FORMAT_MARKDOWN,
    }


def test_baserow_formula_object_serializer_defaults_the_format_to_plain():
    serializer = BaserowFormulaObjectSerializer(data={"formula": "'foo'"})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["format"] == BASEROW_FORMULA_FORMAT_PLAIN
