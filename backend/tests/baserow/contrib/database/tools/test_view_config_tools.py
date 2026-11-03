"""Tests for the view config tools shared by MCP and Kuma."""

import json
from unittest.mock import ANY

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.tools.view_config import (
    FieldVisibility,
    ViewSortItem,
    delete_view_filters,
    delete_views,
    set_field_visibility,
    set_view_sorts,
)
from baserow.contrib.database.tools.views import list_views
from baserow.contrib.database.views.actions import (
    CreateViewSortActionType,
    DeleteViewActionType,
    DeleteViewFilterActionType,
    DeleteViewSortActionType,
    UpdateViewFieldOptionsActionType,
)
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.models import (
    GridViewFieldOptions,
    View,
    ViewFilter,
    ViewSort,
)
from baserow.core.action.models import Action
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError


def _call(endpoint, name, arguments):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await client.call_tool(name, arguments)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


@pytest.fixture
def grid(data_fixture):
    user = data_fixture.create_user(session_id="session")
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    primary = data_fixture.create_text_field(table=table, name="Name", primary=True)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    due = data_fixture.create_date_field(table=table, name="Due")
    view = data_fixture.create_grid_view(table=table, name="Grid")
    ctx = ToolContext(user=user, workspace=workspace)
    return ctx, view, primary, amount, due


def _foreign_field(data_fixture, ctx):
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    return data_fixture.create_text_field(table=table)


def _actions(action_type):
    return Action.objects.filter(type=action_type.type).count()


@pytest.mark.django_db
def test_set_view_sorts_replaces_existing(data_fixture, grid):
    ctx, view, primary, amount, _ = grid
    data_fixture.create_view_sort(view=view, field=primary, order="ASC")

    result = set_view_sorts(
        ctx, view.id, [ViewSortItem(field_id=amount.id, order="DESC")]
    )

    assert result == {"sorts": [{"id": ANY, "field_id": amount.id, "order": "DESC"}]}
    assert ViewSort.objects.filter(view=view).count() == 1


@pytest.mark.django_db
def test_set_view_sorts_updates_the_order_of_a_kept_sort(data_fixture, grid):
    ctx, view, primary, _, _ = grid
    kept = data_fixture.create_view_sort(view=view, field=primary, order="ASC")

    result = set_view_sorts(
        ctx, view.id, [ViewSortItem(field_id=primary.id, order="DESC")]
    )

    assert result["sorts"] == [{"id": kept.id, "field_id": primary.id, "order": "DESC"}]


@pytest.mark.django_db
def test_set_view_sorts_follows_the_order_of_the_list(data_fixture, grid):
    # The first sort in the list must end up as the first in the chain, also when
    # both fields were already sorted the other way round.
    ctx, view, primary, amount, _ = grid
    data_fixture.create_view_sort(view=view, field=primary, order="ASC")
    data_fixture.create_view_sort(view=view, field=amount, order="ASC")

    result = set_view_sorts(
        ctx,
        view.id,
        [ViewSortItem(field_id=amount.id), ViewSortItem(field_id=primary.id)],
    )

    assert [sort["field_id"] for sort in result["sorts"]] == [amount.id, primary.id]
    stored = ViewSort.objects.filter(view=view).order_by("priority", "id")
    assert [sort.field_id for sort in stored] == [amount.id, primary.id]


@pytest.mark.django_db
def test_set_view_sorts_keeps_the_type_of_a_reordered_sort(data_fixture, grid):
    ctx, view, primary, _, _ = grid
    status = data_fixture.create_single_select_field(table=view.table, name="Status")
    data_fixture.create_view_sort(view=view, field=primary, order="ASC")
    data_fixture.create_view_sort(view=view, field=status, order="ASC", type="order")

    set_view_sorts(
        ctx,
        view.id,
        [ViewSortItem(field_id=status.id), ViewSortItem(field_id=primary.id)],
    )

    assert ViewSort.objects.get(view=view, field=status).type == "order"


@pytest.mark.django_db
def test_set_view_sorts_with_empty_list_removes_them(data_fixture, grid):
    ctx, view, primary, _, _ = grid
    data_fixture.create_view_sort(view=view, field=primary, order="ASC")

    assert set_view_sorts(ctx, view.id, []) == {"sorts": []}
    assert ViewSort.objects.filter(view=view).count() == 0


@pytest.mark.django_db
def test_set_view_sorts_registers_an_action_per_change(data_fixture, grid):
    ctx, view, primary, amount, _ = grid
    data_fixture.create_view_sort(view=view, field=primary, order="ASC")

    set_view_sorts(ctx, view.id, [ViewSortItem(field_id=amount.id)])

    assert _actions(DeleteViewSortActionType) == 1
    assert _actions(CreateViewSortActionType) == 1


