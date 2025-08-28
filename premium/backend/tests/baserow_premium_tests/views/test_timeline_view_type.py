from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.storage import FileSystemStorage

import pytest
from baserow_premium.views.exceptions import TimelineViewHasInvalidDateSettings
from baserow_premium.views.handler import get_timeline_view_filtered_queryset
from baserow_premium.views.models import TimelineViewFieldOptions

from baserow.contrib.database.action.scopes import ViewActionScopeType
from baserow.contrib.database.fields.exceptions import (
    FieldNotInTable,
    IncompatibleField,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.views.actions import UpdateViewActionType
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import (
    assert_undo_redo_actions_are_valid,
    setup_interesting_test_table,
)


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_date_field_same_table(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(table=table)
    date_field_diff_table = premium_data_fixture.create_date_field()

    view_handler = ViewHandler()

    with pytest.raises(FieldNotInTable):
        view_handler.create_view(
            user=user,
            table=table,
            type_name="timeline",
            start_date_field=date_field_diff_table,
        )

    with pytest.raises(FieldNotInTable):
        view_handler.create_view(
            user=user,
            table=table,
            type_name="timeline",
            start_date_field=date_field_diff_table.id,
        )

    timeline_view = view_handler.create_view(
        user=user,
        table=table,
        type_name="timeline",
        start_date_field=date_field,
    )

    view_handler.create_view(
        user=user,
        table=table,
        type_name="timeline",
        start_date_field=None,
    )

    with pytest.raises(FieldNotInTable):
        view_handler.update_view(
            user=user,
            view=timeline_view,
            start_date_field=date_field_diff_table,
        )

    with pytest.raises(FieldNotInTable):
        view_handler.update_view(
            user=user,
            view=timeline_view,
            start_date_field=date_field_diff_table.id,
        )

    view_handler.update_view(
        user=user,
        view=timeline_view,
        start_date_field=date_field,
    )

    view_handler.update_view(
        user=user,
        view=timeline_view,
        start_date_field=None,
    )


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_import_export(premium_data_fixture, tmpdir):
    user = premium_data_fixture.create_user()
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    table = premium_data_fixture.create_database_table(user=user)
    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=start_date_field, end_date_field=end_date_field
    )
    start_field_option = premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline_view, field=start_date_field, hidden=True, order=1
    )
    end_field_option = premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline_view, field=end_date_field, hidden=True, order=1
    )
    timeline_view_type = view_type_registry.get("timeline")

    files_buffer = BytesIO()
    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        serialized = timeline_view_type.export_serialized(
            timeline_view,
            ImportExportConfig(include_permission_data=False),
            files_zip=files_zip,
            storage=storage,
        )

    assert serialized["id"] == timeline_view.id
    assert serialized["type"] == "timeline"
    assert serialized["name"] == timeline_view.name
    assert serialized["order"] == 0
    assert serialized["start_date_field_id"] == start_date_field.id
    assert serialized["end_date_field_id"] == end_date_field.id
    assert len(serialized["field_options"]) == 2
    assert serialized["field_options"][0]["id"] == start_field_option.id
    assert serialized["field_options"][0]["field_id"] == start_field_option.field_id
    assert serialized["field_options"][0]["hidden"] is True
    assert serialized["field_options"][0]["order"] == 1
    assert serialized["field_options"][1]["id"] == end_field_option.id
    assert serialized["field_options"][1]["field_id"] == end_field_option.field_id
    assert serialized["field_options"][1]["hidden"] is True
    assert serialized["field_options"][1]["order"] == 1

    imported_start_date_field = premium_data_fixture.create_date_field(table=table)
    imported_end_date_field = premium_data_fixture.create_date_field(table=table)

    id_mapping = {
        "database_fields": {
            start_date_field.id: imported_start_date_field.id,
            end_date_field.id: imported_end_date_field.id,
        }
    }

    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        imported_timeline_view = timeline_view_type.import_serialized(
            timeline_view.table,
            serialized,
            ImportExportConfig(include_permission_data=False),
            id_mapping,
            files_zip,
            storage,
        )

    assert timeline_view.id != imported_timeline_view.id
    assert timeline_view.name == imported_timeline_view.name
    assert timeline_view.order == imported_timeline_view.order
    assert (
        timeline_view.start_date_field_id != imported_timeline_view.start_date_field_id
    )
    assert timeline_view.end_date_field_id != imported_timeline_view.end_date_field_id

    imported_field_options = imported_timeline_view.get_field_options()
    assert len(imported_field_options) == 2
    imported_start_field_option = imported_field_options[0]
    assert start_field_option.id != imported_start_field_option.id
    assert imported_start_date_field.id == imported_start_field_option.field_id
    assert start_field_option.hidden == imported_start_field_option.hidden
    assert start_field_option.order == imported_start_field_option.order

    imported_end_field_option = imported_field_options[1]
    assert end_field_option.id != imported_end_field_option.id
    assert imported_end_date_field.id == imported_end_field_option.field_id
    assert end_field_option.hidden == imported_end_field_option.hidden
    assert end_field_option.order == imported_end_field_option.order


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_created(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_text_field(table=table, primary=True)
    premium_data_fixture.create_text_field(table=table)
    premium_data_fixture.create_text_field(table=table)
    premium_data_fixture.create_text_field(table=table)

    handler = ViewHandler()
    handler.create_view(user, table=table, type_name="timeline")

    all_field_options = (
        TimelineViewFieldOptions.objects.all()
        .order_by("field_id")
        .values_list("hidden", flat=True)
    )
    assert list(all_field_options) == [False, True, True, True]


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_rows_raises_if_date_settings_are_invalid(
    premium_data_fixture,
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table, _, _, _, context = setup_interesting_test_table(
        premium_data_fixture, user=user
    )
    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=start_date_field, end_date_field=end_date_field
    )

    start_date_field = FieldHandler().update_field(
        user=user, field=start_date_field, new_type_name="text"
    )
    timeline_view.refresh_from_db()
    with pytest.raises(IncompatibleField):
        get_timeline_view_filtered_queryset(user, timeline_view)

    start_date_field = FieldHandler().update_field(
        user=user,
        field=start_date_field,
        new_type_name="date",
    )
    end_date_field = FieldHandler().update_field(
        user=user, field=end_date_field, new_type_name="text"
    )

    timeline_view.refresh_from_db()
    with pytest.raises(IncompatibleField):
        get_timeline_view_filtered_queryset(user, timeline_view)

    end_date_field = FieldHandler().update_field(
        user=user, field=end_date_field, new_type_name="date"
    )

    for start_date_params, end_date_params in [
        ({"date_include_time": True}, {"date_include_time": False}),
        ({"date_include_time": False}, {"date_include_time": True}),
        (
            {"date_include_time": True},
            {"date_include_time": True, "date_force_timezone": "Europe/Rome"},
        ),
        (
            {"date_include_time": True, "date_force_timezone": "Europe/Rome"},
            {"date_include_time": True, "date_force_timezone": "UTC"},
        ),
    ]:
        FieldHandler().update_field(
            user=user, field=start_date_field, **start_date_params
        )
        FieldHandler().update_field(user=user, field=end_date_field, **end_date_params)

        timeline_view.refresh_from_db()
        with pytest.raises(TimelineViewHasInvalidDateSettings):
            get_timeline_view_filtered_queryset(user, timeline_view)


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_visible_fields_options_no_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_visible, hidden=False, order=3
    )

    timeline_field_type = view_type_registry.get("timeline")

    fields = timeline_field_type.get_visible_field_options_in_order(timeline)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [field_visible.id]


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_visible_fields_options_hidden_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)
    timeline.start_date_field = start_date_field
    timeline.end_date_field = end_date_field
    timeline.save()

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=start_date_field, hidden=True, order=0
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=end_date_field, hidden=True, order=1
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_visible, hidden=False, order=3
    )

    timeline_field_type = view_type_registry.get("timeline")

    fields = timeline_field_type.get_visible_field_options_in_order(timeline)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [start_date_field.id, end_date_field.id, field_visible.id]


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_visible_fields_options_visible_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)
    timeline.start_date_field = start_date_field
    timeline.end_date_field = end_date_field
    timeline.save()

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=start_date_field, hidden=False, order=0
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=end_date_field, hidden=False, order=0
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_visible, hidden=False, order=3
    )

    timeline_field_type = view_type_registry.get("timeline")

    fields = timeline_field_type.get_visible_field_options_in_order(timeline)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [start_date_field.id, end_date_field.id, field_visible.id]


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_visible_fields_options_without_date_field_option(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)
    timeline.start_date_field = start_date_field
    timeline.end_date_field = end_date_field
    timeline.save()

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_visible, hidden=False, order=3
    )

    timeline_field_type = view_type_registry.get("timeline")

    fields = timeline_field_type.get_visible_field_options_in_order(timeline)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [field_visible.id, start_date_field.id, end_date_field.id]


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_hidden_fields_no_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )
    timeline.timelineviewfieldoptions_set.all().delete()

    timeline_field_type = view_type_registry.get("timeline")
    assert len(timeline_field_type.get_hidden_fields(timeline)) == 0


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_hidden_fields_without_date_field_option(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )
    timeline.timelineviewfieldoptions_set.all().delete()

    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)

    timeline.start_date_field = start_date_field
    timeline.end_date_field = end_date_field
    timeline.save()

    timeline_field_type = view_type_registry.get("timeline")
    assert len(timeline_field_type.get_hidden_fields(timeline)) == 0


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_hidden_fields_with_hidden_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )
    timeline.timelineviewfieldoptions_set.all().delete()

    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)

    timeline.start_date_field = start_date_field
    timeline.end_date_field = end_date_field
    timeline.save()

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=start_date_field, hidden=True
    )

    timeline_field_type = view_type_registry.get("timeline")
    assert len(timeline_field_type.get_hidden_fields(timeline)) == 0


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_hidden_fields_with_hidden_and_visible_fields(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    timeline = premium_data_fixture.create_timeline_view(table=table)
    timeline.timelineviewfieldoptions_set.all().delete()

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_visible, hidden=False
    )

    timeline_field_type = view_type_registry.get("timeline")

    results = timeline_field_type.get_hidden_fields(timeline)
    assert len(results) == 2
    assert field_hidden.id in results
    assert field_no_field_option.id in results


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_hidden_fields_with_field_ids_to_check(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    timeline = premium_data_fixture.create_timeline_view(table=table)
    timeline.timelineviewfieldoptions_set.all().delete()

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_visible, hidden=False
    )

    timeline_field_type = view_type_registry.get("timeline")

    results = timeline_field_type.get_hidden_fields(
        timeline, field_ids_to_check=[field_hidden.id, field_visible.id]
    )
    assert len(results) == 1
    assert field_hidden.id in results


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_get_hidden_fields_all_fields(
    premium_data_fixture, django_assert_num_queries
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )

    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)
    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    timeline.start_date_field = start_date_field
    timeline.end_date_field = end_date_field
    timeline.save()

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=start_date_field, hidden=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=end_date_field, hidden=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view=timeline, field=field_visible, hidden=False
    )

    timeline_field_type = view_type_registry.get("timeline")

    with django_assert_num_queries(2):
        results = timeline_field_type.get_hidden_fields(timeline)
        assert len(results) == 2
        assert start_date_field.id not in results
        assert end_date_field.id not in results
        assert field_hidden.id in results
        assert field_no_field_option.id in results


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.view_timeline
def test_can_undo_redo_update_timeline_view(data_fixture, premium_data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = premium_data_fixture.create_database_table(user=user)
    date_field_1 = premium_data_fixture.create_date_field(table=table)
    date_field_2 = premium_data_fixture.create_date_field(table=table)
    timeline_view = premium_data_fixture.create_timeline_view(table=table)

    original_timeline_data = {
        "name": "Test Original",
        "filter_type": "AND",
        "filters_disabled": False,
        "start_date_field": date_field_1,
        "end_date_field": date_field_2,
    }

    timeline_view_with_changes = ViewHandler().update_view(
        user, timeline_view, **original_timeline_data
    )
    timeline_view = timeline_view_with_changes.updated_view_instance

    assert timeline_view.name == original_timeline_data["name"]
    assert (
        timeline_view.start_date_field_id
        == original_timeline_data["start_date_field"].id
    )
    assert (
        timeline_view.end_date_field_id == original_timeline_data["end_date_field"].id
    )

    new_timeline_data = {
        "name": "Test New",
        "filter_type": "OR",
        "filters_disabled": True,
        "start_date_field": date_field_2,
        "end_date_field": date_field_1,
    }

    timeline_view = action_type_registry.get_by_type(UpdateViewActionType).do(
        user, timeline_view, **new_timeline_data
    )

    assert timeline_view.name == new_timeline_data["name"]
    assert timeline_view.start_date_field_id == new_timeline_data["start_date_field"].id
    assert timeline_view.end_date_field_id == new_timeline_data["end_date_field"].id

    action_undone = ActionHandler.undo(
        user, [ViewActionScopeType.value(timeline_view.id)], session_id
    )

    timeline_view.refresh_from_db()
    assert_undo_redo_actions_are_valid(action_undone, [UpdateViewActionType])

    assert timeline_view.name == original_timeline_data["name"]
    assert (
        timeline_view.start_date_field_id
        == original_timeline_data["start_date_field"].id
    )
    assert (
        timeline_view.end_date_field_id == original_timeline_data["end_date_field"].id
    )

    action_redone = ActionHandler.redo(
        user, [ViewActionScopeType.value(timeline_view.id)], session_id
    )

    timeline_view.refresh_from_db()
    assert_undo_redo_actions_are_valid(action_redone, [UpdateViewActionType])

    assert timeline_view.name == new_timeline_data["name"]
    assert timeline_view.start_date_field_id == new_timeline_data["start_date_field"].id
    assert timeline_view.end_date_field_id == new_timeline_data["end_date_field"].id


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_view_hierarchy(premium_data_fixture):
    user = premium_data_fixture.create_user()
    workspace = premium_data_fixture.create_workspace(user=user)
    app = premium_data_fixture.create_database_application(
        workspace=workspace, name="Test 1"
    )
    table = premium_data_fixture.create_database_table(database=app)
    premium_data_fixture.create_text_field(table=table)

    timeline_view = premium_data_fixture.create_timeline_view(table=table, user=user)

    assert timeline_view.get_parent() == table
    assert timeline_view.get_root() == workspace
    timeline_view_field_options = timeline_view.get_field_options()[0]
    assert timeline_view_field_options.get_parent() == timeline_view
    assert timeline_view_field_options.get_root() == workspace


@pytest.mark.django_db
@pytest.mark.view_timeline
def test_timeline_after_delete_field_set_date_field_to_none(
    premium_data_fixture, data_fixture, django_assert_num_queries
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)

    view = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=start_date_field, end_date_field=end_date_field
    )

    FieldHandler().delete_field(user, start_date_field)
    view.refresh_from_db()

    assert view.start_date_field is None

    FieldHandler().delete_field(user, end_date_field)
    view.refresh_from_db()

    assert view.end_date_field is None
