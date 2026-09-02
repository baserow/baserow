from datetime import datetime, timezone
from unittest.mock import patch

from django.test import override_settings

import pytest
from freezegun import freeze_time

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
            assert mark_item_viewed(user.id, "database_view", view.id) is True

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
            )
        )

        # Within the update interval nothing is written, so nothing is sent.
        with freeze_time("2026-01-01 12:00:10"):
            assert mark_item_viewed(user.id, "database_view", view.id) is False
        assert mock_broadcast.call_count == 1

        # A missing item never broadcasts.
        assert mark_item_viewed(user.id, "database_view", 0) is False
        assert mock_broadcast.call_count == 1

    assert UserLastViewedItem.objects.get().last_viewed == datetime(
        2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc
    )


@pytest.mark.django_db
def test_mark_item_viewed_keeps_the_lock_after_a_real_run(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    args = (user.id, "dashboard", dashboard.id)

    # Outside of eager mode the lock must survive a run that wrote, so no task is
    # enqueued again for the same key until the update interval has passed.
    with patch.object(mark_item_viewed, "release_lock") as release_lock:
        mark_item_viewed.on_success(True, "task-id", args, {})
    release_lock.assert_not_called()

    # A run that wrote nothing must not silence the next view for an interval.
    with patch.object(mark_item_viewed, "release_lock") as release_lock:
        mark_item_viewed.on_success(False, "task-id", args, {})
    release_lock.assert_called_once_with(task_args=args, task_kwargs={})

    # Eager runs share one lock backend across tests and workers, so they
    # release it like the plain singleton would.
    mark_item_viewed.push_request(is_eager=True)
    try:
        with patch.object(mark_item_viewed, "release_lock") as release_lock:
            mark_item_viewed.on_success(True, "task-id", args, {})
    finally:
        mark_item_viewed.pop_request()
    release_lock.assert_called_once_with(task_args=args, task_kwargs={})
