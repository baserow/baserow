import pytest

from baserow.contrib.database.action.scopes import ViewActionScopeType
from baserow.contrib.database.views.actions import CopyViewConfigurationActionType
from baserow.contrib.database.views.models import ViewFilter, ViewSort
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry


@pytest.mark.django_db
def test_can_undo_redo_copy_view_configuration(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table, filter_type="OR")
    dest_view = data_fixture.create_grid_view(table=table, filter_type="AND")

    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="copied"
    )
    data_fixture.create_view_sort(view=source_view, field=field, order="DESC")
    original_filter = data_fixture.create_view_filter(
        view=dest_view, field=field, type="equal", value="original"
    )
    original_sort = data_fixture.create_view_sort(
        view=dest_view, field=field, order="ASC"
    )

    action_type_registry.get_by_type(CopyViewConfigurationActionType).do(
        user, source_view, dest_view, ["filters", "sorts"]
    )

    dest_view.refresh_from_db()
    assert dest_view.filter_type == "OR"
    copied_filter = ViewFilter.objects.get(view=dest_view)
    assert copied_filter.value == "copied"
    copied_sort = ViewSort.objects.get(view=dest_view)
    assert copied_sort.order == "DESC"

    # A single undo reverts the whole copy and restores the original objects
    # with their original ids.
    ActionHandler.undo(user, [ViewActionScopeType.value(dest_view.id)], session_id)

    dest_view.refresh_from_db()
    assert dest_view.filter_type == "AND"
    restored_filter = ViewFilter.objects.get(view=dest_view)
    assert restored_filter.id == original_filter.id
    assert restored_filter.value == "original"
    restored_sort = ViewSort.objects.get(view=dest_view)
    assert restored_sort.id == original_sort.id
    assert restored_sort.order == "ASC"

    # Redo applies the copied configuration again, with the ids created by the
    # original copy.
    ActionHandler.redo(user, [ViewActionScopeType.value(dest_view.id)], session_id)

    dest_view.refresh_from_db()
    assert dest_view.filter_type == "OR"
    redone_filter = ViewFilter.objects.get(view=dest_view)
    assert redone_filter.id == copied_filter.id
    assert redone_filter.value == "copied"
    redone_sort = ViewSort.objects.get(view=dest_view)
    assert redone_sort.id == copied_sort.id


@pytest.mark.django_db
def test_undo_copy_view_configuration_with_deleted_field(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user)
    field = data_fixture.create_text_field(table=table)
    field_to_delete = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)

    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )
    data_fixture.create_view_filter(
        view=dest_view, field=field, type="equal", value="original"
    )
    data_fixture.create_view_filter(
        view=dest_view, field=field_to_delete, type="equal", value="doomed"
    )

    action_type_registry.get_by_type(CopyViewConfigurationActionType).do(
        user, source_view, dest_view, ["filters"]
    )

    # Permanently delete a field that the original configuration references.
    field_to_delete.delete()

    ActionHandler.undo(user, [ViewActionScopeType.value(dest_view.id)], session_id)

    # The filter on the deleted field is skipped, the other one is restored.
    assert [view_filter.value for view_filter in dest_view.viewfilter_set.all()] == [
        "original"
    ]


@pytest.mark.django_db
def test_copy_view_configuration_action_is_scoped_to_dest_view(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )

    action_type_registry.get_by_type(CopyViewConfigurationActionType).do(
        user, source_view, dest_view, ["filters"]
    )

    # Undoing in the scope of the source view does nothing.
    undone = ActionHandler.undo(
        user, [ViewActionScopeType.value(source_view.id)], session_id
    )
    assert undone == []
    assert dest_view.viewfilter_set.count() == 1
