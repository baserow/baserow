from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest
from baserow_premium.views.exceptions import KanbanViewFieldDoesNotBelongToSameTable
from baserow_premium.views.models import KanbanViewFieldOptions

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_field_of_same_table_is_provided(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    single_select_field_2 = premium_data_fixture.create_single_select_field()

    view_handler = ViewHandler()

    with pytest.raises(KanbanViewFieldDoesNotBelongToSameTable):
        view_handler.create_view(
            user=user,
            table=table,
            type_name="kanban",
            single_select_field=single_select_field_2,
        )

    with pytest.raises(KanbanViewFieldDoesNotBelongToSameTable):
        view_handler.create_view(
            user=user,
            table=table,
            type_name="kanban",
            single_select_field=single_select_field_2.id,
        )

    kanban_view = view_handler.create_view(
        user=user,
        table=table,
        type_name="kanban",
        single_select_field=single_select_field,
    )

    with pytest.raises(KanbanViewFieldDoesNotBelongToSameTable):
        view_handler.update_view(
            user=user,
            view=kanban_view,
            single_select_field=single_select_field_2,
        )

    with pytest.raises(KanbanViewFieldDoesNotBelongToSameTable):
        view_handler.update_view(
            user=user,
            view=kanban_view,
            single_select_field=single_select_field_2.id,
        )

    view_handler.update_view(
        user=user,
        view=kanban_view,
        single_select_field=None,
    )


@pytest.mark.django_db
def test_import_export_kanban_view(premium_data_fixture, tmpdir):
    user = premium_data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    table = premium_data_fixture.create_database_table(user=user)
    file_field = premium_data_fixture.create_file_field(table=table)
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=file_field
    )
    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    field_option = premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban_view, field=single_select_field, hidden=True, order=1
    )
    kanban_view.single_select_field = single_select_field
    kanban_view.save()

    files_buffer = BytesIO()
    kanban_field_type = view_type_registry.get("kanban")

    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        serialized = kanban_field_type.export_serialized(
            kanban_view,
            ImportExportConfig(include_permission_data=False),
            files_zip=files_zip,
            storage=storage,
        )

    assert serialized["id"] == kanban_view.id
    assert serialized["type"] == "kanban"
    assert serialized["name"] == kanban_view.name
    assert serialized["order"] == 0
    assert serialized["single_select_field_id"] == single_select_field.id
    assert serialized["card_cover_image_field_id"] == file_field.id
    assert len(serialized["field_options"]) == 2
    assert serialized["field_options"][0]["id"] == field_option.id
    assert serialized["field_options"][0]["field_id"] == field_option.field_id
    assert serialized["field_options"][0]["hidden"] is True
    assert serialized["field_options"][0]["order"] == 1

    imported_single_select_field = premium_data_fixture.create_single_select_field(
        table=table
    )
    imported_file_field = premium_data_fixture.create_file_field(table=table)

    id_mapping = {
        "database_fields": {
            single_select_field.id: imported_single_select_field.id,
            file_field.id: imported_file_field.id,
        }
    }

    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        imported_kanban_view = kanban_field_type.import_serialized(
            kanban_view.table,
            serialized,
            ImportExportConfig(include_permission_data=False),
            id_mapping,
            files_zip,
            storage,
        )

    assert kanban_view.id != imported_kanban_view.id
    assert kanban_view.name == imported_kanban_view.name
    assert kanban_view.order == imported_kanban_view.order
    assert (
        kanban_view.single_select_field_id != imported_kanban_view.single_select_field
    )
    assert (
        kanban_view.card_cover_image_field_id
        != imported_kanban_view.card_cover_image_field_id
    )
    assert imported_kanban_view.card_cover_image_field_id == imported_file_field.id

    imported_field_options = imported_kanban_view.get_field_options()
    assert len(imported_field_options) == 2
    imported_field_option = imported_field_options[0]
    assert field_option.id != imported_field_option.id
    assert imported_single_select_field.id == imported_field_option.field_id
    assert field_option.hidden == imported_field_option.hidden
    assert field_option.order == imported_field_option.order


