"""
Tests for generalized index(), first(), last() on all array types.
index() returns a scalar (the sub_type), supports 0-based and negative indices.
first(arr) = index(arr, 0), last(arr) = index(arr, -1).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.formula.types.exceptions import InvalidFormulaType
from baserow.contrib.database.rows.handler import RowHandler


def _setup_single_select(df, table):
    field = df.create_single_select_field(table=table, name="target")
    opt_a = df.create_select_option(field=field, value="Alpha", order=0)
    opt_b = df.create_select_option(field=field, value="Beta", order=1)
    opt_c = df.create_select_option(field=field, value="Gamma", order=2)
    return field, opt_a.id, opt_b.id, opt_c.id


def _to_date(val: str) -> date:
    return date.fromisoformat(val)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "setup_fn,values,to_expected",
    [
        (
            lambda df, table: df.create_text_field(table=table, name="target"),
            ["apple", "banana", "cherry", "date"],
            None,
        ),
        (
            lambda df, table: df.create_number_field(
                table=table, name="target", number_decimal_places=2
            ),
            [Decimal("10.50"), Decimal("20.00"), Decimal("30.75"), Decimal("40.00")],
            None,
        ),
        (
            lambda df, table: df.create_boolean_field(table=table, name="target"),
            [True, False, True, False],
            None,
        ),
        # Date: write as ISO string, read back as date objects
        (
            lambda df, table: df.create_date_field(table=table, name="target"),
            ["2024-01-15", "2024-06-01", "2024-12-25", "2025-03-01"],
            _to_date,
        ),
        (
            lambda df, table: df.create_duration_field(
                table=table, name="target", duration_format="h:mm"
            ),
            [
                timedelta(hours=1, minutes=30),
                timedelta(hours=2),
                timedelta(hours=3, minutes=45),
                timedelta(hours=5),
            ],
            None,
        ),
        (
            lambda df, table: df.create_url_field(table=table, name="target"),
            [
                "https://example.com",
                "https://baserow.io",
                "https://python.org",
                "https://django.com",
            ],
            None,
        ),
        (
            lambda df, table: df.create_email_field(table=table, name="target"),
            [
                "alice@example.com",
                "bob@example.com",
                "carol@example.com",
                "dave@example.com",
            ],
            None,
        ),
        (
            lambda df, table: df.create_phone_number_field(table=table, name="target"),
            ["+1234567890", "+0987654321", "+1111111111", "+2222222222"],
            None,
        ),
        (
            lambda df, table: df.create_rating_field(table=table, name="target"),
            [3, 5, 1, 4],
            None,
        ),
    ],
    ids=[
        "text",
        "number",
        "boolean",
        "date",
        "duration",
        "url",
        "email",
        "phone",
        "rating",
    ],
)
def test_index_first_last_scalar_types(
    data_fixture,
    api_client,
    setup_fn,
    values,
    to_expected,
):
    """
    index(lookup, n) returns the scalar value at position n.
    first() = index(arr, 0), last() = index(arr, -1).
    Parametrized across scalar field types.

    Also verifies that row updates, row additions with empty values, and
    row deletions in the linked table correctly recalculate the formula
    and that the formula table can still be fetched via the API afterwards.
    """

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table_a = data_fixture.create_database_table(database=database, name="A")
    table_b = data_fixture.create_database_table(database=database, name="B")
    data_fixture.create_text_field(table=table_a, name="pa", primary=True)
    data_fixture.create_text_field(table=table_b, name="pb", primary=True)

    link_field = FieldHandler().create_field(
        user, table_a, "link_row", name="link", link_row_table=table_b
    )

    target_field = setup_fn(data_fixture, table_b)

    expected_vals = [to_expected(v) for v in values] if to_expected else values

    rows_b = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [{target_field.db_column: v} for v in values],
        )
        .created_rows
    )

    # Row A1: links to first 3; Row A2: empty; Row A3: single link
    row_a1, row_a2, row_a3 = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [
                {link_field.db_column: [r.id for r in rows_b[:3]]},
                {link_field.db_column: []},
                {link_field.db_column: [rows_b[3].id]},
            ],
        )
        .created_rows
    )

    lookup_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', '{target_field.name}')",
    )

    first_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="first_val",
        formula="first(field('lookup'))",
    )
    last_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="last_val",
        formula="last(field('lookup'))",
    )
    index0 = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="idx0",
        formula="index(field('lookup'), 0)",
    )
    index1 = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="idx1",
        formula="index(field('lookup'), 1)",
    )
    index_neg1 = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="idx_neg1",
        formula="index(field('lookup'), -1)",
    )

    # Same via a formula field referencing the target field indirectly.
    ref_target = FieldHandler().create_field(
        user,
        table_b,
        "formula",
        name="ref_target",
        formula=f"field('{target_field.name}')",
    )
    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_lookup",
        formula=f"lookup('{link_field.name}', '{ref_target.name}')",
    )
    ref_first = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_first_val",
        formula="first(field('ref_lookup'))",
    )
    ref_last = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_last_val",
        formula="last(field('ref_lookup'))",
    )
    ref_index0 = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_idx0",
        formula="index(field('ref_lookup'), 0)",
    )
    ref_index1 = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_idx1",
        formula="index(field('ref_lookup'), 1)",
    )

    model = table_a.get_model()
    r1 = model.objects.get(id=row_a1.id)
    r2 = model.objects.get(id=row_a2.id)

    assert getattr(r1, index0.db_column) == expected_vals[0]
    assert getattr(r1, index1.db_column) == expected_vals[1]
    assert getattr(r1, index_neg1.db_column) == expected_vals[2]
    assert getattr(r1, first_field.db_column) == expected_vals[0]
    assert getattr(r1, last_field.db_column) == expected_vals[2]

    assert getattr(r2, index0.db_column) is None
    assert getattr(r2, first_field.db_column) is None

    # Row A3: single element — first and last are the same
    r3 = model.objects.get(id=row_a3.id)
    assert getattr(r3, first_field.db_column) == expected_vals[3]
    assert getattr(r3, last_field.db_column) == expected_vals[3]
    assert getattr(r3, index0.db_column) == expected_vals[3]
    assert getattr(r3, index_neg1.db_column) == expected_vals[3]

    # Formula-ref path must match
    assert getattr(r1, ref_first.db_column) == expected_vals[0]
    assert getattr(r1, ref_last.db_column) == expected_vals[2]
    assert getattr(r1, ref_index0.db_column) == expected_vals[0]
    assert getattr(r1, ref_index1.db_column) == expected_vals[1]
    assert getattr(r2, ref_first.db_column) is None
    assert getattr(r3, ref_first.db_column) == expected_vals[3]
    assert getattr(r3, ref_last.db_column) == expected_vals[3]

    RowHandler().update_rows(
        user,
        table_a,
        [
            {
                "id": row_a1.id,
                link_field.db_column: [r.id for r in rows_b],
            }
        ],
    )

    model = table_a.get_model()
    r1 = model.objects.get(id=row_a1.id)
    assert getattr(r1, last_field.db_column) == expected_vals[3]
    assert getattr(r1, ref_last.db_column) == expected_vals[3]

    RowHandler().update_rows(
        user,
        table_b,
        [{"id": rows_b[0].id, target_field.db_column: values[3]}],
    )

    model = table_a.get_model()
    r1 = model.objects.get(id=row_a1.id)
    assert getattr(r1, first_field.db_column) == expected_vals[3]
    assert getattr(r1, ref_first.db_column) == expected_vals[3]

    RowHandler().delete_rows(user, table_b, [rows_b[0].id])

    from baserow.contrib.database.views.handler import ViewHandler

    grid = ViewHandler().create_view(user, table_a, "grid", name="test")
    response = api_client.get(
        f"/api/database/views/grid/{grid.id}/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, (
        f"API crash after update/delete: {response.content.decode()[:300]}"
    )


@pytest.mark.django_db
def test_index_single_select(data_fixture):
    """index() on a single_select lookup returns the select option object."""

    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target, opt_a_id, opt_b_id, opt_c_id = _setup_single_select(data_fixture, table_b)

    row_b1, row_b2, row_b3 = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [
                {target.db_column: opt_a_id},
                {target.db_column: opt_b_id},
                {target.db_column: opt_c_id},
            ],
        )
        .created_rows
    )

    (row_a,) = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [{link_field.db_column: [row_b1.id, row_b2.id, row_b3.id]}],
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

    first_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="first_val",
        formula="first(field('lookup'))",
    )
    last_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="last_val",
        formula="last(field('lookup'))",
    )

    # Same via formula-ref path
    ref_target = FieldHandler().create_field(
        user,
        table_b,
        "formula",
        name="ref_target",
        formula=f"field('{target.name}')",
    )
    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_lookup",
        formula=f"lookup('{link_field.name}', '{ref_target.name}')",
    )
    ref_first = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_first_val",
        formula="first(field('ref_lookup'))",
    )
    ref_last = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_last_val",
        formula="last(field('ref_lookup'))",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)

    first_val = getattr(result, first_field.db_column)
    assert first_val["value"] == "Alpha"

    last_val = getattr(result, last_field.db_column)
    assert last_val["value"] == "Gamma"

    # Formula-ref path must match
    ref_first_val = getattr(result, ref_first.db_column)
    assert ref_first_val["value"] == "Alpha"
    ref_last_val = getattr(result, ref_last.db_column)
    assert ref_last_val["value"] == "Gamma"


@pytest.mark.django_db
def test_index_multiple_select(data_fixture):
    """index() on a multiple_select lookup returns the list of selected options."""

    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target = data_fixture.create_multiple_select_field(table=table_b, name="target")
    opt_a = data_fixture.create_select_option(field=target, value="Red", order=0)
    opt_b = data_fixture.create_select_option(field=target, value="Blue", order=1)
    opt_c = data_fixture.create_select_option(field=target, value="Green", order=2)

    row_b1, row_b2 = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [
                {target.db_column: [opt_a.id, opt_b.id]},  # Red, Blue
                {target.db_column: [opt_c.id]},  # Green
            ],
        )
        .created_rows
    )

    (row_a,) = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [{link_field.db_column: [row_b1.id, row_b2.id]}],
        )
        .created_rows
    )

    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', '{target.name}')",
    )

    first_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="first_val",
        formula="first(field('lookup'))",
    )
    last_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="last_val",
        formula="last(field('lookup'))",
    )

    # Same via formula-ref path
    ref_target = FieldHandler().create_field(
        user,
        table_b,
        "formula",
        name="ref_target",
        formula=f"field('{target.name}')",
    )
    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_lookup",
        formula=f"lookup('{link_field.name}', '{ref_target.name}')",
    )
    ref_first = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_first_val",
        formula="first(field('ref_lookup'))",
    )
    ref_last = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_last_val",
        formula="last(field('ref_lookup'))",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)

    first_val = getattr(result, first_field.db_column)
    assert isinstance(first_val, list)
    assert {o["value"] for o in first_val} == {"Red", "Blue"}

    last_val = getattr(result, last_field.db_column)
    assert isinstance(last_val, list)
    assert {o["value"] for o in last_val} == {"Green"}

    # Formula-ref path must match
    ref_first_val = getattr(result, ref_first.db_column)
    assert isinstance(ref_first_val, list)
    assert {o["value"] for o in ref_first_val} == {"Red", "Blue"}
    ref_last_val = getattr(result, ref_last.db_column)
    assert isinstance(ref_last_val, list)
    assert {o["value"] for o in ref_last_val} == {"Green"}


@pytest.mark.django_db
def test_index_out_of_bounds(data_fixture):
    """index() returns None for out-of-bounds indices."""

    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target = data_fixture.create_text_field(table=table_b, name="target")

    (row_b,) = (
        RowHandler()
        .create_rows(user, table_b, [{target.db_column: "only"}])
        .created_rows
    )

    (row_a,) = (
        RowHandler()
        .create_rows(user, table_a, [{link_field.db_column: [row_b.id]}])
        .created_rows
    )

    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', '{target.name}')",
    )

    oob_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="oob",
        formula="index(field('lookup'), 99)",
    )
    neg_oob = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="neg_oob",
        formula="index(field('lookup'), -99)",
    )

    # Same via formula-ref path
    ref_target = FieldHandler().create_field(
        user,
        table_b,
        "formula",
        name="ref_target",
        formula=f"field('{target.name}')",
    )
    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_lookup",
        formula=f"lookup('{link_field.name}', '{ref_target.name}')",
    )
    ref_oob = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_oob",
        formula="index(field('ref_lookup'), 99)",
    )
    ref_neg_oob = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_neg_oob",
        formula="index(field('ref_lookup'), -99)",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)
    assert getattr(result, oob_field.db_column) is None
    assert getattr(result, neg_oob.db_column) is None
    assert getattr(result, ref_oob.db_column) is None
    assert getattr(result, ref_neg_oob.db_column) is None


@pytest.mark.django_db
def test_index_on_empty_array(data_fixture):
    """index() on an empty lookup returns None."""

    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    data_fixture.create_text_field(table=table_b, name="target")

    (row_a,) = (
        RowHandler()
        .create_rows(user, table_a, [{link_field.db_column: []}])
        .created_rows
    )

    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', 'target')",
    )

    idx_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="idx",
        formula="index(field('lookup'), 0)",
    )

    # Same via formula-ref path
    ref_target = FieldHandler().create_field(
        user,
        table_b,
        "formula",
        name="ref_target",
        formula="field('target')",
    )
    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_lookup",
        formula=f"lookup('{link_field.name}', '{ref_target.name}')",
    )
    ref_idx = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_idx",
        formula="index(field('ref_lookup'), 0)",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)
    assert getattr(result, idx_field.db_column) is None
    assert getattr(result, ref_idx.db_column) is None


@pytest.mark.django_db
def test_first_array_unique_composability(data_fixture):
    """first(array_unique(lookup)) returns the first unique value."""

    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    target = data_fixture.create_text_field(table=table_b, name="target")

    rows_b = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [
                {target.db_column: "dup"},
                {target.db_column: "unique"},
                {target.db_column: "dup"},
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

    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', '{target.name}')",
    )

    first_unique = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="first_unique",
        formula="first(array_unique(field('lookup')))",
    )
    last_unique = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="last_unique",
        formula="last(array_unique(field('lookup')))",
    )

    # Same via formula-ref path
    ref_target = FieldHandler().create_field(
        user,
        table_b,
        "formula",
        name="ref_target",
        formula=f"field('{target.name}')",
    )
    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_lookup",
        formula=f"lookup('{link_field.name}', '{ref_target.name}')",
    )
    ref_first_unique = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_first_unique",
        formula="first(array_unique(field('ref_lookup')))",
    )
    ref_last_unique = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="ref_last_unique",
        formula="last(array_unique(field('ref_lookup')))",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)
    assert getattr(result, first_unique.db_column) == "dup"
    assert getattr(result, last_unique.db_column) == "unique"
    assert getattr(result, ref_first_unique.db_column) == "dup"
    assert getattr(result, ref_last_unique.db_column) == "unique"


@pytest.mark.django_db
def test_index_rejects_non_array(data_fixture):
    """index() on a non-array field produces a formula error."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="name", primary=True)

    with pytest.raises(InvalidFormulaType, match="array"):
        FieldHandler().create_field(
            user,
            table,
            "formula",
            name="bad",
            formula="index(field('name'), 0)",
        )


