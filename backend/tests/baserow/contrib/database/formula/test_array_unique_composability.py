"""
Tests for array_unique composability with other formula functions
(count, join, has_option).
"""

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler


def _setup_text_lookup(data_fixture):
    """Create a text lookup with duplicates: apple, banana, apple → 2 unique."""
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target = data_fixture.create_text_field(table=table_b, name="target")

    rows_b = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [
                {target.db_column: "apple"},
                {target.db_column: "banana"},
                {target.db_column: "apple"},
            ],
        )
        .created_rows
    )

    row_a1, row_a2 = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [
                {link_field.db_column: [r.id for r in rows_b]},
                {link_field.db_column: []},
            ],
        )
        .created_rows
    )

    lookup_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', '{target.name}')",
    )

    return user, table_a, table_b, link_field, target, lookup_field, row_a1, row_a2


def _setup_number_lookup(data_fixture):
    """Create a number lookup with duplicates: 10, 20, 10 → 2 unique."""
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target = data_fixture.create_number_field(
        table=table_b, name="target", number_decimal_places=0
    )

    rows_b = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [
                {target.db_column: 10},
                {target.db_column: 20},
                {target.db_column: 10},
            ],
        )
        .created_rows
    )

    row_a1, row_a2 = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [
                {link_field.db_column: [r.id for r in rows_b]},
                {link_field.db_column: []},
            ],
        )
        .created_rows
    )

    lookup_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', '{target.name}')",
    )

    return user, table_a, table_b, link_field, target, lookup_field, row_a1, row_a2


@pytest.mark.django_db
def test_count_array_unique_text(data_fixture):
    """count(array_unique(field('lookup'))) returns number of unique text values."""
    user, table_a, *_, lookup_field, row_a1, row_a2 = _setup_text_lookup(data_fixture)

    count_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="unique_count",
        formula="count(array_unique(field('lookup')))",
    )

    model = table_a.get_model()
    rows = {r.id: getattr(r, count_field.db_column) for r in model.objects.all()}

    assert rows[row_a1.id] == 2  # apple, banana
    assert rows[row_a2.id] == 0  # empty


@pytest.mark.django_db
def test_count_array_unique_number(data_fixture):
    """count(array_unique(field('lookup'))) returns number of unique number values."""
    user, table_a, *_, lookup_field, row_a1, row_a2 = _setup_number_lookup(data_fixture)

    count_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="unique_count",
        formula="count(array_unique(field('lookup')))",
    )

    model = table_a.get_model()
    rows = {r.id: getattr(r, count_field.db_column) for r in model.objects.all()}

    assert rows[row_a1.id] == 2  # 10, 20
    assert rows[row_a2.id] == 0  # empty


@pytest.mark.django_db
def test_join_array_unique_text(data_fixture):
    """join(array_unique(field('lookup')), ', ') returns comma-separated unique values."""
    user, table_a, *_, lookup_field, row_a1, row_a2 = _setup_text_lookup(data_fixture)

    join_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="unique_joined",
        formula="join(array_unique(field('lookup')), ', ')",
    )

    model = table_a.get_model()
    rows = {r.id: getattr(r, join_field.db_column) for r in model.objects.all()}

    assert rows[row_a1.id] == "apple, banana"
    assert rows[row_a2.id] == ""


@pytest.mark.django_db
def test_count_array_unique_boolean(data_fixture):
    """count(array_unique(field('lookup'))) works with boolean lookups."""
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target = data_fixture.create_boolean_field(table=table_b, name="target")

    RowHandler().create_rows(
        user,
        table_b,
        [
            {target.db_column: True},
            {target.db_column: False},
            {target.db_column: True},  # duplicate
        ],
    )

    rows_b = list(table_b.get_model().objects.all().order_by("id"))

    (row_a,) = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [{link_field.db_column: [r.id for r in rows_b]}],
        )
        .created_rows
    )

    lookup_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', '{target.name}')",
    )

    count_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="unique_count",
        formula="count(array_unique(field('lookup')))",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)
    assert getattr(result, count_field.db_column) == 2  # True, False


@pytest.mark.django_db
def test_count_regular_lookup_still_works(data_fixture):
    """count(field('lookup')) still works (regression check for many-expression path)."""
    user, table_a, *_, lookup_field, row_a1, row_a2 = _setup_text_lookup(data_fixture)

    count_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="count",
        formula="count(field('lookup'))",
    )

    model = table_a.get_model()
    rows = {r.id: getattr(r, count_field.db_column) for r in model.objects.all()}

    assert rows[row_a1.id] == 3  # all 3 including duplicates
    assert rows[row_a2.id] == 0


@pytest.mark.django_db
def test_join_regular_lookup_still_works(data_fixture):
    """join(field('lookup'), ', ') still works (regression check)."""
    user, table_a, *_, lookup_field, row_a1, row_a2 = _setup_text_lookup(data_fixture)

    join_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="joined",
        formula="join(field('lookup'), ', ')",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a1.id)
    val = getattr(result, join_field.db_column)
    # Should contain all 3 values including duplicate
    assert val.count(",") == 2  # 3 items, 2 commas


@pytest.mark.django_db
def test_count_array_unique_inline_lookup(data_fixture):
    """count(array_unique(lookup('link', 'target'))) works with inline lookup."""
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target = data_fixture.create_text_field(table=table_b, name="target")

    rows_b = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [
                {target.db_column: "X"},
                {target.db_column: "Y"},
                {target.db_column: "X"},
            ],
        )
        .created_rows
    )

    (row_a,) = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [{link_field.db_column: [r.id for r in rows_b]}],
        )
        .created_rows
    )

    count_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="unique_count",
        formula=f"count(array_unique(lookup('{link_field.name}', '{target.name}')))",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)
    assert getattr(result, count_field.db_column) == 2


@pytest.mark.django_db
def test_join_array_unique_inline_lookup(data_fixture):
    """join(array_unique(lookup('link', 'target')), sep) works with inline lookup."""
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target = data_fixture.create_text_field(table=table_b, name="target")

    rows_b = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [
                {target.db_column: "X"},
                {target.db_column: "Y"},
                {target.db_column: "X"},
            ],
        )
        .created_rows
    )

    (row_a,) = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [{link_field.db_column: [r.id for r in rows_b]}],
        )
        .created_rows
    )

    join_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="unique_joined",
        formula=f"join(array_unique(lookup('{link_field.name}', '{target.name}')), ', ')",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)
    assert getattr(result, join_field.db_column) == "X, Y"
