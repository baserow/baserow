import typing
from functools import partial

import pytest

from tests.baserow.contrib.database.utils import (
    number_field_factory,
    setup_linked_table_and_lookup,
    text_field_factory,
)

if typing.TYPE_CHECKING:
    from baserow.test_utils.fixtures import Fixtures


def number_lookup_filter_proc(
    data_fixture: "Fixtures",
    filter_type_name: str,
    test_value: str,
    expected_rows: set[str],
    number_decimal_places: int = 5,
):
    """
    Common numeric lookup field test procedure. Each test operates on a fixed set of
    data, where each table row contains a lookup field with a predefined set of linked
    rows.
    """

    t = setup_linked_table_and_lookup(
        data_fixture,
        target_field_factory=partial(
            number_field_factory,
            number_decimal_places=number_decimal_places,
            number_negative=True,
        ),
        helper_fields_table=[partial(text_field_factory, name="row name")],
    )

    row_name_field = t.model.get_field_object_by_user_field_name("row name")["field"]
    link_row_name = t.link_row_field.db_column
    target_name = t.target_field.db_column
    lookup_name = t.lookup_field.db_column

    row_name = row_name_field.db_column

    row_values = [
        "1000.0001",  # 0
        "1000",
        "999.999",
        "123.45",
        "100",
        "50",  # 5
        "1.000001",  # will be rounded to 1.00000
        "1",
        "0.00007",
        "0.00004",
        "0.00001",  # 10
        "0.0000",
        "-0.1",  # mind that it will be rounded to 0.10000
        "-2",
        None,  # 14
        "999.99999999",
    ]
    dict_rows = [{target_name: rval} for rval in row_values]

    linked_rows = t.row_handler.create_rows(
        user=t.user, table=t.other_table, rows_values=dict_rows
    ).created_rows

    # helper to get linked rows by indexes
    def get_linked_rows(*indexes) -> list[int]:
        return [linked_rows[idx].id for idx in indexes]

    rows = [
        {row_name: "above 100", link_row_name: get_linked_rows(0, 1, 2, 3)},
        {row_name: "exact 100", link_row_name: get_linked_rows(4)},
        {row_name: "between 100 and 10", link_row_name: get_linked_rows(4, 5)},
        {
            row_name: "between 10 and 0",
            link_row_name: get_linked_rows(6, 7, 8, 9, 10, 11),
        },
        {row_name: "zero", link_row_name: get_linked_rows(11)},
        {row_name: "below zero", link_row_name: get_linked_rows(12, 13)},
        {row_name: "nineninenine", link_row_name: get_linked_rows(2)},
        {row_name: "onetwothree", link_row_name: get_linked_rows(3)},
        # no refs is a tricky one - we don't have is_empty for numeric field
        {row_name: "no refs", link_row_name: []},
        {row_name: "refs with empty", link_row_name: get_linked_rows(14)},
        {row_name: "100 with empty", link_row_name: get_linked_rows(4, 14)},
        {row_name: "ninieninenine rounded", link_row_name: get_linked_rows(15)},
    ]

    t.row_handler.create_rows(user=t.user, table=t.table, rows_values=rows)

    clean_query = t.view_handler.get_queryset(t.user, t.grid_view)

    t.view_handler.create_filter(
        t.user,
        t.grid_view,
        field=t.lookup_field,
        type_name=filter_type_name,
        value=test_value,
    )

    q = t.view_handler.get_queryset(t.user, t.grid_view)
    print(f"filter {filter_type_name} with value: {(test_value,)}")
    print(f"expected: {expected_rows}")
    print(f"filtered: {[getattr(item, row_name) for item in q]}")
    for item in q:
        print(f" {item.id} -> {getattr(item, row_name)}: {getattr(item, lookup_name)}")
    print()
    for item in clean_query:
        print(f" {item.id} -> {getattr(item, row_name)}: {getattr(item, lookup_name)}")
    assert len(q) == len(expected_rows)
    assert set([getattr(r, row_name) for r in q]) == set(expected_rows)


ALL_ROW_NAMES = [
    "above 100",
    "exact 100",
    "between 100 and 10",
    "between 10 and 0",
    "zero",
    "below zero",
    "nineninenine",
    "onetwothree",
    "no refs",
    "refs with empty",
    "100 with empty",
    "ninieninenine rounded",
]


