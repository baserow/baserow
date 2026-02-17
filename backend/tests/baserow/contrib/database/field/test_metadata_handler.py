import threading

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.metadata_handler import (
    FieldMetadataHandler,
    MetadataUpdate,
)


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_set_and_get_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    metadata = {
        "status": "success",
        "generated_at": "2024-01-15T10:30:00Z",
        "version": 1,
    }
    FieldMetadataHandler.set_metadata(
        model, [MetadataUpdate(row_id=row.id, field_id=field.id, metadata=metadata)]
    )

    row.refresh_from_db()
    retrieved = (
        FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
        .get(row.id, {})
        .get(field.id)
    )

    assert retrieved is not None
    assert retrieved["status"] == "success"
    assert retrieved["generated_at"] == "2024-01-15T10:30:00Z"
    assert retrieved["version"] == 1


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_metadata_merge_behavior(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row.id, field_id=field1.id, metadata={"status": "field1_status"}
            )
        ],
    )

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row.id, field_id=field2.id, metadata={"status": "field2_status"}
            )
        ],
    )

    row.refresh_from_db()
    field1_meta = (
        FieldMetadataHandler.get_metadata(model, [row.id], [field1.id])
        .get(row.id, {})
        .get(field1.id)
    )
    field2_meta = (
        FieldMetadataHandler.get_metadata(model, [row.id], [field2.id])
        .get(row.id, {})
        .get(field2.id)
    )

    assert field1_meta["status"] == "field1_status"
    assert field2_meta["status"] == "field2_status"


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_bulk_set_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()
    row3 = model.objects.create()

    updates = [
        MetadataUpdate(
            row_id=row1.id, field_id=field.id, metadata={"status": "success"}
        ),
        MetadataUpdate(row_id=row2.id, field_id=field.id, metadata={"status": "error"}),
        MetadataUpdate(
            row_id=row3.id, field_id=field.id, metadata={"status": "pending"}
        ),
    ]
    FieldMetadataHandler.set_metadata(model, updates)

    row1.refresh_from_db()
    row2.refresh_from_db()
    row3.refresh_from_db()

    assert (
        FieldMetadataHandler.get_metadata(model, [row1.id], [field.id])
        .get(row1.id, {})
        .get(field.id)["status"]
        == "success"
    )
    assert (
        FieldMetadataHandler.get_metadata(model, [row2.id], [field.id])
        .get(row2.id, {})
        .get(field.id)["status"]
        == "error"
    )
    assert (
        FieldMetadataHandler.get_metadata(model, [row3.id], [field.id])
        .get(row3.id, {})
        .get(field.id)["status"]
        == "pending"
    )


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_delete_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row1.id, field_id=field.id, metadata={"status": "success"}
            )
        ],
    )
    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row2.id, field_id=field.id, metadata={"status": "success"}
            )
        ],
    )

    FieldMetadataHandler.delete_metadata(model, field.id)

    row1.refresh_from_db()
    row2.refresh_from_db()

    assert (
        FieldMetadataHandler.get_metadata(model, [row1.id], [field.id])
        .get(row1.id, {})
        .get(field.id)
        is None
    )
    assert (
        FieldMetadataHandler.get_metadata(model, [row2.id], [field.id])
        .get(row2.id, {})
        .get(field.id)
        is None
    )


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_delete_metadata_preserves_other_keys(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model, [MetadataUpdate(row_id=row.id, field_id=field1.id, metadata={"a": 1})]
    )
    FieldMetadataHandler.set_metadata(
        model, [MetadataUpdate(row_id=row.id, field_id=field2.id, metadata={"b": 2})]
    )

    FieldMetadataHandler.delete_metadata(model, field1.id)

    row.refresh_from_db()
    assert (
        FieldMetadataHandler.get_metadata(model, [row.id], [field1.id])
        .get(row.id, {})
        .get(field1.id)
        is None
    )
    assert FieldMetadataHandler.get_metadata(model, [row.id], [field2.id]).get(
        row.id, {}
    ).get(field2.id) == {"b": 2}


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_get_rows_by_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row_success = model.objects.create()
    row_error = model.objects.create()
    row_pending = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row_success.id, field_id=field.id, metadata={"status": "success"}
            )
        ],
    )
    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row_error.id, field_id=field.id, metadata={"status": "error"}
            )
        ],
    )
    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row_pending.id, field_id=field.id, metadata={"status": "pending"}
            )
        ],
    )

    error_rows = FieldMetadataHandler.get_rows_by_metadata(
        model, field.id, "status", "error"
    )

    assert error_rows.count() == 1
    assert error_rows.first().id == row_error.id