@pytest.mark.django_db
def test_newly_created_kanban_view(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_text_field(table=table, primary=True)
    premium_data_fixture.create_text_field(table=table)
    premium_data_fixture.create_text_field(table=table)
    premium_data_fixture.create_text_field(table=table)

    handler = ViewHandler()
    handler.create_view(user, table=table, type_name="kanban")

    all_field_options = (
        KanbanViewFieldOptions.objects.all()
        .order_by("field_id")
        .values_list("hidden", flat=True)
    )
    assert list(all_field_options) == [False, False, False, True]


@pytest.mark.django_db
def test_convert_card_cover_image_field_to_another(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    file_field = premium_data_fixture.create_file_field(table=table)
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, card_cover_image_field=file_field
    )

    FieldHandler().update_field(user=user, field=file_field, new_type_name="text")
    kanban_view.refresh_from_db()
    assert kanban_view.card_cover_image_field_id is None


@pytest.mark.django_db
def test_convert_card_cover_image_field_deleted(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    file_field = premium_data_fixture.create_file_field(table=table)
    kanban_view = premium_data_fixture.create_kanban_view(
        table=table, card_cover_image_field=file_field
    )

    FieldHandler().delete_field(user=user, field=file_field)

    kanban_view.refresh_from_db()
    assert kanban_view.card_cover_image_field_id is None


@pytest.mark.django_db
def test_get_visible_fields_options_with_no_single_select_and_cover(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=None
    )

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_visible, hidden=False, order=3
    )

    kanban_field_type = view_type_registry.get("kanban")

    fields = kanban_field_type.get_visible_field_options_in_order(kanban)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [field_visible.id]


@pytest.mark.django_db
def test_get_visible_fields_options_with_hidden_single_select_and_cover(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=None
    )

    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    cover_field = premium_data_fixture.create_file_field(table=table)
    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)

    kanban.single_select_field = single_select_field
    kanban.card_cover_image_field = cover_field
    kanban.save()

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=single_select_field, hidden=True, order=0
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=cover_field, hidden=True, order=1
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_visible, hidden=False, order=3
    )

    kanban_field_type = view_type_registry.get("kanban")

    fields = kanban_field_type.get_visible_field_options_in_order(kanban)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [single_select_field.id, cover_field.id, field_visible.id]


@pytest.mark.django_db
def test_get_visible_fields_options_with_visible_single_select_and_cover(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=None
    )

    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    cover_field = premium_data_fixture.create_file_field(table=table)
    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    premium_data_fixture.create_text_field(table=table)

    kanban.single_select_field = single_select_field
    kanban.card_cover_image_field = cover_field
    kanban.save()

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=single_select_field, hidden=False, order=0
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=cover_field, hidden=False, order=1
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_visible, hidden=False, order=3
    )

    kanban_field_type = view_type_registry.get("kanban")

    fields = kanban_field_type.get_visible_field_options_in_order(kanban)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [single_select_field.id, cover_field.id, field_visible.id]


@pytest.mark.django_db
def test_get_visible_fields_options_with_non_existing_single_select_and_cover(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=None
    )

    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    cover_field = premium_data_fixture.create_file_field(table=table)
    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)

    print(single_select_field.id, cover_field.id, field_hidden.id, field_visible.id)

    kanban.single_select_field = single_select_field
    kanban.card_cover_image_field = cover_field
    kanban.save()

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_visible, hidden=False, order=3
    )

    kanban_field_type = view_type_registry.get("kanban")

    fields = kanban_field_type.get_visible_field_options_in_order(kanban)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [field_visible.id, single_select_field.id, cover_field.id]


@pytest.mark.django_db
def test_get_hidden_kanban_view_fields_with_not_existing_single_select_and_cover(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=None
    )
    kanban.kanbanviewfieldoptions_set.all().delete()

    kanban_field_type = view_type_registry.get("kanban")
    assert len(kanban_field_type.get_hidden_fields(kanban)) == 0


