import pytest
from rest_framework.exceptions import ValidationError

from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE


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
