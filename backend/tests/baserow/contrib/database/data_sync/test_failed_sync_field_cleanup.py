import pytest
import responses

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import (
    DataSyncSyncedProperty,
    SyncDataSyncTableJob,
)
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.core.jobs.handler import JobHandler

FEED = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
DTSTAMP:20240901T195345Z
UID:uid-1
DTSTART:20240901T100000Z
DTEND:20240901T110000Z
SUMMARY:Event 1
LOCATION:Amsterdam
END:VEVENT
END:VCALENDAR"""


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_failed_sync_job_does_not_leave_added_fields_behind(data_fixture):
    """
    The schema phase adds fields and synced properties before the rows are
    fetched. When the sync then fails, those fields must not stay behind as
    empty columns on a table that never received the matching rows.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    # `auto_add_new_properties` makes the schema phase add the remaining fields
    # on its own, so the failure has committed schema to leave behind.
    data_sync = DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="T",
        type_name="ical_calendar",
        synced_properties=["uid"],
        ical_url="https://baserow.io/ical.ics",
    )
    data_sync.auto_add_new_properties = True
    data_sync.save()

    fields_before = set(data_sync.table.field_set.values_list("id", flat=True))
    props_before = set(
        DataSyncSyncedProperty.objects.filter(data_sync=data_sync).values_list(
            "id", flat=True
        )
    )

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows

    def failing_get_all_rows(self, instance, progress_builder=None):
        # Drain the real generator so the schema phase has fully committed,
        # then fail the way an unreachable source would.
        list(original_get_all_rows(self, instance, progress_builder=progress_builder))
        raise RuntimeError("write phase boom")

    type(data_sync_type).get_all_rows = failing_get_all_rows
    try:
        with pytest.raises(RuntimeError):
            # Go through the real entry point: the job applies
            # `transaction_atomic_context`.
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    job = (
        SyncDataSyncTableJob.objects.filter(data_sync=data_sync).order_by("-id").first()
    )
    assert job is not None

    fields_after = set(data_sync.table.field_set.values_list("id", flat=True))
    props_after = set(
        DataSyncSyncedProperty.objects.filter(data_sync=data_sync).values_list(
            "id", flat=True
        )
    )
    row_count = data_sync.table.get_model().objects.count()

    assert fields_after - fields_before == set(), (
        f"the failed sync left {len(fields_after - fields_before)} new field(s) "
        f"committed on a table with {row_count} row(s)"
    )
    assert props_after - props_before == set(), (
        f"the failed sync left {len(props_after - props_before)} new "
        f"DataSyncSyncedProperty row(s) committed"
    )
    assert row_count == 0

    # The table must still sync cleanly afterwards.
    DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()
    assert data_sync.last_error is None
    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    assert len(rows) == 1

    summary_prop = DataSyncSyncedProperty.objects.get(
        data_sync=data_sync, key="summary"
    )
    assert getattr(rows[0], f"field_{summary_prop.field_id}") == "Event 1"


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_failed_sync_cleanup_leaves_table_with_a_primary_field(data_fixture):
    """
    The cleanup deletes fields with `allow_deleting_primary=True`, so it must not
    leave the table without a primary field: the table would be unusable and a
    later sync could not repair it.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    data_sync = DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="T",
        type_name="ical_calendar",
        synced_properties=["uid"],
        ical_url="https://baserow.io/ical.ics",
    )
    data_sync.auto_add_new_properties = True
    data_sync.save()

    fields_before = set(data_sync.table.field_set.values_list("id", flat=True))

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows

    def failing_get_all_rows(self, instance, progress_builder=None):
        list(original_get_all_rows(self, instance, progress_builder=progress_builder))
        raise RuntimeError("write phase boom")

    type(data_sync_type).get_all_rows = failing_get_all_rows
    try:
        with pytest.raises(RuntimeError):
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    assert data_sync.table.field_set.filter(primary=True).count() == 1, (
        "the cleanup left the table without exactly one primary field"
    )
    # Without this the test also passes with the cleanup removed entirely: it
    # only pins that the cleanup is not over-broad, not that it ran.
    assert (
        set(data_sync.table.field_set.values_list("id", flat=True)) == fields_before
    ), "the cleanup did not remove the fields the failed sync added"

    # And the table must still be syncable afterwards.
    DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    data_sync.refresh_from_db()
    assert data_sync.last_error is None
    assert data_sync.table.get_model().objects.count() == 1
