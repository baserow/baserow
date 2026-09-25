from django.conf import settings
from django.db import connection, transaction
from django.test.utils import override_settings

import psycopg2
import pytest

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.job_types import SyncDataSyncTableJobType
from baserow.contrib.database.data_sync.models import SyncDataSyncTableJob
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.core.action.registries import action_type_registry
from baserow.core.db import specific_iterator


def _make_two_way_pg_sync(user, database, source_table):
    default_database = settings.DATABASES["default"]
    return DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=["id", "text_col"],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=source_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )


def _edit_during_fetch(user, data_sync, field, target_id, value):
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows
    edited = {}

    def editing_get_all_rows(self, instance, progress_builder=None):
        rows = original_get_all_rows(self, instance, progress_builder=progress_builder)
        if not edited:
            with transaction.atomic():
                action_type_registry.get(UpdateRowsActionType.type).do(
                    user=user,
                    table=instance.table,
                    rows_values=[{"id": target_id, f"field_{field.id}": value}],
                )
            edited["yes"] = True
        return rows

    return data_sync_type, original_get_all_rows, editing_get_all_rows


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_unrelated_column_edit_during_fetch_does_not_defer_the_source_change(
    enterprise_data_fixture, create_postgresql_test_table, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    data_sync = _make_two_way_pg_sync(user, database, create_postgresql_test_table)
    handler = DataSyncHandler()
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    # A column the sync does not own, so the user may always write to it.
    notes_field = FieldHandler().create_field(
        user=user,
        table=data_sync.table,
        type_name="text",
        name="mynotes",
    )

    model = data_sync.table.get_model()
    target = model.objects.order_by("id").first()
    assert target is not None

    # Move the source, so the sync has a real change to apply to this row.
    with transaction.atomic():
        with transaction.get_connection().cursor() as cursor:
            cursor.execute(
                f"UPDATE {create_postgresql_test_table} SET text_col = %s "
                f"WHERE id = %s",
                ["source moved on", getattr(target, f"field_{fields[0].id}")],
            )

    data_sync_type, original, patched = _edit_during_fetch(
        user, data_sync, notes_field, target.id, "my note"
    )
    type(data_sync_type).get_all_rows = patched
    try:
        handler.sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original

    target.refresh_from_db()
    synced_value = getattr(target, f"field_{text_field.id}")
    note_value = getattr(target, f"field_{notes_field.id}")

    assert synced_value == "source moved on", (
        f"the user edited only the non-synced 'mynotes' column, touching no "
        f"synced value, but the source change was still not applied: the cell "
        f"holds {synced_value!r}"
    )
    assert note_value == "my note", (
        f"the user's edit to their own column was lost; it holds {note_value!r}"
    )


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_concurrent_synced_cell_edit_is_not_overwritten_by_a_stale_fetch(
    enterprise_data_fixture, create_postgresql_test_table, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    data_sync = _make_two_way_pg_sync(user, database, create_postgresql_test_table)
    handler = DataSyncHandler()
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    model = data_sync.table.get_model()
    target = model.objects.order_by("id").first()
    assert target is not None
    original_value = getattr(target, f"field_{text_field.id}")

    # The user's edit lands on the synced cell itself, during the fetch.
    data_sync_type, original, patched = _edit_during_fetch(
        user, data_sync, text_field, target.id, "USER EDIT DURING FETCH"
    )
    type(data_sync_type).get_all_rows = patched
    try:
        handler.sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original

    target.refresh_from_db()
    value = getattr(target, f"field_{text_field.id}")

    assert value == "USER EDIT DURING FETCH", (
        f"the user's edit to a synced cell was made during the fetch and pushed "
        f"to the source, but the sync wrote its pre-edit read back over it: the "
        f"cell holds {value!r} (the value before the edit was {original_value!r})"
    )

    # The sync must not have aborted to achieve that.
    data_sync.refresh_from_db()
    assert data_sync.last_error is None, (
        f"the sync reported an error instead of completing: {data_sync.last_error}"
    )
    assert data_sync.last_sync is not None, "the sync did not complete"


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_concurrent_synced_cell_edit_survives_a_sync_run_through_the_job(
    enterprise_data_fixture, create_postgresql_test_table, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    data_sync = _make_two_way_pg_sync(user, database, create_postgresql_test_table)
    handler = DataSyncHandler()
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    model = data_sync.table.get_model()
    target = model.objects.order_by("id").first()
    assert target is not None
    original_value = getattr(target, f"field_{text_field.id}")
    table_name = model._meta.db_table
    column = f"field_{text_field.id}"

    # Move the source as well, so the write phase has a real change to apply to
    # this very cell. Without this the sync finds the cell already equal to the
    # source, writes nothing, and never touches the row the concurrent edit
    # locked -- so the test would pass without exercising either half.
    source_id = getattr(target, f"field_{fields[0].id}")
    with transaction.atomic():
        with transaction.get_connection().cursor() as cursor:
            cursor.execute(
                f"UPDATE {create_postgresql_test_table} SET text_col = %s "
                f"WHERE id = %s",
                ["source moved on", source_id],
            )

    edited = {}

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows

    def editing_get_all_rows(self, instance, progress_builder=None):
        rows = original_get_all_rows(self, instance, progress_builder=progress_builder)
        if not edited:
            # A genuinely separate connection, committed independently. This is
            # what makes the base behaviour (a serialization failure against the
            # sync's REPEATABLE READ snapshot) reachable at all.
            params = connection.get_connection_params()
            params.pop("cursor_factory", None)
            second = psycopg2.connect(**params)
            try:
                second.autocommit = True
                with second.cursor() as cursor:
                    cursor.execute(
                        f'UPDATE "{table_name}" SET "{column}" = %s WHERE id = %s',
                        ["USER EDIT DURING FETCH", target.id],
                    )
            finally:
                second.close()
            edited["yes"] = True
        return rows

    job = SyncDataSyncTableJob.objects.create(user=user, data_sync=data_sync)
    job_type = SyncDataSyncTableJobType()

    type(data_sync_type).get_all_rows = editing_get_all_rows
    try:
        with job_type.transaction_atomic_context(job):
            handler.sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    assert edited, "the concurrent edit never ran, so the test proved nothing"

    target.refresh_from_db()
    value = getattr(target, f"field_{text_field.id}")

    assert value == "USER EDIT DURING FETCH", (
        f"an edit committed from another connection during the fetch was "
        f"overwritten by the sync's pre-edit read: the cell holds {value!r} "
        f"(the value before the edit was {original_value!r})"
    )

    data_sync.refresh_from_db()
    assert data_sync.last_error is None, (
        f"the sync reported an error instead of completing: {data_sync.last_error}"
    )