@pytest.mark.django_db
def test_set_view_sorts_with_field_of_other_table_changes_nothing(data_fixture, grid):
    ctx, view, primary, _, _ = grid
    data_fixture.create_view_sort(view=view, field=primary, order="ASC")
    foreign = _foreign_field(data_fixture, ctx)

    with pytest.raises(FieldDoesNotExist):
        set_view_sorts(ctx, view.id, [ViewSortItem(field_id=foreign.id)])

    assert ViewSort.objects.get(view=view).field_id == primary.id


@pytest.mark.django_db
def test_set_view_sorts_rejects_the_same_field_twice(grid):
    ctx, view, primary, _, _ = grid

    with pytest.raises(ToolInputError):
        set_view_sorts(
            ctx,
            view.id,
            [ViewSortItem(field_id=primary.id), ViewSortItem(field_id=primary.id)],
        )


@pytest.mark.django_db
def test_set_view_sorts_explains_a_view_that_takes_no_sorts(data_fixture, grid):
    ctx, view, primary, _, _ = grid
    form = data_fixture.create_form_view(table=view.table)

    with pytest.raises(ToolInputError):
        set_view_sorts(ctx, form.id, [ViewSortItem(field_id=primary.id)])


@pytest.mark.django_db
def test_set_field_visibility_hides_and_reports_foreign_field(data_fixture, grid):
    ctx, view, _, amount, _ = grid
    foreign = _foreign_field(data_fixture, ctx)

    result = set_field_visibility(
        ctx,
        view.id,
        [
            FieldVisibility(field_id=amount.id, hidden=True),
            FieldVisibility(field_id=foreign.id, hidden=True),
        ],
    )

    assert result["updated_fields"] == [amount.id]
    assert result["errors"] == [
        {"index": 1, "field_id": foreign.id, "error": "Not found in this workspace."}
    ]
    assert GridViewFieldOptions.objects.get(grid_view=view, field=amount).hidden is True
    assert _actions(UpdateViewFieldOptionsActionType) == 1


@pytest.mark.django_db
def test_set_field_visibility_refuses_primary_in_grid(grid):
    ctx, view, primary, _, _ = grid

    result = set_field_visibility(
        ctx, view.id, [FieldVisibility(field_id=primary.id, hidden=True)]
    )

    assert result["updated_fields"] == []
    assert result["errors"][0]["index"] == 0
    assert "primary" in result["errors"][0]["error"]
    assert not GridViewFieldOptions.objects.filter(
        grid_view=view, field=primary, hidden=True
    ).exists()


@pytest.mark.django_db
def test_set_field_visibility_explains_a_form(data_fixture, grid):
    ctx, view, _, amount, _ = grid
    form = data_fixture.create_form_view(table=view.table)

    with pytest.raises(ToolInputError):
        set_field_visibility(
            ctx, form.id, [FieldVisibility(field_id=amount.id, hidden=True)]
        )


@pytest.mark.django_db
def test_delete_views_hides_foreign_and_trashes_own(data_fixture, grid):
    ctx, view, _, _, _ = grid
    other_user = data_fixture.create_user()
    foreign = data_fixture.create_grid_view(user=other_user)
    trashed = data_fixture.create_grid_view(table=view.table, trashed=True)

    result = delete_views(ctx, [999999, foreign.id, trashed.id, view.id])

    assert result["deleted_views"] == [view.id]
    assert result["errors"] == [
        {"index": index, "view_id": view_id, "error": "Not found in this workspace."}
        for index, view_id in enumerate([999999, foreign.id, trashed.id])
    ]
    assert not View.objects.filter(id=view.id).exists()
    assert View.objects_and_trash.get(id=view.id).trashed is True
    assert _actions(DeleteViewActionType) == 1


@pytest.mark.django_db
def test_delete_views_rejects_empty_list(grid):
    ctx, *_ = grid

    with pytest.raises(DjangoValidationError):
        delete_views(ctx, [])


@pytest.mark.django_db
def test_delete_view_filters_registers_actions(data_fixture, grid):
    ctx, view, primary, _, _ = grid
    view_filter = data_fixture.create_view_filter(view=view, field=primary)

    result = delete_view_filters(ctx, [view_filter.id])

    assert result == {"deleted_filters": [view_filter.id], "errors": []}
    assert not ViewFilter.objects.filter(id=view_filter.id).exists()
    assert _actions(DeleteViewFilterActionType) == 1


@pytest.mark.django_db
def test_delete_view_filters_hides_foreign_and_trashed_view(data_fixture, grid):
    ctx, view, primary, _, _ = grid
    foreign = data_fixture.create_view_filter()
    trashed_view = data_fixture.create_grid_view(table=view.table, trashed=True)
    of_trashed = data_fixture.create_view_filter(view=trashed_view, field=primary)

    result = delete_view_filters(ctx, [foreign.id, of_trashed.id])

    assert result["deleted_filters"] == []
    assert {error["error"] for error in result["errors"]} == {
        "Not found in this workspace."
    }
    assert ViewFilter.objects.filter(id=foreign.id).exists()


