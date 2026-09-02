from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.database.views.models import View
from baserow.core.last_viewed.handler import LastViewedHandler
from baserow.core.last_viewed.models import UserLastViewedItem
from baserow.core.trash.handler import TrashHandler


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
            LastViewedHandler.schedule_mark_viewed(user, "database_view", 1)
            assert mock_apply_async.call_count == 0

    mock_apply_async.assert_called_once_with(
        args=(user.id, "database_view", 1), countdown=7
    )


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
        row = LastViewedHandler.mark_viewed(user.id, "database_view", view.id)

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
        assert LastViewedHandler.mark_viewed(user.id, "database_view", view.id) is None
    assert UserLastViewedItem.objects.get().last_viewed == datetime(
        2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc
    )

    with freeze_time("2026-01-01 12:01:30"):
        row = LastViewedHandler.mark_viewed(user.id, "database_view", view.id)

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

    assert LastViewedHandler.mark_viewed(user.id, "database_view", 0) is None

    TrashHandler.trash(user, workspace, database, view)
    assert LastViewedHandler.mark_viewed(user.id, "database_view", view.id) is None
    assert UserLastViewedItem.objects.count() == 0


@pytest.mark.django_db
def test_mark_viewed_ignores_users_outside_the_workspace(data_fixture):
    # Template previews hit the same "loaded" endpoints as regular usage.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    assert LastViewedHandler.mark_viewed(user.id, "database_view", view.id) is None
    assert UserLastViewedItem.objects.count() == 0


@pytest.mark.django_db
def test_mark_viewed_ignores_items_of_trashed_parents(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    TrashHandler.trash(user, workspace, database, table)
    assert LastViewedHandler.mark_viewed(user.id, "database_view", view.id) is None
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
        row = LastViewedHandler.mark_viewed(user.id, item_type, item_id)
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
        LastViewedHandler.mark_viewed(user.id, "database_view", view_1.id)
    with freeze_time("2026-01-02 12:00:00"):
        LastViewedHandler.mark_viewed(user.id, "database_view", view_2.id)
        LastViewedHandler.mark_viewed(other_user.id, "dashboard", dashboard.id)
    with freeze_time("2026-01-03 12:00:00"):
        LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard.id)

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
        assert LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard.id)
    # A fresh row is skipped by the upsert itself, without any extra query.
    with django_assert_num_queries(2):
        assert LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard.id) is None


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
        LastViewedHandler.mark_viewed(user_1.id, "dashboard", dashboard_1.id)
        LastViewedHandler.mark_viewed(user_2.id, "dashboard", dashboard_1.id)
        LastViewedHandler.mark_viewed(user_2.id, "dashboard", dashboard_2.id)

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
        LastViewedHandler.mark_viewed(user.id, "database_view", view.id)
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
    LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard.id)

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
        LastViewedHandler.mark_viewed(user.id, "database_view", view.id)
    kept_view = data_fixture.create_grid_view(table=table)
    LastViewedHandler.mark_viewed(user.id, "database_view", kept_view.id)

    View.objects_and_trash.filter(id__in=[view.id for view in views]).delete()

    with patch("baserow.core.last_viewed.handler.DELETE_BATCH_SIZE", 2):
        assert LastViewedHandler.delete_stale_items() == 5

    assert list(UserLastViewedItem.objects.values_list("item_id", flat=True)) == [
        kept_view.id
    ]
