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
        # helper_fields_other_table=[partial(text_field_factory, name='row_name')],
        helper_fields_table=[partial(text_field_factory, name="row name")],
    )

    row_name_field = t.model.get_field_object_by_user_field_name("row name")["field"]
    link_row_name = t.link_row_field.db_column
    target_name = t.target_field.db_column
    lookup_name = t.lookup_field.db_column

    row_name = row_name_field.db_column
    # nrow_lookup = data_fixture.create_lookup_field(
    #     table=t.table,
    #     through_field=t.link_row_field,
    #     target_field=other_name_field,
    #     through_field_name=t.link_row_field.name,
    #     target_field_name=target_field.name,
    #     setup_dependencies=False,
    # )

    row_values = [
        "1000.0001",  # 0
        "1000",
        "999.999999",
        "123.45",
        "100",
        "50",  # 5
        "1.000001",
        "1",
        "0.00007",
        "0.00004",
        "0.00001",  # 10
        "0.0000",
        "-0.1",
        "-2",
        None,  # 14
    ]
    dict_rows = [{target_name: rval} for rval in row_values]

    linked_rows = t.row_handler.create_rows(
        user=t.user, table=t.other_table, rows_values=dict_rows
    )

    # helper to get linked rows by indexes
    def l(*indexes) -> list[int]:
        return [linked_rows[idx].id for idx in indexes]

    rows = [
        {row_name: "above 100", link_row_name: l(0, 1, 2, 3)},
        {row_name: "exact 100", link_row_name: l(4)},
        {row_name: "between 100 and 10", link_row_name: l(4, 5)},
        {row_name: "between 10 and 0", link_row_name: l(6, 7, 8, 9, 10, 11)},
        {row_name: "zero", link_row_name: l(11)},
        {row_name: "below zero", link_row_name: l(12, 13)},
        {row_name: "nineninenine", link_row_name: l(2)},
        {row_name: "onetwothree", link_row_name: l(3)},
        # no_refs is a tricky one - we don't have is_empty for numeric field
        {row_name: "no_refs", link_row_name: []},
        {row_name: "refs_with_empty", link_row_name: l(14)},
        {row_name: "100_with_empty", link_row_name: l(4, 14)},
    ]

    t.row_handler.create_rows(user=t.user, table=t.table, rows_values=rows)

    q = t.view_handler.get_queryset(t.grid_view)

    t.view_handler.create_filter(
        t.user,
        t.grid_view,
        field=t.lookup_field,
        type_name=filter_type_name,
        value=test_value,
    )

    q = t.view_handler.get_queryset(t.grid_view)
    print(f'filter {filter_type_name} with value: {(test_value,)}')
    print(f"expected: {expected_rows}")
    print(f"filtered: {[getattr(item, row_name) for item in q]}")
    for item in q:
        print(f" {item.id} -> {getattr(item, row_name)}: {getattr(item, lookup_name)}")
    assert len(q) == len(expected_rows)
    assert set([getattr(r, row_name) for r in q]) == set(expected_rows)

ALL_ROW_NAMES = ['above 100', 'exact 100', 'between 100 and 10', 'between 10 and 0', 'zero', 'below zero', 'nineninenine', 'onetwothree',
                     'no_refs', 'refs_with_empty', '100_with_empty']
# filters to test:
#  has empty value
#  doesn't have empty value
#  has value equal
#  doesn't have value equal
#  has value contains
#  doesn't have value contains
#  has value higher than
#  doesn't have value higher than
#  has value higher than or equal
#  doesn't have value higher than or equal
#  has value lower than
#  doesn't have value lower than
#  has value lower than or equal
#  doesn't have value lower than or equal


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows,number_decimal_places",
    [
        ("has_empty_value", "", ["refs_with_empty", "100_with_empty"]),
        (
            "has_not_empty_value",
            "",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "zero",
                "below zero",
                "nineninenine",
                "onetwothree",
                "no_refs",  # this is due to inversion of has_empty_value
                #"refs_with_empty", "100_with_empty"
            ],
        ),
    ],
)
@pytest.mark.django_db
def test_has_empty_value(data_fixture, filter_type_name, test_value, expected_rows):
    return number_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("has_value_equal", "", ALL_ROW_NAMES),
        ("has_value_equal", "invalid", []),
        ("has_value_equal", "100000000000000000000000000000000000000000000000000000000000000000000000",[]),
        (
            "has_value_equal",
            "",
            [
                "above 100",
                "exact 100",
                "between 100 and 10",
                "between 10 and 0",
                "zero",
                "below zero",
                "nineninenine",
                "onetwothree",
                "no_refs",  # this is due to inversion of has_empty_value
            ],
        ),
    ],
)
@pytest.mark.django_db
def test_has_empty_value(data_fixture, filter_type_name, test_value, expected_rows):
    return number_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )
