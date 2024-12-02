import typing
from enum import Enum

import pytest

from tests.baserow.contrib.database.utils import (
    boolean_field_factory,
    email_field_factory,
    long_text_field_factory,
    phone_number_field_factory,
    setup_linked_table_and_lookup,
    single_select_field_factory,
    single_select_field_value_factory,
    text_field_factory,
    text_field_value_factory,
    url_field_factory,
    uuid_field_factory,
)

if typing.TYPE_CHECKING:
    from baserow.test_utils.fixtures import Fixtures


class BooleanLookupRow(int, Enum):
    """
    Helper enum for boolean lookup field filters tests.

    Test data is fixed, so we want to point expected rows indexes. Using this enum
    allows to do it in more descriptive way. Each member is an index of a row with
    a specific data for the test.
    """

    MIXED = 0
    ALL_FALSE = 1
    ALL_TRUE = 2
    NO_VALUES = 3


def boolean_lookup_filter_proc(
    data_fixture: "Fixtures",
    filter_type_name: str,
    test_value: str,
    expected_rows: list[BooleanLookupRow],
):
    """
    Common boolean lookup field test procedure. Each test operates on a fixed set of
    data, where each table row contains a lookup field with a predefined set of linked
    rows.
    """

    test_setup = setup_linked_table_and_lookup(data_fixture, boolean_field_factory)

    dict_rows = [{test_setup.target_field.db_column: idx % 2} for idx in range(0, 10)]

    linked_rows = test_setup.row_handler.create_rows(
        user=test_setup.user, table=test_setup.other_table, rows_values=dict_rows
    )
    rows = [
        # mixed
        {
            test_setup.link_row_field.db_column: [
                linked_rows[0].id,
                linked_rows[1].id,
                linked_rows[2].id,
                linked_rows[3].id,
                linked_rows[4].id,
            ]
        },
        # all false
        {
            test_setup.link_row_field.db_column: [
                linked_rows[0].id,
                linked_rows[2].id,
                linked_rows[4].id,
            ]
        },
        # all true
        {
            test_setup.link_row_field.db_column: [
                linked_rows[1].id,
                linked_rows[3].id,
                linked_rows[5].id,
                linked_rows[7].id,
            ]
        },
        # all none
        {test_setup.link_row_field.db_column: []},
    ]
    r_mixed, r_false, r_true, r_none = test_setup.row_handler.create_rows(
        user=test_setup.user, table=test_setup.table, rows_values=rows
    )
    rows = [r_mixed, r_false, r_true, r_none]
    selected = [rows[idx] for idx in expected_rows]

    test_setup.view_handler.create_filter(
        test_setup.user,
        test_setup.grid_view,
        field=test_setup.lookup_field,
        type_name=filter_type_name,
        value=test_value,
    )
    q = test_setup.view_handler.get_queryset(test_setup.grid_view)
    assert len(q) == len(selected)
    assert set([r.id for r in q]) == set([r.id for r in selected])


@pytest.mark.parametrize(
    "target_field_factory,target_field_value_factory",
    [
        (text_field_factory, text_field_value_factory),
        (long_text_field_factory, text_field_value_factory),
        (email_field_factory, text_field_value_factory),
        (phone_number_field_factory, text_field_value_factory),
        (url_field_factory, text_field_value_factory),
        (single_select_field_factory, single_select_field_value_factory),
    ],
)
@pytest.mark.django_db
def test_has_empty_value_filter_text_field_types(
    data_fixture, target_field_factory, target_field_value_factory
):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    row_A_value = target_field_value_factory(data_fixture, test_setup.target_field, "A")
    row_B_value = target_field_value_factory(data_fixture, test_setup.target_field, "B")
    row_empty_value = target_field_value_factory(data_fixture, test_setup.target_field)

    other_row_A = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": row_A_value}
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": row_B_value}
    )
    other_row_empty = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": row_empty_value}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [
                other_row_A.id,
                other_row_empty.id,
            ]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_B.id]},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_empty_value",
        value="",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_1.id in ids


@pytest.mark.django_db
def test_has_empty_value_filter_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)

    other_row_1 = test_setup.other_table_model.objects.create()
    other_row_2 = test_setup.other_table_model.objects.create()
    other_row_3 = test_setup.other_table_model.objects.create()
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [
                other_row_1.id,
                other_row_3.id,
            ]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_2.id]},
    )
    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_empty_value",
        value="",
    )

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0


@pytest.mark.parametrize(
    "target_field_factory,target_field_value_factory",
    [
        (text_field_factory, text_field_value_factory),
        (long_text_field_factory, text_field_value_factory),
        (email_field_factory, text_field_value_factory),
        (phone_number_field_factory, text_field_value_factory),
        (url_field_factory, text_field_value_factory),
        (single_select_field_factory, single_select_field_value_factory),
    ],
)
@pytest.mark.django_db
def test_has_not_empty_value_filter_text_field_types(
    data_fixture, target_field_factory, target_field_value_factory
):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    row_A_value = target_field_value_factory(data_fixture, test_setup.target_field, "A")
    row_B_value = target_field_value_factory(data_fixture, test_setup.target_field, "B")
    row_empty_value = target_field_value_factory(data_fixture, test_setup.target_field)

    other_row_A = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": row_A_value}
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": row_B_value}
    )
    other_row_empty = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": row_empty_value}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [
                other_row_A.id,
                other_row_empty.id,
            ]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_B.id]},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_empty_value",
        value="",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids


@pytest.mark.django_db
def test_has_not_empty_value_filter_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)

    other_row_1 = test_setup.other_table_model.objects.create()
    other_row_2 = test_setup.other_table_model.objects.create()
    other_row_3 = test_setup.other_table_model.objects.create()
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [
                other_row_1.id,
                other_row_3.id,
            ]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_2.id]},
    )
    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_empty_value",
        value="",
    )

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.parametrize(
    "target_field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        url_field_factory,
    ],
)
@pytest.mark.django_db
def test_has_value_equal_filter_text_field_types(data_fixture, target_field_factory):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    other_row_A = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "A"}
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "B"}
    )
    other_row_C = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "C"}
    )
    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "a"}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_A.id, other_row_B.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_B.id, other_row_a.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_equal",
        value="A",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = "a"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "C"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.django_db
def test_has_value_equal_filter_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)

    other_row_A = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "188e1076-6c88-4bcc-893a-d0903c4169db"
        }
    )
    other_row_C = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "720a3d55-6aac-4d86-a0ce-6049001a4f64"
        }
    )
    other_row_a = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_A.id, other_row_B.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_B.id, other_row_a.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_equal",
        value="77545ce8-cbc0-4748-ba17-668b099a1ef8",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = "77545CE8-cbc0-4748-ba17-668b099a1ef8"  # upper case
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "720a3d55-6aac-4d86-a0ce-6049001a4f64"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.parametrize(
    "target_field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        url_field_factory,
    ],
)
@pytest.mark.django_db
def test_has_not_value_equal_filter_text_field_types(
    data_fixture, target_field_factory
):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    other_row_A = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "A"}
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "B"}
    )
    other_row_C = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "C"}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_A.id, other_row_B.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_B.id]},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_equal",
        value="A",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "a"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = "C"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.django_db
