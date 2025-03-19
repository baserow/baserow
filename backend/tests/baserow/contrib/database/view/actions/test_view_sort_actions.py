import pytest

from baserow.contrib.database.action.scopes import ViewActionScopeType
from baserow.contrib.database.views.actions import (
    CreateViewSortActionType,
    DeleteViewSortActionType,
    UpdateViewSortActionType,
)
from baserow.contrib.database.views.models import ViewSort
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_creating_view_sort(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    number_field = data_fixture.create_number_field(
        table=table, name="value", number_decimal_places=1
    )

    assert ViewSort.objects.count() == 0

    view_sort = action_type_registry.get_by_type(CreateViewSortActionType).do(
        user, grid_view, number_field, "DESC"
    )

    assert ViewSort.objects.filter(pk=view_sort.id).count() == 1
    assert view_sort.view.id == grid_view.id
    assert view_sort.field.id == number_field.id
    assert view_sort.order == "DESC"

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    assert ViewSort.objects.filter(pk=view_sort.id).count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_creating_view_sort(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    number_field = data_fixture.create_number_field(
        table=table, name="value", number_decimal_places=1
    )

    assert ViewSort.objects.count() == 0

    view_sort = action_type_registry.get_by_type(CreateViewSortActionType).do(
        user, grid_view, number_field, "DESC"
    )
    original_view_sort_id = view_sort.id

    assert ViewSort.objects.filter(pk=view_sort.id).count() == 1
    assert view_sort.view.id == grid_view.id
    assert view_sort.field.id == number_field.id
    assert view_sort.order == "DESC"

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    assert ViewSort.objects.filter(pk=view_sort.id).count() == 0

    ActionHandler.redo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    assert ViewSort.objects.filter(pk=view_sort.id).count() == 1
    updated_view_sort = ViewSort.objects.first()
    assert updated_view_sort.id == original_view_sort_id
    assert updated_view_sort.view.id == grid_view.id
    assert updated_view_sort.field.id == number_field.id
    assert updated_view_sort.order == "DESC"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_creating_view_sort_with_type(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_single_select_field(table=table, name="value")

    assert ViewSort.objects.count() == 0

    view_sort = action_type_registry.get_by_type(CreateViewSortActionType).do(
        user, grid_view, field, "DESC", sort_type="order"
    )

    assert ViewSort.objects.filter(pk=view_sort.id).count() == 1
    assert view_sort.type == "order"

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    assert ViewSort.objects.filter(pk=view_sort.id).count() == 0

    ActionHandler.redo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    assert ViewSort.objects.filter(pk=view_sort.id).count() == 1
    updated_view_sort = ViewSort.objects.first()
    assert updated_view_sort.type == "order"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_updating_view_sort(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    view_sort = data_fixture.create_view_sort(
        view=grid_view, field=text_field, order="ASC"
    )

    assert view_sort.view.id == grid_view.id
    assert view_sort.field.id == text_field.id
    assert view_sort.order == "ASC"

    action_type_registry.get_by_type(UpdateViewSortActionType).do(
        user, view_sort, order="DESC"
    )

    view_sort.refresh_from_db()
    assert view_sort.order == "DESC"

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    view_sort.refresh_from_db()
    assert view_sort.order == "ASC"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_updating_view_sort(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    view_sort = data_fixture.create_view_sort(
        view=grid_view, field=text_field, order="ASC"
    )

    assert view_sort.view.id == grid_view.id
    assert view_sort.field.id == text_field.id
    assert view_sort.order == "ASC"

    action_type_registry.get_by_type(UpdateViewSortActionType).do(
        user, view_sort, order="DESC"
    )

    view_sort.refresh_from_db()
    assert view_sort.order == "DESC"

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    view_sort.refresh_from_db()
    assert view_sort.order == "ASC"

    ActionHandler.redo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    view_sort.refresh_from_db()
    assert view_sort.order == "DESC"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_updating_view_sort_type(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    single_select_field = data_fixture.create_single_select_field(table=table)
    view_sort = data_fixture.create_view_sort(
        view=grid_view, field=single_select_field, order="ASC", type="order"
    )

    action_type_registry.get_by_type(UpdateViewSortActionType).do(
        user, view_sort, sort_type="default"
    )

    view_sort.refresh_from_db()
    assert view_sort.type == "default"

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    view_sort.refresh_from_db()
    assert view_sort.type == "order"

    ActionHandler.redo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    view_sort.refresh_from_db()
    assert view_sort.type == "default"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_deleting_view_sort(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    view_sort = data_fixture.create_view_sort(
        view=grid_view, field=text_field, order="ASC"
    )
    original_view_sort_id = view_sort.id

    assert ViewSort.objects.count() == 1
    assert view_sort.view.id == grid_view.id
    assert view_sort.field.id == text_field.id
    assert view_sort.order == "ASC"

    action_type_registry.get_by_type(DeleteViewSortActionType).do(user, view_sort)

    assert ViewSort.objects.count() == 0

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    assert ViewSort.objects.count() == 1
    updated_view_sort = ViewSort.objects.first()
    assert updated_view_sort.id == original_view_sort_id
    assert updated_view_sort.view.id == grid_view.id
    assert updated_view_sort.field.id == text_field.id
    assert updated_view_sort.order == "ASC"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_deleting_view_sort(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    view_sort = data_fixture.create_view_sort(
        view=grid_view, field=text_field, order="ASC"
    )

    assert ViewSort.objects.count() == 1
    assert view_sort.view.id == grid_view.id
    assert view_sort.field.id == text_field.id
    assert view_sort.order == "ASC"

    action_type_registry.get_by_type(DeleteViewSortActionType).do(user, view_sort)

    assert ViewSort.objects.count() == 0

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    assert ViewSort.objects.count() == 1

    ActionHandler.redo(user, [ViewActionScopeType.value(grid_view.id)], session_id)

    assert ViewSort.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_deleting_view_sort_with_type(data_fixture):
    session_id = "1010"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_single_select_field(table=table)
    view_sort = data_fixture.create_view_sort(
        view=grid_view, field=field, order="ASC", type="order"
    )

    action_type_registry.get_by_type(DeleteViewSortActionType).do(user, view_sort)

    assert ViewSort.objects.count() == 0

    ActionHandler.undo(user, [ViewActionScopeType.value(grid_view.id)], session_id)
    sorts = ViewSort.objects.all()
    assert len(sorts) == 1
    assert sorts[0].type == "order"
