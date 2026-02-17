import pytest

from baserow.contrib.database.fields.metadata_handler import FieldMetadataHandler
from baserow_premium.fields.ai_field_metadata import (
    AIFieldMetadataHandler,
    AIGenerationStatus,
    AIMetadataKeys,
)


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_set_generating(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )

    assert metadata is not None
    assert AIMetadataKeys.START in metadata
    assert AIMetadataKeys.END not in metadata
    assert AIGenerationStatus.from_metadata(metadata) == AIGenerationStatus.GENERATING


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_set_success(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    AIFieldMetadataHandler.set_success(model, row.id, ai_field.id)

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )

    assert metadata is not None
    assert AIMetadataKeys.END in metadata
    assert metadata[AIMetadataKeys.OK] is True
    assert AIMetadataKeys.ERROR not in metadata
    assert AIGenerationStatus.from_metadata(metadata) == AIGenerationStatus.SUCCESS


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_set_error(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    AIFieldMetadataHandler.set_error(model, row.id, ai_field.id, "Test error message")

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )

    assert metadata is not None
    assert AIMetadataKeys.END in metadata
    assert metadata[AIMetadataKeys.OK] is False
    assert metadata[AIMetadataKeys.ERROR] == "Test error message"
    assert AIGenerationStatus.from_metadata(metadata) == AIGenerationStatus.ERROR


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_clear_metadata(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()
    row3 = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, [row1.id, row2.id, row3.id])

    row1.refresh_from_db()
    row2.refresh_from_db()
    row3.refresh_from_db()
    assert (
        FieldMetadataHandler.get_metadata(model, [row1.id], [ai_field.id])
        .get(row1.id, {})
        .get(ai_field.id)
        is not None
    )
    assert (
        FieldMetadataHandler.get_metadata(model, [row2.id], [ai_field.id])
        .get(row2.id, {})
        .get(ai_field.id)
        is not None
    )
    assert (
        FieldMetadataHandler.get_metadata(model, [row3.id], [ai_field.id])
        .get(row3.id, {})
        .get(ai_field.id)
        is not None
    )

    AIFieldMetadataHandler.clear_metadata(ai_field, [row2.id, row3.id])

    row1.refresh_from_db()
    row2.refresh_from_db()
    row3.refresh_from_db()

    assert (
        FieldMetadataHandler.get_metadata(model, [row1.id], [ai_field.id])
        .get(row1.id, {})
        .get(ai_field.id)
        is not None
    )
    assert (
        AIGenerationStatus.from_metadata(
            FieldMetadataHandler.get_metadata(model, [row1.id], [ai_field.id])
            .get(row1.id, {})
            .get(ai_field.id)
        )
        == AIGenerationStatus.GENERATING
    )
    assert (
        FieldMetadataHandler.get_metadata(model, [row2.id], [ai_field.id])
        .get(row2.id, {})
        .get(ai_field.id)
        is None
    )
    assert (
        FieldMetadataHandler.get_metadata(model, [row3.id], [ai_field.id])
        .get(row3.id, {})
        .get(ai_field.id)
        is None
    )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_generation_status_from_metadata(premium_data_fixture):
    assert AIGenerationStatus.from_metadata(None) is None
    assert AIGenerationStatus.from_metadata({}) is None

    assert (
        AIGenerationStatus.from_metadata({AIMetadataKeys.START: 1234567890})
        == AIGenerationStatus.GENERATING
    )

    # Has end with ok=True = SUCCESS
    assert (
        AIGenerationStatus.from_metadata(
            {
                AIMetadataKeys.START: 1234567890,
                AIMetadataKeys.END: 1234567900,
                AIMetadataKeys.OK: True,
            }
        )
        == AIGenerationStatus.SUCCESS
    )

    # Has end with ok=False = ERROR
    assert (
        AIGenerationStatus.from_metadata(
            {
                AIMetadataKeys.START: 1234567890,
                AIMetadataKeys.END: 1234567900,
                AIMetadataKeys.OK: False,
                AIMetadataKeys.ERROR: "Some error",
            }
        )
        == AIGenerationStatus.ERROR
    )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_set_generating_bulk(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()
    row3 = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, [row1.id, row2.id, row3.id])

    row1.refresh_from_db()
    row2.refresh_from_db()
    row3.refresh_from_db()

    for row in [row1, row2, row3]:
        metadata = (
            FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
            .get(row.id, {})
            .get(ai_field.id)
        )
        assert metadata is not None
        assert AIMetadataKeys.START in metadata
        assert (
            AIGenerationStatus.from_metadata(metadata) == AIGenerationStatus.GENERATING
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_set_error_truncates_long_message(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    long_error = "E" * 1000
    AIFieldMetadataHandler.set_error(model, row.id, ai_field.id, long_error)

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )

    assert metadata is not None
    assert AIMetadataKeys.ERROR in metadata

    error_message = metadata[AIMetadataKeys.ERROR]
    assert len(error_message) == AIFieldMetadataHandler.MAX_ERROR_MESSAGE_LENGTH
    assert error_message.endswith("...")


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_set_error_short_message_not_truncated(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    short_error = "Short error message"
    AIFieldMetadataHandler.set_error(model, row.id, ai_field.id, short_error)

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )

    assert metadata is not None
    assert metadata[AIMetadataKeys.ERROR] == short_error


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_set_generating_clears_previous_state(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row.id)
    AIFieldMetadataHandler.set_error(model, row.id, ai_field.id, "Previous error")

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )
    assert AIGenerationStatus.from_metadata(metadata) == AIGenerationStatus.ERROR
    assert AIMetadataKeys.END in metadata
    assert AIMetadataKeys.OK in metadata
    assert AIMetadataKeys.ERROR in metadata

    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )

    assert AIGenerationStatus.from_metadata(metadata) == AIGenerationStatus.GENERATING
    assert AIMetadataKeys.START in metadata
    assert AIMetadataKeys.END not in metadata
    assert AIMetadataKeys.OK not in metadata
    assert AIMetadataKeys.ERROR not in metadata


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_metadata_handler_set_generating_clears_success_state(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create()

    AIFieldMetadataHandler.set_generating(ai_field, row.id)
    AIFieldMetadataHandler.set_success(model, row.id, ai_field.id)

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )
    assert AIGenerationStatus.from_metadata(metadata) == AIGenerationStatus.SUCCESS

    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [ai_field.id])
        .get(row.id, {})
        .get(ai_field.id)
    )

    assert AIGenerationStatus.from_metadata(metadata) == AIGenerationStatus.GENERATING
    assert AIMetadataKeys.START in metadata
    assert AIMetadataKeys.END not in metadata
    assert AIMetadataKeys.OK not in metadata