def test_has_not_value_equal_filter_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)

    other_row_A = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "188e1076-6c88-4bcc-893a-d0903c4169db"
        }
    )
    other_row_C = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "720a3d55-6aac-4d86-a0ce-6049001a4f64"
        }
    )
    other_row_a = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_A.id, other_row_B.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_B.id, other_row_a.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_equal",
        value="77545ce8-cbc0-4748-ba17-668b099a1ef8",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "77545CE8-cbc0-4748-ba17-668b099a1ef8"  # upper case
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = "720a3d55-6aac-4d86-a0ce-6049001a4f64"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.parametrize(
    "target_field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        url_field_factory,
    ],
)
@pytest.mark.django_db
def test_has_value_contains_filter_text_field_types(data_fixture, target_field_factory):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    other_row_John_Smith = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "John Smith"}
    )
    other_row_Anna_Smith = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "Anna Smith"}
    )
    other_row_John_Wick = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "John Wick"}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_John_Smith.id]},
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_Anna_Smith.id]},
    )
    row_4 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_John_Wick.id]},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains",
        value="smith",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids

    view_filter.value = "john"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_4.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 4


@pytest.mark.django_db
def test_has_value_contains_filter_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)

    other_row_A = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "188e1076-6c88-4bcc-893a-d0903c4169db"
        }
    )
    other_row_C = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "720a3d55-6aac-4d86-a0ce-6049001a4f64"
        }
    )
    other_row_a = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_A.id, other_row_B.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_B.id, other_row_a.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains",
        value="b099a1",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = "B099a1"  # upper case
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = "69db"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids

    view_filter.value = "xxx"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.parametrize(
    "target_field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        url_field_factory,
    ],
)
@pytest.mark.django_db
def test_has_not_value_contains_filter_text_field_types(
    data_fixture, target_field_factory
):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    other_row_John_Smith = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "John Smith"}
    )
    other_row_Anna_Smith = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "Anna Smith"}
    )
    other_row_John_Wick = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "John Wick"}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_John_Smith.id]},
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_Anna_Smith.id]},
    )
    row_4 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_John_Wick.id]},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_contains",
        value="smith",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_4.id in ids

    view_filter.value = "john"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 4


@pytest.mark.django_db
def test_has_not_value_contains_filter_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)

    other_row_A = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "188e1076-6c88-4bcc-893a-d0903c4169db"
        }
    )
    other_row_C = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "720a3d55-6aac-4d86-a0ce-6049001a4f64"
        }
    )
    other_row_a = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_A.id, other_row_B.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_B.id, other_row_a.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_contains",
        value="b099a1",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "B099a1"  # upper case
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "69db"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "xxx"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.parametrize(
    "target_field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        url_field_factory,
    ],
)
@pytest.mark.django_db
def test_has_value_contains_word_filter_text_field_types(
    data_fixture, target_field_factory
):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    other_row_1 = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "This is a sentence."}
    )
    other_row_2 = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "Another Sentence."}
    )
    other_row_3 = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": ""}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_1.id, other_row_3.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_3.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_2.id]},
    )
    row_4 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains_word",
        value="sentence",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids

    view_filter.value = "Sentence"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 4


@pytest.mark.django_db
def test_has_value_contains_word_filter_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)

    other_row_A = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545ce8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "188e1076-6c88-4bcc-893a-d0903c4169db"
        }
    )
    other_row_C = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "720a3d55-6aac-4d86-a0ce-6049001a4f64"
        }
    )
    other_row_a = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_A.id, other_row_B.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_B.id, other_row_a.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains_word",
        value="77545CE8",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = "77545ce8"  # lower case
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = "69db"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "xxx"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.parametrize(
    "target_field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        url_field_factory,
    ],
)
@pytest.mark.django_db
def test_has_not_value_contains_word_filter_text_field_types(
    data_fixture, target_field_factory
):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    other_row_1 = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "This is a sentence."}
    )
    other_row_2 = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "Another Sentence."}
    )
    other_row_3 = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": ""}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_1.id, other_row_3.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_3.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_2.id]},
    )
    row_4 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_contains_word",
        value="sentence",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_4.id in ids

    view_filter.value = "Sentence"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_4.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 4