@pytest.mark.django_db
def test_view_config_refuses_foreign_view(data_fixture, grid):
    ctx, view, primary, _, _ = grid
    foreign = data_fixture.create_grid_view(user=data_fixture.create_user())

    with pytest.raises(ViewDoesNotExist):
        set_view_sorts(ctx, foreign.id, [])
    with pytest.raises(ViewDoesNotExist):
        set_field_visibility(
            ctx, foreign.id, [FieldVisibility(field_id=primary.id, hidden=False)]
        )


@pytest.mark.django_db
def test_list_views_returns_what_the_config_tools_need(data_fixture, grid):
    ctx, view, primary, amount, due = grid
    sort = data_fixture.create_view_sort(view=view, field=amount, order="DESC")
    view_filter = data_fixture.create_view_filter(
        view=view, field=primary, type="contains", value="x"
    )
    set_field_visibility(ctx, view.id, [FieldVisibility(field_id=due.id, hidden=True)])

    listed = list_views(ctx, view.table_id)["views"][0]

    assert listed["sorts"] == [{"id": sort.id, "field_id": amount.id, "order": "DESC"}]
    assert listed["filters"] == [
        {
            "id": view_filter.id,
            "field_id": primary.id,
            "type": "contains",
            "value": "x",
        }
    ]
    assert listed["hidden_field_ids"] == [due.id]
    assert listed["row_colours"] == []


@pytest.mark.django_db
def test_list_views_reports_fields_a_gallery_hides_by_default(data_fixture, grid):
    # A gallery's field options hide a field until the user shows it, also when no
    # option has been stored for it yet.
    ctx, view, primary, amount, due = grid
    gallery = data_fixture.create_gallery_view(table=view.table)
    set_field_visibility(
        ctx, gallery.id, [FieldVisibility(field_id=amount.id, hidden=False)]
    )

    listed = {v["id"]: v for v in list_views(ctx, view.table_id)["views"]}

    assert listed[gallery.id]["hidden_field_ids"] == [primary.id, due.id]


@pytest.mark.django_db
def test_list_views_query_count_does_not_grow_with_views(
    data_fixture, grid, django_assert_max_num_queries
):
    ctx, view, primary, *_ = grid
    with CaptureQueriesContext(connection) as few:
        list_views(ctx, view.table_id)

    for _ in range(4):
        other = data_fixture.create_grid_view(table=view.table)
        data_fixture.create_view_sort(view=other, field=primary)

    with django_assert_max_num_queries(len(few)):
        list_views(ctx, view.table_id)


@pytest.mark.django_db(transaction=True)
def test_view_config_tools_over_mcp(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, primary=True)
    view = data_fixture.create_grid_view(table=table)
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["set_view_sorts", "delete_views"]
    )

    sorted_view = _call(
        endpoint,
        "set_view_sorts",
        {"view_id": view.id, "sorts": [{"field_id": field.id, "order": "DESC"}]},
    )
    missing = _call(endpoint, "set_view_sorts", {"view_id": 999999, "sorts": []})
    deleted = _call(endpoint, "delete_views", {"view_ids": [view.id]})

    assert json.loads(sorted_view.content[0].text)["sorts"][0]["order"] == "DESC"
    assert missing.isError
    assert missing.content[0].text == "Not found in this workspace."
    assert json.loads(deleted.content[0].text)["deleted_views"] == [view.id]


@pytest.mark.django_db(transaction=True)
def test_view_config_tools_open_their_own_transaction(data_fixture):
    # The MCP server and Kuma call the tools outside a transaction, unlike a test's
    # database fixture, and the handlers lock rows with select_for_update.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    primary = data_fixture.create_text_field(table=table, name="Name", primary=True)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    view = data_fixture.create_grid_view(table=table)
    view_filter = data_fixture.create_view_filter(view=view, field=primary)
    ctx = ToolContext(user=user, workspace=workspace)

    sorts = set_view_sorts(ctx, view.id, [ViewSortItem(field_id=amount.id)])
    visibility = set_field_visibility(
        ctx, view.id, [FieldVisibility(field_id=amount.id, hidden=True)]
    )
    filters = delete_view_filters(ctx, [view_filter.id])
    views = delete_views(ctx, [view.id])

    assert sorts["sorts"][0]["field_id"] == amount.id
    assert visibility == {"updated_fields": [amount.id], "errors": []}
    assert filters["deleted_filters"] == [view_filter.id]
    assert views["deleted_views"] == [view.id]
