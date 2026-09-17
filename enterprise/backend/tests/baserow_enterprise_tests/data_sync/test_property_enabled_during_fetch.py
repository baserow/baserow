from django.test.utils import override_settings

import pytest

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSyncSyncedProperty
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_a_property_enabled_during_the_fetch_does_not_fail_the_write(
    enterprise_data_fixture, synced_roles
):
    """
    The write phase re-reads the enabled properties, deliberately, because they can
    change while the fetch is in flight. The fetched rows however were built from
    the property set as it was *before* the fetch: `local_baserow_table` (like
    `hubspot_contacts`) selects only the enabled properties' columns. Indexing a
    fetched row with a key enabled in between therefore raises a `KeyError`, which
    fails the whole run and loses every row it fetched.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    text_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text", primary=True
    )
    # The property that gets enabled while the fetch is in flight.
    late_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Late", primary=False
    )
    RowHandler().create_row(
        user=user,
        table=source_table,
        values={f"field_{text_field.id}": "a", f"field_{late_field.id}": "late value"},
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{text_field.id}"],
        source_table_id=source_table.id,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    all_properties = ["id", f"field_{text_field.id}", f"field_{late_field.id}"]
    enabled = {}

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original = type(data_sync_type).get_all_rows

    def enabling_get_all_rows(self, instance, progress_builder=None):
        # The rows are built here, against the property set as it is now.
        rows = list(original(self, instance, progress_builder=progress_builder))
        if not enabled:
            enabled["yes"] = True
            # ...and only then does the user enable a further property, the way a
            # concurrent `set_data_sync_synced_properties` request would.
            DataSyncHandler().set_data_sync_synced_properties(
                user, instance, synced_properties=all_properties
            )
        return rows

    type(data_sync_type).get_all_rows = enabling_get_all_rows
    try:
        handler.sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original

    assert enabled, "the concurrent property change never ran, so this proved nothing"

    data_sync.refresh_from_db()
    assert data_sync.last_error is None, (
        f"a property enabled while the fetch was in flight failed the whole sync: "
        f"{data_sync.last_error}"
    )
    assert data_sync.last_sync is not None, "the sync did not complete"

    # The rows fetched before the change are written, without the new property.
    model = data_sync.table.get_model()
    assert model.objects.count() == 1
    synced_text_field_id = DataSyncSyncedProperty.objects.get(
        data_sync=data_sync, key=f"field_{text_field.id}"
    ).field_id
    assert getattr(model.objects.first(), f"field_{synced_text_field_id}") == "a"

    # The next sync fetches with the new property included and fills it in.
    DataSyncHandler().set_data_sync_synced_properties(
        user, data_sync, synced_properties=all_properties
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()
    assert data_sync.last_error is None
    # A new field means a new generated model.
    model = data_sync.table.get_model()
    synced_late_field_id = DataSyncSyncedProperty.objects.get(
        data_sync=data_sync, key=f"field_{late_field.id}"
    ).field_id
    assert (
        getattr(model.objects.first(), f"field_{synced_late_field_id}") == "late value"
    ), "the property enabled mid-fetch was never populated by a following sync"
