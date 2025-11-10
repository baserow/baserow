from datetime import datetime
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from baserow.core.formula.argument_types import (
    AnyBaserowRuntimeFormulaArgumentType,
    BooleanBaserowRuntimeFormulaArgumentType,
    DateTimeBaserowRuntimeFormulaArgumentType,
    DictBaserowRuntimeFormulaArgumentType,
    NumberBaserowRuntimeFormulaArgumentType,
    TextBaserowRuntimeFormulaArgumentType,
    TimezoneBaserowRuntimeFormulaArgumentType,
)
from baserow.core.formula.runtime_formula_types import (
    RuntimeAdd,
    RuntimeAnd,
    RuntimeCapitalize,
    RuntimeConcat,
    RuntimeDateTimeFormat,
    RuntimeDay,
    RuntimeDivide,
    RuntimeEqual,
    RuntimeGenerateUUID,
    RuntimeGet,
    RuntimeGetProperty,
    RuntimeGreaterThan,
    RuntimeGreaterThanOrEqual,
    RuntimeHour,
    RuntimeIf,
    RuntimeIsEven,
    RuntimeIsOdd,
    RuntimeLessThan,
    RuntimeLessThanOrEqual,
    RuntimeLower,
    RuntimeMinus,
    RuntimeMinute,
    RuntimeMonth,
    RuntimeMultiply,
    RuntimeNotEqual,
    RuntimeNow,
    RuntimeOr,
    RuntimeRandomBool,
    RuntimeRandomFloat,
    RuntimeRandomInt,
    RuntimeRound,
    RuntimeSecond,
    RuntimeToday,
    RuntimeUpper,
    RuntimeYear,
)


@pytest.mark.parametrize(
    "args,expected",
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
            [[["a", "b", "c", "d"]], "x"],
            "a,b,c,dx",
        ),
    ],
)
def test_runtime_concat_execute(args, expected):
    parsed_args = RuntimeConcat().parse_args(args)
    result = RuntimeConcat().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        ("foo", None),
        (101, None),
        (3.14, None),
        (True, None),
        (False, None),
        ({}, None),
        (None, None),
        (datetime.now(), None),
    ],
)
def test_runtime_concat_validate_type_of_args(arg, expected):
    result = RuntimeConcat().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], True),
    ],
)
def test_runtime_concat_validate_number_of_args(args, expected):
    result = RuntimeConcat().validate_number_of_args(args)
    assert result is expected


def test_runtime_get_execute():
    context = {
        "id": 101,
        "fruit": "Apple",
        "color": "Red",
    }

    assert RuntimeGet().execute(context, ["id"]) == 101
    assert RuntimeGet().execute(context, ["fruit"]) == "Apple"
    assert RuntimeGet().execute(context, ["color"]) == "Red"


