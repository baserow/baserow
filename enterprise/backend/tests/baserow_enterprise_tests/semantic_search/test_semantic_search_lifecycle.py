import json
import os
import shutil
from io import BytesIO
from pathlib import Path

from django.core.files.storage import FileSystemStorage
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.tasks import periodic_check_pending_search_data
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.models import Template, TrashEntry
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.utils import Progress
from baserow_enterprise.semantic_search.handler import SemanticSearchHandler
from baserow_enterprise.semantic_search.models import (
    SemanticSearchField,
    SemanticSearchPendingUpdate,
)
from baserow_enterprise.semantic_search.vector_table import SemanticSearchVectorTable

from .utils import enable_search_data_updates, get_chunk_counts, index

pytestmark = enable_search_data_updates


def create_indexed_field(data_fixture, user, values=("first", "second")):
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Text", "text")], rows=[[value] for value in values]
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    index(table)
    return table, fields[0], rows


@pytest.mark.django_db
def test_undo_redo_enable_and_type_change(data_fixture, semantic_search):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    field = data_fixture.create_text_field(user=user)
    scopes = [UpdateFieldActionType.scope(field.table_id)]
    action_type = action_type_registry.get_by_type(UpdateFieldActionType)

    action_type.do(user, field, semantic_search_enabled=True)
    assert SemanticSearchField.objects.filter(field=field).exists()

    ActionHandler.undo(user, scopes, session_id)
    assert not SemanticSearchField.objects.filter(field=field).exists()

    ActionHandler.redo(user, scopes, session_id)
    assert SemanticSearchField.objects.filter(field=field).exists()

    action_type.do(user, field.specific, new_type_name="number")
    assert not SemanticSearchField.objects.filter(field=field).exists()

    ActionHandler.undo(user, scopes, session_id)
    assert SemanticSearchField.objects.filter(field=field).exists()


