import uuid
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from baserow.core.formula import BaserowFormulaSyntaxError
from baserow.core.formula.runtime_formula_types import (
    RuntimeAbs,
    RuntimeAdd,
    RuntimeAnd,
    RuntimeAt,
    RuntimeAvg,
    RuntimeCapitalize,
    RuntimeConcat,
    RuntimeContains,
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
    RuntimeIsEmpty,
    RuntimeIsEven,
    RuntimeIsOdd,
    RuntimeJoin,
    RuntimeLength,
    RuntimeLessThan,
    RuntimeLessThanOrEqual,
    RuntimeLower,
    RuntimeMinus,
    RuntimeMinute,
    RuntimeMonth,
    RuntimeMultiply,
    RuntimeNotEqual,
    RuntimeNow,
    RuntimeNull,
    RuntimeNumberFormat,
    RuntimeOr,
    RuntimeRandomBool,
    RuntimeRandomFloat,
    RuntimeRandomInt,
    RuntimeReplace,
    RuntimeReverse,
    RuntimeRound,
    RuntimeSecond,
    RuntimeSplit,
    RuntimeStrip,
    RuntimeSum,
    RuntimeToArray,
    RuntimeToDatetime,
    RuntimeToday,
    RuntimeToDuration,
    RuntimeUpper,
    RuntimeYear,
)
from baserow.test_utils.helpers import AnyBool, AnyFloat, AnyInt


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
        ("foo", []),
        (101, []),
        (3.14, []),
        (True, []),
        (False, []),
        ({}, []),
        (None, []),
        (datetime.now(), []),
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
        ("foo", [(0, "foo")]),
        (True, [(0, True)]),
        (None, [(0, None)]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
        ),
        # These are valid
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ("foo", [(0, "foo")]),
        (True, [(0, True)]),
        (None, [(0, None)]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
        ),
        # These are valid
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ("foo", [(0, "foo")]),
        (True, [(0, True)]),
        (None, [(0, None)]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
        ),
        # These are valid
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ("foo", [(0, "foo")]),
        (True, [(0, True)]),
        (None, [(0, None)]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
        ),
        # These are valid
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ("foo", []),
        (True, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ("foo", []),
        (True, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ([1, "a"], None),
        (["a", 1], None),
        (
            [
                date(2025, 12, 18),
                date(2025, 12, 18),
            ],
            False,
        ),
        (
            [
                date(2025, 12, 19),
                date(2025, 12, 18),
            ],
            True,
        ),
        (
            [
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
            ],
            False,
        ),
        (
            [
                datetime(year=2025, month=11, day=6, hour=12, minute=31),
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
            ],
            True,
        ),
    ],
)
def test_runtime_greater_than_execute(args, expected):
    parsed_args = RuntimeGreaterThan().parse_args(args)

    if expected is None:
        with pytest.raises(TypeError) as e:
            RuntimeGreaterThan().execute({}, parsed_args)
        assert f"'>' not supported between instances of" in str(e)
    else:
        result = RuntimeGreaterThan().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", []),
        (True, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ([1, "a"], None),
        (["a", 1], None),
        (
            [
                date(2025, 12, 18),
                date(2025, 12, 18),
            ],
            False,
        ),
        (
            [
                date(2025, 12, 18),
                date(2025, 12, 19),
            ],
            True,
        ),
        (
            [
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
            ],
            False,
        ),
        (
            [
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
                datetime(year=2025, month=11, day=6, hour=12, minute=31),
            ],
            True,
        ),
    ],
)
def test_runtime_less_than_execute(args, expected):
    parsed_args = RuntimeLessThan().parse_args(args)

    if expected is None:
        with pytest.raises(TypeError) as e:
            RuntimeLessThan().execute({}, parsed_args)
        assert f"'<' not supported between instances of" in str(e)
    else:
        result = RuntimeLessThan().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", []),
        (True, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ([[], "a"], None),
        ([{}, "a"], None),
        ([1, "a"], None),
        (["a", 1], None),
        (
            [
                date(2025, 12, 17),
                date(2025, 12, 18),
            ],
            False,
        ),
        (
            [
                date(2025, 12, 20),
                date(2025, 12, 19),
            ],
            True,
        ),
        (
            [
                datetime(year=2025, month=11, day=6, hour=12, minute=29),
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
            ],
            False,
        ),
        (
            [
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
            ],
            True,
        ),
    ],
)
def test_runtime_greater_than_or_equal_execute(args, expected):
    parsed_args = RuntimeGreaterThanOrEqual().parse_args(args)

    if expected is None:
        with pytest.raises(TypeError) as e:
            RuntimeGreaterThanOrEqual().execute({}, parsed_args)
        assert f"'>=' not supported between instances of" in str(e)
    else:
        result = RuntimeGreaterThanOrEqual().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", []),
        (True, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        ([[], "a"], None),
        ([{}, "a"], None),
        ([1, "a"], None),
        (["a", 1], None),
        (
            [
                date(2025, 12, 18),
                date(2025, 12, 17),
            ],
            False,
        ),
        (
            [
                date(2025, 12, 19),
                date(2025, 12, 20),
            ],
            True,
        ),
        (
            [
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
                datetime(year=2025, month=11, day=6, hour=12, minute=29),
            ],
            False,
        ),
        (
            [
                datetime(year=2025, month=11, day=6, hour=12, minute=29),
                datetime(year=2025, month=11, day=6, hour=12, minute=30),
            ],
            True,
        ),
    ],
)
def test_runtime_less_than_or_equal_execute(args, expected):
    parsed_args = RuntimeLessThanOrEqual().parse_args(args)

    if expected is None:
        with pytest.raises(TypeError) as e:
            RuntimeLessThanOrEqual().execute({}, parsed_args)
        assert f"'<=' not supported between instances of" in str(e)
    else:
        result = RuntimeLessThanOrEqual().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        # All types are allowed
        ("foo", []),
        (True, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        (1, []),
        (3.14, []),
        ("23", []),
        ("23.33", []),
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
        (["bAll"], "BALL"),
        (["Foo Bar"], "FOO BAR"),
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
        ("foo", []),
        (123, []),
        (123.45, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
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
        ("foo", []),
        (123, []),
        (123.45, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
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
        ("foo", []),
        (123, []),
        (123.45, []),
        (None, []),
        ({}, []),
        ([], []),
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
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
        ("23.34", []),
        (123, []),
        (123.45, []),
        (None, [(0, None)]),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
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
        ([5], 5),
        ([-5], 5),
        ([0], 0),
        ([-3.14], 3.14),
        ([3.14], 3.14),
        (["23.45"], 23.45),
        (["-23.45"], 23.45),
    ],
)
def test_runtime_abs_execute(args, expected):
    parsed_args = RuntimeAbs().parse_args(args)
    result = RuntimeAbs().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "arg,expected",
    [
        ("23.34", []),
        (123, []),
        (123.45, []),
        (None, [(0, None)]),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
        ),
    ],
)
def test_runtime_abs_validate_type_of_args(arg, expected):
    result = RuntimeAbs().validate_type_of_args([arg])
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_abs_validate_number_of_args(args, expected):
    result = RuntimeAbs().validate_number_of_args(args)
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
        ("23.34", []),
        (123, []),
        (123.45, []),
        (None, [(0, None)]),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
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
        ("23.34", []),
        (123, []),
        (123.45, []),
        (None, [(0, None)]),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
        (
            datetime(year=2025, month=11, day=6, hour=12, minute=30),
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
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
        (["2025-11-06 11:30:30.861096+00:00", "SSS"], "861"),
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
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        ("2025-11-06", []),
        ("2025-11-06 11:30:30.861096+00:00", []),
        # Otherwise the type is invalid
        ("23.34", [(0, "23.34")]),
        (123, [(0, 123)]),
        (123.45, [(0, 123.45)]),
        (None, []),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
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


def test_runtime_datetime_format_validate_args_raises_for_invalid_timezone():
    with pytest.raises(BaserowFormulaSyntaxError) as exc_info:
        RuntimeDateTimeFormat().validate_args(
            [datetime(2025, 11, 6, 12, 30), "YYYY-MM-DD", "Europe/Foo"]
        )
    assert "'Europe/Foo' is not a valid timezone" in str(exc_info.value)


def test_runtime_datetime_format_validate_args_raises_for_unsupported_format_token():
    with pytest.raises(BaserowFormulaSyntaxError) as exc_info:
        RuntimeDateTimeFormat().validate_args(
            [datetime(2025, 11, 6, 12, 30), "YYYY/MM/DD HH:mm:SS"]
        )
    assert "'YYYY/MM/DD HH:mm:SS' is not a valid datetime format" in str(exc_info.value)


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
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        ("2025-11-06", []),
        ("2025-11-06 11:30:30.861096+00:00", []),
        # Otherwise the type is invalid
        ("23.34", [(0, "23.34")]),
        (123, [(0, 123)]),
        (123.45, [(0, 123.45)]),
        (None, []),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
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
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        ("2025-11-06", []),
        ("2025-11-06 11:30:30.861096+00:00", []),
        # Otherwise the type is invalid
        ("23.34", [(0, "23.34")]),
        (123, [(0, 123)]),
        (123.45, [(0, 123.45)]),
        (None, []),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
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
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        ("2025-11-06", []),
        ("2025-11-06 11:30:30.861096+00:00", []),
        # Otherwise the type is invalid
        ("23.34", [(0, "23.34")]),
        (123, [(0, 123)]),
        (123.45, [(0, 123.45)]),
        (None, []),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
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
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        ("2025-11-06", []),
        ("2025-11-06 11:30:30.861096+00:00", []),
        # Otherwise the type is invalid
        ("23.34", [(0, "23.34")]),
        (123, [(0, 123)]),
        (123.45, [(0, 123.45)]),
        (None, []),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
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
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        ("2025-11-06", []),
        ("2025-11-06 11:30:30.861096+00:00", []),
        # Otherwise the type is invalid
        ("23.34", [(0, "23.34")]),
        (123, [(0, 123)]),
        (123.45, [(0, 123.45)]),
        (None, []),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
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
        (datetime(year=2025, month=11, day=6, hour=12, minute=30), []),
        ("2025-11-06", []),
        ("2025-11-06 11:30:30.861096+00:00", []),
        # Otherwise the type is invalid
        ("23.34", [(0, "23.34")]),
        (123, [(0, 123)]),
        (123.45, [(0, 123.45)]),
        (None, []),
        ("foo", [(0, "foo")]),
        ({}, [(0, {})]),
        ([], [(0, [])]),
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


@pytest.mark.parametrize(
    "args,expected",
    [
        (['{"foo": "bar"}', "foo"], "bar"),
        (['{"foo": "bar"}', "baz"], None),
    ],
)
def test_runtime_get_property_execute(args, expected):
    parsed_args = RuntimeGetProperty().parse_args(args)
    result = RuntimeGetProperty().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        # Dict (or convertable to dict) types are allowed
        (['{"foo": "bar"}', "foo"], []),
        ([{"foo": "bar"}, "foo"], []),
        # Invalid types for 1st arg (2nd arg is cast to string)
        (["foo", "foo"], [(0, "foo")]),
        ([100, "foo"], [(0, 100)]),
        ([12.34, "foo"], [(0, 12.34)]),
        (
            [datetime(year=2025, month=11, day=6, hour=12, minute=30), "foo"],
            [(0, datetime(year=2025, month=11, day=6, hour=12, minute=30))],
        ),
        ([None, "foo"], [(0, None)]),
        ([[], "foo"], [(0, [])]),
    ],
)
def test_runtime_get_property_validate_type_of_args(args, expected):
    result = RuntimeGetProperty().validate_type_of_args(args)
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
def test_runtime_get_property_validate_number_of_args(args, expected):
    result = RuntimeGetProperty().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([1, 100], AnyInt()),
        ([10, 100], AnyInt()),
    ],
)
def test_runtime_random_int_execute(args, expected):
    parsed_args = RuntimeRandomInt().parse_args(args)
    result = RuntimeRandomInt().execute({}, parsed_args)
    assert result == expected
    assert result >= args[0] and result <= args[1]


