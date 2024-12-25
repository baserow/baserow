from unittest.mock import patch

from django.core.exceptions import ValidationError

import pytest

from baserow.core.formula.validator import ensure_string, ensure_string_or_integer


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