@pytest.mark.django_db(transaction=True)
def test_duplicate_field_reuses_vectors(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    semantic_search.embedded_texts.clear()

    new_field, _ = FieldHandler().duplicate_field(user, field, duplicate_data=True)

    assert SemanticSearchField.objects.get(field=new_field).status == "ready"
    assert get_chunk_counts(new_field) == {row.id: 1 for row in rows}
    assert semantic_search.embedded_texts == []


@pytest.mark.django_db
def test_duplicate_field_without_license_keeps_semantic_search(
    data_fixture, enterprise_data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    enterprise_data_fixture.delete_all_licenses()

    new_field, _ = FieldHandler().duplicate_field(user, field)

    assert SemanticSearchField.objects.filter(field=new_field).exists()


@pytest.mark.django_db(transaction=True)
def test_duplicate_database_reuses_vectors(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    semantic_search.embedded_texts.clear()

    database_copy = CoreHandler().duplicate_application(user, table.database)

    new_field = database_copy.table_set.get().field_set.get(name="Text")
    assert get_chunk_counts(new_field) == {row.id: 1 for row in rows}
    assert semantic_search.embedded_texts == []


@pytest.mark.django_db(transaction=True)
def test_export_import_workspace_embeds_again(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    data_fixture.create_text_field(table=table, name="Plain")
    config = ImportExportConfig(include_permission_data=False)

    exported = CoreHandler().export_workspace_applications(
        table.database.workspace, BytesIO(), config
    )
    assert {
        field["name"]: field.get("extensions")
        for field in exported[0]["tables"][0]["fields"]
    } == {"Text": {"semantic_search": {"enabled": True}}, "Plain": None}

    # The data of an export can differ from the vectors on this instance.
    semantic_search.embedded_texts.clear()
    workspace = data_fixture.create_workspace(user=user)
    applications, _ = CoreHandler().import_applications_to_workspace(
        workspace, exported, BytesIO(), config
    )

    new_field = applications[0].table_set.get().field_set.get(name="Text")
    new_row_ids = new_field.table.get_model().objects.values_list("id", flat=True)
    assert get_chunk_counts(new_field) == {row_id: 1 for row_id in new_row_ids}
    assert sorted(semantic_search.embedded_texts) == ["first", "second"]


@pytest.mark.django_db(transaction=True)
def test_import_without_license_remembers_semantic_search(
    data_fixture, enterprise_data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    config = ImportExportConfig(include_permission_data=False)
    exported = CoreHandler().export_workspace_applications(
        table.database.workspace, BytesIO(), config
    )

    enterprise_data_fixture.delete_all_licenses()
    workspace = data_fixture.create_workspace(user=user)
    applications, _ = CoreHandler().import_applications_to_workspace(
        workspace, exported, BytesIO(), config
    )

    new_field = applications[0].table_set.get().field_set.get(name="Text")
    assert SemanticSearchField.objects.filter(field=new_field).exists()
    assert SemanticSearchPendingUpdate.objects.filter(
        field_id=new_field.id, row_id=None
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_snapshots_remember_semantic_search_without_indexing(
    data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=table.database, created_by=user
    )
    semantic_search.embedded_texts.clear()

    SnapshotHandler().perform_create(snapshot, Progress(total=100))

    snapshot.refresh_from_db()
    snapshot_field = (
        snapshot.snapshot_to_application.specific.table_set.get().field_set.get()
    )
    assert SemanticSearchField.objects.filter(field=snapshot_field).exists()
    assert not SemanticSearchPendingUpdate.objects.exists()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_tables WHERE tablename LIKE %s",
            ["database_semantic_search_workspace_None%"],
        )
        assert cursor.fetchone()[0] == 0

    restored = SnapshotHandler().perform_restore(snapshot, Progress(total=100))

    restored_field = restored.specific.table_set.get().field_set.get()
    assert get_chunk_counts(restored_field) == {row.id: 1 for row in rows}
    assert sorted(semantic_search.embedded_texts) == ["first", "second"]


@pytest.mark.django_db
def test_trashed_rows_keep_vectors_until_permanently_deleted(
    data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)

    RowHandler().delete_row_by_id(user, table, rows[0].id)
    assert get_chunk_counts(field) == {row.id: 1 for row in rows}

    with django_capture_on_commit_callbacks(execute=True):
        TrashHandler.empty(user, table.database.workspace_id, table.database_id)
        TrashHandler.permanently_delete_marked_trash()
    periodic_check_pending_search_data()

    assert get_chunk_counts(field) == {rows[1].id: 1}


@pytest.mark.django_db
def test_rows_deleted_without_the_trash_are_removed_by_a_full_update(
    data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)

    RowHandler().delete_rows(user, table, [rows[0].id], permanently_delete=True)
    assert get_chunk_counts(field) == {row.id: 1 for row in rows}

    SemanticSearchHandler().queue_full_updates(
        table, [SemanticSearchField.objects.get()]
    )
    index(table)

    assert get_chunk_counts(field) == {rows[1].id: 1}


@pytest.mark.django_db
def test_permanently_deleted_field_table_and_workspace_delete_vectors(
    data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table, fields, rows = data_fixture.build_table(
        user=user, database=database, columns=[("Text", "text")], rows=[["a"]]
    )
    other_table, other_fields, other_rows = data_fixture.build_table(
        user=user, database=database, columns=[("Text", "text")], rows=[["b"]]
    )
    for field in [fields[0], other_fields[0]]:
        FieldHandler().update_field(user, field, semantic_search_enabled=True)
    index(table)
    index(other_table)

    FieldHandler().delete_field(user, fields[0])
    assert get_chunk_counts(fields[0]) == {rows[0].id: 1}
    with django_capture_on_commit_callbacks(execute=True):
        TrashHandler.empty(user, workspace.id, database.id)
        TrashHandler.permanently_delete_marked_trash()
    periodic_check_pending_search_data()
    assert get_chunk_counts(fields[0]) == {}
    assert not SemanticSearchField.objects.filter(field=fields[0]).exists()

    with django_capture_on_commit_callbacks(execute=True):
        TrashHandler.permanently_delete(other_table)
    periodic_check_pending_search_data()
    assert get_chunk_counts(other_fields[0]) == {}

    with django_capture_on_commit_callbacks(execute=True):
        TrashHandler.permanently_delete(workspace)
    assert not SemanticSearchVectorTable(workspace.id).exists()


@pytest.mark.django_db
def test_restored_field_is_indexed_again(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)

    FieldHandler().delete_field(user, field)
    TrashHandler.restore_item(user, "field", field.id)

    assert SemanticSearchPendingUpdate.objects.filter(
        field_id=field.id, row_id=None
    ).exists()


@pytest.mark.django_db
def test_vector_table_isnt_created_on_every_run(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    SemanticSearchHandler().queue_full_updates(
        table, [SemanticSearchField.objects.get()]
    )

    with CaptureQueriesContext(connection) as captured:
        index(table)

    # Creating the index locks the table, even if the index already exists.
    assert not [query for query in captured if "CREATE" in query["sql"]]


@pytest.mark.django_db
def test_disabling_before_the_vector_table_exists(
    data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Text", "text")], rows=[["first"]]
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)

    # The vectors are deleted in a task, which finds no table to delete them from.
    with django_capture_on_commit_callbacks(execute=True):
        FieldHandler().update_field(user, fields[0], semantic_search_enabled=False)

    assert not SemanticSearchVectorTable(table.database.workspace_id).exists()
    assert not SemanticSearchField.objects.exists()


@pytest.mark.django_db
def test_reenabling_before_the_vectors_are_deleted_keeps_them(
    data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    with django_capture_on_commit_callbacks(execute=True):
        FieldHandler().update_field(user, field, semantic_search_enabled=False)
    RowHandler().update_row_by_id(user, table, rows[0].id, {field.db_column: "new"})
    semantic_search.embedded_texts.clear()

    FieldHandler().update_field(user, field, semantic_search_enabled=True)
    periodic_check_pending_search_data()
    index(table)

    assert get_chunk_counts(field) == {row.id: 1 for row in rows}
    # Only the value that changed while semantic search was disabled.
    assert semantic_search.embedded_texts == ["new"]
    assert not SemanticSearchPendingUpdate.objects_and_trash.exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("use_tmp_media_root")
def test_user_template_copy_isnt_indexed_but_its_install_is(
    data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(data_fixture, user)
    handler = UserTemplateHandler()

    template_workspace = handler.copy_applications(
        user, [table.database], name="Template"
    )

    # The copy remembers the setting, so that its installs are indexed.
    template_fields = SemanticSearchField.objects.filter(
        field__table__database__workspace=template_workspace
    )
    assert template_fields.count() == 1
    assert not SemanticSearchPendingUpdate.objects_and_trash.filter(
        field_id__in=template_fields.values("field_id")
    ).exists()

    template = data_fixture.create_user_template(
        user=user, workspace=template_workspace
    )
    target = data_fixture.create_workspace(user=user)
    content = handler.serialize_template_content(template)
    with transaction.atomic():
        applications = handler.install_template_content(user, target, template, content)
    installed_table = applications[0].specific.table_set.get()
    index(installed_table)

    installed_field = installed_table.field_set.get(name=field.name)
    assert SemanticSearchField.objects.filter(field=installed_field).exists()
    assert len(get_chunk_counts(installed_field)) == len(rows)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_official_template_isnt_indexed_but_its_install_is(
    data_fixture, semantic_search, tmpdir, settings
):
    # The test template, with semantic search enabled for a field like an export
    # of a field with semantic search contains it.
    source = os.path.join(settings.BASE_DIR, "../../../tests/templates")
    template_json = json.loads(Path(source, "example-template.json").read_text())
    customers = template_json["export"][0]["tables"][0]
    name_field = next(field for field in customers["fields"] if field["id"] == 8)
    name_field["extensions"] = {"semantic_search": {"enabled": True}}
    Path(tmpdir, "example-template.json").write_text(json.dumps(template_json))
    shutil.copy(Path(source, "example-template.zip"), Path(tmpdir))
    settings.APPLICATION_TEMPLATES_DIR = str(tmpdir)
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = CoreHandler()

    handler.sync_templates(storage=storage, pattern="example-template")

    # The previewed copy remembers the setting, so that its installs are indexed.
    template = Template.objects.get(slug="example-template")
    template_fields = SemanticSearchField.objects.filter(
        field__table__database__workspace=template.workspace
    )
    assert template_fields.count() == 1
    assert not SemanticSearchPendingUpdate.objects_and_trash.filter(
        field_id__in=template_fields.values("field_id")
    ).exists()

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    applications, _ = handler.install_template(
        user, workspace, template, storage=storage
    )
    installed_table = applications[0].specific.table_set.get(name="Customers")
    index(installed_table)

    installed_field = installed_table.field_set.get(name="Name")
    assert SemanticSearchField.objects.filter(field=installed_field).exists()
    assert len(get_chunk_counts(installed_field)) == len(customers["rows"])


@pytest.mark.django_db
def test_permanently_deleting_rows_queries_semantic_search_once_per_trash_entry(
    data_fixture, semantic_search, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    table, field, rows = create_indexed_field(
        data_fixture, user, values=[f"value {number}" for number in range(25)]
    )
    row_ids = [row.id for row in rows]

    def count_semantic_search_queries(trash_entries: list[list[int]]) -> int:
        for entry_row_ids in trash_entries:
            RowHandler().delete_rows(user, table, entry_row_ids)
        TrashEntry.objects.update(should_be_permanently_deleted=True)
        # Including the marking of the vectors when the deletion is committed.
        with CaptureQueriesContext(connection) as captured:
            with django_capture_on_commit_callbacks(execute=True):
                TrashHandler.permanently_delete_marked_trash()
        return sum(
            "baserow_enterprise_semanticsearch" in query["sql"]
            and 'FROM "database_field"' not in query["sql"]
            for query in captured.captured_queries
        )

    one_row = count_semantic_search_queries([row_ids[:1]])
    many_rows = count_semantic_search_queries([row_ids[1:21]])
    two_entries = count_semantic_search_queries([row_ids[21:22], row_ids[22:23]])

    assert one_row > 0
    assert many_rows == one_row
    assert two_entries == one_row * 2
    periodic_check_pending_search_data()
    assert get_chunk_counts(field) == {row_id: 1 for row_id in row_ids[23:]}


@pytest.mark.django_db
def test_vector_tables_of_workspaces_with_a_clashing_unique_together_name(
    semantic_search,
):
    # Django names the `unique_together` constraint of both these workspaces
    # the same, so the second table wasn't created.
    for workspace_id in (71256, 100624):
        SemanticSearchVectorTable(workspace_id).create_if_not_exists()

    assert SemanticSearchVectorTable(71256).exists()
    assert SemanticSearchVectorTable(100624).exists()


@pytest.mark.django_db
def test_create_vector_table_exits_its_transaction_if_the_index_fails(
    data_fixture, semantic_search
):
    workspace = data_fixture.create_workspace()
    vector_table = SemanticSearchVectorTable(workspace.id)
    # Taking the index's name makes the deferred CREATE INDEX fail.
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE TABLE {vector_table.name}_embedding_idx (id int)")
    savepoint_ids = list(connection.savepoint_ids)

    vector_table.create_if_not_exists()

    assert connection.savepoint_ids == savepoint_ids
    assert not vector_table.exists()
