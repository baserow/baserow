import io
from unittest.mock import MagicMock
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_400_BAD_REQUEST

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.export.table_exporters.csv_table_exporter import (
    CsvQuerysetSerializer,
)
from baserow.contrib.database.fields.exceptions import (
    IncompatiblePrimaryFieldTypeError,
    RichTextImageLimitExceeded,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field, TextField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.rich_text_utils import (
    MAX_RICH_TEXT_IMAGES,
    count_image_references,
    extract_user_file_names,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.contrib.database.trash.models import TrashedRows
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_files.exceptions import UserFileDoesNotExist
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.models import UserFile


@pytest.mark.django_db
@pytest.mark.field_long_text
def test_rich_text_field_cannot_be_primary(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)

    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        FieldHandler().create_field(
            user=user,
            table=table,
            type_name="long_text",
            name="Primary",
            primary=True,
            long_text_enable_rich_text=True,
        )

    # A non rich text field can be used as primary field
    primary_field = FieldHandler().create_field(
        user=user, table=table, type_name="long_text", name="Primary", primary=True
    )

    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        FieldHandler().update_field(
            user=user,
            field=primary_field,
            new_type_name="long_text",
            long_text_enable_rich_text=True,
        )

    rich_text = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="long_text",
        name="Rich text",
        primary=False,
        long_text_enable_rich_text=True,
    )

    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        FieldHandler().change_primary_field(
            user=user, table=table, new_primary_field=rich_text
        )


@pytest.mark.django_db
def test_perm_deleting_rows_delete_rich_text_mentions(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )

    row_1, row_2, row_3 = (
        RowHandler()
        .create_rows(
            user=user,
            table=table,
            rows_values=[
                {field.db_column: f"Hello @{user.id}!"},
                {field.db_column: f"Ciao @{user.id}!"},
                {field.db_column: f"Hola @{user.id}!"},
            ],
        )
        .created_rows
    )

    mentions = RichTextFieldMention.objects.all()
    assert mentions.count() == 3
    assert list(mentions.values_list("row_id", flat=True).order_by("row_id")) == [
        row_1.id,
        row_2.id,
        row_3.id,
    ]

    TrashHandler.permanently_delete(row_1, table.id)
    mentions = RichTextFieldMention.objects.all()
    assert mentions.count() == 2
    assert list(mentions.values_list("row_id", flat=True).order_by("row_id")) == [
        row_2.id,
        row_3.id,
    ]

    trashed_rows = TrashedRows.objects.create(row_ids=[row_2.id, row_3.id], table=table)

    TrashHandler.permanently_delete(trashed_rows, table.id)

    assert RichTextFieldMention.objects.all().count() == 0


@pytest.mark.django_db
def test_rich_text_export_serialized_value_preserves_content(data_fixture, tmpdir):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, "photo.png", ContentFile(b"PNG_DATA"), storage=storage
    )

    model = table.get_model()
    content = f"Some text ![img][{user_file.name}] more"
    row = model.objects.create(**{field_name: content})

    result = field_type.get_export_serialized_value(
        row, field_name, {}, files_zip=None, storage=None
    )

    assert result == content
    assert user_file.name in result