@pytest.mark.parametrize(
    "args,expected",
    [
        # numeric types are allowed
        ([1, 100], []),
        ([2.5, 56.64], []),
        (["3", "4.5"], []),
        # Invalid types for 1st arg
        ([{}, 5], [(0, {})]),
        (["foo", 5], [(0, "foo")]),
        # Invalid types for 2nd arg
        ([5, {}], [(1, {})]),
        ([5, "foo"], [(1, "foo")]),
    ],
)
def test_runtime_random_int_validate_type_of_args(args, expected):
    result = RuntimeRandomInt().validate_type_of_args(args)
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
def test_runtime_random_int_validate_number_of_args(args, expected):
    result = RuntimeRandomInt().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([1, 100], AnyFloat()),
        ([10.24, 100.54], AnyFloat()),
    ],
)
def test_runtime_random_float_execute(args, expected):
    parsed_args = RuntimeRandomFloat().parse_args(args)
    result = RuntimeRandomFloat().execute({}, parsed_args)
    assert result == expected
    assert result >= args[0] and result <= args[1]


@pytest.mark.parametrize(
    "args,expected",
    [
        # numeric types are allowed
        ([1, 100], []),
        ([2.5, 56.64], []),
        (["3", "4.5"], []),
        # Invalid types for 1st arg
        ([{}, 5], [(0, {})]),
        (["foo", 5], [(0, "foo")]),
        # Invalid types for 2nd arg
        ([5, {}], [(1, {})]),
        ([5, "foo"], [(1, "foo")]),
    ],
)
def test_runtime_random_float_validate_type_of_args(args, expected):
    result = RuntimeRandomFloat().validate_type_of_args(args)
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
def test_runtime_random_float_validate_number_of_args(args, expected):
    result = RuntimeRandomFloat().validate_number_of_args(args)
    assert result is expected


