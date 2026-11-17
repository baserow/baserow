from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.models import Database
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.trash.handler import TrashHandler

SEED_ROWS = [("alpha", "in"), ("beta", "in"), ("gamma", "out")]

IN_ROWS = [("alpha", "in"), ("beta", "in"), ("delta", "in")]
ALL_ROWS = sorted(SEED_ROWS + [("delta", "in")])

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
    model = people.get_model()
    for row_name, row_group in SEED_ROWS:
        model.objects.create(
            **{
                name.db_column: row_name,
                group.db_column: row_group,
                note.db_column: "note",
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
        synced_properties=["id", f"field_{name.id}", f"field_{group.id}"],
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


def _restore_after_failed_import(data_fixture, applications):
    later = data_fixture.create_database_application(
        workspace=applications[0].workspace, name="Later"
    )
    export_path = data_fixture.export_workspace_applications_file(
        [*applications, later]
    )
    import_application = ImportExportHandler.import_application
    imported = []

    def fail_on_later(self, *args, **kwargs):
        if len(imported) == len(applications):
            raise RuntimeError("Later fails to import.")
        imported.append(import_application(self, *args, **kwargs))
        return imported[-1]

    with patch.object(ImportExportHandler, "import_application", fail_on_later):
        with pytest.raises(RuntimeError):
            data_fixture.import_workspace_applications_file(export_path)
    user = imported[0].workspace.users.first()
    for application in imported:
        TrashHandler.restore_item(user, "application", application.id)
    return imported


def _copy(data_fixture, tmpdir, path, world, applications):
    if path == "workspace_import":
        return data_fixture.export_and_import_workspace_applications(applications)
    if path == "official_template":
        return data_fixture.install_applications_as_template(applications, tmpdir)
    if path == "failed_workspace_import":
        return _restore_after_failed_import(data_fixture, applications)
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
        ("workspace_import", "source_below", "collaborative", IN_ROWS),
        ("official_template", "source_below", "collaborative", IN_ROWS),
        ("duplicate_database", "same_database", "collaborative", IN_ROWS),
        ("workspace_import", "source_above", "personal", ALL_ROWS),
        ("failed_workspace_import", "source_above", "collaborative", IN_ROWS),
    ],
)
def test_a_copy_of_both_databases_keeps_syncing_from_the_copied_source(
    enterprise_data_fixture, tmpdir, path, layout, view, expected_rows
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
    assert data_sync.source_table_view_id == (copied_view and copied_view.id)
    assert (copied_view is None) == (view == "personal")
    assert data_sync.authorized_user_id is None
    assert not copied_mirror.field_set.filter(
        Q(read_only=False) | Q(immutable_type=False)
    ).exists()

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
    "path", ["workspace_import", "official_template", "failed_workspace_import"]
)
def test_a_copy_without_the_source_table(enterprise_data_fixture, tmpdir, path):
    world = _build(enterprise_data_fixture, "source_below")

    copied = _copy(
        enterprise_data_fixture, tmpdir, path, world, [world.mirror_database]
    )

    copied_mirror = _table(copied, "Synced", "Mirror")
    with pytest.raises(ObjectDoesNotExist):
        copied_mirror.data_sync
    assert not copied_mirror.field_set.filter(
        Q(read_only=True) | Q(immutable_type=True) | Q(immutable_properties=True)
    ).exists()
    assert _rows(copied_mirror) == sorted(SEED_ROWS)


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
    _sync(copied_mirror)
    assert _rows(copied_mirror) == [("alpha", "in"), ("beta", "in")]
