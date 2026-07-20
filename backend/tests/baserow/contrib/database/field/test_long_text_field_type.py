import io
from unittest.mock import MagicMock
from zipfile import ZipFile

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

import pytest

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.export.table_exporters.csv_table_exporter import (
    CsvQuerysetSerializer,
)
from baserow.contrib.database.fields.exceptions import IncompatiblePrimaryFieldTypeError
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.contrib.database.trash.models import TrashedRows
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_files.handler import UserFileHandler


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

    from unittest.mock import MagicMock

    files_zip = MagicMock()
    files_zip.info_list.return_value = []

    cache = {}
    result = field_type.get_export_serialized_value(
        row, field_name, cache, files_zip=files_zip, storage=storage
    )

    assert result == content
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

    from unittest.mock import MagicMock

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
    """``get_export_serialized_value`` should not raise when the image file
    referenced in the content is missing from storage. The content is returned
    unchanged and the missing file is silently skipped."""

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

    files_zip = MagicMock()
    files_zip.info_list.return_value = []
    # file_chunk_generator is a lazy generator — the FileNotFoundError only
    # fires when the generator is consumed inside files_zip.add(). Simulate
    # that by making `add` raise the error, which is what the real zip would
    # do when iterating the chunk generator for a missing file.
    files_zip.add.side_effect = FileNotFoundError

    cache = {}
    result = field_type.get_export_serialized_value(
        row, field_name, cache, files_zip=files_zip, storage=storage
    )

    # Content is returned unchanged, no exception raised
    assert result == content
    assert user_file.name in result


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
