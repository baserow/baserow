from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, QuerySet
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.data_sync.export_serialized import (
    DataSyncExportSerializedStructure,
)
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.fields.models import Field, SelectOption
from baserow.contrib.database.models import Database, Table
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import Application
from baserow.core.trash.handler import TrashHandler

SEED_ROWS = [("alpha", "in"), ("beta", "in"), ("gamma", "out")]

VIEW_ROWS = [("alpha", "in"), ("beta", "in")]
IN_ROWS = [*VIEW_ROWS, ("delta", "in")]

pytestmark = [
    pytest.mark.import_export_workspace,
    pytest.mark.data_sync,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("use_tmp_media_root"),
]


def _build(data_fixture, layout, view=None):
    data_fixture.enable_enterprise()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    source_database = data_fixture.create_database_application(
        workspace=workspace, name="Source", order=1
    )
    if layout == "same_database":
        mirror_database = source_database
    else:
        mirror_database = data_fixture.create_database_application(
            workspace=workspace,
            name="Synced",
            order=2 if layout == "source_above" else 0,
        )

    people = data_fixture.create_database_table(database=source_database, name="People")
    name = data_fixture.create_text_field(table=people, name="Name", primary=True)
    group = data_fixture.create_text_field(table=people, name="Group")
    note = data_fixture.create_text_field(table=people, name="Note")
    status = data_fixture.create_single_select_field(table=people, name="Status")
    options = {
        value: data_fixture.create_select_option(field=status, value=value)
        for value in ("ready", "blocked")
    }
    model = people.get_model()
    for row_name, row_group in SEED_ROWS:
        model.objects.create(
            **{
                name.db_column: row_name,
                group.db_column: row_group,
                note.db_column: "note",
                status.db_column: options["blocked" if row_group == "out" else "ready"],
            }
        )

    in_only = data_fixture.create_grid_view(
        table=people,
        name="In only",
        ownership_type=view or "collaborative",
        owned_by=user if view == "personal" else None,
    )
    data_fixture.create_view_filter(view=in_only, field=group, type="equal", value="in")

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=mirror_database,
        table_name="Mirror",
        type_name="local_baserow_table",
        synced_properties=[
            "id",
            f"field_{name.id}",
            f"field_{group.id}",
            f"field_{status.id}",
        ],
        source_table_id=people.id,
        source_table_view_id=in_only.id if view else None,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    return SimpleNamespace(
        user=user,
        source_database=source_database,
        mirror_database=mirror_database,
        people=people,
        in_only=in_only,
    )


def _a_later_application_fails(data_fixture, applications):
    later = data_fixture.create_database_application(
        workspace=applications[0].workspace, name="Later"
    )
    import_application = ImportExportHandler.import_application
    imported = []

    def fail_on_later(self, *args, **kwargs):
        if len(imported) == len(applications):
            raise RuntimeError("Later fails to import.")
        imported.append(import_application(self, *args, **kwargs))
        return imported[-1]

    return [*applications, later], patch.object(
        ImportExportHandler, "import_application", fail_on_later
    )


def _locking_the_fields_again_fails():
    bulk_update = QuerySet.bulk_update

    def fail_on_fields(self, *args, **kwargs):
        if self.model is Field:
            raise RuntimeError("Interrupted before the fields are locked again.")
        return bulk_update(self, *args, **kwargs)

    return patch.object(QuerySet, "bulk_update", fail_on_fields)


def _tables_opened_while_importing():
    import_application = ImportExportHandler.import_application

    def open_tables(self, *args, **kwargs):
        application = import_application(self, *args, **kwargs)
        for table in Table.objects.filter(database_id=application.id):
            table.get_model()
        return application

    return patch.object(ImportExportHandler, "import_application", open_tables)


def _restore_after_failed_import(data_fixture, applications, failure):
    export_path = data_fixture.export_workspace_applications_file(applications)
    with failure, pytest.raises(RuntimeError):
        data_fixture.import_workspace_applications_file(export_path)
    imported = list(Application.objects_and_trash.filter(trashed=True))
    user = imported[0].workspace.users.first()
    for application in imported:
        TrashHandler.restore_item(user, "application", application.id)
    return imported


