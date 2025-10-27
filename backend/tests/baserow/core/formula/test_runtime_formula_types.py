from unittest.mock import MagicMock

import pytest

from baserow.core.formula.runtime_formula_types import RuntimeConcat


@pytest.mark.parametrize(
    "formula_args,expected",
    [
        (
            [[["Apple", "Banana"]], "Cherry"],
            "Apple,BananaCherry",
        ),
        (
            [[["Apple", "Banana"]], ",Cherry"],
            "Apple,Banana,Cherry",
        ),
        (
            [[["Apple", "Banana"]], ", Cherry"],
            "Apple,Banana, Cherry",
        ),
    ],
)
def test_returns_concatenated_value(formula_args, expected):
    """
    Ensure that formula_args and non-formula strings are concatenated correctly.
    """

    context = MagicMock()
    result = RuntimeConcat().execute(context, formula_args)
    assert result == expected
