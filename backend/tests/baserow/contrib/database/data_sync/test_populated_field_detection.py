from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.data_sync.handler import DataSyncHandler


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_factory,value",
    [
        ("create_boolean_field", False),
        ("create_number_field", 0),
        ("create_number_field", Decimal("0")),
        ("create_rating_field", 0),
    ],
)
def test_a_falsy_but_real_value_counts_as_populated(data_fixture, field_factory, value):
    """
    A 0 or a False is data the user can see. Treating it as empty would let the
    cleanup permanently delete a column that holds values.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = getattr(data_fixture, field_factory)(table=table, name="c")

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": value})

    populated = DataSyncHandler()._get_populated_field_ids(table, [field])

    assert populated == {field.id}, (
        f"{value!r} is a real value a user can see, but the field was reported "
        f"as empty, which would let the cleanup permanently delete it"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("empty_value", [None, ""])
def test_an_empty_text_cell_does_not_count_as_populated(data_fixture, empty_value):
    """
    The counterpart: a column holding only empty cells must be reported empty,
    otherwise the cleanup can never remove the fields a failed sync added.

    "" matters specifically because that -- not NULL -- is what a text column
    stores, so this is the case that must not be confused with real data.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="c")

    model = table.get_model()
    for _ in range(3):
        model.objects.create(**{f"field_{field.id}": empty_value})

    assert DataSyncHandler()._get_populated_field_ids(table, [field]) == set()


@pytest.mark.django_db
def test_only_the_field_that_holds_data_is_reported_as_populated(data_fixture):
    """Each field is judged on its own column, not on the row as a whole."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    empty_field = data_fixture.create_text_field(table=table, name="empty")
    filled_field = data_fixture.create_text_field(table=table, name="filled")

    model = table.get_model()
    model.objects.create(
        **{f"field_{empty_field.id}": "", f"field_{filled_field.id}": "real"}
    )

    populated = DataSyncHandler()._get_populated_field_ids(
        table, [empty_field, filled_field]
    )

    assert populated == {filled_field.id}


@pytest.mark.django_db
def test_a_failing_check_reports_every_field_as_populated(data_fixture):
    """
    Fail safe. If the emptiness check can't be made, the cleanup must assume the
    columns hold data, because the alternative is permanently deleting a field
    that does.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_a = data_fixture.create_text_field(table=table, name="a")
    field_b = data_fixture.create_text_field(table=table, name="b")

    with patch.object(type(table), "get_model", side_effect=Exception("boom")):
        populated = DataSyncHandler()._get_populated_field_ids(
            table, [field_a, field_b]
        )

    assert populated == {field_a.id, field_b.id}, (
        "the check failed, so every field must be reported as populated; "
        "anything else lets the cleanup permanently delete a field it could "
        "not verify was empty"
    )


@pytest.mark.django_db
def test_the_empty_case_does_not_scan_the_whole_table(data_fixture):
    """
    The empty case is the one that proceeds to permanently delete, and it is the
    one where every row matches the `NOT NULL` filter (a text column stores ""),
    so it is where an unbounded query hurts most.

    Asserting the SQL carries a LIMIT pins the bound itself rather than a
    timing, which would be flaky.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="c")

    model = table.get_model()
    model.objects.bulk_create([model(**{f"field_{field.id}": ""}) for _ in range(200)])

    with CaptureQueriesContext(connection) as captured:
        assert DataSyncHandler()._get_populated_field_ids(table, [field]) == set()

    row_queries = [
        q["sql"]
        for q in captured.captured_queries
        if f'"field_{field.id}"' in q["sql"]
        and q["sql"].lstrip().upper().startswith("SELECT")
    ]
    assert row_queries, "expected the check to query the field's column"
    for sql in row_queries:
        assert "LIMIT" in sql.upper(), (
            f"the emptiness check streams the whole table instead of stopping "
            f"at the first row: {sql}"
        )
