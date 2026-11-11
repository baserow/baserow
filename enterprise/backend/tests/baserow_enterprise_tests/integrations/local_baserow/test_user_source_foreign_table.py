import pytest

from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import get_default_storage
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.exceptions import UserSourceImproperlyConfigured
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import DEFAULT_USER_ROLE_PREFIX

from .helpers import populate_local_baserow_test_data


def _point_at_another_workspace_table(data_fixture, user_source):
    """
    Points the user source at a table of another workspace, like an import used to
    when the table's database wasn't imported, and returns that table.
    """

    other_user = data_fixture.create_user()
    table, fields, _ = data_fixture.build_table(
        user=other_user,
        columns=[("Email", "text"), ("Name", "text"), ("Role", "text")],
        rows=[["secret@example.com", "Secret", "admin"]],
    )
    email_field, name_field, role_field = fields
    type(user_source).objects.filter(id=user_source.id).update(
        table=table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )
    user_source.refresh_from_db()
    return table


@pytest.mark.django_db
def test_a_user_source_reading_another_workspace_table_isnt_readable(
    data_fixture,
):
    user_source = populate_local_baserow_test_data(data_fixture)["user_source"]
    user_source_type = user_source.get_type()
    assert user_source_type.is_readable(user_source)

    _point_at_another_workspace_table(data_fixture, user_source)

    # It's configured, but its users are never read, see the count test below.
    assert user_source_type.is_configured(user_source)
    assert not user_source_type.is_readable(user_source)
    with pytest.raises(UserSourceImproperlyConfigured):
        user_source_type.is_readable(user_source, raise_exception=True)
    assert user_source_type.list_users(user_source) == []
    with pytest.raises(UserNotFound):
        user_source_type.get_user(user_source, email="secret@example.com")


@pytest.mark.django_db
def test_a_user_source_reading_another_workspace_table_reveals_no_roles(
    data_fixture,
):
    user_source = populate_local_baserow_test_data(data_fixture)["user_source"]
    _point_at_another_workspace_table(data_fixture, user_source)

    roles = user_source.get_type().get_roles(user_source)

    assert roles == [f"{DEFAULT_USER_ROLE_PREFIX}{user_source.id}"]


@pytest.mark.django_db
def test_a_user_source_with_fields_of_another_table_isnt_readable(data_fixture):
    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]

    # A table of the same workspace, but not the user source's.
    other_table = data_fixture.create_database_table(
        user=data["user"], database=user_source.table.database
    )
    other_field = data_fixture.create_text_field(table=other_table, name="Email")
    type(user_source).objects.filter(id=user_source.id).update(email_field=other_field)
    user_source.refresh_from_db()

    assert not user_source.get_type().is_readable(user_source)


@pytest.mark.django_db
def test_a_user_source_with_a_trashed_integration_reveals_no_roles(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source, integration = data_fixture.create_user_table_and_role(
        user, builder, "editor"
    )

    # Deleting an integration trashes it, the user source keeps its id.
    TrashHandler.trash(user, builder.workspace, builder, integration)
    user_source = UserSourceHandler().get_user_source(user_source.id)
    user_source_type = user_source.get_type()

    assert user_source.integration_id == integration.id
    assert not user_source_type.is_readable(user_source)
    assert user_source_type.get_roles(user_source) == [
        f"{DEFAULT_USER_ROLE_PREFIX}{user_source.id}"
    ]


@pytest.mark.django_db
def test_a_user_source_reading_another_workspace_table_counts_no_users(
    data_fixture,
):
    user_source = populate_local_baserow_test_data(data_fixture)["user_source"]
    user_source_type = user_source.get_type()
    assert user_source_type.get_user_count(user_source).count > 0

    _point_at_another_workspace_table(data_fixture, user_source)

    # The count cached before is dropped by the next count.
    user_source_type.update_user_count()
    assert user_source_type.get_user_count(user_source) is None


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_without_the_database_clears_the_user_source_table(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_local_baserow_table_user_source(
        application=builder, user=user
    )
    database = user_source.table.database
    data_fixture.create_import_export_trusted_source()
    handler = ImportExportHandler()
    storage = get_default_storage()
    resource = handler.export_workspace_applications(
        applications=[database, builder],
        import_export_config=ImportExportConfig(
            include_permission_data=False, reduce_disk_space_usage=False
        ),
    )
    export_path = handler.get_export_storage_path(resource.get_archive_name())

    importer = data_fixture.create_user()
    target_workspace = data_fixture.create_workspace(user=importer)
    with storage.open(export_path, "rb") as archive:
        import_resource = handler.create_resource_from_file(
            importer, "export.zip", archive
        )
    [imported_builder] = handler.import_workspace_applications(
        importer, target_workspace, import_resource, application_ids=[builder.id]
    )

    imported = UserSource.objects.get(application_id=imported_builder.id).specific
    assert imported.table_id is None
    assert imported.email_field_id is None
    assert imported.name_field_id is None
    assert imported.role_field_id is None
