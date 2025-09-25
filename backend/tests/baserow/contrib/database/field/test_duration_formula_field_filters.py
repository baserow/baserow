import typing
from datetime import timedelta
from functools import partial

import pytest

from baserow.contrib.database.fields.field_types import FormulaFieldType
from baserow.contrib.database.fields.utils.duration import D_H_M_S
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
    expected_test_value: None = None,
):
    """
    Common duration formula field test procedure. Each test operates on a fixed set of
    data, where each table row contains a formula field with a predefined value.

    Formula duration field will store calculated duration value 'as is', with
    raw value's precision regardless selected duration_format.

    The value will be truncated/rounded according to duration_format for display only.

    However, when filtering, a filter value will be truncated/rounded to the format,
    which may introduce inconsistencies in filtering.

    """

    formula_text = """field('target')"""
    t = setup_formula_field(
        data_fixture,
        formula_text=formula_text,
        formula_type="duration",
        # Data field is a source of values for formula field. In this case we want it
        # to be at seconds precision, so we can measure filter value rounding effects.
        data_field_factory=partial(duration_field_factory, duration_format=D_H_M_S),
        extra_fields=[partial(text_field_factory, name="text_field")],
        # Duration format for formula field causes filter value to be rounded
        # Note that field value will remain the same regardless format
        formula_extra_kwargs={"duration_format": duration_format},
    )

    assert t.formula_field.formula_type == "duration"
    t.view_handler.create_filter(
        t.user,
        t.grid_view,
        field=t.formula_field,
        type_name=filter_type_name,
        value=test_value,
    )
    src_field_name = t.data_source_field.db_column
    formula_field_name = t.formula_field.db_column
    refname = t.extra_fields["text_field"].db_column

    rows = [
        {src_field_name: 3600, refname: "1h"},
        {src_field_name: 2 * 3600, refname: "2h"},
        {src_field_name: 3 * 3600, refname: "3h"},
        {src_field_name: 4 * 3600, refname: "4h"},
        {src_field_name: 5 * 3600, refname: "5h"},
        {src_field_name: None, refname: "none"},
        {src_field_name: 3601, refname: "1h 1s"},
        {src_field_name: 3599, refname: "1h -1s"},
        {src_field_name: (3 * 3600) + 1, refname: "3h 1s"},
        {src_field_name: (3 * 3600) - 1, refname: "3h -1s"},
        {src_field_name: 59, refname: "59s"},
        {src_field_name: 61, refname: "1m 1s"},
    ]

    t.row_handler.create_rows(
        user=t.user,
        table=t.table,
        rows_values=rows,
        send_webhook_events=False,
        send_realtime_update=False,
    )

    q = t.view_handler.get_queryset(t.user, t.grid_view)
    actual_names = [getattr(r, refname) for r in q]
    actual_duration_values = [getattr(r, t.data_source_field.db_column) for r in q]
    actual_formula_values = [getattr(r, t.formula_field.db_column) for r in q]

    if expected_test_value is not None:
        mfield = FormulaFieldType().get_model_field(t.formula_field)
        assert t.formula_field.duration_format == duration_format
        assert (
            getattr(mfield.expression_field, "duration_format", None) == duration_format
        )
        actual_test_value = mfield.get_prep_value(test_value)
        assert actual_test_value == expected_test_value

    assert len(q) == len(expected_rows)
    assert set(actual_names) == set(expected_rows)


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows,duration_format,expected_test_value",
    [
        (
            "equal",
            str(3 * 3600),
            [
                "3h",
            ],
            "h:mm",
            timedelta(hours=3),
        ),
        ("equal", "3h", ["3h"], "h:mm", timedelta(hours=3)),
        ("equal", str(3 * 3600), ["3h"], "d h mm ss", timedelta(hours=3)),
        (
            "equal",
            str((3 * 3600) + 2),
            ["3h"],
            "h:mm",
            timedelta(hours=3),
        ),  # rounded to 3h
        ("equal", "3600s", ["1h"], "h:mm", timedelta(hours=1)),
        ("equal", "1:00", ["1h"], "h:mm", timedelta(hours=1)),  # 1h
        ("equal", "1:00", [], "h:mm:ss", timedelta(minutes=1)),  # 1m
        ("equal", "0:59", ["1h"], "d h", timedelta(hours=1)),  # 1h
        ("equal", "0:59", ["59s"], "d h mm ss", timedelta(seconds=59)),  # 59s
        ("equal", "3601s", ["1h"], "h:mm", timedelta(hours=1)),  # rounded to 1h
        (
            "equal",
            "3601s",
            ["1h 1s"],
            "h:mm:ss",
            timedelta(hours=1, seconds=1),
        ),  # exact 1h 1s
        ("equal", "1d 20h", [], "d h:mm", timedelta(days=1, hours=20)),
        ("equal", str(3 * 1800), [], "d h mm ss", timedelta(hours=1, minutes=30)),
        # 1.5h rounded to 2h
        ("equal", str(3 * 1800), ["2h"], "d h", timedelta(hours=2)),
        ("equal", "invalid", [], "d h mm ss", None),
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
            None,
        ),
        (
            "not_equal",
            str(3 * 3600),
            [
                "1h",
                "2h",
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
            "h:mm",
            timedelta(hours=3),
        ),
        (
            "not_equal",
            "3h 2s",
            # equals 3h due to rounding
            [
                "1h",
                "2h",
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
            timedelta(hours=3),
        ),
        (
            "not_equal",
            str(3 * 3600),
            [
                "1h",
                "2h",
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
            timedelta(hours=3),
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
            timedelta(hours=1, minutes=30),
        ),
        (
            "not_equal",
            str(3 * 1800),  # 2h due to rounding
            [
                "1h",
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
            timedelta(hours=2),
        ),
        (
            "not_equal",
            "1:00",  # parsed as 1m
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
            timedelta(minutes=1),
        ),
        (
            "not_equal",
            "1:00",  # parsed as 1h
            [
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
            "h:mm",
            timedelta(hours=1),
        ),
        (
            "not_equal",
            "invalid",
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
            None,
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
            None,
        ),
    ],
)
@pytest.mark.django_db
def test_duration_formula_equal_value_filter(
    data_fixture,
    filter_type_name,
    test_value,
    expected_rows,
    duration_format,
    expected_test_value,
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
        data_fixture,
        duration_format,
        filter_type_name,
        test_value,
        expected_rows,
        expected_test_value,
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows,duration_format,expected_test_value",
    [
        (
            "higher_than",
            str(3 * 1800),
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h mm ss",
            timedelta(hours=1, minutes=30),
        ),
        (
            "higher_than",
            str(3 * 1800),
            ["3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h",
            timedelta(hours=2),
        ),
        (
            "higher_than",
            str(3600),
            ["2h", "3h", "4h", "5h", "1h 1s", "3h 1s", "3h -1s"],
            "d h mm",
            timedelta(hours=1),
        ),
        (
            "higher_than",
            str((2 * 3600) - 2),
            [
                "3h",
                "4h",
                "5h",
                "3h 1s",
                "3h -1s",
            ],
            "d h mm",
            timedelta(hours=2),
        ),
        (
            "higher_than",
            "1:59:59",
            ["3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h",
            timedelta(hours=2),
        ),
        (
            "higher_than",
            "1:59:59",
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "h:mm:ss",
            timedelta(hours=1, minutes=59, seconds=59),
        ),
        (
            "higher_than",
            str(3600),
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s", "1h 1s"],
            "d h mm ss",
            timedelta(hours=1),
        ),
        (
            "higher_than",
            str(3600),
            ["2h", "3h", "4h", "5h", "1h 1s", "3h 1s", "3h -1s"],
            "d h",
            timedelta(hours=1),
        ),
        (
            "higher_than",
            "1:01",
            ["2h", "3h", "4h", "5h", "1h 1s", "3h 1s", "3h -1s"],
            "d h",
            timedelta(hours=1),
        ),
        (
            "higher_than",
            "1:01",
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "h:mm",
            timedelta(hours=1, minutes=1),
        ),
        # value parsed to 1m
        (
            "higher_than",
            "1:01",
            ["1h", "2h", "3h", "4h", "5h", "1h 1s", "1h -1s", "3h 1s", "3h -1s"],
            "h:mm:ss",
            timedelta(minutes=1, seconds=1),
        ),
        (
            "higher_than",
            "1:00",
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
                "1m 1s",
            ],
            "h:mm:ss",
            timedelta(minutes=1),
        ),
        (
            "higher_than",
            str(3 * 3600),
            ["4h", "5h", "3h 1s"],
            "d h",
            timedelta(hours=3),
        ),
        ("higher_than", str((3 * 3600) + 1801), ["5h"], "d h", timedelta(hours=4)),
        (
            "higher_than",
            str((3 * 3600) + 1801),
            ["4h", "5h"],
            "h:mm:ss",
            timedelta(hours=3, minutes=30, seconds=1),
        ),
        ("higher_than", "invalid", [], "d h", None),
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
            None,
        ),
        (
            "higher_than_or_equal",
            str(3 * 1800),
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h",
            timedelta(hours=2),
        ),
        (
            "higher_than_or_equal",
            str(3 * 1800),
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "h:mm:ss",
            timedelta(hours=1, minutes=30),
        ),
        (
            "higher_than_or_equal",
            str((3 * 3600) + 1),
            ["3h", "4h", "5h", "3h 1s"],
            "d h",
            timedelta(hours=3),
        ),
        (
            "higher_than_or_equal",
            str((3 * 3600) + 1),
            ["4h", "5h", "3h 1s"],
            "h:mm:ss",
            timedelta(hours=3, seconds=1),
        ),
        (
            "higher_than_or_equal",
            "1:59:59",  # 1h59m59s
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "h:mm:ss",
            timedelta(hours=1, minutes=59, seconds=59),
        ),
        (
            "higher_than_or_equal",
            "1:59:59",  # 1h59m59s
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h",
            timedelta(hours=2),
        ),
        (
            "higher_than_or_equal",
            "1:59",  # parsed as 1m59s
            ["1h", "2h", "3h", "4h", "5h", "1h 1s", "1h -1s", "3h 1s", "3h -1s"],
            "h:mm:ss",
            timedelta(minutes=1, seconds=59),
        ),
        (
            "higher_than_or_equal",
            "1:59",  # parsed as 1h59m, rounded to 2h
            ["2h", "3h", "4h", "5h", "3h 1s", "3h -1s"],
            "d h",
            timedelta(hours=2),
        ),
        ("higher_than_or_equal", "invalid", [], "d h mm ss", None),
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
            None,
        ),
    ],
)
@pytest.mark.django_db
def test_duration_formula_higher_than_equal_value_filter(
    data_fixture,
    filter_type_name,
    test_value,
    expected_rows,
    duration_format,
    expected_test_value,
):
    duration_formula_filter_proc(
        data_fixture,
        duration_format,
        filter_type_name,
        test_value,
        expected_rows,
        expected_test_value,
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows,duration_format,expected_test_value",
    [
        # duration rounding will bump filter value from 1.5h to 2h for `d h` format
        (
            "lower_than",
            str(3 * 1800),
            ["1h", "1h -1s", "1h 1s", "59s", "1m 1s"],
            "d h",
            timedelta(hours=2),
        ),
        # filter value is rounded to 1h
        (
            "lower_than",
            str(3599),
            ["1h -1s", "59s", "1m 1s"],
            "d h",
            timedelta(hours=1),
        ),
        (
            "lower_than",
            str(3 * 3600),
            ["1h", "2h", "1h 1s", "1h -1s", "3h -1s", "59s", "1m 1s"],
            "d h mm ss",
            timedelta(hours=3),
        ),
        ("lower_than", "invalid", [], "d h mm ss", None),
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
            None,
        ),
        (
            "lower_than_or_equal",
            "1:01",  # parsed as 1m1!
            ["59s", "1m 1s"],
            "h:mm:ss",
            timedelta(seconds=61),
        ),
        (
            "lower_than_or_equal",
            "1:01",  # parsed as 1h1m, but truncated to 1h
            ["1h", "1h -1s", "59s", "1m 1s"],
            "d h",
            timedelta(hours=1),
        ),
        (
            "lower_than_or_equal",
            str(3 * 3600),
            ["1h", "2h", "3h", "1h 1s", "1h -1s", "3h -1s", "59s", "1m 1s"],
            "d h",
            timedelta(hours=3),
        ),
        (
            "lower_than_or_equal",
            str((3 * 3600) - 1801),
            ["1h", "2h", "1h -1s", "1h 1s", "59s", "1m 1s"],
            "d h",
            timedelta(hours=2),
        ),
        (
            "lower_than_or_equal",
            "1:01",  # parsed as 1m1s
            ["1m 1s", "59s"],
            "h:mm:ss",
            timedelta(seconds=61),
        ),
        (
            "lower_than_or_equal",
            "0:01",  # parsed as 1m!
            ["59s"],
            "h:mm",
            timedelta(minutes=1),
        ),
        (
            "lower_than_or_equal",
            "0:59",  # parsed 59m, rounded to 1h
            ["1h", "1h -1s", "59s", "1m 1s"],
            "d h",
            timedelta(hours=1),
        ),
        ("lower_than_or_equal", "invalid", [], "d h mm ss", None),
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
            None,
        ),
    ],
)
@pytest.mark.django_db
def test_duration_formula_lower_than_equal_value_filter(
    data_fixture,
    filter_type_name,
    test_value,
    expected_rows,
    duration_format,
    expected_test_value,
):
    duration_formula_filter_proc(
        data_fixture,
        duration_format,
        filter_type_name,
        test_value,
        expected_rows,
        expected_test_value,
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
