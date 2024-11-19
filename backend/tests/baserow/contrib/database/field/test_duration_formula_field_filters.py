import typing
from functools import partial

import pytest

from tests.baserow.contrib.database.utils import (
    duration_field_factory,
    setup_formula_field,
    text_field_factory,
)

if typing.TYPE_CHECKING:
    from baserow.test_utils.fixtures import Fixtures


def duration_formula_filter_proc(
    data_fixture: "Fixtures",
    duration_format: str,
    filter_type_name: str,
    test_value: str,
    expected_rows: list[int],
):
    """
    Common duration formula field test procedure. Each test operates on a fixed set of
    data, where each table row contains a formula field with a predefined value.
    """

    formula_text = """field('target')"""
    t = setup_formula_field(
        data_fixture,
        formula_text=formula_text,
        formula_type="duration",
        data_field_factory=partial(
            duration_field_factory, duration_format=duration_format
        ),
        extra_fields=[partial(text_field_factory, name="text_field")],
    )

    assert t.formula_field.formula_type == "duration"
    t.view_handler.create_filter(
        t.user,
        t.grid_view,
        field=t.formula_field,
        type_name=filter_type_name,
        value=test_value,
    )
    fname = t.data_source_field.db_column
    refname = t.extra_fields["text_field"].db_column

    rows = [
        {fname: 3600, refname: "1h"},
        {fname: 2 * 3600, refname: "2h"},
        {fname: 3 * 3600, refname: "3h"},
        {fname: 4 * 3600, refname: "4h"},
        {fname: 5 * 3600, refname: "5h"},
        {fname: None, refname: "none"},
        {fname: 3601, refname: "1h 1s"},
        {fname: 3599, refname: "1h -1s"},
        {fname: (3 * 3600) + 1, refname: "3h 1s"},
        {fname: (3 * 3600) - 1, refname: "3h -1s"},
        {fname: 59, refname: "59s"},
        {fname: 61, refname: "1m 1s"},
    ]

    t.row_handler.create_rows(
        user=t.user,
        table=t.table,
        rows_values=rows,
        send_webhook_events=False,
        send_realtime_update=False,
    )

    q = t.view_handler.get_queryset(t.grid_view)
    actual_names = [getattr(r, refname) for r in q]
    print("expected", expected_rows)
    print("actual", actual_names)
    assert len(q) == len(expected_rows)
    assert set(actual_names) == set(expected_rows)


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows,duration_format",
    [
        ("equal", str(3 * 3600), ["3h", "3h 1s", "3h -1s"], "h:mm"),
        ("equal", str((3 * 3600) + 2), ["3h", "3h 1s", "3h -1s"], "h:mm"),
        ("equal", "3600s", ["1h", "1h 1s", "1h -1s"], "h:mm"),
        ("equal", "1:00", ["1h", "1h 1s", "1h -1s"], "h:mm"),  # 1h
        ("equal", "1:00", ["1h"], "d h mm ss"),  # 1h
        ("equal", "3602s", ["1h", "1h 1s", "1h -1s"], "h:mm"),
        ("equal", "3h", ["3h", "3h 1s", "3h -1s"], "h:mm"),
        ("equal", "1d 20h", [], "d h:mm"),
        ("equal", str(3 * 3600), ["3h"], "d h mm ss"),  # exact
        ("equal", str(3 * 1800), [], "d h mm ss"),
        ("equal", "invalid", [], "d h mm ss"),
        (
            "equal",
            "",
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h mm ss",
        ),
        (
            "not_equal",
            str(3 * 3600),
            ["1h", "2h", "4h", "5h", "none", "1h 1s", "1h -1s", "59s", "1m 1s"],
            "h:mm",
        ),
        (
            "not_equal",
            "3h 2s",
            ["1h", "2h", "4h", "5h", "none", "1h 1s", "1h -1s", "59s", "1m 1s"],
            "d h",
        ),
        (
            "not_equal",
            str(3 * 3600),
            ["1h", "2h", "4h", "5h", "none", "1h 1s", "1h -1s", "59s", "1m 1s"],
            "d h",
        ),
        (
            "not_equal",
            str(3 * 1800),
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h mm ss",
        ),
        (
            "not_equal",
            "1:00",  # parsed as 1h
            [
                # "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h mm ss",
        ),
        (
            "not_equal",
            "1:00",
            [
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "h:mm",
        ),
        (
            "not_equal",
            "invalid",
            # this is a negation of 'equal' with 'invalid' value,
            # so it will yield all values
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h mm ss",
        ),
        (
            "not_equal",
            "",
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h mm ss",
        ),
    ],
)
@pytest.mark.django_db
def test_duration_formula_equal_value_filter(
    data_fixture, filter_type_name, test_value, expected_rows, duration_format
):
    """
    Test equal/not equal filters. Note that due to implementation,
     filter value will be rounded accordingly to duration format set for the field.

    :param data_fixture:
    :param filter_type_name:
    :param test_value:
    :param expected_rows:
    :param duration_format:
    :return:
    """

    duration_formula_filter_proc(
        data_fixture, duration_format, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows,duration_format",
    [
        (
            "higher_than",
            str(3 * 1800),
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h mm ss",
        ),
        (
            "higher_than",
            str(3600),
            [
                "2h",
                "3h",
                "4h",
                "5h",
                "3h 1s",
                "3h -1s",
            ],  # 1h 1s will be truncated to 1h, so won't be in the set
            "d h mm",
        ),
        (
            "higher_than",
            str((2 * 3600) - 2),  # this will be rounded up to 2h precisely
            [
                "3h",
                "4h",
                "5h",
                "3h 1s",
                "3h -1s",
            ],  # 1h 1s will be truncated to 1h, so won't be in the set
            "d h mm",
        ),
        (
            "higher_than",
            "1h 59:59",
            [],  # treated as invalid as it's not decimal-compatible
            "h:mm:ss",
        ),
        (
            "higher_than",
            str(3600),
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s", "1h 1s"],
            "d h mm ss",
        ),
        ("higher_than", str(3600), ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"], "d h"),
        ("higher_than", "1:00", ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"], "d h"),
        ("higher_than", "1:00", ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"], "h:mm"),
        (
            "higher_than",
            "1:00",
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s", "1h 1s"],
            "h:mm:ss",
        ),
        ("higher_than", str(3 * 3600), ["4h", "5h"], "d h"),
        ("higher_than", str((3 * 3600) + 1801), ["4h", "5h"], "d h"),
        ("higher_than", "invalid", [], "d h"),
        (
            "higher_than",
            "",
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h",
        ),
        (
            "higher_than_or_equal",
            str(3 * 1800),
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h",
        ),
        (
            "higher_than_or_equal",
            str(3 * 3600),
            ["3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h",
        ),
        (
            "higher_than_or_equal",
            "1:59:59",
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "h:mm:ss",
        ),
        (
            "higher_than_or_equal",
            "1:59",  # parsed as 1h59m
            [
                "2h",
                "3h",
                "4h",
                "5h",
                "3h 1s",
                "3h -1s",
            ],
            "h:mm:ss",
        ),
        (
            "higher_than_or_equal",
            "1:59",  # parsed as 1h59m
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h",
        ),
        ("higher_than_or_equal", "invalid", [], "d h mm ss"),
        (
            "higher_than_or_equal",
            "",
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h mm ss",
        ),
    ],
)
@pytest.mark.django_db
def test_duration_formula_higher_than_equal_value_filter(
    data_fixture, filter_type_name, test_value, expected_rows, duration_format
):
    duration_formula_filter_proc(
        data_fixture, duration_format, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows,duration_format",
    [
        ("lower_than", str(3 * 1800), ["1h", "1h -1s", "1h 1s", "59s", "1m 1s"], "d h"),
        # filter value is rounded to 1h, row values also
        ("lower_than", str(3599), ["59s", "1m 1s"], "d h"),
        (
            "lower_than",
            str(3 * 3600),
            ["1h", "2h", "1h 1s", "1h -1s", "3h -1s", "59s", "1m 1s"],
            "d h mm ss",
        ),
        ("lower_than", "invalid", [], "d h mm ss"),
        (
            "lower_than",
            "",
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h mm ss",
        ),
        (
            "lower_than_or_equal",
            "1:01",  # parsed as 1h1s!
            ["1h", "1h 1s", "1h -1s", "59s", "1m 1s"],
            "h:mm:ss",
        ),
        (
            "lower_than_or_equal",
            "1:01",  # parsed as 1h1m!
            ["1h", "1h 1s", "1h -1s", "59s", "1m 1s"],
            "d h",
        ),
        (
            "lower_than_or_equal",
            str(3 * 3600),
            ["1h", "2h", "3h", "1h 1s", "1h -1s", "3h 1s", "3h -1s", "59s", "1m 1s"],
            "d h",
        ),
        (
            "lower_than_or_equal",
            str((3 * 3600) - 1801),
            ["1h", "2h", "1h -1s", "1h 1s", "59s", "1m 1s"],
            "d h",
        ),
        (
            "lower_than_or_equal",
            "0:59",  # parsed as 59s!
            ["1m 1s", "59s"],
            "h:mm:ss",
        ),
        (
            "lower_than_or_equal",
            "0:59",  # parsed as 59s!
            ["1m 1s", "59s"],
            "d h",
        ),
        ("lower_than_or_equal", "invalid", [], "d h mm ss"),
        (
            "lower_than_or_equal",
            "",
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "none",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h mm ss",
        ),
    ],
)
@pytest.mark.django_db
def test_duration_formula_lower_than_equal_value_filter(
    data_fixture, filter_type_name, test_value, expected_rows, duration_format
):
    duration_formula_filter_proc(
        data_fixture, duration_format, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows,duration_format",
    [
        ("empty", "", ["none"], "d h"),
        (
            "not_empty",
            "",
            [
                "1h",
                "2h",
                "3h",
                "4h",
                "5h",
                "1h 1s",
                "1h -1s",
                "3h 1s",
                "3h -1s",
                "59s",
                "1m 1s",
            ],
            "d h",
        ),
    ],
)
@pytest.mark.django_db
def test_duration_formula_empty_value_filter(
    data_fixture, filter_type_name, test_value, expected_rows, duration_format
):
    duration_formula_filter_proc(
        data_fixture, duration_format, filter_type_name, test_value, expected_rows
    )