@pytest.mark.parametrize(
    "filter_type_name,expected_rows",
    [
        ("has_empty_value", ["refs with empty", "100 with empty"]),
        (
            "has_not_empty_value",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "zero",
                "below zero",
                "nineninenine",
                "ninieninenine rounded",
                "onetwothree",
                "no refs",  # this is due to inversion of has_empty_value
                # "refs with empty", "100 with empty"
            ],
        ),
    ],
)
@pytest.mark.django_db
def test_number_lookup_field_has_empty_value_filter(
    data_fixture, filter_type_name, expected_rows
):
    return number_lookup_filter_proc(data_fixture, filter_type_name, "", expected_rows)


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("has_value_equal", "", ALL_ROW_NAMES),
        ("has_value_equal", "invalid", []),
        # too large, the same as invalid
        (
            "has_value_equal",
            "1" + ("0" * 40),
            [],
        ),
        (
            "has_value_equal",
            "100",
            ["exact 100", "between 100 and 10", "100 with empty"],
        ),
        # no rounding to 0.00001
        ("has_value_equal", "100.00000000001", []),
        ("has_not_value_equal", "", ALL_ROW_NAMES),
        ("has_not_value_equal", "invalid", ALL_ROW_NAMES),
        (
            "has_not_value_equal",
            "1" + ("0" * 40),
            ALL_ROW_NAMES,
        ),
        ("has_not_value_equal", "999", ALL_ROW_NAMES),
        ("has_not_value_equal", "1.00000001", ALL_ROW_NAMES),
        (
            "has_not_value_equal",
            "0.0",
            [o for o in ALL_ROW_NAMES if o not in {"zero", "between 10 and 0"}],
        ),
    ],
)
@pytest.mark.django_db
def test_number_lookup_field_has_value_equal_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    return number_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("has_value_contains", "", ALL_ROW_NAMES),
        ("has_value_contains", "invalid", []),
        (
            "has_value_contains",
            "1" + ("0" * 40),
            [],
        ),
        (
            "has_value_contains",
            "100",
            # includes '0.10000'
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "below zero",
                "100 with empty",
                "ninieninenine rounded",
            ],
        ),
        ("has_value_contains", "999", ["nineninenine", "above 100"]),
        ("has_value_contains", "99.999", ["nineninenine", "above 100"]),
        ("has_not_value_contains", "", ALL_ROW_NAMES),
        ("has_not_value_contains", "invalid", ALL_ROW_NAMES),
        (
            "has_not_value_contains",
            "1" + ("0" * 40),
            ALL_ROW_NAMES,
        ),
        (
            "has_not_value_contains",
            "999",
            [o for o in ALL_ROW_NAMES if o not in {"nineninenine", "above 100"}],
        ),
        ("has_not_value_contains", "1.00000001", ALL_ROW_NAMES),
        (
            "has_not_value_contains",
            "001",
            # between 10 and 0 contains 1.00001
            # above 100 contains 1000.0001
            [o for o in ALL_ROW_NAMES if o not in {"between 10 and 0", "above 100"}],
        ),
    ],
)
@pytest.mark.django_db
def test_number_lookup_field_has_value_contains_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    return number_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("has_value_higher", "", ALL_ROW_NAMES),
        ("has_value_higher", "invalid", []),
        (
            "has_value_higher",
            "1" + ("0" * 40),
            [],
        ),
        (
            "has_value_higher",
            "-1" + ("0" * 40),
            [o for o in ALL_ROW_NAMES if o not in {"no refs", "refs with empty"}],
        ),
        (
            "has_value_higher",
            "-0.0000001",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "zero",
                "nineninenine",
                "onetwothree",
                "100 with empty",
                "ninieninenine rounded",
            ],
        ),
        (
            "has_value_higher",
            "0.00000001",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "nineninenine",
                "onetwothree",
                "100 with empty",
                "ninieninenine rounded",
            ],
        ),
        (
            "has_value_higher",
            "999.998999",  # not rounded
            ["above 100", "nineninenine", "ninieninenine rounded"],
        ),
        ("has_value_higher", "999.999", ["above 100", "ninieninenine rounded"]),
    ],
)
@pytest.mark.django_db
def test_number_lookup_field_has_value_higher_than_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    return number_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("has_value_higher_or_equal", "", ALL_ROW_NAMES),
        ("has_value_higher_or_equal", "invalid", []),
        (
            "has_value_higher_or_equal",
            "1" + ("0" * 40),
            [],
        ),
        (
            "has_value_higher_or_equal",
            "-1" + ("0" * 40),
            [o for o in ALL_ROW_NAMES if o not in {"no refs", "refs with empty"}],
        ),
        (
            "has_value_higher_or_equal",
            "-0.0",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "zero",
                "nineninenine",
                "onetwothree",
                "100 with empty",
                "ninieninenine rounded",
            ],
        ),
        (
            "has_value_higher_or_equal",
            "999.999",
            ["above 100", "nineninenine", "ninieninenine rounded"],
        ),
        ("has_not_value_higher_or_equal", "", ALL_ROW_NAMES),
        (
            "has_not_value_higher_or_equal",
            "invalid",
            ALL_ROW_NAMES,
        ),  # reversed has_value_higher_or_equal
        (
            "has_not_value_higher_or_equal",
            "1" + ("0" * 40),
            ALL_ROW_NAMES,  # reversed has_value_higher_or_equal
        ),
        (
            "has_not_value_higher_or_equal",
            "-1" + ("0" * 40),
            [o for o in ALL_ROW_NAMES if o in {"no refs", "refs with empty"}],
        ),
        (
            "has_not_value_higher_or_equal",
            "-0.0",
            ["below zero", "no refs", "refs with empty"],
        ),
        (
            "has_not_value_higher_or_equal",
            "999.999",
            [
                o
                for o in ALL_ROW_NAMES
                if o not in {"above 100", "nineninenine", "ninieninenine rounded"}
            ],
        ),
    ],
)
@pytest.mark.django_db
def test_number_lookup_field_has_value_higher_equal_than_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    return number_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("has_value_lower_or_equal", "", ALL_ROW_NAMES),
        ("has_value_lower_or_equal", "invalid", []),
        (
            "has_value_lower_or_equal",
            "1" + ("0" * 40),
            [o for o in ALL_ROW_NAMES if o not in {"no refs", "refs with empty"}],
        ),
        (
            "has_value_lower_or_equal",
            "-1" + ("0" * 40),
            [],
        ),
        (
            "has_value_lower_or_equal",
            "-0.0",
            ["between 10 and 0", "zero", "below zero"],
        ),
        (
            "has_value_lower_or_equal",
            "999.999",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "zero",
                "below zero",
                "nineninenine",
                "onetwothree",
                "100 with empty",
            ],
        ),
        ("has_not_value_lower_or_equal", "", ALL_ROW_NAMES),
        (
            "has_not_value_lower_or_equal",
            "invalid",
            ALL_ROW_NAMES,
        ),  # reversed has_value_lower_or_equal
        (
            "has_not_value_lower_or_equal",
            "1" + ("0" * 40),
            ["no refs", "refs with empty"],  # reversed has_value_lower_or_equal
        ),
        (
            "has_not_value_lower_or_equal",
            "-1" + ("0" * 40),
            ALL_ROW_NAMES,
        ),
        (
            "has_not_value_lower_or_equal",
            "-0.0",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "nineninenine",
                "onetwothree",
                "no refs",
                "refs with empty",
                "100 with empty",
                "ninieninenine rounded",
            ],
        ),
        (
            "has_not_value_lower_or_equal",
            "999.999",
            ["no refs", "refs with empty", "ninieninenine rounded"],
        ),
    ],
)
@pytest.mark.django_db
def test_number_lookup_field_has_value_lower_equal_than_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    return number_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("has_value_lower", "", ALL_ROW_NAMES),
        ("has_value_lower", "invalid", []),
        (
            "has_value_lower",
            "1" + ("0" * 40),
            [o for o in ALL_ROW_NAMES if o not in {"no refs", "refs with empty"}],
        ),
        (
            "has_value_lower",
            "-1" + ("0" * 40),
            [],
        ),
        (
            "has_value_lower",
            "-0.0",
            ["below zero"],
        ),
        (
            "has_value_lower",
            "999.999",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "zero",
                "below zero",
                "onetwothree",
                "100 with empty",
            ],
        ),
        ("has_not_value_lower", "", ALL_ROW_NAMES),
        (
            "has_not_value_lower",
            "invalid",
            ALL_ROW_NAMES,
        ),  # reversed has_value_lower
        (
            "has_not_value_lower",
            "1" + ("0" * 40),
            ["no refs", "refs with empty"],  # reversed has_value_lower
        ),
        (
            "has_not_value_lower",
            "-1" + ("0" * 40),
            ALL_ROW_NAMES,
        ),
        (
            "has_not_value_lower",
            "-0.0",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "zero",
                "nineninenine",
                "onetwothree",
                "no refs",
                "refs with empty",
                "100 with empty",
                "ninieninenine rounded",
            ],
        ),
        (
            "has_not_value_lower",
            "999.999",
            ["nineninenine", "no refs", "refs with empty", "ninieninenine rounded"],
        ),
    ],
)
@pytest.mark.django_db
def test_number_lookup_field_has_value_lower_than_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    return number_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )
