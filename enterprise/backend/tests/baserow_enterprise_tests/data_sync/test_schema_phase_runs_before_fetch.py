from django.db import transaction
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSyncSyncedProperty
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.contrib.database.fields.constants import DeleteFieldStrategyEnum
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import NumberField, TextField
from baserow.contrib.database.rows.handler import RowHandler


def _source_with_details(fixture, user):
    source_table = fixture.create_database_table(user=user, name="Source")
    name_field = fixture.create_text_field(
        table=source_table, name="Name", primary=True
    )
    details_field = fixture.create_text_field(
        table=source_table, name="Details", primary=False
    )
    RowHandler().create_row(
        user=user,
        table=source_table,
        values={f"field_{name_field.id}": "a", f"field_{details_field.id}": "hello"},
    )
    return source_table, name_field, details_field


def _synced(fixture, user, source_table, synced_properties, **kwargs):
    database = fixture.create_database_application(user=user)
    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=synced_properties,
        source_table_id=source_table.id,
        **kwargs,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)
    data_sync.refresh_from_db()
    assert data_sync.last_error is None
    return data_sync


def _synced_field(data_sync, key):
    return DataSyncSyncedProperty.objects.get(data_sync=data_sync, key=key).field


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_a_permanently_deleted_source_column_does_not_break_the_sync(
    enterprise_data_fixture, synced_roles
):
    """
    `local_baserow_table` fetches the enabled properties' columns from the source.
    A property whose source column is gone for good has to be removed before that
    fetch, or every following sync asks for a column that no longer exists.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    source_table, name_field, details_field = _source_with_details(
        enterprise_data_fixture, user
    )
    data_sync = _synced(
        enterprise_data_fixture,
        user,
        source_table,
        ["id", f"field_{name_field.id}", f"field_{details_field.id}"],
    )
    synced_details_field = _synced_field(data_sync, f"field_{details_field.id}")

    with transaction.atomic():
        FieldHandler().delete_field(
            user,
            details_field,
            delete_strategy=DeleteFieldStrategyEnum.PERMANENTLY_DELETE,
        )

    data_sync = DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)

    assert data_sync.last_error is None, (
        f"the sync failed after its source column was permanently deleted: "
        f"{data_sync.last_error}"
    )
    assert not data_sync.table.field_set.filter(id=synced_details_field.id).exists()
    assert data_sync.table.get_model().objects.count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_a_source_column_replaced_by_one_with_the_same_name_keeps_its_name(
    enterprise_data_fixture, synced_roles
):
    """
    The obsolete column is removed before the replacement is added, so the
    replacement can take its name instead of getting a `2` suffix.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    source_table, name_field, details_field = _source_with_details(
        enterprise_data_fixture, user
    )
    data_sync = _synced(
        enterprise_data_fixture,
        user,
        source_table,
        ["id", f"field_{name_field.id}", f"field_{details_field.id}"],
        auto_add_new_properties=True,
    )
    assert _synced_field(data_sync, f"field_{details_field.id}").name == "Details"

    FieldHandler().delete_field(user, details_field)
    new_details_field = FieldHandler().create_field(
        user=user, table=source_table, type_name="text", name="Details"
    )

    data_sync = DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)

    assert data_sync.last_error is None
    assert not DataSyncSyncedProperty.objects.filter(
        data_sync=data_sync, key=f"field_{details_field.id}"
    ).exists()
    replacement = _synced_field(data_sync, f"field_{new_details_field.id}")
    assert replacement.name == "Details", (
        f"the replacement column was named {replacement.name!r}"
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_a_changed_source_column_type_is_applied_even_when_the_fetch_fails(
    enterprise_data_fixture, synced_roles
):
    """
    The schema phase commits before the fetch, so a type change of a source
    column is applied to the synced column even when the fetch then fails. This
    is deliberate: the source column already has the new type, so the value in
    the old one can't survive a successful sync either, and the schema is
    already what the next sync needs.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    source_table, name_field, details_field = _source_with_details(
        enterprise_data_fixture, user
    )
    data_sync = _synced(
        enterprise_data_fixture,
        user,
        source_table,
        ["id", f"field_{name_field.id}", f"field_{details_field.id}"],
    )
    synced_details_field = _synced_field(data_sync, f"field_{details_field.id}")
    assert isinstance(synced_details_field.specific, TextField)
    model = data_sync.table.get_model()
    assert getattr(model.objects.first(), f"field_{synced_details_field.id}") == (
        "hello"
    )

    FieldHandler().update_field(user=user, field=details_field, new_type_name="number")

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows

    def failing_get_all_rows(self, instance, progress_builder=None):
        raise RuntimeError("fetch boom")

    type(data_sync_type).get_all_rows = failing_get_all_rows
    try:
        with pytest.raises(RuntimeError):
            DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    synced_details_field = _synced_field(data_sync, f"field_{details_field.id}")
    assert isinstance(synced_details_field.specific, NumberField), (
        "the fetch failed, and the schema change committed before it was rolled back"
    )
    model = data_sync.table.get_model()
    assert getattr(model.objects.first(), f"field_{synced_details_field.id}") is None

    data_sync = DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_error is None