@pytest.mark.django_db
def test_has_not_value_contains_word_filter_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)

    other_row_A = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545ce8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    other_row_B = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "188e1076-6c88-4bcc-893a-d0903c4169db"
        }
    )
    other_row_C = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "720a3d55-6aac-4d86-a0ce-6049001a4f64"
        }
    )
    other_row_a = test_setup.other_table_model.objects.create(
        **{
            f"field_{test_setup.target_field.id}": "77545CE8-cbc0-4748-ba17-668b099a1ef8"
        }
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_A.id, other_row_B.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_B.id, other_row_a.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_contains_word",
        value="77545CE8",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "77545ce8"  # lower case
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "69db"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = "xxx"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3


@pytest.mark.parametrize(
    "target_field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        url_field_factory,
    ],
)
@pytest.mark.django_db
def test_has_value_length_is_lower_than_text_field_types(
    data_fixture, target_field_factory
):
    test_setup = setup_linked_table_and_lookup(data_fixture, target_field_factory)

    other_row_10a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "aaaaaaaaaa"}
    )
    other_row_5a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": "aaaaa"}
    )
    other_row_0a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": ""}
    )
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_10a.id]},
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_0a.id, other_row_10a.id]
        },
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_5a.id]},
    )
    row_4 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_length_is_lower_than",
        value="10",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "5"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "11"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 4


@pytest.mark.django_db
def test_has_value_length_is_lower_than_uuid_field_types(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, uuid_field_factory)
    other_row_1 = test_setup.other_table_model.objects.create()
    other_row_2 = test_setup.other_table_model.objects.create()
    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_1.id]},
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_1.id, other_row_2.id]
        },
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_2.id]},
    )
    row_4 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": []},
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_length_is_lower_than",
        value="37",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "36"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = ""
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 4


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "has_all_values_equal",
            "0",
            [BooleanLookupRow.ALL_FALSE],
        ),
        (
            "has_all_values_equal",
            "1",
            [BooleanLookupRow.ALL_TRUE],
        ),
        (
            "has_all_values_equal",
            "False",
            [BooleanLookupRow.ALL_FALSE],
        ),
        (
            "has_all_values_equal",
            "True",
            [BooleanLookupRow.ALL_TRUE],
        ),
        (
            "has_all_values_equal",
            "f",
            [BooleanLookupRow.ALL_FALSE],
        ),
        (
            "has_all_values_equal",
            "t",
            [BooleanLookupRow.ALL_TRUE],
        ),
        (
            "has_all_values_equal",
            "",
            [BooleanLookupRow.ALL_FALSE],
        ),
        (
            "has_all_values_equal",
            "invalid",
            [BooleanLookupRow.ALL_FALSE],
        ),
    ],
)
@pytest.mark.django_db
def test_has_all_values_equal_filter_boolean_lookup_field_type(
    data_fixture, filter_type_name, test_value, expected_rows
):
    boolean_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "has_value_equal",
            "0",
            [BooleanLookupRow.MIXED, BooleanLookupRow.ALL_FALSE],
        ),
        (
            "has_value_equal",
            "1",
            [BooleanLookupRow.MIXED, BooleanLookupRow.ALL_TRUE],
        ),
        (
            "has_value_equal",
            "f",
            [BooleanLookupRow.MIXED, BooleanLookupRow.ALL_FALSE],
        ),
        (
            "has_value_equal",
            "t",
            [BooleanLookupRow.MIXED, BooleanLookupRow.ALL_TRUE],
        ),
        (
            "has_value_equal",
            "False",
            [BooleanLookupRow.MIXED, BooleanLookupRow.ALL_FALSE],
        ),
        (
            "has_value_equal",
            "True",
            [BooleanLookupRow.MIXED, BooleanLookupRow.ALL_TRUE],
        ),
        (
            "has_value_equal",
            "",
            [BooleanLookupRow.MIXED, BooleanLookupRow.ALL_FALSE],
        ),
        (
            "has_value_equal",
            "invalid",
            [BooleanLookupRow.MIXED, BooleanLookupRow.ALL_FALSE],
        ),
    ],
)
@pytest.mark.django_db
def test_has_value_equal_filter_boolean_lookup_field_type(
    data_fixture, filter_type_name, test_value, expected_rows
):
    boolean_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "has_not_value_equal",
            "0",
            [BooleanLookupRow.ALL_TRUE, BooleanLookupRow.NO_VALUES],
        ),
        (
            "has_not_value_equal",
            "1",
            [BooleanLookupRow.ALL_FALSE, BooleanLookupRow.NO_VALUES],
        ),
        (
            "has_not_value_equal",
            "f",
            [BooleanLookupRow.ALL_TRUE, BooleanLookupRow.NO_VALUES],
        ),
        (
            "has_not_value_equal",
            "t",
            [BooleanLookupRow.ALL_FALSE, BooleanLookupRow.NO_VALUES],
        ),
        (
            "has_not_value_equal",
            "False",
            [BooleanLookupRow.ALL_TRUE, BooleanLookupRow.NO_VALUES],
        ),
        (
            "has_not_value_equal",
            "True",
            [BooleanLookupRow.ALL_FALSE, BooleanLookupRow.NO_VALUES],
        ),
        (
            "has_not_value_equal",
            "",
            [BooleanLookupRow.ALL_TRUE, BooleanLookupRow.NO_VALUES],
        ),
        (
            "has_not_value_equal",
            "invalid",
            [BooleanLookupRow.ALL_TRUE, BooleanLookupRow.NO_VALUES],
        ),
    ],
)
@pytest.mark.django_db
def test_has_not_value_equal_filter_boolean_lookup_field_type(
    data_fixture, filter_type_name, test_value, expected_rows
):
    boolean_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "not_empty",
            "",
            [
                BooleanLookupRow.MIXED,
                BooleanLookupRow.ALL_FALSE,
                BooleanLookupRow.ALL_TRUE,
            ],
        ),
        (
            "empty",
            "",
            [BooleanLookupRow.NO_VALUES],
        ),
    ],
)
@pytest.mark.django_db
def test_empty_not_empty_filters_boolean_lookup_field_type(
    data_fixture, filter_type_name, test_value, expected_rows
):
    boolean_lookup_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.django_db
