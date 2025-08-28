import typing
from enum import Enum

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.utils.duration import parse_duration_value
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.array_view_filters import (
    HasDateAfterViewFilterType,
    HasDateBeforeViewFilterType,
    HasDateEqualViewFilterType,
    HasDateOnOrAfterViewFilterType,
    HasDateOnOrBeforeViewFilterType,
    HasDateWithinViewFilterType,
    HasNotDateAfterViewFilterType,
    HasNotDateBeforeViewFilterType,
    HasNotDateEqualViewFilterType,
    HasNotDateOnOrAfterViewFilterType,
    HasNotDateOnOrBeforeViewFilterType,
    HasNotDateWithinViewFilterType,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.view_filters import (
    DateIsAfterMultiStepFilterType,
    DateIsBeforeMultiStepFilterType,
    DateIsEqualMultiStepFilterType,
    DateIsNotEqualMultiStepFilterType,
    DateIsOnOrAfterMultiStepFilterType,
    DateIsOnOrBeforeMultiStepFilterType,
    DateIsWithinMultiStepFilterType,
)
from baserow.core.handler import CoreHandler
from tests.baserow.contrib.database.utils import (
    boolean_field_factory,
    date_field_factory,
    datetime_field_factory,
    duration_field_factory,
    email_field_factory,
    file_field_factory,
    long_text_field_factory,
    multiple_collaborators_field_factory,
    multiple_select_field_factory,
    multiple_select_field_value_factory,
    number_field_factory,
    phone_number_field_factory,
    setup_linked_table_and_lookup,
    single_select_field_factory,
    single_select_field_value_factory,
    text_field_factory,
    text_field_value_factory,
    url_field_factory,
    uuid_field_factory,
)

from .date_utils import (
    DATE_MULTI_STEP_OPERATOR_VALID_RESULTS,
    FREEZED_TODAY,
    MNEMONIC_VALUES,
    TEST_MULTI_STEP_DATE_OPERATORS_DATETIMES,
)

if typing.TYPE_CHECKING:
    from baserow.test_utils.fixtures import Fixtures


def duration_value(val: str, format: str = "d h") -> str:
    """
    Parses symbolic duration value to a proper number of seconds for the test.
    """

    return str(int(parse_duration_value(val, format)))


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
    ).created_rows
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
    ).created_rows
    rows = [r_mixed, r_false, r_true, r_none]
    selected = [rows[idx] for idx in expected_rows]

    test_setup.view_handler.create_filter(
        test_setup.user,
        test_setup.grid_view,
        field=test_setup.lookup_field,
        type_name=filter_type_name,
        value=test_value,
    )
    q = test_setup.view_handler.get_queryset(test_setup.user, test_setup.grid_view)
    assert len(q) == len(selected)
    assert set([r.id for r in q]) == set([r.id for r in selected])


