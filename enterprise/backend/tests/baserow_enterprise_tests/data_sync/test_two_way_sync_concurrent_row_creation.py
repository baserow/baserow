from django.conf import settings
from django.db import connection
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.contrib.database.rows.actions import (
    CreateRowActionType,
    DeleteRowActionType,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.db import specific_iterator


def _make_two_way_pg_sync(fixture, user, database, source_table):
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


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_two_way_row_created_during_fetch_is_not_deleted_by_that_sync(
    enterprise_data_fixture, create_postgresql_test_table, synced_roles
):
    """
    A two-way synced table is writable by a real user. If that user creates a
    row while the sync's fetch phase is still in flight, the post-fetch diff
    sees a row that is not in the fetched set. With `delete_unmatched_rows`
    (default True) that row becomes a delete candidate.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    data_sync = _make_two_way_pg_sync(
        enterprise_data_fixture, user, database, create_postgresql_test_table
    )
    DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()
    assert data_sync.delete_unmatched_rows is True
    assert data_sync.table.is_read_only_data_synced_table is False

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    text_field = fields[1]

    model = data_sync.table.get_model()
    created_during_fetch = {}

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows

    def slow_get_all_rows(self, instance, progress_builder=None):
        rows = original_get_all_rows(self, instance, progress_builder=progress_builder)
        if "id" not in created_during_fetch:
            # A user adds a row through the normal, permitted entry point while
            # the fetch is still running. No transaction or lock is held here.
            row = action_type_registry.get(CreateRowActionType.type).do(
                user=user,
                table=instance.table,
                values={f"field_{text_field.id}": "added during fetch"},
            )
            created_during_fetch["id"] = row.id
        return rows

    type(data_sync_type).get_all_rows = slow_get_all_rows
    try:
        DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    row_id = created_during_fetch["id"]
    assert model.objects.filter(id=row_id).exists(), (
        f"row {row_id}, created by a user through CreateRowActionType while the "
        f"fetch phase was running, was deleted by that same sync"
    )


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_two_way_row_deleted_during_fetch_is_not_created_again_by_that_sync(
    enterprise_data_fixture, create_postgresql_test_table, synced_roles
):
    """
    The mirror image of the test above. A user deletes a row while the fetch is
    in flight; the delete is pushed to the source, but the fetched data still
    holds the row. The post-fetch diff must not treat it as new and bring it
    back with a fresh id.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    data_sync = _make_two_way_pg_sync(
        enterprise_data_fixture, user, database, create_postgresql_test_table
    )
    DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows_before = model.objects.count()
    assert rows_before > 0
    target = model.objects.order_by("id").first()
    deleted_during_fetch = {}

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows

    def slow_get_all_rows(self, instance, progress_builder=None):
        rows = original_get_all_rows(self, instance, progress_builder=progress_builder)
        if "id" not in deleted_during_fetch:
            # The user deletes a row through the normal entry point while the
            # fetch is still running. The delete is pushed to the source.
            action_type_registry.get(DeleteRowActionType.type).do(
                user=user, table=instance.table, row_id=target.id
            )
            deleted_during_fetch["id"] = target.id
        return rows

    type(data_sync_type).get_all_rows = slow_get_all_rows
    try:
        DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    data_sync.refresh_from_db()
    assert data_sync.last_error is None
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {create_postgresql_test_table}")
        assert cursor.fetchone()[0] == rows_before - 1, (
            "the delete was not pushed to the source, so this test proves nothing"
        )
    assert model.objects.count() == rows_before - 1, (
        "the row a user deleted while the fetch was running was created again "
        "from the stale fetched data"
    )
