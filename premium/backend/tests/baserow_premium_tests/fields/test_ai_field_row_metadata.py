from unittest.mock import patch

from django.utils import timezone

import pytest

from baserow.contrib.database.fields.metadata_handler import (
    FieldMetadataHandler,
    MetadataUpdate,
)
from baserow.contrib.database.rows.registries import row_metadata_registry
from baserow_premium.fields.ai_field_metadata import (
    AIFieldMetadataHandler,
    AIMetadataKeys,
)


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_registered(premium_data_fixture):
    metadata_type = row_metadata_registry.get("ai_field")
    assert metadata_type is not None
    assert metadata_type.type == "ai_field"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_no_ai_fields(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    model = table.get_model()
    row = model.objects.create()

    metadata_type = row_metadata_registry.get("ai_field")
    result = metadata_type.generate_metadata_for_rows(user, table, [row.id])

    assert result == {}


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_no_metadata_column(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")
    model = table.get_model()
    row = model.objects.create()

    metadata_type = row_metadata_registry.get("ai_field")
    result = metadata_type.generate_metadata_for_rows(user, table, [row.id])

    assert result == {}


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_single_field(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    metadata_type = row_metadata_registry.get("ai_field")
    result = metadata_type.generate_metadata_for_rows(user, table, [row.id])

    assert row.id in result
    assert str(ai_field.id) in result[row.id]

    # API format: object with status key
    field_status = result[row.id][str(ai_field.id)]
    assert field_status == {"status": "generating"}


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_multiple_fields(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field1 = premium_data_fixture.create_ai_field(table=table, name="AI 1")
    ai_field2 = premium_data_fixture.create_ai_field(table=table, name="AI 2")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field1, row.id)
    AIFieldMetadataHandler.set_generating(ai_field2, row.id)
    AIFieldMetadataHandler.set_success(model, row.id, ai_field2.id)

    metadata_type = row_metadata_registry.get("ai_field")
    result = metadata_type.generate_metadata_for_rows(user, table, [row.id])

    assert row.id in result
    # Only generating status is shown
    assert str(ai_field1.id) in result[row.id]
    assert result[row.id][str(ai_field1.id)] == {"status": "generating"}

    # Success status is not shown
    assert str(ai_field2.id) not in result[row.id]


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_multiple_rows(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row1.id)
    AIFieldMetadataHandler.set_error(model, row2.id, ai_field.id, "Test error")

    metadata_type = row_metadata_registry.get("ai_field")
    result = metadata_type.generate_metadata_for_rows(user, table, [row1.id, row2.id])

    assert row1.id in result
    assert row2.id in result

    # API format: objects with status key
    assert result[row1.id][str(ai_field.id)] == {"status": "generating"}
    assert result[row2.id][str(ai_field.id)] == {"status": "error"}


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_status_transformation(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()

    metadata_type = row_metadata_registry.get("ai_field")

    # Status is derived from internal metadata structure
    # Test generating status (has start, no end)
    row_generating = model.objects.create()
    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row_generating.id,
                field_id=ai_field.id,
                metadata={AIMetadataKeys.START: timezone.now().timestamp()},
            )
        ],
        merge=False,
    )
    result = metadata_type.generate_metadata_for_rows(user, table, [row_generating.id])
    assert result[row_generating.id][str(ai_field.id)] == {"status": "generating"}

    # Test error status (has end, ok=False)
    row_error = model.objects.create()
    AIFieldMetadataHandler.set_error(model, row_error.id, ai_field.id, "Test error")
    result = metadata_type.generate_metadata_for_rows(user, table, [row_error.id])
    assert result[row_error.id][str(ai_field.id)] == {"status": "error"}

    # Test success status is not shown (has end, ok=True)
    row_success = model.objects.create()
    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row_success.id,
                field_id=ai_field.id,
                metadata={
                    AIMetadataKeys.START: timezone.now().timestamp(),
                    AIMetadataKeys.END: timezone.now().timestamp(),
                    AIMetadataKeys.OK: True,
                },
            )
        ],
        merge=False,
    )
    result = metadata_type.generate_metadata_for_rows(user, table, [row_success.id])
    assert row_success.id not in result

    # Test row without metadata is not shown
    row_no_metadata = model.objects.create()
    result = metadata_type.generate_metadata_for_rows(user, table, [row_no_metadata.id])
    assert row_no_metadata.id not in result


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_no_metadata_for_field(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row_with_metadata = model.objects.create()
    row_without_metadata = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row_with_metadata.id)

    metadata_type = row_metadata_registry.get("ai_field")
    result = metadata_type.generate_metadata_for_rows(
        user, table, [row_with_metadata.id, row_without_metadata.id]
    )

    assert row_with_metadata.id in result
    assert row_without_metadata.id not in result


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_error_expiration(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    # Set error with current timestamp
    AIFieldMetadataHandler.set_error(model, row.id, ai_field.id, "Test error")

    metadata_type = row_metadata_registry.get("ai_field")

    # Error should be visible immediately
    result = metadata_type.generate_metadata_for_rows(user, table, [row.id])
    assert result[row.id][str(ai_field.id)] == {"status": "error"}

    # Mock time to be after expiration (1 hour + 1 second)
    future_time = timezone.now().timestamp() + 3601

    with patch("django.utils.timezone.now") as mock_now:
        mock_now.return_value.timestamp.return_value = future_time

        # Error should not be visible after expiration
        result = metadata_type.generate_metadata_for_rows(user, table, [row.id])
        assert row.id not in result


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_type_serializer_field(premium_data_fixture):
    metadata_type = row_metadata_registry.get("ai_field")
    serializer_field = metadata_type.get_example_serializer_field()

    assert serializer_field is not None
    assert hasattr(serializer_field, "help_text")
    assert "status indicators" in serializer_field.help_text