@pytest.mark.parametrize(
    "field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        url_field_factory,
        number_field_factory,
        single_select_field_factory,
        multiple_select_field_factory,
        date_field_factory,
        datetime_field_factory,
        duration_field_factory,
        multiple_collaborators_field_factory,
        file_field_factory,
    ],
)
@pytest.mark.django_db
def test_empty_not_empty_array_filter(field_factory, data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    target_field = field_factory(data_fixture, table_b, user)
    lookup_field = data_fixture.create_lookup_field(
        name="lookup",
        table=table_a,
        through_field=link_a_to_b,
        target_field=target_field,
        through_field_name=link_a_to_b.name,
        target_field_name=target_field.name,
    )
    view = data_fixture.create_grid_view(user=user, table=table_a)
    view_filter = data_fixture.create_view_filter(
        view=view, field=lookup_field, type="empty"
    )

    row_handler = RowHandler()
    row_empty_b1, row_empty_b2 = row_handler.force_create_rows(
        user, table_b, [{}, {}]
    ).created_rows
    field_type = target_field.get_type()
    random_value = field_type.random_value(target_field, data_fixture.fake, {})

    b3_value = field_type.random_to_input_value(target_field, random_value)
    assert b3_value  # Ensure we're not getting empty value

    row_b3 = row_handler.force_create_row(
        user, table_b, {target_field.db_column: b3_value}
    )

    model_a = table_a.get_model()
    row_a1, row_a2, row_a3, row_a4, row_a5, row_a6 = row_handler.force_create_rows(
        user,
        table_a,
        [
            {},
            {link_a_to_b.db_column: [row_empty_b1.id]},
            {link_a_to_b.db_column: [row_empty_b2.id]},
            {link_a_to_b.db_column: [row_empty_b1.id, row_empty_b2.id]},
            {link_a_to_b.db_column: [row_b3.id, row_empty_b2.id]},
            {link_a_to_b.db_column: [row_b3.id]},
        ],
        model=model_a,
    ).created_rows

    handler = ViewHandler()
    ids = [r.id for r in handler.apply_filters(view, model_a.objects.all()).all()]
    assert ids == [row_a1.id, row_a2.id, row_a3.id, row_a4.id]

    view_filter.type = "not_empty"
    view_filter.save()

    ids = [r.id for r in handler.apply_filters(view, model_a.objects.all()).all()]
    assert ids == [row_a5.id, row_a6.id]


@pytest.mark.parametrize(
    "fixture_method_name",
    [
        "create_last_modified_field",
        "create_created_on_field",
        "create_autonumber_field",
        "create_uuid_field",
    ],
)
@pytest.mark.django_db
def test_empty_not_empty_read_only_array_filter(fixture_method_name, data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    target_field = getattr(data_fixture, fixture_method_name)(table=table_b)
    lookup_field = data_fixture.create_lookup_field(
        name="lookup",
        table=table_a,
        through_field=link_a_to_b,
        target_field=target_field,
        through_field_name=link_a_to_b.name,
        target_field_name=target_field.name,
    )
    view = data_fixture.create_grid_view(user=user, table=table_a)
    view_filter = data_fixture.create_view_filter(
        view=view, field=lookup_field, type="empty"
    )

    row_handler = RowHandler()
    (row_b1,) = row_handler.create_rows(user, table_b, [{}]).created_rows

    model_a = table_a.get_model()
    row_a1, row_a2, row_a3 = row_handler.force_create_rows(
        user,
        table_a,
        [{}, {link_a_to_b.db_column: [row_b1.id]}, {link_a_to_b.db_column: []}],
        model=model_a,
    ).created_rows

    handler = ViewHandler()
    ids = [r.id for r in handler.apply_filters(view, model_a.objects.all()).all()]
    assert ids == [row_a1.id, row_a3.id]

    view_filter.type = "not_empty"
    view_filter.save()

    ids = [r.id for r in handler.apply_filters(view, model_a.objects.all()).all()]
    assert ids == [row_a2.id]


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
            [
                BooleanLookupRow.ALL_TRUE,
                BooleanLookupRow.ALL_FALSE,
                BooleanLookupRow.NO_VALUES,
                BooleanLookupRow.MIXED,
            ],
        ),
        (
            "has_all_values_equal",
            "invalid",
            [],
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
            [
                BooleanLookupRow.MIXED,
                BooleanLookupRow.ALL_FALSE,
                BooleanLookupRow.NO_VALUES,
                BooleanLookupRow.ALL_TRUE,
            ],
        ),
        (
            "has_value_equal",
            "invalid",
            [],
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
            [
                BooleanLookupRow.MIXED,
                BooleanLookupRow.ALL_FALSE,
                BooleanLookupRow.NO_VALUES,
                BooleanLookupRow.ALL_TRUE,
            ],
        ),
        (
            "has_not_value_equal",
            "invalid",
            # inverse of has_value_equal with `invalid` value
            [
                BooleanLookupRow.ALL_TRUE,
                BooleanLookupRow.ALL_FALSE,
                BooleanLookupRow.NO_VALUES,
                BooleanLookupRow.MIXED,
            ],
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


def setup_multiple_collaborators_fields(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, multiple_collaborators_field_factory
    )

    # tables layout:
    #   table A:
    #     row A: one collab, Collaborator A
    #     row B: two collabs, Collaborator A, Collaborator B
    #     row C: no collaborator,
    #   table B (test table for filters):
    #     one value row, [ row A ]
    #     two values row, [row A, row B]
    #     two values, one empty, [row A, row C - empty ]
    #     no values, []

    user = test_setup.user
    user.first_name = "derp"
    user.save()
    table = test_setup.table
    other_table = test_setup.other_table
    other_user_A = data_fixture.create_user(first_name="test user")
    other_user_B = data_fixture.create_user(first_name="other user")
    database = test_setup.table.database
    workspace = database.workspace
    chandler = CoreHandler()
    thandler = TableHandler()
    fhandler = FieldHandler()
    rhandler = RowHandler()

    chandler.add_user_to_workspace(workspace, other_user_A)
    chandler.add_user_to_workspace(workspace, other_user_B)
    text_field_a = data_fixture.create_text_field(
        table=table, user=user, name="pk", primary=True
    )
    text_field_b = data_fixture.create_text_field(
        table=other_table, user=user, name="pk", primary=True
    )

    related_table_rows = [
        {
            text_field_b.db_column: "relA",
            test_setup.target_field.db_column: [other_user_A.id],
        },
        {
            text_field_b.db_column: "relB",
            test_setup.target_field.db_column: [other_user_A.id, other_user_B.id],
        },
        {text_field_b.db_column: "relC", test_setup.target_field.db_column: []},
    ]

    related_rows = rhandler.force_create_rows(
        user,
        table=other_table,
        rows_values=related_table_rows,
        send_webhook_events=False,
        send_realtime_update=False,
    )

    related_rows = {
        getattr(r, text_field_b.db_column): r for r in related_rows.created_rows
    }

    table_rows = [
        {
            text_field_a.db_column: "A",
            test_setup.link_row_field.db_column: [related_rows["relA"].id],
        },
        {
            text_field_a.db_column: "B",
            test_setup.link_row_field.db_column: [
                related_rows["relA"].id,
                related_rows["relB"].id,
            ],
        },
        {
            text_field_a.db_column: "C",
            test_setup.link_row_field.db_column: [
                related_rows["relA"].id,
                related_rows["relC"].id,
            ],
        },
        {text_field_a.db_column: "D", test_setup.link_row_field.db_column: []},
    ]
    created_rows = rhandler.force_create_rows(
        user=user,
        table=table,
        rows_values=table_rows,
        send_webhook_events=False,
        send_realtime_update=False,
    )

    created_rows = {
        getattr(r, text_field_a.db_column): r for r in created_rows.created_rows
    }

    test_setup.extra["other_users"] = {
        u.first_name: u for u in [other_user_A, other_user_B]
    }
    return test_setup, created_rows, related_rows


def setup_multiple_select_rows(data_fixture):
    test_setup = setup_linked_table_and_lookup(
        data_fixture, multiple_select_field_factory
    )

    user = test_setup.user
    row_A_value = multiple_select_field_value_factory(
        data_fixture, test_setup.target_field, "Aa C"
    )
    row_B_value = multiple_select_field_value_factory(
        data_fixture, test_setup.target_field, "B"
    )
    row_empty_value = multiple_select_field_value_factory(
        data_fixture, test_setup.target_field
    )

    (
        other_row_A,
        other_row_B,
        other_row_empty,
    ) = test_setup.row_handler.force_create_rows(
        user,
        test_setup.other_table,
        [
            {f"field_{test_setup.target_field.id}": row_A_value},
            {f"field_{test_setup.target_field.id}": row_B_value},
            {f"field_{test_setup.target_field.id}": row_empty_value},
        ],
    ).created_rows
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
    return test_setup, [row_1, row_2, row_3], [*row_A_value, *row_B_value]


def setup_duration_lookup_fields(data_fixture):
    test_setup = setup_linked_table_and_lookup(data_fixture, duration_field_factory)

    # tables layout:
    #  referenced B:
    #   * row B1 [no value]
    #   * row B2 [1h value]
    #   * row B3 [1d value]
    #   * row B4 [1d 6h value]
    #
    #  table A:
    #  * A1 - no values []
    #  * A2 - empty value [B1]
    #  * A3 - 1h value [B2]
    #  * A4 - 1h, 1d 6h value [B2, B4]
    #  * A5 - 1h, 1d [B2, B3]
    #  * A6 - 1d 6h [B4]
    #  * A7 - 1h + empty [B2, B1]

    user = test_setup.user
    user.first_name = "derp"
    user.save()
    table = test_setup.table
    other_table = test_setup.other_table
    database = test_setup.table.database
    workspace = database.workspace
    chandler = CoreHandler()
    thandler = TableHandler()
    fhandler = FieldHandler()
    rhandler = RowHandler()

    pk_A = data_fixture.create_text_field(
        table=table, user=user, name="pk", primary=True
    )
    pk_B = data_fixture.create_text_field(
        table=other_table, user=user, name="pk", primary=True
    )
    pk_b_name = pk_B.db_column
    pk_a_name = pk_A.db_column
    dur_b_name = test_setup.target_field.db_column
    lookup_name = test_setup.link_row_field.db_column

    related_table_rows = [
        {pk_b_name: "B1", dur_b_name: None},
        {pk_b_name: "B2", dur_b_name: "1h"},
        {pk_b_name: "B3", dur_b_name: "1d"},
        {pk_b_name: "B4", dur_b_name: "1d 6h"},
    ]

    related_rows = rhandler.force_create_rows(
        user,
        table=other_table,
        rows_values=related_table_rows,
        send_webhook_events=False,
        send_realtime_update=False,
    )

    related_rows = {getattr(r, pk_b_name): r for r in related_rows.created_rows}

    def rel(row_name):
        return related_rows[row_name].id

    table_rows = [
        {pk_a_name: "A1", lookup_name: []},
        {pk_a_name: "A2", lookup_name: [rel("B1")]},
        {pk_a_name: "A3", lookup_name: [rel("B2")]},
        {pk_a_name: "A4", lookup_name: [rel("B2"), rel("B4")]},
        {pk_a_name: "A5", lookup_name: [rel("B2"), rel("B3")]},
        {pk_a_name: "A6", lookup_name: [rel("B4")]},
        {pk_a_name: "A7", lookup_name: [rel("B2"), rel("B1")]},
    ]
    created_rows = rhandler.force_create_rows(
        user=user,
        table=table,
        rows_values=table_rows,
        send_webhook_events=False,
        send_realtime_update=False,
    )

    created_rows = {getattr(r, pk_a_name): r for r in created_rows.created_rows}

    return test_setup, created_rows, related_rows


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_has_or_has_not_empty_value_filter_multiple_collaborators_lookup_type(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_multiple_collaborators_fields(
        data_fixture
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
    assert created_rows["C"].id in ids

    view_filter.type = "has_not_empty_value"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [created_rows["A"].id, created_rows["B"].id, created_rows["D"].id]


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_has_or_doesnt_have_value_equal_filter_multiple_collaborators_lookup_field_types(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_multiple_collaborators_fields(
        data_fixture
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_equal",
        value=str(test_setup.extra["other_users"]["other user"].id),
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert created_rows["B"].id in ids

    view_filter.type = "has_not_value_equal"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [created_rows[row_id].id for row_id in ["A", "C", "D"]]


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_has_or_doesnt_have_value_contains_filter_multiple_collaborators_lookup_field_types(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_multiple_collaborators_fields(
        data_fixture
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains",
        value="oth",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert created_rows["B"].id in ids

    view_filter.type = "has_not_value_contains"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [created_rows[row_id].id for row_id in ["A", "C", "D"]]


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_has_or_doesnt_have_value_contains_word_filter_multiple_collaborators_lookup_field_types(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_multiple_collaborators_fields(
        data_fixture
    )

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains_word",
        value="other",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 1
    assert created_rows["B"].id in ids

    view_filter.type = "has_not_value_contains_word"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [created_rows[row_id].id for row_id in ["A", "C", "D"]]


@pytest.mark.django_db
@pytest.mark.field_duration
def test_has_or_has_not_empty_value_filter_duration_lookup_type(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_duration_lookup_fields(data_fixture)

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
    assert [created_rows["A2"].id, created_rows["A7"].id] == ids

    view_filter.type = "has_not_empty_value"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [created_rows["A1"].id] + [
        created_rows[f"A{row_name}"].id for row_name in range(3, 7)
    ]


@pytest.mark.django_db
@pytest.mark.field_duration
def test_has_or_has_not_value_higher_than_filter_duration_lookup_type(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_duration_lookup_fields(data_fixture)

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_higher",
        value=duration_value("1d"),
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert [
        created_rows["A4"].id,
        created_rows["A6"].id,
    ] == ids

    view_filter.type = "has_not_value_higher"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    # A1,A2,A3,A5,A6,A7
    assert ids == [
        created_rows[f"A{row_name}"].id
        for row_name in range(1, 8)
        if row_name not in {4, 6}
    ]


@pytest.mark.django_db
@pytest.mark.field_duration
def test_has_or_has_not_value_higher_or_equal_than_filter_duration_lookup_type(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_duration_lookup_fields(data_fixture)

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_higher_or_equal",
        value=duration_value("1d"),
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert [
        created_rows["A4"].id,
        created_rows["A5"].id,
        created_rows["A6"].id,
    ] == ids

    view_filter.type = "has_not_value_higher_or_equal"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [
        created_rows[f"A{row_name}"].id
        for row_name in range(1, 8)
        if row_name not in {4, 5, 6}
    ]


@pytest.mark.django_db
@pytest.mark.field_duration
def test_has_or_has_not_value_lower_or_equal_than_filter_duration_lookup_type(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_duration_lookup_fields(data_fixture)

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_lower_or_equal",
        value=duration_value("1d"),
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]

    assert ids == [
        created_rows[f"A{row_name}"].id
        for row_name in range(1, 8)
        if row_name not in {1, 2, 6}
    ]

    view_filter.type = "has_not_value_lower_or_equal"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [
        created_rows[f"A{row_name}"].id
        for row_name in range(1, 8)
        if row_name in {1, 2, 6}
    ]


@pytest.mark.django_db
@pytest.mark.field_duration
def test_has_or_has_not_value_lower_than_filter_duration_lookup_type(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_duration_lookup_fields(data_fixture)

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_lower",
        value=duration_value("1d"),
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]

    assert ids == [
        created_rows[f"A{row_name}"].id
        for row_name in range(1, 8)
        if row_name not in {1, 2, 6}
    ]

    view_filter.type = "has_not_value_lower"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [
        created_rows[f"A{row_name}"].id
        for row_name in range(1, 8)
        if row_name in {1, 2, 6}
    ]


@pytest.mark.django_db
@pytest.mark.field_duration
def test_has_or_has_not_value_equal_duration_lookup_type(
    data_fixture,
):
    test_setup, created_rows, related_rows = setup_duration_lookup_fields(data_fixture)

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_equal",
        value=duration_value("1d"),
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]

    assert ids == [
        created_rows[f"A{row_name}"].id for row_name in range(1, 8) if row_name in {5}
    ]

    view_filter.type = "has_not_value_equal"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]

    assert ids == [
        created_rows[f"A{row_name}"].id
        for row_name in range(1, 8)
        if row_name not in {5}
    ]


@pytest.mark.django_db
@pytest.mark.field_multiple_select
def test_has_or_has_not_empty_value_filter_multiple_select_field_types(
    data_fixture,
):
    test_setup, [row_1, row_2, row_3], _ = setup_multiple_select_rows(data_fixture)

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

    view_filter.type = "has_not_empty_value"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [row_2.id, row_3.id]


@pytest.mark.django_db
@pytest.mark.field_multiple_select
def test_has_or_doesnt_have_value_contains_filter_multiple_select_field_types(
    data_fixture,
):
    test_setup, [row_1, row_2, row_3], _ = setup_multiple_select_rows(data_fixture)

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains",
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

    view_filter.type = "has_not_value_contains"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [row_2.id, row_3.id]


@pytest.mark.django_db
@pytest.mark.field_multiple_select
def test_has_or_doesnt_have_value_contains_word_filter_multiple_select_field_types(
    data_fixture,
):
    test_setup, [row_1, row_2, row_3], _ = setup_multiple_select_rows(data_fixture)

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains_word",
        value="A",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert len(ids) == 0

    view_filter.value = "Aa"
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert row_1.id in ids

    view_filter.type = "has_not_value_contains_word"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [row_2.id, row_3.id]


@pytest.mark.django_db
@pytest.mark.field_multiple_select
def test_has_or_doesnt_have_value_equal_filter_multiple_select_field_types(
    data_fixture,
):
    test_setup, [row_1, row_2, row_3], options = setup_multiple_select_rows(
        data_fixture
    )
    # row_1 links to other_row_A (options[0]) and other_row_empty ([])
    # row_2 links to other_row_empty ([])
    # row_3 links to other_row_B (options[1])

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
    assert len(ids) == 0

    view_filter.value = str(options[0])
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [row_1.id]

    view_filter.value = ",".join([str(oid) for oid in options])
    view_filter.save()
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == []  # no row has all options

    view_filter.type = "has_not_value_equal"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [row_1.id, row_2.id, row_3.id]


def setup_date_rows(data_fixture, field_factory):
    test_setup = setup_linked_table_and_lookup(data_fixture, field_factory)
    user = test_setup.user
    target_field = test_setup.target_field
    other_row_1, other_row_2, other_row_3 = test_setup.row_handler.force_create_rows(
        user,
        test_setup.other_table,
        [
            {target_field.db_column: "2020-01-01"},
            {target_field.db_column: "2019-01-02"},
            {},
        ],
        model=test_setup.other_table_model,
    ).created_rows
    row_1, row_2, empty_row = test_setup.row_handler.force_create_rows(
        user,
        test_setup.table,
        [
            {test_setup.link_row_field.db_column: [other_row_1.id]},
            {test_setup.link_row_field.db_column: [other_row_2.id]},
            {test_setup.link_row_field.db_column: [other_row_3.id]},
        ],
        model=test_setup.model,
    ).created_rows
    return test_setup, [row_1, row_2, empty_row]


@pytest.mark.django_db
@pytest.mark.field_date
@pytest.mark.parametrize("field_factory", [date_field_factory, datetime_field_factory])
def test_has_or_has_not_empty_value_filter_date_field_types(
    data_fixture, field_factory
):
    test_setup, [row_1, row_2, empty_row] = setup_date_rows(data_fixture, field_factory)

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
    assert ids == [empty_row.id]

    view_filter.type = "has_not_empty_value"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [row_1.id, row_2.id]


@pytest.mark.django_db
@pytest.mark.field_date
@pytest.mark.parametrize("field_factory", [date_field_factory, datetime_field_factory])
def test_has_or_has_not_value_contains_filter_date_field_types(
    data_fixture, field_factory
):
    test_setup, [row_1, row_2, empty_row] = setup_date_rows(data_fixture, field_factory)

    view_filter = data_fixture.create_view_filter(
        view=test_setup.grid_view,
        field=test_setup.lookup_field,
        type="has_value_contains",
        value="19",
    )
    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [row_2.id]

    view_filter.type = "has_not_value_contains"
    view_filter.save()

    ids = [
        r.id
        for r in test_setup.view_handler.apply_filters(
            test_setup.grid_view, test_setup.model.objects.all()
        ).all()
    ]
    assert ids == [row_1.id, empty_row.id]


SINGLE_TO_ARRAY_FILTER_TYPE_MAP = {
    DateIsEqualMultiStepFilterType.type: {"has": HasDateEqualViewFilterType.type},
    DateIsNotEqualMultiStepFilterType.type: {"has": HasNotDateEqualViewFilterType.type},
    DateIsBeforeMultiStepFilterType.type: {
        "has": HasDateBeforeViewFilterType.type,
        "has_not": HasNotDateBeforeViewFilterType.type,
    },
    DateIsOnOrBeforeMultiStepFilterType.type: {
        "has": HasDateOnOrBeforeViewFilterType.type,
        "has_not": HasNotDateOnOrBeforeViewFilterType.type,
    },
    DateIsAfterMultiStepFilterType.type: {
        "has": HasDateAfterViewFilterType.type,
        "has_not": HasNotDateAfterViewFilterType.type,
    },
    DateIsOnOrAfterMultiStepFilterType.type: {
        "has": HasDateOnOrAfterViewFilterType.type,
        "has_not": HasNotDateOnOrAfterViewFilterType.type,
    },
    DateIsWithinMultiStepFilterType.type: {
        "has": HasDateWithinViewFilterType.type,
        "has_not": HasNotDateWithinViewFilterType.type,
    },
}


@pytest.fixture()
def table_view_fields_rows(data_fixture):
    user = data_fixture.create_user()
    orig_table = data_fixture.create_database_table(user=user)
    date_field = data_fixture.create_date_field(table=orig_table)
    datetime_field = data_fixture.create_date_field(
        table=orig_table, date_include_time=True
    )
    orig_rows = (
        RowHandler()
        .force_create_rows(
            user,
            orig_table,
            [
                {
                    date_field.db_column: date_value,
                    datetime_field.db_column: date_value,
                }
                for date_value in TEST_MULTI_STEP_DATE_OPERATORS_DATETIMES
            ],
        )
        .created_rows
    )

    table = data_fixture.create_database_table(database=orig_table.database)
    link_field = data_fixture.create_link_row_field(
        table=table, link_row_table=orig_table, name="link_field"
    )
    lookup_date_field = data_fixture.create_lookup_field(
        table=table,
        name="lookup_date_field",
        through_field=link_field,
        target_field=date_field,
        through_field_name=link_field.name,
        target_field_name=date_field.name,
    )
    lookup_datetime_field = data_fixture.create_lookup_field(
        table=table,
        name="lookup_datetime_field",
        through_field=link_field,
        target_field=datetime_field,
        through_field_name=link_field.name,
        target_field_name=datetime_field.name,
    )
    rows = (
        RowHandler()
        .force_create_rows(
            user,
            table,
            [{link_field.db_column: [r.id]} for r in orig_rows],
        )
        .created_rows
    )

    grid_view = data_fixture.create_grid_view(table=table)
    return table, grid_view, lookup_date_field, lookup_datetime_field, rows


@pytest.mark.parametrize(
    "filter_type,operator,filter_value,expected_results",
    [
        (
            filter_type,
            opr.value,
            opr_data.get("value", ""),
            [MNEMONIC_VALUES[v] for v in opr_data["expected_results"]],
        )
        for filter_type in DATE_MULTI_STEP_OPERATOR_VALID_RESULTS.keys()
        for (opr, opr_data) in DATE_MULTI_STEP_OPERATOR_VALID_RESULTS[
            filter_type
        ].items()
    ],
)
@pytest.mark.django_db
def test_date_array_filter_types(
    data_fixture,
    filter_type,
    operator,
    filter_value,
    expected_results,
    table_view_fields_rows,
):
    (
        table,
        grid_view,
        lookup_date_field,
        lookup_datetime_field,
        rows,
    ) = table_view_fields_rows

    handler = ViewHandler()
    model = table.get_model()

    def apply_filters_and_assert(expected):
        with freeze_time(FREEZED_TODAY):
            qs = handler.apply_filters(grid_view, model.objects.all())
            ids = set([r.id for r in qs.all()])
        res_pos = [i for (i, r) in enumerate(rows) if r.id in ids]

        mnem_keys = list(MNEMONIC_VALUES.keys())
        mnem_res_pos = [mnem_keys[v] for v in res_pos]
        mnem_exp_res = [mnem_keys[v] for v in expected]
        assert res_pos == unordered(
            expected
        ), f"{filter_type} - {operator}: {mnem_res_pos} != {mnem_exp_res}"

    # with date
    array_filter_type_has = SINGLE_TO_ARRAY_FILTER_TYPE_MAP[filter_type]["has"]
    array_filter_type_has_not = SINGLE_TO_ARRAY_FILTER_TYPE_MAP[filter_type].get(
        "has_not"
    )
    expected_results_for_has_not = list(
        set(MNEMONIC_VALUES.values()) - set(expected_results)
    )
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=lookup_date_field,
        type=array_filter_type_has,
        value=f"UTC?{filter_value}?{operator}",
    )
    apply_filters_and_assert(expected_results)

    if array_filter_type_has_not is not None:
        view_filter.type = array_filter_type_has_not
        view_filter.save()
        apply_filters_and_assert(expected_results_for_has_not)

    # with datetime
    view_filter.type = array_filter_type_has
    view_filter.field = lookup_datetime_field
    view_filter.save()

    apply_filters_and_assert(expected_results)

    if array_filter_type_has_not is not None:
        view_filter.type = array_filter_type_has_not
        view_filter.save()
        apply_filters_and_assert(expected_results_for_has_not)
