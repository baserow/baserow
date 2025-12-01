from datetime import date, datetime

import pytest

from baserow.core.formula.argument_types import (
    DateTimeBaserowRuntimeFormulaArgumentType,
    DictBaserowRuntimeFormulaArgumentType,
    NumberBaserowRuntimeFormulaArgumentType,
    TextBaserowRuntimeFormulaArgumentType,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (-5, True),
        (-5.5, True),
        ("-5.5", True),
        (0, True),
        (10, True),
        ("10", True),
        (16.25, True),
        ("16.25", True),
        ("foo", False),
        (" 1 ", False),
        ("", False),
        (None, False),
    ],
)
def test_number_test_method(value, expected):
    assert NumberBaserowRuntimeFormulaArgumentType().test(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (-5, -5),
        ("-5", -5),
        (0, 0),
        ("0", 0),
        (15.6, 15.6),
        ("15.6", 15.6),
    ],
)
def test_number_parse_method(value, expected):
    assert NumberBaserowRuntimeFormulaArgumentType().parse(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (-5, True),
        (-5.5, True),
        ("-5.5", True),
        (0, True),
        (10, True),
        ("10", True),
        (16.25, True),
        ("16.25", True),
        ("", True),
        ({}, True),
        ([], True),
        (None, True),
    ],
)
def test_text_test_method(value, expected):
    assert TextBaserowRuntimeFormulaArgumentType().test(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (-5, "-5"),
        ("-5", "-5"),
        (0, "0"),
        ("0", "0"),
        (15.6, "15.6"),
        ("15.6", "15.6"),
        ({"foo": "bar"}, '{"foo": "bar"}'),
        (["a", "b"], "a,b"),
        (None, ""),
    ],
)
def test_text_parse_method(value, expected):
    assert TextBaserowRuntimeFormulaArgumentType().parse(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2025-12-31", True),
        ("2025-12-31 14:22", True),
        ("2025-12-31 14:22:11", True),
        (date.today(), True),
        (datetime.now(), True),
        # None just returns True
        (None, True),
        # Invalid date format
        ("31-12-2025 14:22:11", False),
        (-5, False),
        (-5.5, False),
        (0, False),
        (10, False),
        (16.25, False),
        ("", False),
        ("-5.5", False),
        ("10", False),
        ("16.25", False),
        ([], False),
        ({}, False),
    ],
)
def test_datetime_test_method(value, expected):
    assert DateTimeBaserowRuntimeFormulaArgumentType().test(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        # A date is converted to datetime with hour/minute/second to 0
        (
            "2025-12-31",
            datetime(year=2025, month=12, day=31, hour=0, minute=0, second=0),
        ),
        (
            "2025-12-31 14:22",
            datetime(year=2025, month=12, day=31, hour=14, minute=22, second=0),
        ),
        (
            "2025-12-31 14:22:11",
            datetime(year=2025, month=12, day=31, hour=14, minute=22, second=11),
        ),
        (
            date(year=2025, month=10, day=22),
            datetime(year=2025, month=10, day=22, hour=0, minute=0, second=0),
        ),
        (
            datetime(year=2025, month=10, day=22, hour=1, minute=2, second=3),
            datetime(year=2025, month=10, day=22, hour=1, minute=2, second=3),
        ),
        (None, None),
    ],
)
def test_datetime_parse_method(value, expected):
    assert DateTimeBaserowRuntimeFormulaArgumentType().parse(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ({}, True),
        ("{}", True),
        ('{"foo": "bar"}', True),
        # Invalid JSON due to single quotes
        ("{'foo': 'bar'}", False),
        ("", False),
        ([], False),
        (0, False),
        (100, False),
        ("foo", False),
        (None, False),
    ],
)
def test_dict_test_method(value, expected):
    assert DictBaserowRuntimeFormulaArgumentType().test(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ({}, {}),
        ('{"foo": "bar"}', {"foo": "bar"}),
        ({"foo": "bar"}, {"foo": "bar"}),
    ],
)
def test_dict_parse_method(value, expected):
    assert DictBaserowRuntimeFormulaArgumentType().parse(value) == expected