def _copy(data_fixture, tmpdir, path, world, applications):
    if path == "workspace_import":
        return data_fixture.export_and_import_workspace_applications(applications)
    if path == "workspace_import_opening_tables":
        with _tables_opened_while_importing():
            return data_fixture.export_and_import_workspace_applications(applications)
    if path == "official_template":
        return data_fixture.install_applications_as_template(applications, tmpdir)
    if path == "failed_workspace_import":
        return _restore_after_failed_import(
            data_fixture, *_a_later_application_fails(data_fixture, applications)
        )
    if path == "interrupted_workspace_import":
        return _restore_after_failed_import(
            data_fixture, applications, _locking_the_fields_again_fails()
        )
    [application] = applications
    return [CoreHandler().duplicate_application(world.user, application)]


def _table(applications, database_name, table_name):
    database = next(
        app.specific
        for app in applications
        if isinstance(app.specific, Database) and app.name.startswith(database_name)
    )
    return database.table_set.get(name=table_name)


def _rows(table):
    name = table.field_set.get(name="Name")
    group = table.field_set.get(name="Group")
    return sorted(
        (getattr(row, name.db_column), getattr(row, group.db_column))
        for row in table.get_model().objects.all()
    )


def _names_in_view(table, view_name):
    view = table.view_set.get(name=view_name).specific
    name = table.field_set.get(name="Name")
    rows = ViewHandler().apply_filters(view, table.get_model().objects.all())
    return sorted(getattr(row, name.db_column) for row in rows)


def _edit_a_row(api_client, data_fixture, table):
    user = table.database.workspace.users.first()
    group = table.field_set.get(name="Group")
    row = table.get_model().objects.first()
    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        {f"field_{group.id}": "edited"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(user)}",
    )
    return response.status_code


def _sync(table):
    data_sync = table.data_sync.specific
    user = table.database.workspace.users.first()
    DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    table.refresh_from_db()


@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    "path,layout,view,expected_rows",
    [
        ("workspace_import", "source_above", "collaborative", IN_ROWS),
        ("workspace_import_opening_tables", "source_below", "collaborative", IN_ROWS),
        ("official_template", "source_below", "collaborative", IN_ROWS),
        ("duplicate_database", "same_database", "collaborative", IN_ROWS),
        ("failed_workspace_import", "source_above", "collaborative", IN_ROWS),
    ],
)
def test_a_copy_of_both_databases_keeps_syncing_from_the_copied_source(
    enterprise_data_fixture, api_client, tmpdir, path, layout, view, expected_rows
):
    world = _build(enterprise_data_fixture, layout, view=view)
    sidebar = world.source_database.workspace.application_set.order_by("order")
    mirror_database_name = "Source" if layout == "same_database" else "Synced"

    copied = _copy(enterprise_data_fixture, tmpdir, path, world, list(sidebar))

    copied_people = _table(copied, "Source", "People")
    copied_mirror = _table(copied, mirror_database_name, "Mirror")
    copied_view = copied_people.view_set.filter(name="In only").first()
    data_sync = copied_mirror.data_sync.specific
    assert copied_people.id != world.people.id
    assert data_sync.source_table_id == copied_people.id
    assert data_sync.source_table_view_id == copied_view.id
    assert data_sync.authorized_user_id is None
    assert not copied_mirror.field_set.filter(
        Q(read_only=False) | Q(immutable_type=False)
    ).exists()
    edited = _edit_a_row(api_client, enterprise_data_fixture, copied_mirror)
    assert edited == HTTP_400_BAD_REQUEST

    name = copied_people.field_set.get(name="Name")
    group = copied_people.field_set.get(name="Group")
    copied_people.get_model().objects.create(
        **{name.db_column: "delta", group.db_column: "in"}
    )
    _sync(copied_mirror)

    assert _rows(copied_mirror) == expected_rows
    assert not copied_mirror.field_set.filter(name="Note").exists()


@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    "path,layout,view,with_source,expected_rows",
    [
        ("workspace_import", "source_below", None, False, sorted(SEED_ROWS)),
        ("official_template", "source_below", None, False, sorted(SEED_ROWS)),
        ("failed_workspace_import", "source_below", None, False, sorted(SEED_ROWS)),
        ("interrupted_workspace_import", "source_below", None, True, sorted(SEED_ROWS)),
        ("workspace_import", "source_above", "personal", True, VIEW_ROWS),
    ],
)
def test_a_copy_that_cannot_stay_synced_becomes_a_plain_table(
    enterprise_data_fixture,
    api_client,
    tmpdir,
    path,
    layout,
    view,
    with_source,
    expected_rows,
):
    world = _build(enterprise_data_fixture, layout, view=view)
    applications = [world.mirror_database]
    if with_source:
        applications = list(world.mirror_database.workspace.application_set.all())

    copied = _copy(enterprise_data_fixture, tmpdir, path, world, applications)

    copied_mirror = _table(copied, "Synced", "Mirror")
    with pytest.raises(ObjectDoesNotExist):
        copied_mirror.data_sync
    assert not copied_mirror.field_set.filter(
        Q(read_only=True) | Q(immutable_type=True) | Q(immutable_properties=True)
    ).exists()
    assert _rows(copied_mirror) == expected_rows
    edited = _edit_a_row(api_client, enterprise_data_fixture, copied_mirror)
    assert edited == HTTP_200_OK