@pytest.mark.django_db
def test_index_file_field_still_works(data_fixture):
    """index() on a file array still works (backward compatibility)."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    file_field = data_fixture.create_file_field(table=table, name="files")

    user_file = data_fixture.create_user_file()
    RowHandler().create_rows(
        user,
        table,
        [
            {
                file_field.db_column: [
                    {"name": user_file.name, "visible_name": "test.txt"}
                ]
            }
        ],
    )

    idx_field = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="first_file",
        formula="index(field('files'), 0)",
    )

    model = table.get_model()
    result = model.objects.first()
    val = getattr(result, idx_field.db_column)
    # File index should return the file object (JSONB)
    assert val is not None
    assert "visible_name" in val


@pytest.mark.django_db
def test_index_nan_argument_returns_null(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    text_field = data_fixture.create_text_field(table=table_b, name="target")

    b_row = (
        RowHandler()
        .create_rows(user, table_b, [{text_field.db_column: "A"}])
        .created_rows[0]
    )

    row_a = (
        RowHandler()
        .create_rows(user, table_a, [{link_field.db_column: [b_row.id]}])
        .created_rows[0]
    )

    FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="lookup",
        formula=f"lookup('{link_field.name}', '{text_field.name}')",
    )

    nan_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="nan_index",
        formula="index(field('lookup'), tonumber('x'))",
    )
    div_zero_field = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="div_zero_index",
        formula="index(field('lookup'), 1/0)",
    )

    model = table_a.get_model()
    result = model.objects.get(id=row_a.id)
    assert getattr(result, nan_field.db_column) is None
    assert getattr(result, div_zero_field.db_column) is None
