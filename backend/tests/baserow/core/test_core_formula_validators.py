from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError

import pytest

from baserow.core.formula.validator import (
    ensure_numeric,
    ensure_string,
    ensure_string_or_integer,
)


@pytest.mark.parametrize("value", [0, 1, 10, 100])
@patch("baserow.core.formula.validator.ensure_string")
def test_ensure_string_or_integer_returns_integer(mock_ensure_string, value):
    """
    Ensure that if an integer is passed in, it is returned as an integer.
    """

    result = ensure_string_or_integer(value)
    assert result == value
    mock_ensure_string.assert_not_called()


@pytest.mark.parametrize("value", ["0", "1"])
def test_ensure_string_or_integer_returns_string(value):
    """
    Ensure that if a string is passed in, it is returned.
    """

    result = ensure_string_or_integer(value)
    assert result == value


@pytest.mark.parametrize("value", [None, "", []])
def test_ensure_string_or_integer_raises_if_allow_empty_is_false(value):
    """
    Ensure that if the value is falsey and allow_empty is False, an
    exception is raised.
    """

    with pytest.raises(ValidationError) as e:
        ensure_string_or_integer(value, allow_empty=False)

    assert e.value.message == "A valid String is required."


@pytest.mark.parametrize("value", [None, "", []])
def test_ensure_string_or_integer_returns_empty_string_if_allow_empty_is_true(value):
    """
    Ensure that if the value is falsey and allow_empty is True, an
    empty string is returned.
    """

    result = ensure_string_or_integer(value, allow_empty=True)

    assert result == ""


@pytest.mark.parametrize(
    "value,",
    [
        "",
        None,
        [],
        {},
    ],
)
def test_ensure_string_raises_error_if_allow_empty_is_false(value):
    """
    Test the ensure_string() function.

    Ensure a ValidationError is raised if the value is falsey and allow_empty
    is False.
    """

    with pytest.raises(ValidationError) as e:
        ensure_string(value, allow_empty=False)

    assert e.value.message == "A valid String is required."


@pytest.mark.parametrize(
    "value,",
    [
        "",
        None,
        [],
        {},
    ],
)
def test_ensure_string_returns_empty_string_if_allow_empty_is_true(value):
    """
    Test the ensure_string() function.

    Ensure that if value falsey and allow_empty is True or not provided,
    an empty string is returned.
    """

    result = ensure_string(value, allow_empty=True)
    assert result == ""

    # Test default value of allow_empty kwarg
    result = ensure_string(value)
    assert result == ""


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            ["foo"],
            "foo",
        ),
        (
            ["foo", ["bar"]],
            "foo,bar",
        ),
        (
            ["foo", {}],
            "foo",
        ),
        (
            ["foo", {"bar": "baz"}],
            'foo,{"bar": "baz"}',
        ),
        (
            ["foo", {"bar": "baz"}, "a", ["b"]],
            'foo,{"bar": "baz"},a,b',
        ),
    ],
)
def test_ensure_string_returns_string_version_of_list(value, expected):
    """
    Test the ensure_string() function.

    Ensure that if value is a list, a string version of that list is returned.
    """

    result = ensure_string(value)
    assert result == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            {"foo": "bar"},
            '{"foo": "bar"}',
        ),
        (
            {"foo": ["a", "b"], "baz": {"d": ["e", "f"]}},
            '{"foo": ["a", "b"], "baz": {"d": ["e", "f"]}}',
        ),
    ],
)
def test_ensure_string_returns_string_version_of_dict(value, expected):
    """
    Test the ensure_string() function.

    Ensure that if value is a dict, a string version of that dict is returned.
    """

    result = ensure_string(value)
    assert result == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        # str
        (
            "foo",
            "foo",
        ),
        # tuple
        (
            ("foo",),
            "('foo',)",
        ),
        # set
        (
            {"foo"},
            "{'foo'}",
        ),
    ],
)
def test_ensure_string_returns_str_by_default(value, expected):
    """
    Test the ensure_string() function.

    Ensure that if value is non empty, by default a string version is returned.
    """

    result = ensure_string(value)
    assert result == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, 0),
        (1, 1),
        (10, 10),
        (-5, -5),
        (3.14, 3.14),
        (-2.5, -2.5),
        (Decimal("10.5"), Decimal("10.5")),
        ("0", 0),
        ("1", 1),
        ("10", 10),
        ("-5", -5),
        ("3.14", 3.14),
        ("-2.5", -2.5),
        ("10.5", 10.5),
    ],
)
def test_ensure_numeric_returns_correct_numeric_value(value, expected):
    """
    Test the ensure_numeric() function.

    Ensure that valid numeric values or
    convertible values return the correct numeric type.
    """

    result = ensure_numeric(value)
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize(
    "value",
    [
        "abc",
        "1a",
        "a1",
        "1.2.3",
        "1,000",
        True,
        False,
        [],
        {},
        object(),
    ],
)
def test_ensure_numeric_raises_error_for_invalid_values(value):
    """
    Test the ensure_numeric() function.

    Ensure a ValidationError is raised
    if the value cannot be converted to a numeric type.
    """

    with pytest.raises(ValidationError) as e:
        ensure_numeric(value)

    assert f"Value '{value}' is not a valid number or convertible to a number." in str(
        e.value
    )


@pytest.mark.parametrize(
    "value,allow_null,expected",
    [
        (None, True, None),
        ("", True, None),
        (None, False, None),  # This will raise an error
        ("", False, None),  # This will raise an error
    ],
)
def test_ensure_numeric_handles_null_values(value, allow_null, expected):
    """
    Test the ensure_numeric() function.

    Ensure that None or empty string values are handled correctly
     based on allow_null parameter.
    """

    if not allow_null:
        with pytest.raises(ValidationError):
            ensure_numeric(value, allow_null=allow_null)
    else:
        result = ensure_numeric(value, allow_null=allow_null)
        assert result is expected


def test_ensure_numeric_with_very_large_numbers():
    """
    Test the ensure_numeric() function with very large numbers.

    Ensure that very large numbers are handled correctly.
    """

    large_number = "9" * 100
    result = ensure_numeric(large_number)
    assert isinstance(result, (int, float, Decimal))
    assert str(result) == large_number
