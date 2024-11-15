import typing
from datetime import timedelta

import pytest

from tests.baserow.contrib.database.utils import (
    duration_field_factory,
    setup_formula_field,
)

if typing.TYPE_CHECKING:
    from baserow.test_utils.fixtures import Fixtures


def duration_formula_filter_proc(
    data_fixture: "Fixtures",
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
        data_field_factory=duration_field_factory,
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

    rows = [
        {fname: 1 * 3600},
        {fname: 2 * 3600},
        {fname: 3 * 3600},
        {fname: 4 * 3600},
        {fname: 5 * 3600},
        {fname: None},
    ]

    t.row_handler.create_rows(
        user=t.user,
        table=t.table,
        rows_values=rows,
        send_webhook_events=False,
        send_realtime_update=False,
    )

    q = t.view_handler.get_queryset(t.grid_view)
    print("expected", expected_rows)
    print(
        "received",
        [(getattr(r, fname), getattr(r, t.formula_field.db_column)) for r in q],
    )
    assert len(q) == len(expected_rows)
    assert set([getattr(r, fname) for r in q]) == set(
        [
            timedelta(seconds=tdelta) if tdelta is not None else None
            for tdelta in expected_rows
        ]
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("equal", 3 * 3600, [3 * 3600]),
        ("equal", 3 * 1800, []),
        ("not_equal", 3 * 3600, [1 * 3600, 2 * 3600, 4 * 3600, 5 * 3600, None]),
        (
            "not_equal",
            3 * 1800,
            [1 * 3600, 2 * 3600, 3 * 3600, 4 * 3600, 5 * 3600, None],
        ),
    ],
)
@pytest.mark.django_db
def test_duration_formula_equal_value_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    duration_formula_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("higher_than", 3 * 1800, [2 * 3600, 3 * 3600, 4 * 3600, 5 * 3600]),
        ("higher_than", 3 * 3600, [4 * 3600, 5 * 3600]),
        ("higher_than_or_equal", 3 * 1800, [2 * 3600, 3 * 3600, 4 * 3600, 5 * 3600]),
        ("higher_than_or_equal", 3 * 3600, [3 * 3600, 4 * 3600, 5 * 3600]),
    ],
)
@pytest.mark.django_db
def test_duration_formula_higher_than_equal_value_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    duration_formula_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "lower_than",
            3 * 1800,
            [
                1 * 3600,
            ],
        ),
        ("lower_than", 3 * 3600, [1 * 3600, 2 * 3600]),
        (
            "lower_than_or_equal",
            3 * 1800,
            [
                1 * 3600,
            ],
        ),
        ("lower_than_or_equal", 2 * 3600, [1 * 3600, 2 * 3600]),
    ],
)
@pytest.mark.django_db
def test_duration_formula_lower_than_equal_value_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    duration_formula_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("empty", "", [None]),
        ("not_empty", "", [1 * 3600, 2 * 3600, 3 * 3600, 4 * 3600, 5 * 3600]),
    ],
)
@pytest.mark.django_db
def test_duration_formula_empty_value_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    duration_formula_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )
