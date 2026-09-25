from datetime import datetime, timezone
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.celery_singleton_backend import RedisBackendForSingleton
from baserow.core.last_viewed.models import UserLastViewedItem
from baserow.core.last_viewed.tasks import mark_item_viewed


def test_mark_item_viewed_is_a_singleton_per_user_and_item():
    assert mark_item_viewed.unique_on == ["user_id", "item_type", "item_id"]
    assert mark_item_viewed.raise_on_duplicate is False
    # Without an expiry a crashed worker would lock the key forever.
    assert mark_item_viewed.lock_expiry > 0


@pytest.mark.django_db
@override_settings(BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS=60)
def test_mark_item_viewed_broadcasts_to_user_only_when_changed(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    with patch("baserow.ws.tasks.broadcast_to_users.apply") as mock_broadcast:
        with freeze_time("2026-01-01 12:00:00"):
            assert (
                mark_item_viewed(
                    user.id,
                    "database_view",
                    view.id,
                    datetime.now(tz=timezone.utc).isoformat(),
                )
                is True
            )

        mock_broadcast.assert_called_once_with(
            (
                [user.id],
                {
                    "type": "last_viewed_updated",
                    "item_type": "database_view",
                    "item_id": view.id,
                    "application_id": database.id,
                    "workspace_id": workspace.id,
                    "last_viewed": "2026-01-01T12:00:00Z",
                },
            ),
            # A reconnecting client reloads the value with the applications, so
            # the event must not count toward the replay limit.
            {"record": False},
        )

        # Within the update interval nothing is written, so nothing is sent.
        with freeze_time("2026-01-01 12:00:10"):
            assert (
                mark_item_viewed(
                    user.id,
                    "database_view",
                    view.id,
                    datetime.now(tz=timezone.utc).isoformat(),
                )
                is False
            )
        assert mock_broadcast.call_count == 1

        # A missing item never broadcasts.
        assert (
            mark_item_viewed(
                user.id, "database_view", 0, datetime.now(tz=timezone.utc).isoformat()
            )
            is False
        )
        assert mock_broadcast.call_count == 1

    assert UserLastViewedItem.objects.get().last_viewed == datetime(
        2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc
    )


@pytest.mark.django_db
def test_mark_item_viewed_lock_handling_is_fenced_by_task_id(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    args = (user.id, "dashboard", dashboard.id, "2026-01-01T12:00:00+00:00")
    lock = mark_item_viewed.generate_lock(mark_item_viewed.name, args, {})
    interval = settings.BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS

    # Outside of eager mode the lock must survive a run that wrote, re-armed for
    # the update interval counted from the write, so no task is enqueued again
    # for the same key until the database floor has passed.
    with (
        patch.object(
            RedisBackendForSingleton, "extend_lock_if", return_value=True
        ) as extend_lock_if,
        patch.object(
            RedisBackendForSingleton, "release_lock_if", return_value=True
        ) as release_lock_if,
    ):
        mark_item_viewed.on_success(True, "task-id", args, {})
    extend_lock_if.assert_called_once_with(lock, "task-id", interval)
    release_lock_if.assert_not_called()

    # A run that wrote nothing must not silence the next view for an interval,
    # but may only drop a lock it still owns: a task that outlived its lease
    # must leave the lock of the task that replaced it alone.
    with patch.object(
        RedisBackendForSingleton, "release_lock_if", return_value=True
    ) as release_lock_if:
        mark_item_viewed.on_success(False, "task-id", args, {})
    release_lock_if.assert_called_once_with(lock, "task-id")

    with patch.object(
        RedisBackendForSingleton, "release_lock_if", return_value=True
    ) as release_lock_if:
        mark_item_viewed.on_failure(Exception(), "task-id", args, {}, None)
    release_lock_if.assert_called_once_with(lock, "task-id")

    # Eager runs share one lock backend across tests and workers, so they
    # release it like the plain singleton would.
    mark_item_viewed.push_request(is_eager=True)
    try:
        with patch.object(
            RedisBackendForSingleton, "release_lock_if", return_value=True
        ) as release_lock_if:
            mark_item_viewed.on_success(True, "task-id", args, {})
    finally:
        mark_item_viewed.pop_request()
    release_lock_if.assert_called_once_with(lock, "task-id")


def test_fenced_lock_helpers_only_touch_the_holders_lock():
    backend = RedisBackendForSingleton()
    backend.redis.delete("lock")
    backend.lock("lock", "old-task", expiry=100)

    assert backend.release_lock_if("lock", "new-task") is False
    # The shared connection does not decode responses.
    assert backend.get("lock") == b"old-task"
    assert backend.extend_lock_if("lock", "new-task", 5) is False
    assert backend.extend_lock_if("lock", "old-task", 5) is True
    assert backend.release_lock_if("lock", "old-task") is True
    assert backend.get("lock") is None


@pytest.mark.django_db
@override_settings(BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS=30)
def test_on_success_re_arms_the_held_lock_and_leaves_a_taken_over_one_alone(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    args = (user.id, "dashboard", dashboard.id, "2026-01-01T12:00:00+00:00")
    lock = mark_item_viewed.generate_lock(mark_item_viewed.name, args, {})
    redis = mark_item_viewed.singleton_backend.redis
    redis.delete(lock)

    # Taken at enqueue time with the bounded expiry, then re-armed for the
    # update interval once the task has written.
    assert mark_item_viewed.aquire_lock(lock, "task-id") is True
    redis.expire(lock, 300)
    mark_item_viewed.push_request(is_eager=False)
    try:
        mark_item_viewed.on_success(True, "task-id", args, {})
        assert 0 < redis.ttl(lock) <= 30

        # A newer task took the lock over after this one's lease expired:
        # neither a write nor a no-op of the old task may touch it.
        redis.set(lock, "new-task", ex=300)
        mark_item_viewed.on_success(True, "task-id", args, {})
        assert redis.get(lock) == b"new-task"
        assert redis.ttl(lock) > 30
        mark_item_viewed.on_success(False, "task-id", args, {})
        assert redis.get(lock) == b"new-task"
        mark_item_viewed.on_failure(Exception(), "task-id", args, {}, None)
        assert redis.get(lock) == b"new-task"

        # The holder itself can drop it after a no-op.
        mark_item_viewed.on_success(False, "new-task", args, {})
        assert redis.get(lock) is None
    finally:
        mark_item_viewed.pop_request()