def test_runtime_random_bool_execute():
    parsed_args = RuntimeRandomBool().parse_args([])
    result = RuntimeRandomBool().execute({}, parsed_args)
    assert result == AnyBool()


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], True),
        (["foo"], False),
        (["foo", "bar"], False),
    ],
)
def test_runtime_random_bool_validate_number_of_args(args, expected):
    result = RuntimeRandomBool().validate_number_of_args(args)
    assert result is expected


def test_runtime_generate_uuid_execute():
    parsed_args = RuntimeGenerateUUID().parse_args([])
    result = RuntimeGenerateUUID().execute({}, parsed_args)
    assert isinstance(result, str)

    parsed = uuid.UUID(result)
    assert str(parsed) == result


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], True),
        (["foo"], False),
        (["foo", "bar"], False),
    ],
)
def test_runtime_generate_uuid_validate_number_of_args(args, expected):
    result = RuntimeGenerateUUID().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([True, "foo", "bar"], "foo"),
        ([False, "foo", "bar"], "bar"),
    ],
)
def test_runtime_if_execute(args, expected):
    parsed_args = RuntimeIf().parse_args(args)
    result = RuntimeIf().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        # Valid types for 1st arg (2nd and 3rd args can be Any)
        ([True, "foo", "bar"], []),
        ([False, "foo", "bar"], []),
        (["true", "foo", "bar"], []),
        (["false", "foo", "bar"], []),
        (["True", "foo", "bar"], []),
        (["False", "foo", "bar"], []),
    ],
)
def test_runtime_if_validate_type_of_args(args, expected):
    result = RuntimeIf().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], False),
        (["foo", "bar", "baz"], True),
        (["foo", "bar", "baz", "bat"], False),
    ],
)
def test_runtime_if_validate_number_of_args(args, expected):
    result = RuntimeIf().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([True, True], True),
        ([True, False], False),
        ([False, False], False),
    ],
)
def test_runtime_and_execute(args, expected):
    parsed_args = RuntimeAnd().parse_args(args)
    result = RuntimeAnd().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        # Valid types for 1st arg
        ([True, True], []),
        (["true", True], []),
        (["True", True], []),
        ([False, True], []),
        (["false", True], []),
        (["False", True], []),
        # Valid types for 2nd arg
        ([True, True], []),
        ([True, "true"], []),
        ([True, "True"], []),
        ([True, False], []),
        ([True, "false"], []),
        ([True, "False"], []),
        # With strict=False, all values are valid (converted via bool())
        (["foo", True], []),
        ([{}, True], []),
        (["", True], []),
        ([True, "foo"], []),
        ([True, {}], []),
        ([True, ""], []),
        ([100, True], []),
        ([True, 100], []),
    ],
)
def test_runtime_and_validate_type_of_args(args, expected):
    result = RuntimeAnd().validate_type_of_args(args)
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
def test_runtime_and_validate_number_of_args(args, expected):
    result = RuntimeAnd().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([True, True], True),
        ([True, False], True),
        ([False, False], False),
    ],
)
def test_runtime_or_execute(args, expected):
    parsed_args = RuntimeOr().parse_args(args)
    result = RuntimeOr().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        # Valid types for 1st arg
        ([True, True], []),
        (["true", True], []),
        (["True", True], []),
        ([False, True], []),
        (["false", True], []),
        (["False", True], []),
        # Valid types for 2nd arg
        ([True, True], []),
        ([True, "true"], []),
        ([True, "True"], []),
        ([True, False], []),
        ([True, "false"], []),
        ([True, "False"], []),
        # With strict=False, all values are valid (converted via bool())
        (["foo", True], []),
        ([{}, True], []),
        (["", True], []),
        ([True, "foo"], []),
        ([True, {}], []),
        ([True, ""], []),
        ([100, True], []),
        ([True, 100], []),
    ],
)
def test_runtime_or_validate_type_of_args(args, expected):
    result = RuntimeOr().validate_type_of_args(args)
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
def test_runtime_or_validate_number_of_args(args, expected):
    result = RuntimeOr().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["Hello, world!", "l", "-"], "He--o, wor-d!"),
        ([1112111, 2, 3], "1113111"),
    ],
)
def test_runtime_replace_execute(args, expected):
    parsed_args = RuntimeReplace().parse_args(args)
    result = RuntimeReplace().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        # Valid types for all args
        (["foo", "bar", "baz"], []),
        ([100, 200, 300], []),
    ],
)
def test_runtime_replace_validate_type_of_args(args, expected):
    result = RuntimeReplace().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], False),
        (["foo", "bar"], False),
        (["foo", "bar", "baz"], True),
        (["foo", "bar", "baz", "x"], False),
    ],
)
def test_runtime_replace_validate_number_of_args(args, expected):
    result = RuntimeReplace().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["Hello, world!"], 13),
        ([{"a": "b", "c": "d"}], 2),
        ([["a", "b", "c", "d"]], 4),
        ([3], None),
        (["0"], 1),
    ],
)
def test_runtime_length_execute(args, expected):
    parsed_args = RuntimeLength().parse_args(args)

    if expected is None:
        with pytest.raises(TypeError) as e:
            RuntimeLength().execute({}, parsed_args)
        assert "has no len" in str(e)
    else:
        result = RuntimeLength().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["foo"], []),
        (['{"foo": "bar"}'], []),
        (['["foo", "bar"]'], []),
    ],
)
def test_runtime_length_validate_type_of_args(args, expected):
    result = RuntimeLength().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_length_validate_number_of_args(args, expected):
    result = RuntimeLength().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["Hello, world!", "ll"], True),
        (["Hello, world!", "goodbye"], False),
        (['"foo bar"', "foo"], True),
        ([["foo", "bar"], "foo"], True),
        ([{"foo": "bar"}, "foo"], True),
        ([1, 2], None),
    ],
)
def test_runtime_contains_execute(args, expected):
    parsed_args = RuntimeContains().parse_args(args)

    if expected is None:
        with pytest.raises(TypeError) as e:
            RuntimeContains().execute({}, parsed_args)
        assert "iterable" in str(e)
    else:
        result = RuntimeContains().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["foo"], []),
        (['{"foo": "bar"}'], []),
        (['["foo", "bar"]'], []),
    ],
)
def test_runtime_contains_validate_type_of_args(args, expected):
    result = RuntimeContains().validate_type_of_args(args)
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
def test_runtime_contains_validate_number_of_args(args, expected):
    result = RuntimeContains().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["Hello, world!"], "!dlrow ,olleH"),
        ([["Hello", "world!"]], ["world!", "Hello"]),
        (["😀💙🚀"], "🚀💙😀"),
        (["Hello, world!"], "!dlrow ,olleH"),
        ([1], None),
    ],
)
def test_runtime_reverse_execute(args, expected):
    parsed_args = RuntimeReverse().parse_args(args)

    if expected is None:
        with pytest.raises(TypeError) as e:
            RuntimeReverse().execute({}, parsed_args)
        assert f"Cannot reverse {parsed_args[0]}" in str(e)
    else:
        result = RuntimeReverse().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["foo"], []),
        (["😀💙🚀"], []),
        (['["foo", "bar"]'], []),
    ],
)
def test_runtime_reverse_validate_type_of_args(args, expected):
    result = RuntimeReverse().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_reverse_validate_number_of_args(args, expected):
    result = RuntimeReverse().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([["foo", "bar"]], "foo,bar"),
        ([["foo", "bar"], "*"], "foo*bar"),
        (["foo", "*"], "f*o*o"),
        ([1], None),
    ],
)
def test_runtime_join_execute(args, expected):
    parsed_args = RuntimeJoin().parse_args(args)

    if expected is None:
        with pytest.raises(TypeError) as e:
            RuntimeJoin().execute({}, parsed_args)
        assert "can only join an iterable" in str(e)
    else:
        result = RuntimeJoin().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (['["foo", "bar"]'], []),
        (['["foo", "bar"]', "baz"], []),
    ],
)
def test_runtime_join_validate_type_of_args(args, expected):
    result = RuntimeJoin().validate_type_of_args(args)
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
def test_runtime_join_validate_number_of_args(args, expected):
    result = RuntimeJoin().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["foobar", "b"], ["foo", "ar"]),
        (["foobar"], ["foobar"]),
    ],
)
def test_runtime_split_execute(args, expected):
    parsed_args = RuntimeSplit().parse_args(args)
    result = RuntimeSplit().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (['["foo", "bar"]'], []),
        (['["foo", "bar"]', "baz"], []),
    ],
)
def test_runtime_split_validate_type_of_args(args, expected):
    result = RuntimeSplit().validate_type_of_args(args)
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
def test_runtime_split_validate_number_of_args(args, expected):
    result = RuntimeSplit().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([0], False),
        ([0.0], False),
        ([0.1], False),
        ([1], False),
        (["0"], False),
        ([""], True),
        ([None], True),
        ([date.today()], False),
        ([[]], True),
        ([{}], True),
        (["[]"], False),
        (["{}"], False),
        ([" "], True),
        (["foo"], False),
        ([["foo"]], False),
        ([{"foo": "bar"}], False),
    ],
)
def test_runtime_is_empty_execute(args, expected):
    parsed_args = RuntimeIsEmpty().parse_args(args)
    result = RuntimeIsEmpty().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([""], []),
        (["foo"], []),
        ([[]], []),
        ([{}], []),
    ],
)
def test_runtime_is_empty_validate_type_of_args(args, expected):
    result = RuntimeIsEmpty().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_is_empty_validate_number_of_args(args, expected):
    result = RuntimeIsEmpty().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([""], ""),
        ([" "], ""),
        ([" foo "], "foo"),
        (["foo"], "foo"),
    ],
)
def test_runtime_strip_execute(args, expected):
    parsed_args = RuntimeStrip().parse_args(args)
    result = RuntimeStrip().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([""], []),
        (["foo"], []),
    ],
)
def test_runtime_strip_validate_type_of_args(args, expected):
    result = RuntimeStrip().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_strip_validate_number_of_args(args, expected):
    result = RuntimeStrip().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([[1, 2, 3]], 6.0),
    ],
)
def test_runtime_sum_execute(args, expected):
    parsed_args = RuntimeSum().parse_args(args)
    result = RuntimeSum().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([""], []),
        (['["1", "foo"]'], [(0, '["1", "foo"]')]),
        ([["1", 2]], []),
    ],
)
def test_runtime_sum_validate_type_of_args(args, expected):
    result = RuntimeSum().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_sum_validate_number_of_args(args, expected):
    result = RuntimeSum().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([[1, 2, 3, 4]], 2.5),
    ],
)
def test_runtime_avg_execute(args, expected):
    parsed_args = RuntimeAvg().parse_args(args)
    result = RuntimeAvg().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([""], []),
        (['["1", "foo"]'], [(0, '["1", "foo"]')]),
        ([["1", 2]], []),
    ],
)
def test_runtime_avg_validate_type_of_args(args, expected):
    result = RuntimeAvg().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_avg_validate_number_of_args(args, expected):
    result = RuntimeAvg().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([["foo", "bar"], 1], "bar"),
        ([["foo", "bar"], 2], None),
        (["foobar", 3], "b"),
        ([3, 1], None),
    ],
)
def test_runtime_at_execute(args, expected):
    parsed_args = RuntimeAt().parse_args(args)

    if expected is None:
        with pytest.raises((IndexError, TypeError)) as e:
            RuntimeAt().execute({}, parsed_args)
    else:
        result = RuntimeAt().execute({}, parsed_args)
        assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["[]", "2"], []),
        ([[], 2], []),
    ],
)
def test_runtime_at_validate_type_of_args(args, expected):
    result = RuntimeAt().validate_type_of_args(args)
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
def test_runtime_at_validate_number_of_args(args, expected):
    result = RuntimeAt().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["foo,bar"], ["foo", "bar"]),
        ([["foo", "bar"]], ["foo", "bar"]),
        (['["foo", "bar"]'], ['["foo"', '"bar"]']),
        ([123], ["123"]),
    ],
)
def test_runtime_to_array_execute(args, expected):
    parsed_args = RuntimeToArray().parse_args(args)
    result = RuntimeToArray().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["[]"], []),
        ([[]], []),
        (["foo,bar"], []),
    ],
)
def test_runtime_to_array_validate_type_of_args(args, expected):
    result = RuntimeToArray().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["foo"], True),
        (["foo", "bar"], False),
    ],
)
def test_runtime_to_array_validate_number_of_args(args, expected):
    result = RuntimeToArray().validate_number_of_args(args)
    assert result is expected