@pytest.mark.django_db
def test_rich_text_export_serialized_value_no_images(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    model = table.get_model()
    row = model.objects.create(**{field_name: "Plain text only"})

    result = field_type.get_export_serialized_value(
        row, field_name, {}, files_zip=None, storage=None
    )

    assert result == "Plain text only"


@pytest.mark.django_db
def test_rich_text_import_serialized_value_rewrites_names(data_fixture, tmpdir):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zf:
        zf.writestr("abc123_def456.png", b"PNG_DATA")
    zip_buffer.seek(0)
    files_zip = ZipFile(zip_buffer, "r")

    model = table.get_model()
    row = model(**{field_name: ""})
    content = "Text ![img][abc123_def456.png] end"

    field_type.set_import_serialized_value(
        row, field_name, content, {}, {}, files_zip=files_zip, storage=storage
    )

    result = getattr(row, field_name)
    assert "abc123_def456.png" not in result
    assert "![img][" in result
    assert "] end" in result


@pytest.mark.django_db
def test_rich_text_import_preserves_alt_when_alt_matches_filename(data_fixture, tmpdir):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zf:
        zf.writestr("abc123_def456.png", b"PNG_DATA")
    zip_buffer.seek(0)
    files_zip = ZipFile(zip_buffer, "r")

    model = table.get_model()
    row = model(**{field_name: ""})
    content = "![abc123_def456.png][abc123_def456.png]"

    field_type.set_import_serialized_value(
        row, field_name, content, {}, {}, files_zip=files_zip, storage=storage
    )

    result = getattr(row, field_name)
    # Alt text must be preserved unchanged even though it matches the old filename
    assert result.startswith("![abc123_def456.png][")
    # The name bracket must have been rewritten to the new uploaded name
    assert result != content


@pytest.mark.django_db
def test_rich_text_import_same_storage_passthrough(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    model = table.get_model()
    row = model(**{field_name: ""})
    content = "Text ![img][abc123_def456.png] end"

    field_type.set_import_serialized_value(
        row, field_name, content, {}, {}, files_zip=None, storage=None
    )

    assert getattr(row, field_name) == content


@pytest.mark.django_db
def test_rich_text_get_export_value_resolves_urls(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    user_file = data_fixture.create_user_file(
        original_name="test.png", original_extension="png"
    )

    field_type = field_type_registry.get_by_model(field)
    field_object = {"field": field, "type": field_type, "name": f"field_{field.id}"}

    content = f"![img][{user_file.name}]"
    result = field_type.get_export_value(content, field_object)

    assert result != content
    assert "user_files/" in result
    assert result.startswith("![img](")


@pytest.mark.django_db
def test_rich_text_get_export_value_is_idempotent_for_resolved_values(data_fixture):
    """
    A stored value can already carry a resolved URL, so `get_export_value` must
    strip before appending or the cell exports as `![alt](fresh)(stale)`.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    user_file = data_fixture.create_user_file(
        original_name="photo.png", is_image=True, original_extension="png"
    )

    field_type = field_type_registry.get_by_model(field)
    field_object = {"field": field, "type": field_type, "name": f"field_{field.id}"}

    stored = f"hi ![photo][{user_file.name}](http://old-instance/media/x.png) bye"
    result = field_type.get_export_value(stored, field_object)

    assert ")(" not in result
    assert "old-instance" not in result


@pytest.mark.django_db
def test_rich_text_import_does_not_persist_a_stale_resolved_url(data_fixture):
    """
    An archive can carry URLs pointing at storage this instance does not own, so
    the import path must strip them back to the stored `![alt][name]` form.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    user_file = data_fixture.create_user_file(
        original_name="photo.png", is_image=True, original_extension="png"
    )
    model = table.get_model()
    row = model.objects.create()
    field_type = field_type_registry.get_by_model(field)

    field_type.set_import_serialized_value(
        row,
        f"field_{field.id}",
        f"hi ![photo][{user_file.name}](http://old-instance/media/x.png) bye",
        {},
        {},
        files_zip=None,
        storage=None,
    )
    row.save()
    row.refresh_from_db()

    stored = getattr(row, f"field_{field.id}")

    assert "old-instance" not in stored
    assert f"![photo][{user_file.name}]" in stored


@pytest.mark.django_db
def test_rich_text_get_export_value_text_only_unchanged(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )

    field_type = field_type_registry.get_by_model(field)
    field_object = {"field": field, "type": field_type, "name": f"field_{field.id}"}

    result = field_type.get_export_value("Plain text", field_object)
    assert result == "Plain text"


@pytest.mark.django_db
def test_rich_text_export_serialized_value_packs_files_into_zip(data_fixture, tmpdir):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, "photo.png", ContentFile(b"PNG_DATA"), storage=storage
    )

    model = table.get_model()
    content = f"Some text ![img][{user_file.name}] more"
    row = model.objects.create(**{field_name: content})

    files_zip = MagicMock()
    files_zip.info_list.return_value = []

    cache = {}
    result = field_type.get_export_serialized_value(
        row, field_name, cache, files_zip=files_zip, storage=storage
    )

    assert isinstance(result, dict)
    assert result["content"] == content
    assert len(result["images"]) == 1
    assert result["images"][0]["name"] == user_file.name
    assert result["images"][0]["original_name"] == user_file.original_name
    files_zip.add.assert_called_once()
    call_args = files_zip.add.call_args
    assert call_args[0][1] == user_file.name


@pytest.mark.django_db
def test_rich_text_export_serialized_value_skips_existing_zip_entry(
    data_fixture, tmpdir
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, "photo.png", ContentFile(b"PNG_DATA"), storage=storage
    )

    model = table.get_model()
    content = f"![img][{user_file.name}]"
    row = model.objects.create(**{field_name: content})

    files_zip = MagicMock()
    files_zip.info_list.return_value = [{"name": user_file.name}]

    cache = {}
    field_type.get_export_serialized_value(
        row, field_name, cache, files_zip=files_zip, storage=storage
    )

    files_zip.add.assert_not_called()


@pytest.mark.django_db
def test_rich_text_import_only_replaces_inside_image_refs(data_fixture, tmpdir):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zf:
        zf.writestr("abc123_def456.png", b"PNG_DATA")
    zip_buffer.seek(0)
    files_zip = ZipFile(zip_buffer, "r")

    model = table.get_model()
    row = model(**{field_name: ""})
    content = "See file abc123_def456.png and ![img][abc123_def456.png] here"

    field_type.set_import_serialized_value(
        row, field_name, content, {}, {}, files_zip=files_zip, storage=storage
    )

    result = getattr(row, field_name)
    assert "See file abc123_def456.png" in result
    assert "![img][abc123_def456.png]" not in result


@pytest.mark.django_db
def test_rich_text_import_uses_cache_for_same_filename(data_fixture, tmpdir):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zf:
        zf.writestr("abc123_def456.png", b"PNG_DATA")
    zip_buffer.seek(0)
    files_zip = ZipFile(zip_buffer, "r")

    model = table.get_model()
    cache = {}

    row1 = model(**{field_name: ""})
    field_type.set_import_serialized_value(
        row1,
        field_name,
        "![img][abc123_def456.png]",
        {},
        cache,
        files_zip=files_zip,
        storage=storage,
    )

    row2 = model(**{field_name: ""})
    field_type.set_import_serialized_value(
        row2,
        field_name,
        "![pic][abc123_def456.png]",
        {},
        cache,
        files_zip=files_zip,
        storage=storage,
    )

    result1 = getattr(row1, field_name)
    result2 = getattr(row2, field_name)
    new_name_1 = result1.split("[")[-1].rstrip("]")
    new_name_2 = result2.split("[")[-1].rstrip("]")
    assert new_name_1 == new_name_2


@pytest.mark.django_db
def test_rich_text_get_export_value_multiple_images(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    user_file_1 = data_fixture.create_user_file(
        original_name="a.png", original_extension="png"
    )
    user_file_2 = data_fixture.create_user_file(
        original_name="b.jpg", original_extension="jpg"
    )

    field_type = field_type_registry.get_by_model(field)
    field_object = {"field": field, "type": field_type, "name": f"field_{field.id}"}

    content = f"![a][{user_file_1.name}] text ![b][{user_file_2.name}]"
    result = field_type.get_export_value(content, field_object)

    assert f"[{user_file_1.name}]" not in result
    assert f"[{user_file_2.name}]" not in result
    assert "![a](" in result
    assert "![b](" in result
    assert "user_files/" in result


@pytest.mark.django_db
def test_rich_text_get_export_value_preserves_nonimage_brackets(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    user_file = data_fixture.create_user_file(
        original_name="test.png", original_extension="png"
    )

    field_type = field_type_registry.get_by_model(field)
    field_object = {"field": field, "type": field_type, "name": f"field_{field.id}"}

    content = f"[link](url) and ![img][{user_file.name}]"
    result = field_type.get_export_value(content, field_object)

    assert result.startswith("[link](url) and ![img](")
    assert "user_files/" in result


@pytest.mark.django_db
def test_csv_export_mixed_field_types_with_rich_text_images(data_fixture):
    """CSV export via CsvQuerysetSerializer works when a table has both a
    LongText field (with images) and a NumberField.  This exercises the
    ``_get_field_serializer`` path where ``get_export_value`` is called
    without a ``cache`` kwarg — the critical bug-fix scenario."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    rich_field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    number_field = data_fixture.create_number_field(table=table, name="Count")
    user_file = data_fixture.create_user_file(
        original_name="photo.png", original_extension="png"
    )

    model = table.get_model()
    content = f"Text ![img][{user_file.name}] end"
    model.objects.create(
        **{f"field_{rich_field.id}": content, f"field_{number_field.id}": 42}
    )

    serializer = CsvQuerysetSerializer.for_table(table)

    # Collect rows written by the serializer callbacks
    written_rows = []

    def fake_write_rows(queryset, write_row, progress_weight=100):
        for i, row in enumerate(queryset):
            is_last = i == len(queryset) - 1
            write_row(row, is_last)

    mock_file = MagicMock()
    csv_writer = MagicMock()
    mock_file.get_csv_dict_writer.return_value = csv_writer
    mock_file.write_rows.side_effect = fake_write_rows

    serializer.write_to_file(mock_file)

    all_writerow_calls = [call[0][0] for call in csv_writer.writerow.call_args_list]
    # First writerow is the header, second is the data row
    assert len(all_writerow_calls) == 2
    data_row = all_writerow_calls[1]
    rich_field_key = f"field_{rich_field.id}"
    number_field_key = f"field_{number_field.id}"

    assert rich_field_key in data_row
    assert number_field_key in data_row
    # Rich text value should have resolved URL (![img](url) format)
    assert "user_files/" in data_row[rich_field_key]
    # Number field should have its value
    assert "42" in data_row[number_field_key]


@pytest.mark.django_db
def test_ws_broadcast_serializer_resolves_rich_text_urls(data_fixture):
    """Rows serialized for WebSocket broadcast (is_response=True) should
    contain resolved ``![img][name](url)`` URLs in rich text fields."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    user_file = data_fixture.create_user_file(
        original_name="ws_test.png", original_extension="png"
    )

    model = table.get_model()
    content = f"WS ![img][{user_file.name}]"
    row = model.objects.create(**{f"field_{field.id}": content})

    serializer_class = get_row_serializer_class(model, RowSerializer, is_response=True)
    data = serializer_class(row).data
    field_key = f"field_{field.id}"

    assert f"![img][{user_file.name}](" in data[field_key]
    assert "user_files/" in data[field_key]


@pytest.mark.django_db
def test_export_serialized_value_missing_storage_file(data_fixture, tmpdir):
    """``files_zip.add`` only enqueues a lazy chunk generator, so a missing file
    would otherwise blow up when the zip is streamed. The export must check
    existence up front and skip the file instead of enqueueing it."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, "photo.png", ContentFile(b"PNG_DATA"), storage=storage
    )

    # Delete the actual file from storage so it is missing
    file_path = handler.user_file_path(user_file.name)
    storage.delete(file_path)

    model = table.get_model()
    content = f"Some text ![img][{user_file.name}] more"
    row = model.objects.create(**{field_name: content})
    row_2 = model.objects.create(**{field_name: content})

    files_zip = MagicMock()
    files_zip.info_list.return_value = []

    cache = {}
    result = field_type.get_export_serialized_value(
        row, field_name, cache, files_zip=files_zip, storage=storage
    )
    result_2 = field_type.get_export_serialized_value(
        row_2, field_name, cache, files_zip=files_zip, storage=storage
    )

    # Missing file skipped — content returned as plain string, no image metadata,
    # nothing enqueued into the zip and the miss is cached across rows.
    assert result == content
    assert result_2 == content
    files_zip.add.assert_not_called()
    assert user_file.name not in cache.get("_zip_names", set())
    assert f"user_file_{user_file.name}" not in cache
    assert cache["_missing_user_files"] == {user_file.name}


@pytest.mark.django_db
def test_import_serialized_value_missing_zip_entry(data_fixture, tmpdir):
    """``set_import_serialized_value`` should not raise when the zip file
    does not contain the referenced image. The content is set on the row
    with the original filename preserved (not replaced)."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    # Create an empty zip — no files at all
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zf:
        pass  # deliberately empty
    zip_buffer.seek(0)
    files_zip = ZipFile(zip_buffer, "r")

    model = table.get_model()
    row = model(**{field_name: ""})
    content = "Text ![img][abc123_def456.png] end"

    field_type.set_import_serialized_value(
        row, field_name, content, {}, {}, files_zip=files_zip, storage=storage
    )

    result = getattr(row, field_name)
    # Original filename is preserved since it could not be re-uploaded
    assert "![img][abc123_def456.png]" in result
    assert result == content


def _rich_text_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    return user, table, field, field_type_registry.get_by_model(field)


@pytest.mark.django_db
def test_prepare_value_for_db_accepts_existing_image(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(original_name="a.png", is_image=True)
    value = f"text ![alt][{user_file.name}]"

    assert field_type.prepare_value_for_db(field, value) == value


@pytest.mark.django_db
def test_prepare_value_for_db_rejects_missing_user_file(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)

    with pytest.raises(UserFileDoesNotExist) as exc:
        field_type.prepare_value_for_db(field, "![x][zzzz_yyyy.png]")

    assert exc.value.file_names_or_ids == ["zzzz_yyyy.png"]


@pytest.mark.django_db
def test_prepare_value_for_db_rejects_non_image_user_file(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(original_name="doc.pdf", is_image=False)

    with pytest.raises(ValidationError) as exc:
        field_type.prepare_value_for_db(field, f"![x][{user_file.name}]")

    assert exc.value.code == "not_an_image"


@pytest.mark.django_db
def test_prepare_value_for_db_accepts_svg_user_file(data_fixture):
    """SVG uploads are neutralized (``is_image=False``) because they are active
    content when opened directly, but they are safe to embed via ``<img>``."""

    _, _, field, field_type = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(
        original_name="logo.svg", is_image=False, mime_type="application/octet-stream"
    )
    value = f"![logo][{user_file.name}]"

    assert field_type.prepare_value_for_db(field, value) == value


@pytest.mark.django_db
def test_prepare_value_for_db_keeps_external_images_as_written(data_fixture):
    """The frontend decides whether an external image is shown, so the stored
    value keeps it exactly as written, whatever markdown form it takes."""

    _, _, field, field_type = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(original_name="a.png", is_image=True)
    value = (
        f"![ok][{user_file.name}] ![ext](https://example.com/p.gif) "
        "![inline](data:image/png;base64,AAAA)\n\n"
        "![logo][remote]\n\n[remote]: https://example.com/p.gif"
    )

    assert field_type.prepare_value_for_db(field, value) == value
    assert field_type.prepare_value_for_db_in_bulk(field, {0: value}) == {0: value}


@pytest.mark.django_db
def test_prepare_value_for_db_ignores_non_rich_text_and_empty(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    plain = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=False
    )
    field_type = field_type_registry.get_by_model(plain)
    value = "![x][zzzz_yyyy.png] ![y](https://evil.com/p.gif)"

    assert field_type.prepare_value_for_db(plain, value) == value
    assert field_type.prepare_value_for_db(plain, None) is None
    assert field_type.prepare_value_for_db(plain, "") == ""


@pytest.mark.django_db
def test_prepare_value_for_db_limits_image_count(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)
    value = " ".join(
        f"![x][{'a' * 8}{i:04d}_hash.png]" for i in range(MAX_RICH_TEXT_IMAGES + 1)
    )

    with pytest.raises(ValidationError) as exc:
        field_type.prepare_value_for_db(field, value)

    assert exc.value.code == "too_many_images"


@pytest.mark.django_db
def test_prepare_value_for_db_in_bulk_single_query(
    data_fixture, django_assert_num_queries
):
    _, _, field, field_type = _rich_text_field(data_fixture)
    files = [
        data_fixture.create_user_file(original_name=f"{i}.png", is_image=True)
        for i in range(5)
    ]
    values_by_row = {
        i: f"row {i} ![a][{files[i % 5].name}] ![b][{files[(i + 1) % 5].name}] "
        "![ext](https://evil.com/x.png)"
        for i in range(50)
    }
    values_by_row[50] = None
    values_by_row[51] = "no images here"

    with django_assert_num_queries(1):
        result = field_type.prepare_value_for_db_in_bulk(field, values_by_row)

    assert result[0] == (
        f"row 0 ![a][{files[0].name}] ![b][{files[1].name}] "
        "![ext](https://evil.com/x.png)"
    )
    assert result[50] is None
    assert result[51] == "no images here"


@pytest.mark.django_db
def test_prepare_value_for_db_in_bulk_errors(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)
    ok = data_fixture.create_user_file(original_name="a.png", is_image=True)
    pdf = data_fixture.create_user_file(original_name="a.pdf", is_image=False)
    values_by_row = {
        0: f"![a][{ok.name}]",
        1: "![m][zzzz_yyyy.png]",
        2: f"![p][{pdf.name}]",
    }

    with pytest.raises(UserFileDoesNotExist):
        field_type.prepare_value_for_db_in_bulk(field, dict(values_by_row))

    result = field_type.prepare_value_for_db_in_bulk(
        field, dict(values_by_row), continue_on_error=True
    )
    assert result[0] == f"![a][{ok.name}]"
    assert isinstance(result[1], UserFileDoesNotExist)
    assert isinstance(result[2], ValidationError)
    assert result[2].code == "not_an_image"


@pytest.mark.django_db
def test_prepare_value_for_db_in_bulk_non_rich_text_untouched(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    plain = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=False
    )
    field_type = field_type_registry.get_by_model(plain)
    values_by_row = {0: "![x][zzzz_yyyy.png]", 1: None}

    assert field_type.prepare_value_for_db_in_bulk(plain, dict(values_by_row)) == (
        values_by_row
    )


@pytest.mark.django_db
def test_row_handler_batch_create_validates_rich_text_images(data_fixture):
    user, table, field, _ = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(original_name="a.png", is_image=True)

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    field.db_column: f"![a][{user_file.name}] ![e](https://evil.com/x.png)"
                },
                {field.db_column: "plain"},
            ],
        )
        .created_rows
    )
    assert getattr(rows[0], field.db_column) == (
        f"![a][{user_file.name}] ![e](https://evil.com/x.png)"
    )

    with pytest.raises(UserFileDoesNotExist):
        RowHandler().create_rows(
            user, table, rows_values=[{field.db_column: "![m][zzzz_yyyy.png]"}]
        )


@pytest.mark.django_db
def test_get_human_readable_value_uses_alt_text(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)
    field_object = {"field": field}
    value = (
        r"Intro ![my \[photo\]][abc_def.png] mid "
        "![second][ghi_jkl.jpg](https://storage/ghi_jkl.jpg) "
        "![](https://ext.example/x.png) end"
    )

    assert field_type.get_human_readable_value(value, field_object) == (
        "Intro my [photo] mid second ![](https://ext.example/x.png) end"
    )
    assert field_type.get_human_readable_value(None, field_object) == ""
    assert field_type.get_human_readable_value("", field_object) == ""


@pytest.mark.django_db
def test_get_human_readable_value_non_rich_text_unchanged(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    plain = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=False
    )
    field_type = field_type_registry.get_by_model(plain)
    value = "![alt][abc_def.png]"

    assert field_type.get_human_readable_value(value, {"field": plain}) == value


@pytest.mark.django_db
def test_get_export_value_non_rich_text_unchanged(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    plain = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=False
    )
    field_type = field_type_registry.get_by_model(plain)
    value = "![alt][abc_def.png]"

    assert field_type.get_export_value(value, {"field": plain}) == value


@pytest.mark.django_db
def test_import_serialized_value_keeps_external_images_as_written(data_fixture):
    _, table, field, field_type = _rich_text_field(data_fixture)
    model = table.get_model()

    for value in [
        "![e](https://example.com/x.png)",
        "![logo][remote]\n\n[remote]: https://example.com/p.gif",
    ]:
        row = model()
        field_type.set_import_serialized_value(
            row, field.db_column, value, {}, {}, None, None
        )
        assert getattr(row, field.db_column) == value


@pytest.mark.django_db
def test_rich_text_import_backfills_bytes_when_user_file_is_deduplicated(
    data_fixture, tmpdir
):
    """A zip import into a different storage must still write the image bytes.

    `UserFileHandler.upload_user_file` deduplicates on
    `(original_name, sha256_hash)` and returns the existing row without writing
    anything to the storage it was passed. Rich text passes the true human
    `original_name`, so re-importing into a database that already holds that row
    used to leave the cell pointing at files absent from the destination storage.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    field_name = f"field_{field.id}"
    field_type = field_type_registry.get_by_model(field)

    source_storage = FileSystemStorage(
        location=str(tmpdir.mkdir("source")), base_url="http://localhost"
    )
    destination_storage = FileSystemStorage(
        location=str(tmpdir.mkdir("destination")), base_url="http://localhost"
    )

    image_bytes = b"PNG_DATA_FOR_DEDUP_BACKFILL"
    user_file_handler = UserFileHandler()
    user_file = user_file_handler.upload_user_file(
        user, "one.png", ContentFile(image_bytes), storage=source_storage
    )

    # The export packs the file under its storage name and records the human name.
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zf:
        zf.writestr(user_file.name, image_bytes)
    zip_buffer.seek(0)
    files_zip = ZipFile(zip_buffer, "r")

    serialized = {
        "content": f"Text ![one][{user_file.name}] end",
        "images": [{"name": user_file.name, "original_name": "one.png"}],
    }

    model = table.get_model()
    row = model(**{field_name: ""})

    field_type.set_import_serialized_value(
        row,
        field_name,
        serialized,
        {},
        {},
        files_zip=files_zip,
        storage=destination_storage,
    )

    result = getattr(row, field_name)
    imported_names = extract_user_file_names(result)
    assert imported_names, f"no user file names left in imported content: {result!r}"

    for name in imported_names:
        path = user_file_handler.user_file_path(name)
        assert destination_storage.exists(path), (
            f"{name} is referenced by the imported cell but is missing from the "
            f"destination storage"
        )
        with destination_storage.open(path, "rb") as f:
            assert f.read() == image_bytes


@pytest.mark.django_db
def test_prepare_value_for_db_limits_repeated_image_occurrences(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(original_name="a.png", is_image=True)
    # One distinct name, so the distinct-name count alone would never trip the
    # limit even though the client has to render every occurrence.
    value = " ".join(f"![x][{user_file.name}]" for _ in range(MAX_RICH_TEXT_IMAGES + 1))

    with pytest.raises(ValidationError) as exc:
        field_type.prepare_value_for_db(field, value)

    assert exc.value.code == "too_many_images"


@pytest.mark.django_db
def test_prepare_value_for_db_in_bulk_limits_repeated_image_occurrences(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(original_name="a.png", is_image=True)
    ok = f"![x][{user_file.name}]"
    too_many = " ".join(ok for _ in range(MAX_RICH_TEXT_IMAGES + 1))

    result = field_type.prepare_value_for_db_in_bulk(
        field, {0: ok, 1: too_many}, continue_on_error=True
    )

    assert result[0] == ok
    assert isinstance(result[1], ValidationError)
    assert result[1].code == "too_many_images"


@pytest.mark.django_db
def test_import_serialized_value_enforces_image_limit(data_fixture):
    _, table, field, field_type = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(original_name="a.png", is_image=True)
    row = table.get_model()()
    value = " ".join(f"![x][{user_file.name}]" for _ in range(MAX_RICH_TEXT_IMAGES + 5))

    field_type.set_import_serialized_value(
        row, field.db_column, value, {}, {}, None, None
    )

    stored = getattr(row, field.db_column)
    assert count_image_references(stored) == MAX_RICH_TEXT_IMAGES


@pytest.mark.django_db
def test_import_serialized_value_does_not_upload_surplus_images(data_fixture, tmpdir):
    """The limit is applied before the zip is read, so an archive cell with more
    images than allowed never leaves orphaned user files behind."""

    _, table, field, field_type = _rich_text_field(data_fixture)
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    names = [f"img{i}_{'a' * 8}.png" for i in range(MAX_RICH_TEXT_IMAGES + 1)]

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zf:
        for name in names:
            zf.writestr(name, f"PNG_{name}".encode())
    zip_buffer.seek(0)
    files_zip = ZipFile(zip_buffer, "r")

    row = table.get_model()()
    before = UserFile.objects.count()
    field_type.set_import_serialized_value(
        row,
        field.db_column,
        " ".join(f"![x][{name}]" for name in names),
        {},
        {},
        files_zip=files_zip,
        storage=storage,
    )

    stored = getattr(row, field.db_column)
    assert count_image_references(stored) == MAX_RICH_TEXT_IMAGES
    assert UserFile.objects.count() - before == MAX_RICH_TEXT_IMAGES


@pytest.mark.django_db
def test_prepare_value_for_db_leaves_code_literal(data_fixture):
    """Image syntax inside inline code or a fenced block is documentation, not a
    reference: it is neither validated nor rewritten."""

    _, _, field, field_type = _rich_text_field(data_fixture)
    value = (
        "Use `![alt][zzzz_yyyy.png]` or `![alt](https://e.com/a.png)`:\n"
        "```\n![alt][zzzz_yyyy.png]\n![alt](https://e.com/a.png)\n```\n"
        "![ext](https://e.com/b.png)"
    )

    assert field_type.prepare_value_for_db(field, value) == value


@pytest.mark.django_db
def test_prepare_value_for_db_strips_resolved_urls(data_fixture):
    _, _, field, field_type = _rich_text_field(data_fixture)
    user_file = data_fixture.create_user_file(original_name="a.png", is_image=True)
    value = f"![a][{user_file.name}](http://h/media/{user_file.name})"

    assert field_type.prepare_value_for_db(field, value) == f"![a][{user_file.name}]"
    assert field_type.prepare_value_for_db_in_bulk(field, {0: value}) == {
        0: f"![a][{user_file.name}]"
    }


@pytest.mark.django_db
def test_max_length_ignores_resolved_image_urls(data_fixture, api_client, settings):
    """A value returned by GET carries the resolved image URLs. Sending it back
    unchanged must not fail `max_length`, which is checked on the stored form."""

    from django.urls import reverse

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )
    user_file = data_fixture.create_user_file(is_image=True, original_name="a.png")
    stored = f"![a][{user_file.name}]"
    row = table.get_model().objects.create(**{f"field_{field.id}": stored})

    settings.MAX_FIELD_TEXT_LENGTH = len(stored) + 5
    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
    )
    value = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}").json()[
        f"field_{field.id}"
    ]
    assert len(value) > settings.MAX_FIELD_TEXT_LENGTH

    response = api_client.patch(
        url,
        {f"field_{field.id}": value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json()[f"field_{field.id}"] == value

    response = api_client.patch(
        url,
        {f"field_{field.id}": value + "x" * 6},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


def _over_limit_value():
    return " ".join(
        f"![x][{'a' * 8}{i:04d}_hash.png]" for i in range(MAX_RICH_TEXT_IMAGES + 1)
    )


@pytest.mark.django_db
def test_enabling_rich_text_rejects_values_over_image_limit(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=False
    )
    RowHandler().create_row(user, table, {field.db_column: _over_limit_value()})

    # The API wraps the update in a transaction, which the error rolls back.
    with pytest.raises(RichTextImageLimitExceeded), transaction.atomic():
        FieldHandler().update_field(user, field, long_text_enable_rich_text=True)

    field.refresh_from_db()
    assert not field.long_text_enable_rich_text


@pytest.mark.django_db
def test_enabling_rich_text_ignores_code_and_values_within_limit(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=False
    )
    RowHandler().create_rows(
        user,
        table,
        [
            {field.db_column: f"```\n{_over_limit_value()}\n```"},
            {field.db_column: "![x][abc_def.png] " * MAX_RICH_TEXT_IMAGES},
        ],
    )

    field = FieldHandler().update_field(user, field, long_text_enable_rich_text=True)

    assert field.long_text_enable_rich_text


@pytest.mark.django_db
def test_converting_text_to_rich_text_rejects_values_over_image_limit(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    RowHandler().create_row(user, table, {field.db_column: _over_limit_value()})

    with pytest.raises(RichTextImageLimitExceeded), transaction.atomic():
        FieldHandler().update_field(
            user, field, new_type_name="long_text", long_text_enable_rich_text=True
        )

    assert isinstance(Field.objects.get(id=field.id).specific, TextField)


@pytest.mark.django_db
def test_enabling_rich_text_over_image_limit_is_a_400(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=False
    )
    RowHandler().create_row(user, table, {field.db_column: _over_limit_value()})

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {"long_text_enable_rich_text": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_RICH_TEXT_IMAGE_LIMIT_EXCEEDED"
    field.refresh_from_db()
    assert not field.long_text_enable_rich_text
