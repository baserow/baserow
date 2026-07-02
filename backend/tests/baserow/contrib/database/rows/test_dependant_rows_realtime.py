from contextlib import contextmanager

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.signals import dependant_rows_updated
from baserow.core.trash.handler import TrashHandler


@contextmanager
def capture_dependant_rows_updates():
    calls = []

    def receiver(sender, **kwargs):
        calls.append(kwargs)

    dependant_rows_updated.connect(receiver)
    try:
        yield calls
    finally:
        dependant_rows_updated.disconnect(receiver)


def _updates_by_table(calls):
    updates = {}
    for call in calls:
        for update in call["dependant_rows_updates"]:
            updates[update.table.id] = update
    return updates


@pytest.mark.django_db
def test_updating_a_row_sends_dependant_rows_updates_for_the_linked_table(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific
    lookup_a = data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'primary'), '')"
    )

    row_b1, row_b2 = (
        RowHandler()
        .create_rows(
            user, table_b, [{primary_b.db_column: "b1"}, {primary_b.db_column: "b2"}]
        )
        .created_rows
    )
    row_a1, row_a2 = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [{link_a_b.db_column: [row_b1.id]}, {link_a_b.db_column: [row_b2.id]}],
        )
        .created_rows
    )

    with capture_dependant_rows_updates() as calls:
        RowHandler().force_update_rows(
            user=user,
            table=table_b,
            rows_values=[{"id": row_b1.id, primary_b.db_column: "renamed"}],
        )

    updates = _updates_by_table(calls)
    # Only rows of table_a display values coming from the renamed row; row_a2
    # links to another row and must not be included.
    assert set(updates.keys()) == {table_a.id}
    assert updates[table_a.id].row_ids == [row_a1.id]
    assert set(updates[table_a.id].field_ids) == {lookup_a.id, link_a_b.id}
    assert updates[table_a.id].requires_refresh is False
    row_a1.refresh_from_db()
    assert getattr(row_a1, lookup_a.db_column) == "renamed"


@pytest.mark.django_db
def test_updating_a_row_sends_dependant_rows_updates_without_any_formula_field(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "b1"}])
        .created_rows[0]
    )
    row_a1 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])
        .created_rows[0]
    )

    with capture_dependant_rows_updates() as calls:
        RowHandler().force_update_rows(
            user=user,
            table=table_b,
            rows_values=[{"id": row_b1.id, primary_b.db_column: "renamed"}],
        )

    updates = _updates_by_table(calls)
    # The link row field resolves its display value at serialization time so no
    # SQL update runs, but the affected rows must still be found.
    assert set(updates.keys()) == {table_a.id}
    assert updates[table_a.id].row_ids == [row_a1.id]
    assert updates[table_a.id].field_ids == [link_a_b.id]


@pytest.mark.django_db
def test_creating_a_row_sends_dependant_rows_updates_for_the_linked_table(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific
    related_link_b = link_a_b.link_row_related_field

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "b1"}])
        .created_rows[0]
    )

    with capture_dependant_rows_updates() as calls:
        RowHandler().create_row(
            user=user, table=table_a, values={link_a_b.db_column: [row_b1.id]}
        )

    updates = _updates_by_table(calls)
    # The new row appears in row_b1's reverse link cell.
    assert table_b.id in updates
    assert updates[table_b.id].row_ids == [row_b1.id]
    assert related_link_b.id in updates[table_b.id].field_ids


@pytest.mark.django_db
def test_deleting_a_row_sends_dependant_rows_updates_for_the_linked_table(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific
    lookup_a = data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'primary'), '')"
    )

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "b1"}])
        .created_rows[0]
    )
    row_a1 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])
        .created_rows[0]
    )

    with capture_dependant_rows_updates() as calls:
        RowHandler().delete_row_by_id(user, table_b, row_b1.id)

    updates = _updates_by_table(calls)
    assert table_a.id in updates
    assert updates[table_a.id].row_ids == [row_a1.id]
    assert lookup_a.id in updates[table_a.id].field_ids
    row_a1.refresh_from_db()
    assert not getattr(row_a1, lookup_a.db_column)