@pytest.mark.django_db
def test_get_rows_with_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row_with_meta = model.objects.create()
    row_without_meta = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row_with_meta.id,
                field_id=field.id,
                metadata={"status": "success"},
            )
        ],
    )

    rows_with_meta = FieldMetadataHandler.get_rows_with_metadata(model, field.id)

    assert rows_with_meta.count() == 1
    assert rows_with_meta.first().id == row_with_meta.id


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_graceful_degradation_without_column(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    table.field_metadata_column_added = False
    table.save()

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row.id, field_id=field.id, metadata={"status": "success"}
            )
        ],
    )
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
        .get(row.id, {})
        .get(field.id)
    )
    assert metadata is None

    rows = FieldMetadataHandler.get_rows_by_metadata(
        model, field.id, "status", "success"
    )
    assert rows.count() == 0


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_metadata_atomicity(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row.id,
                field_id=field.id,
                metadata={"status": "pending", "attempt": 1},
            )
        ],
    )

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row.id,
                field_id=field.id,
                metadata={"status": "success", "attempt": 2},
            )
        ],
    )

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
        .get(row.id, {})
        .get(field.id)
    )

    assert metadata["status"] == "success"
    assert metadata["attempt"] == 2


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_delete_metadata_for_specific_rows(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()
    row3 = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row1.id, field_id=field.id, metadata={"status": "generating"}
            )
        ],
    )
    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row2.id, field_id=field.id, metadata={"status": "generating"}
            )
        ],
    )
    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row3.id, field_id=field.id, metadata={"status": "generating"}
            )
        ],
    )

    FieldMetadataHandler.delete_metadata(model, field.id, row_ids=[row2.id, row3.id])

    row1.refresh_from_db()
    row2.refresh_from_db()
    row3.refresh_from_db()

    assert FieldMetadataHandler.get_metadata(model, [row1.id], [field.id]).get(
        row1.id, {}
    ).get(field.id) == {"status": "generating"}
    assert (
        FieldMetadataHandler.get_metadata(model, [row2.id], [field.id])
        .get(row2.id, {})
        .get(field.id)
        is None
    )
    assert (
        FieldMetadataHandler.get_metadata(model, [row3.id], [field.id])
        .get(row3.id, {})
        .get(field.id)
        is None
    )


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_delete_metadata_for_rows_preserves_other_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model, [MetadataUpdate(row_id=row.id, field_id=field1.id, metadata={"a": 1})]
    )
    FieldMetadataHandler.set_metadata(
        model, [MetadataUpdate(row_id=row.id, field_id=field2.id, metadata={"b": 2})]
    )

    FieldMetadataHandler.delete_metadata(model, field1.id, row_ids=[row.id])

    row.refresh_from_db()
    assert (
        FieldMetadataHandler.get_metadata(model, [row.id], [field1.id])
        .get(row.id, {})
        .get(field1.id)
        is None
    )
    assert FieldMetadataHandler.get_metadata(model, [row.id], [field2.id]).get(
        row.id, {}
    ).get(field2.id) == {"b": 2}


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_get_metadata_from_model(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    metadata = {"status": "success", "data": "test"}
    FieldMetadataHandler.set_metadata(
        model, [MetadataUpdate(row_id=row.id, field_id=field.id, metadata=metadata)]
    )

    retrieved = (
        FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
        .get(row.id, {})
        .get(field.id)
    )

    assert retrieved is not None
    assert retrieved["status"] == "success"
    assert retrieved["data"] == "test"


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_set_metadata_replace_mode(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [MetadataUpdate(row_id=row.id, field_id=field.id, metadata={"a": 1, "b": 2})],
    )

    FieldMetadataHandler.set_metadata(
        model,
        [MetadataUpdate(row_id=row.id, field_id=field.id, metadata={"c": 3})],
        merge=False,
    )

    row.refresh_from_db()
    metadata = (
        FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
        .get(row.id, {})
        .get(field.id)
    )

    assert metadata == {"c": 3}


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_get_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()
    row3 = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row1.id, field_id=field1.id, metadata={"status": "success"}
            ),
            MetadataUpdate(row_id=row1.id, field_id=field2.id, metadata={"count": 5}),
            MetadataUpdate(
                row_id=row2.id, field_id=field1.id, metadata={"status": "error"}
            ),
            # row3 has no metadata
        ],
    )

    result = FieldMetadataHandler.get_metadata(model, [row1.id, row2.id, row3.id])

    assert row1.id in result
    assert row2.id in result
    assert row3.id not in result

    assert result[row1.id][field1.id] == {"status": "success"}
    assert result[row1.id][field2.id] == {"count": 5}
    assert result[row2.id][field1.id] == {"status": "error"}


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_get_metadata_with_field_filter(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(row_id=row.id, field_id=field1.id, metadata={"a": 1}),
            MetadataUpdate(row_id=row.id, field_id=field2.id, metadata={"b": 2}),
        ],
    )

    result = FieldMetadataHandler.get_metadata(model, [row.id], field_ids=[field1.id])

    assert row.id in result
    assert field1.id in result[row.id]
    assert field2.id not in result[row.id]


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_get_metadata_empty_row_ids(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()

    result = FieldMetadataHandler.get_metadata(model, [])
    assert result == {}


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_get_metadata_without_metadata_column(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    table.field_metadata_column_added = False
    table.save()

    model = table.get_model()
    row = model.objects.create()

    result = FieldMetadataHandler.get_metadata(model, [row.id])
    assert result == {}


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_field_duplication_does_not_copy_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(
                row_id=row1.id, field_id=field.id, metadata={"status": "success"}
            ),
            MetadataUpdate(
                row_id=row2.id, field_id=field.id, metadata={"status": "error"}
            ),
        ],
    )

    original_metadata = FieldMetadataHandler.get_metadata(
        model, [row1.id, row2.id], [field.id]
    )
    assert row1.id in original_metadata
    assert row2.id in original_metadata
    assert original_metadata[row1.id][field.id] == {"status": "success"}
    assert original_metadata[row2.id][field.id] == {"status": "error"}

    duplicated_field, _ = FieldHandler().duplicate_field(
        user, field, duplicate_data=True
    )

    model = table.get_model()

    duplicated_metadata = FieldMetadataHandler.get_metadata(
        model, [row1.id, row2.id], [duplicated_field.id]
    )

    for row_id in [row1.id, row2.id]:
        if row_id in duplicated_metadata:
            assert duplicated_field.id not in duplicated_metadata[row_id]

    original_metadata_after = FieldMetadataHandler.get_metadata(
        model, [row1.id, row2.id], [field.id]
    )
    assert original_metadata_after[row1.id][field.id] == {"status": "success"}
    assert original_metadata_after[row2.id][field.id] == {"status": "error"}


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_on_field_deleted_clears_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [
            MetadataUpdate(row_id=row.id, field_id=field1.id, metadata={"a": 1}),
            MetadataUpdate(row_id=row.id, field_id=field2.id, metadata={"b": 2}),
        ],
    )

    FieldMetadataHandler.on_field_deleted(field1)

    row.refresh_from_db()
    result = FieldMetadataHandler.get_metadata(model, [row.id])
    assert result.get(row.id, {}).get(field1.id) is None
    assert result[row.id][field2.id] == {"b": 2}


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_on_field_updated_clears_metadata_on_type_change(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [MetadataUpdate(row_id=row.id, field_id=field.id, metadata={"status": "ok"})],
    )

    FieldMetadataHandler.on_field_updated(field, field_type_changed=True)

    row.refresh_from_db()
    result = FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
    assert result.get(row.id, {}).get(field.id) is None