@pytest.mark.parametrize(
    "args,expected",
    [
        ([1, 2], 3),
        ([2, 3], 5),
        ([2, 3.14], 5.140000000000001),
        ([2.43, 3.14], 5.57),
        ([-4, 23], 19),
    ],
)
def test_runtime_add_execute(args, expected):
    parsed_args = RuntimeAdd().parse_args(args)
    result = RuntimeAdd().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # These are invalid
        ("foo", "foo"),
        (True, True),
        (None, None),
        ({}, {}),
        ([], []),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
        ),
        # These are valid
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_add_validate_type_of_args(arg, expected):
    result = RuntimeAdd().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_add_validate_number_of_args(args, expected):
    result = RuntimeAdd().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([3, 1], 2),
        ([3.14, 4.56], -1.4199999999999995),
        ([45.25, -2], 47.25),
    ],
)
def test_runtime_minus_execute(args, expected):
    parsed_args = RuntimeMinus().parse_args(args)
    result = RuntimeMinus().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # These are invalid
        ("foo", "foo"),
        (True, True),
        (None, None),
        ({}, {}),
        ([], []),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
        ),
        # These are valid
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_minus_validate_type_of_args(arg, expected):
    result = RuntimeMinus().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_minus_validate_number_of_args(args, expected):
    result = RuntimeMinus().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([3, 1], 3),
        ([3.14, 4.56], 14.318399999999999),
        ([52.14, -2], -104.28),
    ],
)
def test_runtime_multiply_execute(args, expected):
    parsed_args = RuntimeMultiply().parse_args(args)
    result = RuntimeMultiply().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # These are invalid
        ("foo", "foo"),
        (True, True),
        (None, None),
        ({}, {}),
        ([], []),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
        ),
        # These are valid
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_multiply_validate_type_of_args(arg, expected):
    result = RuntimeMultiply().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_multiply_validate_number_of_args(args, expected):
    result = RuntimeMultiply().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([4, 2], 2),
        ([3.14, 1.56], 2.0128205128205128),
        ([23.24, -2], -11.62),
    ],
)
def test_runtime_divide_execute(args, expected):
    parsed_args = RuntimeDivide().parse_args(args)
    result = RuntimeDivide().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # These are invalid
        ("foo", "foo"),
        (True, True),
        (None, None),
        ({}, {}),
        ([], []),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
        ),
        # These are valid
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_divide_validate_type_of_args(arg, expected):
    result = RuntimeDivide().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_divide_validate_number_of_args(args, expected):
    result = RuntimeDivide().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([2, 2], True),
        ([2, 3], False),
        (["foo", "foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_equal_execute(args, expected):
    parsed_args = RuntimeEqual().parse_args(args)
    result = RuntimeEqual().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", None),
        (True, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_equal_validate_type_of_args(arg, expected):
    result = RuntimeEqual().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_equal_validate_number_of_args(args, expected):
    result = RuntimeEqual().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([2, 2], False),
        ([2, 3], True),
        (["foo", "foo"], False),
        (["foo", "bar"], True),
    ],
)
def test_runtime_not_equal_execute(args, expected):
    parsed_args = RuntimeNotEqual().parse_args(args)
    result = RuntimeNotEqual().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", None),
        (True, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_not_equal_validate_type_of_args(arg, expected):
    result = RuntimeNotEqual().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_not_equal_validate_number_of_args(args, expected):
    result = RuntimeNotEqual().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([2, 2], False),
        ([2, 3], False),
        ([3, 2], True),
        (["apple", "ball"], False),
        (["ball", "apple"], True),
    ],
)
def test_runtime_greater_than_execute(args, expected):
    parsed_args = RuntimeGreaterThan().parse_args(args)
    result = RuntimeGreaterThan().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", None),
        (True, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_greater_than_validate_type_of_args(arg, expected):
    result = RuntimeGreaterThan().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_greater_than_validate_number_of_args(args, expected):
    result = RuntimeGreaterThan().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([2, 2], False),
        ([2, 3], True),
        ([3, 2], False),
        (["apple", "ball"], True),
        (["ball", "apple"], False),
    ],
)
def test_runtime_less_than_execute(args, expected):
    parsed_args = RuntimeLessThan().parse_args(args)
    result = RuntimeLessThan().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", None),
        (True, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_less_than_validate_type_of_args(arg, expected):
    result = RuntimeLessThan().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_less_than_validate_number_of_args(args, expected):
    result = RuntimeLessThan().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([2, 2], True),
        ([2, 3], False),
        ([3, 2], True),
        (["apple", "ball"], False),
        (["ball", "apple"], True),
    ],
)
def test_runtime_greater_than_or_equal_execute(args, expected):
    parsed_args = RuntimeGreaterThanOrEqual().parse_args(args)
    result = RuntimeGreaterThanOrEqual().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", None),
        (True, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_greater_than_or_equal_validate_type_of_args(arg, expected):
    result = RuntimeGreaterThanOrEqual().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_greater_than_or_equal_validate_number_of_args(args, expected):
    result = RuntimeGreaterThanOrEqual().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([2, 2], True),
        ([2, 3], True),
        ([3, 2], False),
        (["apple", "ball"], True),
        (["ball", "apple"], False),
    ],
)
def test_runtime_less_than_or_equal_execute(args, expected):
    parsed_args = RuntimeLessThanOrEqual().parse_args(args)
    result = RuntimeLessThanOrEqual().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", None),
        (True, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        (1, None),
        (3.14, None),
        ("23", None),
        ("23.33", None),
    ],
)
def test_runtime_less_than_or_equal_validate_type_of_args(arg, expected):
    result = RuntimeLessThanOrEqual().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_less_than_or_equal_validate_number_of_args(args, expected):
    result = RuntimeLessThanOrEqual().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["apple"], "APPLE"),
        (["ball"], "BALL"),
        (["foo bar"], "FOO BAR"),
    ],
)
def test_runtime_upper_execute(args, expected):
    parsed_args = RuntimeUpper().parse_args(args)
    result = RuntimeUpper().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Text (or convertable to text) types are allowed
        ("foo", None),
        (123, None),
        (123.45, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
    ],
)
def test_runtime_upper_validate_type_of_args(arg, expected):
    result = RuntimeUpper().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_upper_validate_number_of_args(args, expected):
    result = RuntimeUpper().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["ApPle"], "apple"),
        (["BALL"], "ball"),
        (["Foo BAR"], "foo bar"),
    ],
)
def test_runtime_lower_execute(args, expected):
    parsed_args = RuntimeLower().parse_args(args)
    result = RuntimeLower().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Text (or convertable to text) types are allowed
        ("foo", None),
        (123, None),
        (123.45, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
    ],
)
def test_runtime_lower_validate_type_of_args(arg, expected):
    result = RuntimeLower().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_lower_validate_number_of_args(args, expected):
    result = RuntimeLower().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["ApPle"], "Apple"),
        (["BALL"], "Ball"),
        (["Foo BAR"], "Foo bar"),
    ],
)
def test_runtime_capitalize_execute(args, expected):
    parsed_args = RuntimeCapitalize().parse_args(args)
    result = RuntimeCapitalize().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Text (or convertable to text) types are allowed
        ("foo", None),
        (123, None),
        (123.45, None),
        (None, None),
        ({}, None),
        ([], None),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
    ],
)
def test_runtime_capitalize_validate_type_of_args(arg, expected):
    result = RuntimeCapitalize().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_capitalize_validate_number_of_args(args, expected):
    result = RuntimeCapitalize().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["23.45", 2], 23.45),
        # Defaults to 2 decimal places
        ([33.4567], 33.46),
        ([33, 0], 33),
        ([49.4587, 3], 49.459),
    ],
)
def test_runtime_round_execute(args, expected):
    parsed_args = RuntimeRound().parse_args(args)
    result = RuntimeRound().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Number (or convertable to number) types are allowed
        ("23.34", None),
        (123, None),
        (123.45, None),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
        ),
    ],
)
def test_runtime_round_validate_type_of_args(arg, expected):
    result = RuntimeRound().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], False),
    ],
)
def test_runtime_round_validate_number_of_args(args, expected):
    result = RuntimeRound().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["23.45"], False),
        (["24"], True),
        ([33.4567], False),
        ([33], False),
        ([50], True),
    ],
)
def test_runtime_is_even_execute(args, expected):
    parsed_args = RuntimeIsEven().parse_args(args)
    result = RuntimeIsEven().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Number (or convertable to number) types are allowed
        ("23.34", None),
        (123, None),
        (123.45, None),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
        ),
    ],
)
def test_runtime_is_even_validate_type_of_args(arg, expected):
    result = RuntimeIsEven().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_is_even_validate_number_of_args(args, expected):
    result = RuntimeIsEven().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["23.45"], True),
        (["24"], False),
        ([33.4567], True),
        ([33], True),
        ([50], False),
    ],
)
def test_runtime_is_odd_execute(args, expected):
    parsed_args = RuntimeIsOdd().parse_args(args)
    result = RuntimeIsOdd().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Number (or convertable to number) types are allowed
        ("23.34", None),
        (123, None),
        (123.45, None),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
        ),
    ],
)
def test_runtime_is_odd_validate_type_of_args(arg, expected):
    result = RuntimeIsOdd().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_is_odd_validate_number_of_args(args, expected):
    result = RuntimeIsOdd().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2025-11-03", "YY/MM/DD"], "25/11/03"),
        (["2025-11-03", "DD/MM/YYYY HH:mm:ss"], "03/11/2025 00:00:00"),
        (
            ["2025-11-06 11:30:30.861096+00:00", "DD/MM/YYYY HH:mm:ss"],
            "06/11/2025 11:30:30",
        ),
        (["2025-11-06 11:30:30.861096+00:00", "%f"], "861096"),
    ],
)
def test_runtime_datetime_format_execute(args, expected):
    parsed_args = RuntimeDateTimeFormat().parse_args(args)
    context = MagicMock()
    context.get_timezone_name.return_value = "UTC"

    result = RuntimeDateTimeFormat().execute(context, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Date like values are valid
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        ("2025-11-06", None),
        ("2025-11-06 11:30:30.861096+00:00", None),
        # Otherwise the type is invalid
        ("23.34", "23.34"),
        (123, 123),
        (123.45, 123.45),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
    ],
)
def test_runtime_datetime_format_validate_type_of_args(arg, expected):
    result = RuntimeDateTimeFormat().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], True),
        (["foo", "bar", "baz"], True),
        (["foo", "bar", "baz", "x"], False),
    ],
)
def test_runtime_datetime_format_validate_number_of_args(args, expected):
    result = RuntimeDateTimeFormat().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2025-11-03"], 3),
        (["2025-11-04 11:30:30.861096+00:00"], 4),
        (["2025-11-05 11:30:30.861096+00:00"], 5),
    ],
)
def test_runtime_day_execute(args, expected):
    parsed_args = RuntimeDay().parse_args(args)
    result = RuntimeDay().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Date like values are valid
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        ("2025-11-06", None),
        ("2025-11-06 11:30:30.861096+00:00", None),
        # Otherwise the type is invalid
        ("23.34", "23.34"),
        (123, 123),
        (123.45, 123.45),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
    ],
)
def test_runtime_day_validate_type_of_args(arg, expected):
    result = RuntimeDay().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_day_validate_number_of_args(args, expected):
    result = RuntimeDay().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2025-09-03"], 9),
        (["2025-10-04 11:30:30.861096+00:00"], 10),
        (["2025-11-05 11:30:30.861096+00:00"], 11),
    ],
)
def test_runtime_month_execute(args, expected):
    parsed_args = RuntimeMonth().parse_args(args)
    result = RuntimeMonth().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Date like values are valid
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        ("2025-11-06", None),
        ("2025-11-06 11:30:30.861096+00:00", None),
        # Otherwise the type is invalid
        ("23.34", "23.34"),
        (123, 123),
        (123.45, 123.45),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
    ],
)
def test_runtime_month_validate_type_of_args(arg, expected):
    result = RuntimeMonth().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_month_validate_number_of_args(args, expected):
    result = RuntimeMonth().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2023-09-03"], 2023),
        (["2024-10-04 11:30:30.861096+00:00"], 2024),
        (["2025-11-05 11:30:30.861096+00:00"], 2025),
    ],
)
def test_runtime_year_execute(args, expected):
    parsed_args = RuntimeYear().parse_args(args)
    result = RuntimeYear().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Date like values are valid
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        ("2025-11-06", None),
        ("2025-11-06 11:30:30.861096+00:00", None),
        # Otherwise the type is invalid
        ("23.34", "23.34"),
        (123, 123),
        (123.45, 123.45),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
    ],
)
def test_runtime_year_validate_type_of_args(arg, expected):
    result = RuntimeYear().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_year_validate_number_of_args(args, expected):
    result = RuntimeYear().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2023-09-03"], 0),
        (["2024-10-04 11:30:30.861096+00:00"], 11),
        (["2025-11-05 12:30:30.861096+00:00"], 12),
        (["2025-11-05 16:30:30.861096+00:00"], 16),
    ],
)
def test_runtime_hour_execute(args, expected):
    parsed_args = RuntimeHour().parse_args(args)
    result = RuntimeHour().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Date like values are valid
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        ("2025-11-06", None),
        ("2025-11-06 11:30:30.861096+00:00", None),
        # Otherwise the type is invalid
        ("23.34", "23.34"),
        (123, 123),
        (123.45, 123.45),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
    ],
)
def test_runtime_hour_validate_type_of_args(arg, expected):
    result = RuntimeHour().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_hour_validate_number_of_args(args, expected):
    result = RuntimeHour().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2023-09-03"], 0),
        (["2024-10-04 11:05:30.861096+00:00"], 5),
        (["2025-11-05 12:32:30.861096+00:00"], 32),
        (["2025-11-05 16:33:30.861096+00:00"], 33),
    ],
)
def test_runtime_minute_execute(args, expected):
    parsed_args = RuntimeMinute().parse_args(args)
    result = RuntimeMinute().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Date like values are valid
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        ("2025-11-06", None),
        ("2025-11-06 11:30:30.861096+00:00", None),
        # Otherwise the type is invalid
        ("23.34", "23.34"),
        (123, 123),
        (123.45, 123.45),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
    ],
)
def test_runtime_minute_validate_type_of_args(arg, expected):
    result = RuntimeMinute().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_minute_validate_number_of_args(args, expected):
    result = RuntimeMinute().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2023-09-03"], 0),
        (["2024-10-04 11:05:05.861096+00:00"], 5),
        (["2025-11-05 12:32:30.861096+00:00"], 30),
        (["2025-11-05 16:33:49.861096+00:00"], 49),
    ],
)
def test_runtime_second_execute(args, expected):
    parsed_args = RuntimeSecond().parse_args(args)
    result = RuntimeSecond().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # Date like values are valid
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), None),
        ("2025-11-06", None),
        ("2025-11-06 11:30:30.861096+00:00", None),
        # Otherwise the type is invalid
        ("23.34", "23.34"),
        (123, 123),
        (123.45, 123.45),
        (None, None),
        ("foo", "foo"),
        ({}, {}),
        ([], []),
    ],
)
def test_runtime_second_validate_type_of_args(arg, expected):
    result = RuntimeSecond().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_second_validate_number_of_args(args, expected):
    result = RuntimeSecond().validate_number_of_args(args)
    assert result is expected


def test_runtime_now_execute():
    with freeze_time("2025-11-06 15:48:51"):
        parsed_args = RuntimeNow().parse_args([])
        result = RuntimeNow().execute({}, parsed_args)
        assert str(result) == "2025-11-06 15:48:51+00:00"


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], True),
        (["foo"], False),
    ],
)
def test_runtime_now_validate_number_of_args(args, expected):
    result = RuntimeNow().validate_number_of_args(args)
    assert result is expected


def test_runtime_today_execute():
    with freeze_time("2025-11-06 15:48:51"):
        parsed_args = RuntimeToday().parse_args([])
        result = RuntimeToday().execute({}, parsed_args)
        assert str(result) == "2025-11-06"


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], True),
        (["foo"], False),
    ],
)
def test_runtime_today_validate_number_of_args(args, expected):
    result = RuntimeToday().validate_number_of_args(args)
    assert result is expected