@override_settings(DEBUG=True)
def test_a_duplicate_without_its_source_view_keeps_the_view_and_fails_to_sync(
    enterprise_data_fixture,
):
    world = _build(enterprise_data_fixture, "same_database", view="collaborative")
    TrashHandler.trash(
        world.user,
        world.source_database.workspace,
        world.source_database,
        world.in_only,
    )

    copied = CoreHandler().duplicate_application(world.user, world.source_database)

    copied_mirror = _table([copied], "Source", "Mirror")
    data_sync = copied_mirror.data_sync.specific
    assert data_sync.source_table_view_id == world.in_only.id
    _sync(copied_mirror)
    data_sync.refresh_from_db()
    assert (
        data_sync.last_error == f"The view with id {world.in_only.id} does not exist."
    )
    assert _rows(copied_mirror) == VIEW_ROWS


@override_settings(DEBUG=True)
def test_a_duplicated_database_keeps_syncing_from_the_original_source(
    enterprise_data_fixture,
):
    world = _build(enterprise_data_fixture, "source_above", view="collaborative")

    copied = CoreHandler().duplicate_application(world.user, world.mirror_database)

    copied_mirror = _table([copied], "Synced", "Mirror")
    data_sync = copied_mirror.data_sync.specific
    assert data_sync.source_table_id == world.people.id
    assert data_sync.source_table_view_id == world.in_only.id
    name = world.people.field_set.get(name="Name")
    group = world.people.field_set.get(name="Group")
    world.people.get_model().objects.create(
        **{name.db_column: "delta", group.db_column: "in"}
    )
    _sync(copied_mirror)
    assert _rows(copied_mirror) == IN_ROWS


@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    "path,layout,with_source",
    [
        ("workspace_import", "source_below", True),
        ("duplicate_database", "source_above", False),
    ],
)
def test_a_synced_copy_keeps_its_select_options_and_filtered_views(
    enterprise_data_fixture, tmpdir, path, layout, with_source
):
    world = _build(enterprise_data_fixture, layout)
    mirror = _table([world.mirror_database], "Synced", "Mirror")
    archived = enterprise_data_fixture.create_select_option(
        field=world.people.field_set.get(name="Status"), value="archived"
    )
    _sync(mirror)
    archived.delete()
    status = mirror.field_set.get(name="Status").specific
    blocked = status.select_options.get(value="blocked")
    for view_name, filter_type in [
        ("Blocked", "single_select_equal"),
        ("Not blocked", "single_select_not_equal"),
    ]:
        view = enterprise_data_fixture.create_grid_view(table=mirror, name=view_name)
        enterprise_data_fixture.create_view_filter(
            view=view, field=status, type=filter_type, value=str(blocked.id)
        )
    applications = [world.mirror_database]
    if with_source:
        applications = list(world.mirror_database.workspace.application_set.all())
    foreign = enterprise_data_fixture.create_select_option(value="foreign")
    export_property = DataSyncExportSerializedStructure.property

    def with_foreign_target(key, field_id, unique_primary, metadata):
        if metadata:
            mapping = {**metadata["select_options_mapping"], "0": foreign.id}
            metadata = {**metadata, "select_options_mapping": mapping}
        return export_property(key, field_id, unique_primary, metadata)

    with patch.object(
        DataSyncExportSerializedStructure, "property", with_foreign_target
    ):
        copied = _copy(enterprise_data_fixture, tmpdir, path, world, applications)

    copied_mirror = _table(copied, "Synced", "Mirror")
    _sync(copied_mirror)
    assert list(
        SelectOption.objects.filter(id=foreign.id).values_list("field_id", "value")
    ) == [(foreign.field_id, "foreign")]
    copied_status = copied_mirror.field_set.get(name="Status").specific
    assert sorted(copied_status.select_options.values_list("value", flat=True)) == [
        "blocked",
        "ready",
    ]
    assert _names_in_view(copied_mirror, "Blocked") == ["gamma"]
    assert _names_in_view(copied_mirror, "Not blocked") == ["alpha", "beta"]