@pytest.mark.django_db
def test_batch_deleting_rows_sends_dependant_rows_updates_for_the_linked_table(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific
    data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'primary'), '')"
    )

    row_b1, row_b2 = (
        RowHandler()
        .create_rows(
            user, table_b, [{primary_b.db_column: "b1"}, {primary_b.db_column: "b2"}]
        )
        .created_rows
    )
    row_a1 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id, row_b2.id]}])
        .created_rows[0]
    )

    with capture_dependant_rows_updates() as calls:
        RowHandler().delete_rows(user, table_b, [row_b1.id, row_b2.id])

    updates = _updates_by_table(calls)
    assert table_a.id in updates
    assert updates[table_a.id].row_ids == [row_a1.id]


@pytest.mark.django_db
def test_restoring_a_row_sends_dependant_rows_updates_for_the_linked_table(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific
    data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'primary'), '')"
    )

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "b1"}])
        .created_rows[0]
    )
    row_a1 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])
        .created_rows[0]
    )
    RowHandler().delete_row_by_id(user, table_b, row_b1.id)

    with capture_dependant_rows_updates() as calls:
        TrashHandler.restore_item(
            user, "row", row_b1.id, parent_trash_item_id=table_b.id
        )

    updates = _updates_by_table(calls)
    assert table_a.id in updates
    assert updates[table_a.id].row_ids == [row_a1.id]


@pytest.mark.django_db
def test_dependant_rows_are_not_collected_without_realtime_update(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "b1"}])
        .created_rows[0]
    )
    RowHandler().create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])

    # Imports, data sync and batch jobs pass send_realtime_update=False, so the
    # work of finding the affected rows must be skipped entirely.
    with (
        capture_dependant_rows_updates() as calls,
        CaptureQueriesContext(connection) as captured,
    ):
        RowHandler().force_update_rows(
            user=user,
            table=table_b,
            rows_values=[{"id": row_b1.id, primary_b.db_column: "renamed"}],
            send_realtime_update=False,
        )

    assert calls == []
    table_a_db_name = f"database_table_{table_a.id}"
    assert not any(
        query["sql"].startswith(f'SELECT "{table_a_db_name}"."id" FROM')
        for query in captured.captured_queries
    )


@pytest.mark.django_db
def test_no_dependant_rows_updates_sent_without_dependants(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    row = RowHandler().create_row(user=user, table=table, values={})

    with capture_dependant_rows_updates() as calls:
        RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[{"id": row.id, field.db_column: "changed"}],
        )

    assert calls == []


@pytest.mark.django_db
def test_formula_referencing_self_link_recalculates_rows_linking_to_updated_row(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    primary = data_fixture.create_text_field(table=table, primary=True, name="name")
    self_link = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        link_row_table=table,
        name="depend on",
    )
    formula = data_fixture.create_formula_field(
        table=table, formula="join(field('depend on'), ',')"
    )

    row_a = RowHandler().create_row(
        user=user, table=table, values={primary.db_column: "a"}
    )
    row_b = RowHandler().create_row(
        user=user, table=table, values={self_link.db_column: [row_a.id]}
    )
    row_b.refresh_from_db()
    assert getattr(row_b, formula.db_column) == "a"

    with capture_dependant_rows_updates() as calls:
        RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[{"id": row_a.id, primary.db_column: "renamed"}],
        )

    row_b.refresh_from_db()
    assert getattr(row_b, formula.db_column) == "renamed"
    updates = _updates_by_table(calls)
    assert updates[table.id].row_ids == [row_b.id]
    assert self_link.id in updates[table.id].field_ids
    assert formula.id in updates[table.id].field_ids
