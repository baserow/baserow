from django.test.utils import override_settings

import pytest

from baserow.contrib.database.data_sync.handler import DataSyncHandler


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sync_table_with_ai_field(enterprise_data_fixture, premium_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    field_1 = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text", primary=True
    )
    ai_field = premium_data_fixture.create_ai_field(
        table=source_table,
        name="ai_field",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="field('text_field')",
    )
    source_model = source_table.get_model()
    source_row_1 = source_model.objects.create(
        **{
            f"field_{field_1.id}": "Text field",
            f"field_{ai_field.id}": "AI Field value #1",
        }
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{field_1.id}", f"field_{ai_field.id}"],
        source_table_id=source_table.id,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    source_row_1.refresh_from_db()

    # We don't need AI calculations for this test. We just need value changed to
    # trigger the sync.
    setattr(source_row_1, f"field_{ai_field.id}", "AI Field value #2")
    source_row_1.save()

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    source_row_1.refresh_from_db()

    assert data_sync.last_sync is not None
    assert data_sync.last_error is None
