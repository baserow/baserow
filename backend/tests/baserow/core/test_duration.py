import re
from datetime import timedelta

import pytest

from baserow.core.duration import (
    is_valid_duration_format,
    parse_value_with_duration_format,
    tokenize_duration_format,
)


class TestTokenizeDurationFormat:
    @pytest.mark.parametrize(
        "format_str,value,expected_fields,expected_groups",
        [
            ("h:mm", "1:30", ["hours", "minutes"], ("1", "30")),
            # literal `:` separators are escaped
            (
                "h:mm:ss",
                "1:23:45",
                ["hours", "minutes", "seconds"],
                ("1", "23", "45"),
            ),
            # space-separated tokens
            (
                "d h mm ss",
                "2 3 04 05",
                ["days", "hours", "minutes", "seconds"],
                ("2", "3", "04", "05"),
            ),
            # two-char tokens take precedence over one-char (hh, not h+h)
            ("hh:mm", "12:34", ["hours", "minutes"], ("12", "34")),
            # arbitrary literal chars (avoid d/h/m/s, which are token letters)
            ("d|h.", "2|5.", ["days", "hours"], ("2", "5")),
            # leading minus is optional
            ("h:mm", "-1:30", ["hours", "minutes"], ("1", "30")),
        ],
    )
    def test_tokenizes_valid_format(
        self, format_str, value, expected_fields, expected_groups
    ):
        result = tokenize_duration_format(format_str)

        assert result is not None
        regex, fields = result
        assert isinstance(regex, re.Pattern)
        assert fields == expected_fields
        match = regex.match(value)
        assert match is not None
        assert match.groups() == expected_groups

    @pytest.mark.parametrize(
        "format_str,value",
        [
            # anchored to start of string
            ("h:mm", "prefix 1:30"),
            # anchored to end of string
            ("h:mm", "1:30 trailing"),
            # literal mismatch (`|` in format, `/` in value)
            ("d|h.", "2/5."),
        ],
    )
    def test_value_does_not_match_format(self, format_str, value):
        regex, _ = tokenize_duration_format(format_str)

        assert regex.match(value) is None

    @pytest.mark.parametrize(
        "format_str",
        [
            "h:mm:h",  # h repeated
            "mm mm",  # mm repeated
            "h hh",  # h then hh — both map to "hours"
            "ss s",  # ss then s — both map to "seconds"
        ],
    )
    def test_repeated_tokens_are_invalid(self, format_str):
        assert tokenize_duration_format(format_str) is None

    @pytest.mark.parametrize(
        "format_str",
        [
            "",
            ":::",  # only literals, no token
            "   ",  # only whitespace, no token
        ],
    )
    def test_format_with_no_tokens_is_invalid(self, format_str):
        assert tokenize_duration_format(format_str) is None

    @pytest.mark.parametrize("value", [None, 1, 1.5, [], {}, object()])
    def test_non_string_input_returns_none(self, value):
        assert tokenize_duration_format(value) is None


class TestIsValidDurationFormat:
    @pytest.mark.parametrize(
        "format_str",
        [
            "h:mm",
            "h:mm:ss",
            "d h:mm:ss",
            "d h mm ss",
            "d",
            "hh:mm:ss",
        ],
    )
    def test_returns_true_for_valid_formats(self, format_str):
        assert is_valid_duration_format(format_str) is True

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "h:h",  # repeated token
            ":::",  # only literals
            None,
            123,
            [],
            {},
        ],
    )
    def test_returns_false_for_invalid_inputs(self, value):
        assert is_valid_duration_format(value) is False


class TestParseValueWithDurationFormat:
    @pytest.mark.parametrize(
        "value,format_str,expected",
        [
            ("1:30", "h:mm", timedelta(hours=1, minutes=30)),
            ("1:23:45", "h:mm:ss", timedelta(hours=1, minutes=23, seconds=45)),
            (
                "2 3:04:05",
                "d h:mm:ss",
                timedelta(days=2, hours=3, minutes=4, seconds=5),
            ),
            ("3 4", "d h", timedelta(days=3, hours=4)),
            ("-1:30", "h:mm", -timedelta(hours=1, minutes=30)),
            # surrounding whitespace is stripped
            ("  1:30  ", "h:mm", timedelta(hours=1, minutes=30)),
            ("0:00", "h:mm", timedelta(0)),
            # negative zero is still zero
            ("-0:00", "h:mm", timedelta(0)),
            # the generated regex uses \d+ for every field, so single-digit
            # values are accepted even where the format suggests two digits
            ("1:5", "h:mm", timedelta(hours=1, minutes=5)),
            # "hh:mm" tokenizes as hh + mm, not h + h + mm
            ("12:34", "hh:mm", timedelta(hours=12, minutes=34)),
            # 25 hours rolls over into 1d 1h in the resulting timedelta
            ("25:00", "h:mm", timedelta(days=1, hours=1)),
        ],
    )
    def test_parses_valid_values(self, value, format_str, expected):
        assert parse_value_with_duration_format(value, format_str) == expected

    @pytest.mark.parametrize(
        "value,format_str",
        [
            # value doesn't match the format's literal separator
            ("1.30", "h:mm"),
            # value has trailing garbage
            ("1:30 extra", "h:mm"),
            # non-string values
            (None, "h:mm"),
            (1, "h:mm"),
            (1.5, "h:mm"),
            ([], "h:mm"),
            ({}, "h:mm"),
            # invalid format strings
            ("1:30", None),
            ("1:30", ""),
            ("1:30", "h:h"),
            ("1:30", 123),
            ("1:30", ":::"),
        ],
    )
    def test_returns_none_for_invalid_input(self, value, format_str):
        assert parse_value_with_duration_format(value, format_str) is None