def test_has_value_equal_filter_single_select_field(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, single_select_field_factory
    )

    opt_a = data_fixture.create_select_option(field=test_setup.target_field, value="a")
    opt_b = data_fixture.create_select_option(field=test_setup.target_field, value="b")
    opt_c = data_fixture.create_select_option(field=test_setup.target_field, value="c")

    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_a}
    )
    other_row_b = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_b}
    )
    other_row_c = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_c}
    )

    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_a.id, other_row_b.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_b.id, other_row_c.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_equal",
        value=str(opt_a.id),
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids

    view_filter.value = str(opt_b.id)
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids


@pytest.mark.django_db
def test_has_not_value_equal_filter_single_select_field(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, single_select_field_factory
    )

    opt_a = data_fixture.create_select_option(field=test_setup.target_field, value="a")
    opt_b = data_fixture.create_select_option(field=test_setup.target_field, value="b")
    opt_c = data_fixture.create_select_option(field=test_setup.target_field, value="c")

    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_a}
    )
    other_row_b = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_b}
    )
    other_row_c = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_c}
    )

    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_a.id, other_row_b.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_b.id, other_row_c.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_equal",
        value=str(opt_c.id),
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids

    view_filter.value = str(opt_b.id)
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_2.id in ids


@pytest.mark.django_db
def test_has_value_contains_filter_single_select_field(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, single_select_field_factory
    )

    opt_a = data_fixture.create_select_option(field=test_setup.target_field, value="a")
    opt_b = data_fixture.create_select_option(field=test_setup.target_field, value="ba")
    opt_c = data_fixture.create_select_option(field=test_setup.target_field, value="c")

    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_a}
    )
    other_row_b = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_b}
    )
    other_row_c = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_c}
    )

    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_a.id, other_row_b.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_b.id, other_row_c.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains",
        value="a",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "c"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_3.id in ids


