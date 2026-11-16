import hashlib
from io import BytesIO
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

import pytest
from PIL import Image

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.core.deferred_callbacks import register_deferred_callback
from baserow.core.handler import CoreHandler
from baserow.core.models import Application, UserFile
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import get_default_storage
from baserow.core.user_files.exceptions import TemplateImportWithoutFilesZip
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.template_files import (
    get_template_file_owner,
    is_template_file_unique,
    template_file_owner,
    template_file_prefix,
)
from baserow.core.user_templates.file_transfer import TemplateFilesTransfer


def _png_bytes(color):
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_template_file_prefix():
    assert template_file_prefix(12) == "tpl0000000012"
    assert template_file_prefix(2147483647) == "tpl2147483647"


def test_is_template_file_unique():
    assert is_template_file_unique("tpl0000000012abcdefghijklmnopqrs")
    assert not is_template_file_unique("tplabcdefghijklmnopqrstuvwxyz012")
    assert not is_template_file_unique("tpl123abcdefghijklmnopqrstuvwxyz")
    assert not is_template_file_unique("xtpl0000000012abcdefghijklmnopqr")
    assert not is_template_file_unique("Tpl0000000012abcdefghijklmnopqrs")


@pytest.mark.django_db
def test_generate_unique_rerolls_template_prefix():
    draws = iter(
        ["tplAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "abcAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"]
    )

    with patch(
        "baserow.core.user_files.handler.random_string",
        side_effect=lambda length: next(draws),
    ):
        unique = UserFileHandler().generate_unique("hash", "txt")

    assert unique == "abcAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


@pytest.mark.django_db
def test_template_dedup_is_per_template_workspace(data_fixture, use_tmp_media_root):
    user = data_fixture.create_user()
    handler = UserFileHandler()
    storage = get_default_storage()
    normal = handler.upload_user_file(user, "a.png", BytesIO(_png_bytes("red")))

    with template_file_owner(1):
        copy = handler.upload_user_file(None, "a.png", BytesIO(_png_bytes("red")))
        same_template = handler.upload_user_file(
            None, "a.png", BytesIO(_png_bytes("red"))
        )
    with template_file_owner(10):
        other_template = handler.upload_user_file(
            None, "a.png", BytesIO(_png_bytes("red"))
        )

    assert copy.id != normal.id
    assert copy.unique.startswith("tpl0000000001")
    assert len(copy.unique) == 32
    assert copy.sha256_hash == normal.sha256_hash
    assert copy.uploaded_by is None
    assert copy.is_image
    assert storage.exists(handler.user_file_path(copy))
    assert storage.exists(handler.user_file_thumbnail_path(copy, "tiny"))
    assert same_template.id == copy.id
    assert other_template.id not in (normal.id, copy.id)
    assert other_template.unique.startswith("tpl0000000010")


@pytest.mark.django_db
def test_template_files_selects_only_that_workspace(data_fixture):
    own = data_fixture.create_user_file(unique="tpl0000000001abcdefghijklmnopqrs")
    other_template = data_fixture.create_user_file(
        unique="tpl0000000010abcdefghijklmnopqrs"
    )
    normal = data_fixture.create_user_file(unique="abcdefghijklmnopqrstuvwxyz012345")
    lookalike = data_fixture.create_user_file(unique="tplabcdefghijklmnopqrstuvwxyz012")
    short_id_lookalike = data_fixture.create_user_file(
        unique="tpl123abcdefghijklmnopqrstuvwxyz"
    )

    assert list(UserFile.objects.template_files(1)) == [own]
    assert list(UserFile.objects.template_files(10)) == [other_template]
    assert set(UserFile.objects.template_files()) == {own, other_template}
    assert set(UserFile.objects.exclude_template_files()) == {
        normal,
        lookalike,
        short_id_lookalike,
    }


@pytest.mark.django_db
def test_upload_identical_to_template_file_creates_new_file(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    handler = UserFileHandler()

    with template_file_owner(12):
        template_copy = handler.upload_user_file(None, "a.txt", ContentFile(b"Hello"))

    uploaded = handler.upload_user_file(user, "a.txt", ContentFile(b"Hello"))

    assert uploaded.id != template_copy.id
    assert not is_template_file_unique(uploaded.unique)
    assert uploaded.uploaded_by == user


@pytest.mark.django_db
def test_normal_dedup_reuses_legacy_tpl_lookalike(data_fixture, use_tmp_media_root):
    legacy = data_fixture.create_user_file(
        original_name="a.txt",
        unique="tplabcdefghijklmnopqrstuvwxyz012",
        sha256_hash=hashlib.sha256(b"Hello").hexdigest(),
    )

    uploaded = UserFileHandler().upload_user_file(None, "a.txt", ContentFile(b"Hello"))

    assert uploaded.id == legacy.id


def _dedup_queries(queries):
    return [
        query["sql"]
        for query in queries
        if query["sql"].startswith("SELECT")
        and '"core_userfile"."sha256_hash" =' in query["sql"]
        and '"core_userfile"."original_name" =' in query["sql"]
    ]


@pytest.mark.django_db
def test_upload_dedup_query_is_unordered(use_tmp_media_root):
    handler = UserFileHandler()
    normal = handler.upload_user_file(None, "a.txt", ContentFile(b"Hello"))
    with template_file_owner(12):
        template_copy = handler.upload_user_file(None, "a.txt", ContentFile(b"Hello"))

    with CaptureQueriesContext(connection) as normal_queries:
        assert handler.upload_user_file(None, "a.txt", ContentFile(b"Hello")) == normal
    with template_file_owner(12), CaptureQueriesContext(connection) as template_queries:
        assert (
            handler.upload_user_file(None, "a.txt", ContentFile(b"Hello"))
            == template_copy
        )

    [normal_sql] = _dedup_queries(normal_queries.captured_queries)
    [template_sql] = _dedup_queries(template_queries.captured_queries)
    assert "ORDER BY" not in normal_sql
    assert "ORDER BY" not in template_sql
    assert len(normal_queries.captured_queries) == 1
    assert len(template_queries.captured_queries) == 1


def _serialized_database(data_fixture, files):
    database = data_fixture.create_database_application(name="Copied")
    data_fixture.create_database_table(database=database)
    config = ImportExportConfig(include_permission_data=False)
    return [
        database.get_type().export_serialized(database, config, files, files.storage)
    ]


def _template_import_config():
    return ImportExportConfig(
        include_permission_data=False, user_files_belong_to_workspace=True
    )


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_core_import_in_template_mode_without_files_raises(
    data_fixture, use_tmp_media_root
):
    workspace = data_fixture.create_workspace()
    files = TemplateFilesTransfer(get_default_storage())
    serialized = _serialized_database(data_fixture, files)

    with pytest.raises(TemplateImportWithoutFilesZip):
        CoreHandler().import_applications_to_workspace(
            workspace, serialized, None, _template_import_config()
        )

    assert not Application.objects.filter(workspace=workspace).exists()
    assert get_template_file_owner() is None


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_core_import_resets_template_mode_on_error(data_fixture, use_tmp_media_root):
    workspace = data_fixture.create_workspace()
    storage = get_default_storage()
    files = TemplateFilesTransfer(storage)
    serialized = _serialized_database(data_fixture, files)
    content = _png_bytes("red")
    normal_file = UserFileHandler().upload_user_file(None, "a.png", BytesIO(content))
    import_serialized = DatabaseApplicationType.import_serialized
    owners = []

    def fail_in_a_deferred_callback():
        owners.append(get_template_file_owner())
        raise RuntimeError("deferred boom")

    def import_and_defer_a_failure(self, *args, **kwargs):
        owners.append(get_template_file_owner())
        application = import_serialized(self, *args, **kwargs)
        register_deferred_callback(fail_in_a_deferred_callback)
        return application

    with (
        patch.object(
            DatabaseApplicationType, "import_serialized", import_and_defer_a_failure
        ),
        pytest.raises(RuntimeError, match="deferred boom"),
        transaction.atomic(),
    ):
        CoreHandler().import_applications_to_workspace(
            workspace, serialized, files, _template_import_config(), storage=storage
        )

    assert owners == [workspace.id, workspace.id]
    assert get_template_file_owner() is None
    assert (
        UserFileHandler().upload_user_file(None, "a.png", BytesIO(content))
        == normal_file
    )
