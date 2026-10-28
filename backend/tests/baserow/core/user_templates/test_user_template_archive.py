from unittest.mock import patch

from django.core.files.base import ContentFile
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

import pytest

from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import Template
from baserow.core.storage import get_default_storage
from baserow.core.user_templates.archive import (
    clear_template_archive_stamp,
    delete_template_archives,
    get_template_archive_stamp,
    has_valid_archive,
    template_archive_dir,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.utils import Progress
from tests.baserow.core.user_templates.utils import (
    add_password_data,
    assert_password_data_left_out,
    create_template_with_content,
    import_archive,
    install_marks,
    store_archive,
    store_template_archive,
    template_archive_names,
)

ARCHIVE_VERSION = "baserow.core.user_templates.archive.VERSION"
WRITE_ARCHIVE = "write_applications_archive"


@pytest.fixture(autouse=True)
def clear_stamp():
    clear_template_archive_stamp()
    yield
    clear_template_archive_stamp()


def build(revision, **kwargs):
    UserTemplateHandler().build_template_archive(revision, **kwargs)
    return revision.archive.name


@pytest.mark.django_db
def test_template_archive_stamp_changes_once_cleared_after_a_migration():
    # Rolled back with the test, unlike in a transactional test. The database of
    # the tests is created without migrations, so the table may be missing.
    recorder = MigrationRecorder(connection)
    recorder.ensure_schema()
    stamp = get_template_archive_stamp()
    recorder.record_applied("core", "9999_test")

    assert get_template_archive_stamp() == stamp

    clear_template_archive_stamp()

    assert get_template_archive_stamp() != stamp


def test_deleting_template_archives_refuses_another_directory():
    for directory in ["template-revisions/", "template-archives/", "media/1/"]:
        with pytest.raises(ValueError):
            delete_template_archives(directory)


@install_marks
def test_build_template_archive(data_fixture):
    owner = data_fixture.create_user()
    template, table, view = create_template_with_content(
        data_fixture, owner, install_count=3
    )
    add_password_data(data_fixture, table, view)
    updated_on = Template.objects.get(id=template.id).updated_on
    progress = Progress(100)

    name = build(template, progress_builder=progress.create_child_builder(100))

    assert progress.progress == 100
    assert name.startswith(
        f"template-archives/{template.id}/{get_template_archive_stamp()}_"
    )
    assert name.endswith(".zip")
    assert template_archive_names(template) == [name]
    template.refresh_from_db()
    assert template.archive.name == name
    assert template.updated_on == updated_on
    assert template.install_count == 3
    assert has_valid_archive(template)
    importer = data_fixture.create_user()
    applications = import_archive(data_fixture, importer, name)
    assert [application.name for application in applications] == ["Projects"]
    imported_table = applications[0].specific.table_set.get()
    primary_field = imported_table.field_set.get(primary=True)
    assert list(
        imported_table.get_model().objects.values_list(
            primary_field.db_column, flat=True
        )
    ) == ["First"]
    assert_password_data_left_out(imported_table)


@install_marks
def test_build_template_archive_replaces_the_archive_of_another_version(
    data_fixture,
):
    template, _, _ = create_template_with_content(data_fixture)
    old_name = build(template)

    with patch(ARCHIVE_VERSION, "0.0.0-other"):
        assert not has_valid_archive(template)
        name = build(template)
        assert has_valid_archive(template)

    assert name != old_name
    assert template_archive_names(template) == [name]
    assert Template.objects.get(id=template.id).archive.name == name


@install_marks
def test_build_template_archive_replaces_an_archive_named_like_before(data_fixture):
    old_name = store_archive()
    root, _, _ = create_template_with_content(data_fixture, archive=old_name)
    # It only changed the details, so it shares the content and the archive name.
    revision = data_fixture.create_user_template_revision(
        root, workspace=root.workspace, archive=old_name
    )

    assert not has_valid_archive(root)

    build(revision)

    # The root still refers to it.
    assert get_default_storage().exists(old_name)

    name = build(root)

    assert name.startswith(template_archive_dir(root.id))
    assert has_valid_archive(root)
    assert not get_default_storage().exists(old_name)


@install_marks
def test_build_template_archive_doesnt_reuse_the_archive_of_another_revision(
    data_fixture,
):
    root, _, _ = create_template_with_content(data_fixture)
    root_name = build(root)
    # It only changed the details, so it shares the content and the archive name.
    revision = data_fixture.create_user_template_revision(
        root, workspace=root.workspace, archive=root_name
    )

    assert not has_valid_archive(revision)

    name = build(revision)

    assert name.startswith(template_archive_dir(revision.id))
    assert template_archive_names(revision) == [name]
    assert template_archive_names(root) == [root_name]
    assert has_valid_archive(root)


@install_marks
def test_build_template_archive_leaves_no_file_when_it_fails(data_fixture):
    template, _, _ = create_template_with_content(data_fixture)
    write_archive = ImportExportHandler.write_applications_archive

    def write_then_delete(self, *args, **kwargs):
        write_archive(self, *args, **kwargs)
        Template.objects.filter(id=template.id).delete()

    with patch.object(ImportExportHandler, WRITE_ARCHIVE, write_then_delete):
        with pytest.raises(TemplateDoesNotExist):
            build(template)

    assert template_archive_names(template) == []
    assert not Template.objects.filter(id=template.id).exclude(archive="").exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("use_tmp_media_root")
def test_has_valid_archive(data_fixture):
    template = data_fixture.create_user_template()

    assert not has_valid_archive(template)

    name = store_template_archive(template)

    assert has_valid_archive(template)

    get_default_storage().delete(name)

    assert not has_valid_archive(template)


@pytest.mark.django_db
@pytest.mark.usefixtures("use_tmp_media_root")
def test_delete_template_archives_keeps_the_ones_a_template_refers_to(
    data_fixture,
):
    template = data_fixture.create_user_template()
    directory = template_archive_dir(template.id)
    storage = get_default_storage()
    kept = storage.save(f"{directory}kept.zip", ContentFile(b"kept"))
    stray = storage.save(f"{directory}stray.zip", ContentFile(b"stray"))
    # Another template refers to it, like one copied from it.
    referred = store_template_archive(template)
    other = data_fixture.create_user_template(archive=referred)
    Template.objects.filter(id=template.id).update(archive="")

    delete_template_archives(directory, keep=[kept])

    assert template_archive_names(template) == sorted([kept, referred])
    assert not storage.exists(stray)

    other.delete()
    delete_template_archives(directory)

    assert not storage.exists(directory)
    # Deleting twice does nothing.
    delete_template_archives(directory)