@pytest.mark.django_db
def test_has_not_value_contains_filter_single_select_field(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, single_select_field_factory
    )

    opt_a = data_fixture.create_select_option(field=test_setup.target_field, value="a")
    opt_b = data_fixture.create_select_option(field=test_setup.target_field, value="ba")
    opt_c = data_fixture.create_select_option(field=test_setup.target_field, value="c")

    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_a}
    )
    other_row_b = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_b}
    )
    other_row_c = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_c}
    )

    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_a.id, other_row_b.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_b.id, other_row_c.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_contains",
        value="a",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "c"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids


@pytest.mark.django_db
def test_has_value_contains_word_filter_single_select_field(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, single_select_field_factory
    )

    opt_a = data_fixture.create_select_option(field=test_setup.target_field, value="a")
    opt_b = data_fixture.create_select_option(field=test_setup.target_field, value="b")
    opt_c = data_fixture.create_select_option(field=test_setup.target_field, value="ca")

    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_a}
    )
    other_row_b = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_b}
    )
    other_row_c = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_c}
    )

    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_a.id, other_row_b.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_b.id, other_row_c.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains_word",
        value="a",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids

    view_filter.value = "ca"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_3.id in ids


@pytest.mark.django_db
def test_has_not_value_contains_word_filter_single_select_field(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, single_select_field_factory
    )

    opt_a = data_fixture.create_select_option(field=test_setup.target_field, value="a")
    opt_b = data_fixture.create_select_option(field=test_setup.target_field, value="b")
    opt_c = data_fixture.create_select_option(field=test_setup.target_field, value="ca")

    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_a}
    )
    other_row_b = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_b}
    )
    other_row_c = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_c}
    )

    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_a.id, other_row_b.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_b.id, other_row_c.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_not_value_contains_word",
        value="a",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.value = "ca"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids


@pytest.mark.django_db
def test_has_any_select_option_equal_filter_single_select_field(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, single_select_field_factory
    )

    opt_a = data_fixture.create_select_option(field=test_setup.target_field, value="a")
    opt_b = data_fixture.create_select_option(field=test_setup.target_field, value="b")
    opt_c = data_fixture.create_select_option(field=test_setup.target_field, value="c")

    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_a}
    )
    other_row_b = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_b}
    )
    other_row_c = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_c}
    )

    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_a.id, other_row_b.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_b.id, other_row_c.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_any_select_option_equal",
        value=f"{opt_a.id},{opt_c.id}",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = f"{opt_b.id},{opt_c.id}"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids


@pytest.mark.django_db
def test_has_none_select_option_equal_filter_single_select_field(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, single_select_field_factory
    )

    opt_a = data_fixture.create_select_option(field=test_setup.target_field, value="a")
    opt_b = data_fixture.create_select_option(field=test_setup.target_field, value="b")
    opt_c = data_fixture.create_select_option(field=test_setup.target_field, value="ca")

    other_row_a = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_a}
    )
    other_row_b = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_b}
    )
    other_row_c = test_setup.other_table_model.objects.create(
        **{f"field_{test_setup.target_field.id}": opt_c}
    )

    row_1 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_a.id, other_row_b.id]
        },
    )
    row_2 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={f"field_{test_setup.link_row_field.id}": [other_row_a.id]},
    )
    row_3 = test_setup.row_handler.create_row(
        user=test_setup.user,
        table=test_setup.table,
        values={
            f"field_{test_setup.link_row_field.id}": [other_row_b.id, other_row_c.id]
        },
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_none_select_option_equal",
        value=f"{opt_a.id},{opt_c.id}",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = f"{opt_b.id},{opt_c.id}"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert row_2.id in ids