@pytest.mark.row_metadata
@pytest.mark.django_db
def test_on_field_updated_preserves_metadata_when_type_unchanged(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    FieldMetadataHandler.set_metadata(
        model,
        [MetadataUpdate(row_id=row.id, field_id=field.id, metadata={"status": "ok"})],
    )

    FieldMetadataHandler.on_field_updated(field, field_type_changed=False)

    row.refresh_from_db()
    result = FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
    assert result[row.id][field.id] == {"status": "ok"}


@pytest.mark.row_metadata
@pytest.mark.django_db(transaction=True)
def test_concurrent_merge_updates_different_fields_preserve_both(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    barrier = threading.Barrier(2, timeout=5)
    errors = []

    def update_field(field_id, value):
        try:
            barrier.wait()
            FieldMetadataHandler.set_metadata(
                model,
                [MetadataUpdate(row_id=row.id, field_id=field_id, metadata=value)],
                merge=True,
            )
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=update_field, args=(field1.id, {"x": 1}))
    t2 = threading.Thread(target=update_field, args=(field2.id, {"y": 2}))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"Threads raised errors: {errors}"

    row.refresh_from_db()
    result = FieldMetadataHandler.get_metadata(model, [row.id])
    assert result[row.id][field1.id] == {"x": 1}
    assert result[row.id][field2.id] == {"y": 2}