def test_runtime_null_execute():
    parsed_args = RuntimeNull().parse_args([])
    result = RuntimeNull().execute({}, parsed_args)
    assert result is None


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], True),
        (["foo"], False),
    ],
)
def test_runtime_null_validate_number_of_args(args, expected):
    result = RuntimeNull().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([1000000], "1,000,000"),
        ([1000000, 2], "1,000,000.00"),
        ([1000000, 2, " ", ","], "1 000 000,00"),
        ([1000000, 2, ".", ","], "1.000.000,00"),
        ([212590.18, 2], "212,590.18"),
        ([212590.18, 2, " "], "212 590.18"),
        ([212590.18, 2, " ", ","], "212 590,18"),
        ([-1234567.89, 2], "-1,234,567.89"),
        ([1000, 0, ""], "1000"),
        ([1000, 3], "1,000.000"),
        ([0, 2], "0.00"),
    ],
)
def test_runtime_number_format_execute(args, expected):
    parsed_args = RuntimeNumberFormat().parse_args(args)
    result = RuntimeNumberFormat().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([1000], []),
        ([1000, 2], []),
        ([1000, 2, ","], []),
        ([1000, 2, " ", ","], []),
        (["foo"], [(0, "foo")]),
        ([1000, "bar"], [(1, "bar")]),
        ([1000, 2, ";"], [(2, ";")]),
        ([1000, 2, ",", ";"], [(3, ";")]),
    ],
)
def test_runtime_number_format_validate_type_of_args(args, expected):
    result = RuntimeNumberFormat().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        ([1000], True),
        ([1000, 2], True),
        ([1000, 2, ","], True),
        ([1000, 2, ",", "."], True),
        ([1000, 2, ",", ".", "extra"], False),
    ],
)
def test_runtime_number_format_validate_number_of_args(args, expected):
    result = RuntimeNumberFormat().validate_number_of_args(args)
    assert result is expected