@pytest.mark.django_db
def test_get_hidden_kanban_view_fields_without_single_select_and_cover_field_options(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=None
    )
    kanban.kanbanviewfieldoptions_set.all().delete()

    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    cover_field = premium_data_fixture.create_file_field(table=table)

    kanban.single_select_field = single_select_field
    kanban.card_cover_image_field = cover_field
    kanban.save()

    kanban_field_type = view_type_registry.get("kanban")
    assert len(kanban_field_type.get_hidden_fields(kanban)) == 0


@pytest.mark.django_db
def test_get_hidden_kanban_view_fields_with_hidden_single_select_and_cover_field_options(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=None
    )
    kanban.kanbanviewfieldoptions_set.all().delete()

    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    cover_field = premium_data_fixture.create_file_field(table=table)

    kanban.single_select_field = single_select_field
    kanban.card_cover_image_field = cover_field
    kanban.save()

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=single_select_field, hidden=True
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=cover_field, hidden=True
    )

    kanban_field_type = view_type_registry.get("kanban")
    assert len(kanban_field_type.get_hidden_fields(kanban)) == 0


@pytest.mark.django_db
def test_get_hidden_kanban_view_fields_with_hidden_and_visible_fields(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(table=table)
    kanban.kanbanviewfieldoptions_set.all().delete()

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_visible, hidden=False
    )

    kanban_field_type = view_type_registry.get("kanban")

    results = kanban_field_type.get_hidden_fields(kanban)
    assert len(results) == 2
    assert field_hidden.id in results
    assert field_no_field_option.id in results


@pytest.mark.django_db
def test_get_hidden_kanban_view_fields_with_field_ids_to_check(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(table=table)
    kanban.kanbanviewfieldoptions_set.all().delete()

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_visible, hidden=False
    )

    kanban_field_type = view_type_registry.get("kanban")

    results = kanban_field_type.get_hidden_fields(
        kanban, field_ids_to_check=[field_hidden.id, field_visible.id]
    )
    assert len(results) == 1
    assert field_hidden.id in results


@pytest.mark.django_db
def test_get_hidden_kanban_view_fields_all_fields(
    premium_data_fixture, django_assert_num_queries
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    kanban = premium_data_fixture.create_kanban_view(
        table=table, single_select_field=None, card_cover_image_field=None
    )

    single_select_field = premium_data_fixture.create_single_select_field(table=table)
    cover_field = premium_data_fixture.create_file_field(table=table)
    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    kanban.single_select_field = single_select_field
    kanban.card_cover_image_field = cover_field
    kanban.save()

    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=single_select_field, hidden=True
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=cover_field, hidden=False
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_kanban_view_field_option(
        kanban_view=kanban, field=field_visible, hidden=False
    )

    kanban_field_type = view_type_registry.get("kanban")

    with django_assert_num_queries(2):
        results = kanban_field_type.get_hidden_fields(kanban)
        assert len(results) == 2
        assert field_hidden.id in results
        assert field_no_field_option.id in results


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.schedule_update_search_data"
)
def test_when_public_field_updated_number_of_queries_does_not_increase_with_amount_of_kanban_views(
    mock, premium_data_fixture, django_assert_num_queries
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    visible_field = premium_data_fixture.create_text_field(
        table=table, order=0, name="b"
    )

    premium_data_fixture.create_kanban_view(
        user=user,
        table=table,
        public=True,
    )

    # Warm up the caches
    FieldHandler().update_field(user, visible_field, name="c")

    with CaptureQueriesContext(connection) as captured:
        FieldHandler().update_field(user, visible_field, name="a")

    premium_data_fixture.create_kanban_view(
        user=user,
        table=table,
        public=True,
    )

    with django_assert_num_queries(len(captured.captured_queries)):
        FieldHandler().update_field(user, visible_field, name="abc")
