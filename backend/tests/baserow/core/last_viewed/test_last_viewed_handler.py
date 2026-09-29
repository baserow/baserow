from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest
from freezegun import freeze_time

from baserow.contrib.database.views.models import View
from baserow.core.last_viewed.handler import LastViewedHandler
from baserow.core.last_viewed.models import UserLastViewedItem
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.utils import IMPERSONATED_BY_USER_ATTR


@pytest.mark.django_db
def test_schedule_mark_viewed_defers_task_until_commit(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()

    with (
        patch(
            "baserow.core.last_viewed.tasks.mark_item_viewed.apply_async"
        ) as mock_apply_async,
        override_settings(BASEROW_LAST_VIEWED_DEBOUNCE_SECONDS=7),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            with freeze_time("2026-01-01 12:00:00"):
                LastViewedHandler.schedule_mark_viewed(user, "database_view", 1)
            assert mock_apply_async.call_count == 0

    mock_apply_async.assert_called_once_with(
        args=(user.id, "database_view", 1, "2026-01-01T12:00:00+00:00"), countdown=7
    )


@pytest.mark.django_db
def test_schedule_mark_viewed_ignores_impersonated_users(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    setattr(user, IMPERSONATED_BY_USER_ATTR, data_fixture.create_user().id)

    with patch(
        "baserow.core.last_viewed.tasks.mark_item_viewed.apply_async"
    ) as mock_apply_async:
        with django_capture_on_commit_callbacks(execute=True):
            LastViewedHandler.schedule_mark_viewed(user, "database_view", 1)

    assert mock_apply_async.call_count == 0


@pytest.mark.django_db
def test_schedule_mark_viewed_ignores_template_visitors(
    django_capture_on_commit_callbacks,
):
    with patch(
        "baserow.core.last_viewed.tasks.mark_item_viewed.apply_async"
    ) as mock_apply_async:
        with django_capture_on_commit_callbacks(execute=True):
            LastViewedHandler.schedule_mark_viewed(AnonymousUser(), "database_view", 1)

    assert mock_apply_async.call_count == 0


@pytest.mark.django_db
@override_settings(BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS=60)
def test_mark_viewed_creates_then_respects_update_interval(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    with freeze_time("2026-01-01 12:00:00"):
        row = LastViewedHandler.mark_viewed(
            user.id, "database_view", view.id, datetime.now(tz=timezone.utc)
        )

    assert row is not None
    assert row.application_id == database.id
    assert row.workspace_id == workspace.id
    stored = UserLastViewedItem.objects.get()
    assert stored.user_id == user.id
    assert stored.item_type == "database_view"
    assert stored.item_id == view.id
    assert stored.last_viewed == datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Fresher than the interval: nothing changes and nothing is reported.
    with freeze_time("2026-01-01 12:00:30"):
        assert (
            LastViewedHandler.mark_viewed(
                user.id, "database_view", view.id, datetime.now(tz=timezone.utc)
            )
            is None
        )
    assert UserLastViewedItem.objects.get().last_viewed == datetime(
        2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc
    )

    with freeze_time("2026-01-01 12:01:30"):
        row = LastViewedHandler.mark_viewed(
            user.id, "database_view", view.id, datetime.now(tz=timezone.utc)
        )

    assert row is not None
    assert row.last_viewed == datetime(2026, 1, 1, 12, 1, 30, tzinfo=timezone.utc)
    assert UserLastViewedItem.objects.count() == 1
    assert UserLastViewedItem.objects.get().last_viewed == row.last_viewed


@pytest.mark.django_db
def test_mark_viewed_is_noop_for_missing_or_trashed_item(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    assert (
        LastViewedHandler.mark_viewed(
            user.id, "database_view", 0, datetime.now(tz=timezone.utc)
        )
        is None
    )

    TrashHandler.trash(user, workspace, database, view)
    assert (
        LastViewedHandler.mark_viewed(
            user.id, "database_view", view.id, datetime.now(tz=timezone.utc)
        )
        is None
    )
    assert UserLastViewedItem.objects.count() == 0


@pytest.mark.django_db
def test_mark_viewed_ignores_users_outside_the_workspace(data_fixture):
    # Template previews hit the same "loaded" endpoints as regular usage.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    assert (
        LastViewedHandler.mark_viewed(
            user.id, "database_view", view.id, datetime.now(tz=timezone.utc)
        )
        is None
    )
    assert UserLastViewedItem.objects.count() == 0


@pytest.mark.django_db
def test_mark_viewed_ignores_items_of_trashed_parents(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    TrashHandler.trash(user, workspace, database, table)
    assert (
        LastViewedHandler.mark_viewed(
            user.id, "database_view", view.id, datetime.now(tz=timezone.utc)
        )
        is None
    )
    assert UserLastViewedItem.objects.count() == 0


@pytest.mark.django_db
def test_mark_viewed_resolves_parents_for_every_item_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    dashboard = data_fixture.create_dashboard_application(workspace=workspace)

    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    expected = {
        ("database_view", view.id): database.id,
        ("builder_page", page.id): builder.id,
        ("dashboard", dashboard.id): dashboard.id,
        ("automation_workflow", workflow.id): automation.id,
    }
    for (item_type, item_id), application_id in expected.items():
        row = LastViewedHandler.mark_viewed(
            user.id, item_type, item_id, datetime.now(tz=timezone.utc)
        )
        assert row.application_id == application_id
        assert row.workspace_id == workspace.id

    assert UserLastViewedItem.objects.count() == 4


@pytest.mark.django_db
def test_get_last_viewed_per_application(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[user, other_user])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view_1 = data_fixture.create_grid_view(table=table)
    view_2 = data_fixture.create_grid_view(table=table)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    never_viewed = data_fixture.create_builder_application(workspace=workspace)

    with freeze_time("2026-01-01 12:00:00"):
        LastViewedHandler.mark_viewed(
            user.id, "database_view", view_1.id, datetime.now(tz=timezone.utc)
        )
    with freeze_time("2026-01-02 12:00:00"):
        LastViewedHandler.mark_viewed(
            user.id, "database_view", view_2.id, datetime.now(tz=timezone.utc)
        )
        LastViewedHandler.mark_viewed(
            other_user.id, "dashboard", dashboard.id, datetime.now(tz=timezone.utc)
        )
    with freeze_time("2026-01-03 12:00:00"):
        LastViewedHandler.mark_viewed(
            user.id, "dashboard", dashboard.id, datetime.now(tz=timezone.utc)
        )

    ids = [database.id, dashboard.id, never_viewed.id]
    with django_assert_num_queries(1):
        result = LastViewedHandler.get_last_viewed_per_application(user, ids)

    assert result == {
        database.id: datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        dashboard.id: datetime(2026, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
    }
    assert LastViewedHandler.get_last_viewed_per_application(other_user, ids) == {
        dashboard.id: datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
    }
    assert LastViewedHandler.get_last_viewed_per_application(user, []) == {}


@pytest.mark.django_db
def test_mark_viewed_costs_two_queries(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)

    with django_assert_num_queries(2):
        assert LastViewedHandler.mark_viewed(
            user.id, "dashboard", dashboard.id, datetime.now(tz=timezone.utc)
        )
    # A fresh row is skipped by the upsert itself, without any extra query.
    with django_assert_num_queries(2):
        assert (
            LastViewedHandler.mark_viewed(
                user.id, "dashboard", dashboard.id, datetime.now(tz=timezone.utc)
            )
            is None
        )


@pytest.mark.django_db
def test_get_last_viewed_per_user_and_application(
    data_fixture, django_assert_num_queries
):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[user_1, user_2, user_3])
    dashboard_1 = data_fixture.create_dashboard_application(workspace=workspace)
    dashboard_2 = data_fixture.create_dashboard_application(workspace=workspace)

    with freeze_time("2026-01-01 12:00:00"):
        LastViewedHandler.mark_viewed(
            user_1.id, "dashboard", dashboard_1.id, datetime.now(tz=timezone.utc)
        )
        LastViewedHandler.mark_viewed(
            user_2.id, "dashboard", dashboard_1.id, datetime.now(tz=timezone.utc)
        )
        LastViewedHandler.mark_viewed(
            user_2.id, "dashboard", dashboard_2.id, datetime.now(tz=timezone.utc)
        )

    expected_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    with django_assert_num_queries(1):
        result = LastViewedHandler.get_last_viewed_per_user_and_application(
            [dashboard_1.id, dashboard_2.id]
        )
    assert result == {
        user_1.id: {dashboard_1.id: expected_time},
        user_2.id: {dashboard_1.id: expected_time, dashboard_2.id: expected_time},
    }
    assert LastViewedHandler.get_last_viewed_per_user_and_application(
        [dashboard_1.id], user_ids=[user_2.id, user_3.id]
    ) == {user_2.id: {dashboard_1.id: expected_time}}
    assert LastViewedHandler.get_last_viewed_per_user_and_application([]) == {}


@pytest.mark.django_db
def test_delete_stale_items(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    kept_view = data_fixture.create_grid_view(table=table)
    trashed_view = data_fixture.create_grid_view(table=table)
    deleted_view = data_fixture.create_grid_view(table=table)

    for view in (kept_view, trashed_view, deleted_view):
        LastViewedHandler.mark_viewed(
            user.id, "database_view", view.id, datetime.now(tz=timezone.utc)
        )
    UserLastViewedItem.objects.create(
        user=user,
        item_type="unknown_type",
        item_id=1,
        application=database,
        workspace=workspace,
        last_viewed=datetime.now(tz=timezone.utc),
    )

    TrashHandler.trash(user, workspace, database, trashed_view)
    # Bypass the trash so no receiver runs, like an out-of-band deletion would.
    View.objects_and_trash.filter(id=deleted_view.id).delete()

    assert LastViewedHandler.delete_stale_items() == 2
    assert sorted(
        UserLastViewedItem.objects.values_list("item_type", "item_id")
    ) == sorted([("database_view", kept_view.id), ("database_view", trashed_view.id)])


@pytest.mark.django_db
def test_delete_stale_items_keeps_recent_rows_untouched(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    LastViewedHandler.mark_viewed(
        user.id, "dashboard", dashboard.id, datetime.now(tz=timezone.utc)
    )

    assert LastViewedHandler.delete_stale_items() == 0
    assert UserLastViewedItem.objects.count() == 1
    assert UserLastViewedItem.objects.get().last_viewed > datetime.now(
        tz=timezone.utc
    ) - timedelta(minutes=1)


@pytest.mark.django_db
def test_delete_stale_items_deletes_in_batches(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    views = [data_fixture.create_grid_view(table=table) for _ in range(5)]
    for view in views:
        LastViewedHandler.mark_viewed(
            user.id, "database_view", view.id, datetime.now(tz=timezone.utc)
        )
    kept_view = data_fixture.create_grid_view(table=table)
    LastViewedHandler.mark_viewed(
        user.id, "database_view", kept_view.id, datetime.now(tz=timezone.utc)
    )

    View.objects_and_trash.filter(id__in=[view.id for view in views]).delete()

    with patch("baserow.core.last_viewed.handler.DELETE_BATCH_SIZE", 2):
        assert LastViewedHandler.delete_stale_items() == 5

    assert list(UserLastViewedItem.objects.values_list("item_id", flat=True)) == [
        kept_view.id
    ]


@pytest.mark.django_db
@override_settings(BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS=60)
def test_mark_viewed_stores_the_visit_moment_regardless_of_processing_order(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard_a = data_fixture.create_dashboard_application(workspace=workspace)
    dashboard_b = data_fixture.create_dashboard_application(workspace=workspace)
    visit_a = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    visit_b = datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc)

    # B's task runs before the delayed task of A: A must not look newer than B.
    with freeze_time("2026-01-01 12:10:00"):
        LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard_b.id, visit_b)
        LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard_a.id, visit_a)

    assert LastViewedHandler.get_last_viewed_per_application(
        user, [dashboard_a.id, dashboard_b.id]
    ) == {dashboard_a.id: visit_a, dashboard_b.id: visit_b}

    # A late visit of an item that was opened again since must not go back.
    assert (
        LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard_b.id, visit_a)
        is None
    )
    assert UserLastViewedItem.objects.get(item_id=dashboard_b.id).last_viewed == visit_b


def _record(user, item_type, item, application, workspace, when):
    return UserLastViewedItem.objects.create(
        user=user,
        item_type=item_type,
        item_id=item.id,
        application=application,
        workspace=workspace,
        last_viewed=datetime.fromisoformat(when).replace(tzinfo=timezone.utc),
    )


def _ids(items):
    return [(item.item_type.type, item.instance.id) for item in items]


@pytest.mark.django_db
def test_list_items_orders_newest_first_and_paginates(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view_1 = data_fixture.create_grid_view(table=table)
    view_2 = data_fixture.create_grid_view(table=table)
    view_3 = data_fixture.create_grid_view(table=table)
    _record(user, "database_view", view_1, database, workspace, "2026-01-01 10:00")
    _record(user, "database_view", view_2, database, workspace, "2026-01-03 10:00")
    _record(user, "database_view", view_3, database, workspace, "2026-01-02 10:00")

    items, cursor = LastViewedHandler.list_items(user, limit=2)
    assert _ids(items) == [("database_view", view_2.id), ("database_view", view_3.id)]
    assert cursor is not None

    items, cursor = LastViewedHandler.list_items(user, limit=2, cursor=cursor)
    assert _ids(items) == [("database_view", view_1.id)]
    assert cursor is None

    items, cursor = LastViewedHandler.list_items(user, limit=3)
    assert len(items) == 3
    assert cursor is None


@pytest.mark.django_db
def test_list_items_resolves_every_item_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_form_view(table=table)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    _record(user, "database_view", view, database, workspace, "2026-01-04 10:00")
    _record(user, "builder_page", page, builder, workspace, "2026-01-03 10:00")
    _record(user, "dashboard", dashboard, dashboard, workspace, "2026-01-02 10:00")
    _record(
        user, "automation_workflow", workflow, automation, workspace, "2026-01-01 10:00"
    )

    items, cursor = LastViewedHandler.list_items(user, limit=20)

    assert cursor is None
    assert [
        (item.item_type.type, item.instance.id, item.sub_type, item.row.application_id)
        for item in items
    ] == [
        ("database_view", view.id, "form", database.id),
        ("builder_page", page.id, None, builder.id),
        ("dashboard", dashboard.id, None, dashboard.id),
        ("automation_workflow", workflow.id, None, automation.id),
    ]
    # Fetched with the row, so the serializer does not query per item.
    assert items[0].row.workspace.name == workspace.name
    assert items[0].instance.table.name == table.name


@pytest.mark.django_db
def test_list_items_filters_by_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace()
    dashboard_1 = data_fixture.create_dashboard_application(workspace=workspace_1)
    dashboard_2 = data_fixture.create_dashboard_application(workspace=workspace_2)
    other_dashboard = data_fixture.create_dashboard_application(
        workspace=other_workspace
    )
    _record(
        user, "dashboard", dashboard_1, dashboard_1, workspace_1, "2026-01-01 10:00"
    )
    _record(
        user, "dashboard", dashboard_2, dashboard_2, workspace_2, "2026-01-02 10:00"
    )
    # Left behind by a membership that no longer exists.
    _record(
        user,
        "dashboard",
        other_dashboard,
        other_dashboard,
        other_workspace,
        "2026-01-03 10:00",
    )

    items, _ = LastViewedHandler.list_items(user, limit=20)
    assert _ids(items) == [("dashboard", dashboard_2.id), ("dashboard", dashboard_1.id)]

    items, _ = LastViewedHandler.list_items(
        user, workspace_ids=[workspace_1.id], limit=20
    )
    assert _ids(items) == [("dashboard", dashboard_1.id)]

    items, cursor = LastViewedHandler.list_items(
        user, workspace_ids=[other_workspace.id], limit=20
    )
    assert items == []
    assert cursor is None


@pytest.mark.django_db
def test_list_items_returns_nothing_for_a_user_without_workspaces(data_fixture):
    user = data_fixture.create_user()

    assert LastViewedHandler.list_items(user, limit=20) == ([], None)


@pytest.mark.django_db
def test_list_items_filters_by_type_and_sub_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    grid = data_fixture.create_grid_view(table=table)
    form = data_fixture.create_form_view(table=table)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    _record(user, "database_view", grid, database, workspace, "2026-01-03 10:00")
    _record(user, "database_view", form, database, workspace, "2026-01-02 10:00")
    _record(user, "builder_page", page, builder, workspace, "2026-01-01 10:00")

    items, _ = LastViewedHandler.list_items(
        user, type_filters={"database_view": {"form"}}, limit=20
    )
    assert _ids(items) == [("database_view", form.id)]

    items, _ = LastViewedHandler.list_items(
        user, type_filters={"database_view": None}, limit=20
    )
    assert _ids(items) == [("database_view", grid.id), ("database_view", form.id)]

    items, _ = LastViewedHandler.list_items(
        user,
        type_filters={"database_view": {"grid"}, "builder_page": None},
        limit=20,
    )
    assert _ids(items) == [("database_view", grid.id), ("builder_page", page.id)]


@pytest.mark.django_db
def test_list_items_excludes_trashed_items_without_leaving_gaps(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    trashed_table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    trashed_view = data_fixture.create_grid_view(table=table)
    view_of_trashed_table = data_fixture.create_grid_view(table=trashed_table)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    trashed_builder = data_fixture.create_builder_application(workspace=workspace)
    page_of_trashed_builder = data_fixture.create_builder_page(builder=trashed_builder)
    automation = data_fixture.create_automation_application(workspace=workspace)
    trashed_workflow = data_fixture.create_automation_workflow(automation=automation)

    _record(
        user, "database_view", trashed_view, database, workspace, "2026-01-09 10:00"
    )
    _record(
        user,
        "database_view",
        view_of_trashed_table,
        database,
        workspace,
        "2026-01-08 10:00",
    )
    _record(
        user,
        "builder_page",
        page_of_trashed_builder,
        trashed_builder,
        workspace,
        "2026-01-07 10:00",
    )
    _record(
        user,
        "automation_workflow",
        trashed_workflow,
        automation,
        workspace,
        "2026-01-06 10:00",
    )
    _record(user, "database_view", view, database, workspace, "2026-01-02 10:00")
    _record(user, "builder_page", page, builder, workspace, "2026-01-01 10:00")

    TrashHandler.trash(user, workspace, database, trashed_view)
    TrashHandler.trash(user, workspace, database, trashed_table)
    TrashHandler.trash(user, workspace, trashed_builder, trashed_builder)
    TrashHandler.trash(user, workspace, automation, trashed_workflow)

    # The trashed rows are newer, but they must not consume a slot of the page.
    items, cursor = LastViewedHandler.list_items(user, limit=1)
    assert _ids(items) == [("database_view", view.id)]
    assert cursor is not None

    items, cursor = LastViewedHandler.list_items(user, limit=1, cursor=cursor)
    assert _ids(items) == [("builder_page", page.id)]
    assert cursor is None


@pytest.mark.django_db
def test_list_items_query_count_is_independent_of_rows_and_workspaces(data_fixture):
    user = data_fixture.create_user()

    def add_workspace_with_items(count):
        workspace = data_fixture.create_workspace(user=user)
        database = data_fixture.create_database_application(workspace=workspace)
        table = data_fixture.create_database_table(database=database)
        builder = data_fixture.create_builder_application(workspace=workspace)
        automation = data_fixture.create_automation_application(workspace=workspace)
        dashboard = data_fixture.create_dashboard_application(workspace=workspace)
        for i in range(count):
            view = data_fixture.create_grid_view(table=table)
            page = data_fixture.create_builder_page(builder=builder)
            workflow = data_fixture.create_automation_workflow(automation=automation)
            when = f"2026-01-{i + 1:02d} 10:00"
            _record(user, "database_view", view, database, workspace, when)
            _record(user, "builder_page", page, builder, workspace, when)
            _record(user, "automation_workflow", workflow, automation, workspace, when)
        _record(user, "dashboard", dashboard, dashboard, workspace, "2026-02-01 10:00")

    add_workspace_with_items(1)
    with CaptureQueriesContext(connection) as small:
        items, _ = LastViewedHandler.list_items(user, limit=20)
    assert len(items) == 4

    add_workspace_with_items(5)
    add_workspace_with_items(5)
    with CaptureQueriesContext(connection) as large:
        items, _ = LastViewedHandler.list_items(user, limit=20)
    assert len(items) == 20

    assert len(large.captured_queries) == len(small.captured_queries)


@pytest.mark.django_db
def test_list_items_costs_a_fixed_number_of_queries(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    _record(user, "database_view", view, database, workspace, "2026-01-04 10:00")
    _record(user, "builder_page", page, builder, workspace, "2026-01-03 10:00")
    _record(user, "dashboard", dashboard, dashboard, workspace, "2026-01-02 10:00")
    _record(
        user, "automation_workflow", workflow, automation, workspace, "2026-01-01 10:00"
    )

    # The first call fills the caches the permission managers keep per request.
    LastViewedHandler.list_items(user, limit=20)

    with CaptureQueriesContext(connection) as ctx:
        items, _ = LastViewedHandler.list_items(user, limit=20)

    assert len(items) == 4
    # The workspaces of the user, the batch of rows, the visibility of each type
    # in it, the rows of the page and the items of each type in it.
    assert len(ctx.captured_queries) == 13, "\n\n".join(
        q["sql"][:200] for q in ctx.captured_queries
    )


@pytest.mark.django_db
def test_list_items_scans_past_items_that_are_gone_in_growing_batches(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    # Rows of items that no longer exist, all viewed more recently than the only
    # one that is left, so the scan has to look past every one of them.
    UserLastViewedItem.objects.bulk_create(
        [
            UserLastViewedItem(
                user=user,
                item_type="database_view",
                item_id=1_000_000 + i,
                application=database,
                workspace=workspace,
                last_viewed=datetime(2026, 2, 1, tzinfo=timezone.utc)
                + timedelta(minutes=i),
            )
            for i in range(700)
        ]
    )
    _record(user, "database_view", view, database, workspace, "2026-01-01 10:00")

    with CaptureQueriesContext(connection) as ctx:
        items, cursor = LastViewedHandler.list_items(user, limit=20)

    assert _ids(items) == [("database_view", view.id)]
    assert cursor is None
    # Each batch is twice the size of the one before, so looking past 700 rows
    # takes a handful of queries instead of one per row.
    assert len(ctx.captured_queries) == 13


@pytest.mark.django_db
def test_list_items_reads_a_bounded_number_of_rows_per_request(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    # Rows of items that no longer exist, all viewed more recently than the only
    # one that is left.
    UserLastViewedItem.objects.bulk_create(
        [
            UserLastViewedItem(
                user=user,
                item_type="database_view",
                item_id=1_000_000 + i,
                application=database,
                workspace=workspace,
                last_viewed=datetime(2026, 2, 1, tzinfo=timezone.utc)
                + timedelta(minutes=i),
            )
            for i in range(500)
        ]
    )
    _record(user, "database_view", view, database, workspace, "2026-01-01 10:00")

    with patch("baserow.core.last_viewed.handler.MAX_SCANNED_ROWS", 300):
        # Nothing visible within the rows read, but the cursor continues after them
        # instead of claiming the history is done.
        items, cursor = LastViewedHandler.list_items(user, limit=20)
        assert items == []
        assert cursor is not None

        items, cursor = LastViewedHandler.list_items(user, limit=20, cursor=cursor)
        assert _ids(items) == [("database_view", view.id)]
        assert cursor is None


@pytest.mark.django_db
def test_list_items_cursor_neither_repeats_nor_skips_when_the_history_changes(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    views = [data_fixture.create_grid_view(table=table) for _ in range(6)]
    rows = [
        _record(user, "database_view", view, database, workspace, f"2026-01-0{9 - i}")
        for i, view in enumerate(views)
    ]
    ids = [("database_view", view.id) for view in views]

    items, cursor = LastViewedHandler.list_items(user, limit=2)
    assert _ids(items) == ids[0:2]

    # Opening the oldest item moves it above the loaded page, which would make an
    # offset repeat the last item of the first page.
    UserLastViewedItem.objects.filter(id=rows[5].id).update(
        last_viewed=datetime(2026, 2, 1, tzinfo=timezone.utc)
    )
    items, cursor = LastViewedHandler.list_items(user, limit=2, cursor=cursor)
    assert _ids(items) == ids[2:4]

    # Trashing an item of a loaded page would make an offset skip the next one.
    TrashHandler.trash(user, workspace, database, views[2])
    items, cursor = LastViewedHandler.list_items(user, limit=2, cursor=cursor)
    assert _ids(items) == ids[4:5]
    assert cursor is None