def test_runtime_number_format_validate_args_raises_when_separators_are_same():
    with pytest.raises(BaserowFormulaSyntaxError) as exc_info:
        RuntimeNumberFormat().validate_args([1000, 2, ",", ","])
    assert "thousand separator and decimal separator cannot be the same" in str(
        exc_info.value
    )


def test_runtime_number_format_execute_raises_when_separators_are_same():
    with pytest.raises(BaserowFormulaSyntaxError):
        RuntimeNumberFormat().validate_args([1000, 2, ",", ","])


def test_runtime_number_format_validate_args_raises_human_readable_error_for_bad_thousand_sep():
    with pytest.raises(BaserowFormulaSyntaxError) as exc_info:
        RuntimeNumberFormat().validate_args([1000, 2, ";"])
    assert "';' is not a valid thousand separator" in str(exc_info.value)


def test_runtime_number_format_validate_args_raises_human_readable_error_for_bad_decimal_sep():
    with pytest.raises(BaserowFormulaSyntaxError) as exc_info:
        RuntimeNumberFormat().validate_args([1000, 2, ",", ";"])
    assert "';' is not a valid decimal separator" in str(exc_info.value)


@pytest.mark.parametrize(
    "args,expected",
    [
        (["1 day"], timedelta(days=1)),
        (["2 days"], timedelta(days=2)),
        (["3 weeks"], timedelta(weeks=3)),
        (["4 hours"], timedelta(hours=4)),
        (["30 minutes"], timedelta(minutes=30)),
        (["45 seconds"], timedelta(seconds=45)),
        (["1 year"], timedelta(days=365)),
        (["1 month"], timedelta(days=30)),
        (["1:30"], timedelta(seconds=90)),
        (["1:30:00"], timedelta(hours=1, minutes=30)),
        (["11:12:13.14"], timedelta(hours=11, minutes=12, seconds=13.14)),
        (["1d"], timedelta(days=1)),
        (["5h"], timedelta(hours=5)),
        (["1d 12h"], timedelta(days=1, hours=12)),
        (["1d 2h 3m"], timedelta(days=1, hours=2, minutes=3)),
        (["12.5"], timedelta(seconds=12.5)),
        (["0 days"], timedelta(0)),
        (["-1:30"], timedelta(seconds=-90)),
    ],
)
def test_runtime_to_duration_execute(args, expected):
    parsed_args = RuntimeToDuration().parse_args(args)
    result = RuntimeToDuration().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        # Valid duration strings — arg passes
        (["1 day"], []),
        (["2 days"], []),
        ([1], []),
        # Invalid strings — arg is returned as invalid
        (["foo"], [(0, "foo")]),
        ([""], [(0, "")]),
        ([None], [(0, None)]),
    ],
)
def test_runtime_to_duration_validate_type_of_args(args, expected):
    result = RuntimeToDuration().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["1 day"], True),
        (["1 day", "extra"], False),
    ],
)
def test_runtime_to_duration_validate_number_of_args(args, expected):
    result = RuntimeToDuration().validate_number_of_args(args)
    assert result is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (
            [datetime(2025, 1, 1, 12, 0, 0), timedelta(days=1)],
            datetime(2025, 1, 2, 12, 0, 0),
        ),
        (
            [timedelta(days=1), datetime(2025, 1, 1, 12, 0, 0)],
            datetime(2025, 1, 2, 12, 0, 0),
        ),
        (
            [datetime(2025, 6, 15), timedelta(hours=3)],
            datetime(2025, 6, 15, 3, 0, 0),
        ),
    ],
)
def test_runtime_add_with_datetime_and_timedelta(args, expected):
    parsed_args = RuntimeAdd().parse_args(args)
    result = RuntimeAdd().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([datetime(2025, 1, 1, 12, 0, 0), timedelta(days=1)], []),
        ([timedelta(days=1), datetime(2025, 1, 1, 12, 0, 0)], []),
        ([timedelta(days=1), timedelta(days=2)], [(0, timedelta(days=1))]),
        (["foo", timedelta(days=1)], [(0, "foo")]),
    ],
)
def test_runtime_add_validate_type_of_args_with_timedelta(args, expected):
    result = RuntimeAdd().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (
            [datetime(2025, 1, 2, 12, 0, 0), timedelta(days=1)],
            datetime(2025, 1, 1, 12, 0, 0),
        ),
        (
            [datetime(2025, 6, 15, 3, 0, 0), timedelta(hours=3)],
            datetime(2025, 6, 15, 0, 0, 0),
        ),
    ],
)
def test_runtime_minus_with_datetime_and_timedelta(args, expected):
    parsed_args = RuntimeMinus().parse_args(args)
    result = RuntimeMinus().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([datetime(2025, 1, 2, 12, 0, 0), timedelta(days=1)], []),
        ([timedelta(days=1), datetime(2025, 1, 1, 12, 0, 0)], [(0, timedelta(days=1))]),
        ([timedelta(days=1), timedelta(days=2)], [(0, timedelta(days=1))]),
        (["foo", timedelta(days=1)], [(0, "foo")]),
    ],
)
def test_runtime_minus_validate_type_of_args_with_timedelta(args, expected):
    result = RuntimeMinus().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2024-01-15"], datetime(2024, 1, 15, 0, 0, 0)),
        (["2024-01-15T12:30:00"], datetime(2024, 1, 15, 12, 30, 0)),
        (["2024-01-15T12:30:00.123456"], datetime(2024, 1, 15, 12, 30, 0, 123456)),
        (["15/01/2024", "DD/MM/YYYY"], datetime(2024, 1, 15, 0, 0, 0)),
        (["01-15-2024", "MM-DD-YYYY"], datetime(2024, 1, 15, 0, 0, 0)),
        (["2024-01-15 12:30", "YYYY-MM-DD HH:mm"], datetime(2024, 1, 15, 12, 30, 0)),
    ],
)
def test_runtime_to_datetime_execute(args, expected):
    parsed_args = RuntimeToDatetime().parse_args(args)
    result = RuntimeToDatetime().execute({}, parsed_args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (["2024-01-15"], []),
        (["not-a-date"], []),
        (["2024-01-15", "YYYY-MM-DD"], []),
    ],
)
def test_runtime_to_datetime_validate_type_of_args(args, expected):
    result = RuntimeToDatetime().validate_type_of_args(args)
    assert result == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], False),
        (["2024-01-15"], True),
        (["2024-01-15", "YYYY-MM-DD"], True),
        (["2024-01-15", "YYYY-MM-DD", "extra"], False),
    ],
)
def test_runtime_to_datetime_validate_number_of_args(args, expected):
    result = RuntimeToDatetime().validate_number_of_args(args)
    assert result is expected


def test_runtime_to_datetime_validate_args_raises_for_invalid_iso_string():
    with pytest.raises(BaserowFormulaSyntaxError) as exc_info:
        RuntimeToDatetime().validate_args(["not-a-date"])
    assert "is not a valid ISO datetime string" in str(exc_info.value)


def test_runtime_to_datetime_validate_args_raises_for_string_not_matching_format():
    with pytest.raises(BaserowFormulaSyntaxError) as exc_info:
        RuntimeToDatetime().validate_args(["2024-01-15", "DD/MM/YYYY"])
    assert "could not be parsed using format" in str(exc_info.value)


@pytest.mark.parametrize(
    "args",
    [
        ["2025/06/04 12:23:45", "YYYY/MM/DD HH:mm:SS"],
        ["2025/06/04 12:23:45", ""],
    ],
)
def test_runtime_to_datetime_validate_args_raises_for_unsupported_format_token(args):
    with pytest.raises(BaserowFormulaSyntaxError) as exc_info:
        RuntimeToDatetime().validate_args(args)
    assert "is not a valid datetime format" in str(exc_info.value)
