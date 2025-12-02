from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from baserow_premium.row_comments.handler import (
    RowCommentHandler,
    RowCommentsNotificationModes,
)
from baserow_premium.row_comments.trash_types import RowCommentTrashableItemType
from freezegun import freeze_time

from baserow.core.db import transaction_atomic
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_comment_created(mock_broadcast_to_channel_group, premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("comment")

    mock_broadcast_to_channel_group.delay.reset_mock()

    with freeze_time("2020-01-02 12:00"):
        c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args

    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "row_comment_created"
    assert args[0][1]["row_comment"] == {
        "message": {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "comment"}]}
            ],
        },
        "created_on": "2020-01-02T12:00:00Z",
        "first_name": "test_user",
        "id": c.id,
        "user_id": user.id,
        "row_id": rows[0].id,
        "table_id": table.id,
        "updated_on": "2020-01-02T12:00:00Z",
        "edited": False,
        "trashed": False,
    }


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_row_comment_updated(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("comment")

    with freeze_time("2020-01-02 12:00"):
        c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    updated_message = premium_data_fixture.create_comment_message_from_plain_text(
        "updated comment"
    )
    with patch(
        "baserow.ws.registries.broadcast_to_channel_group"
    ) as mock_broadcast_to_channel_group:
        with freeze_time("2020-01-02 12:01"):
            RowCommentHandler.update_comment(user, c, updated_message)

        mock_broadcast_to_channel_group.delay.assert_called_once()
        args = mock_broadcast_to_channel_group.delay.call_args

        assert args[0][0] == f"table-{table.id}"
        assert args[0][1]["type"] == "row_comment_updated"
        assert args[0][1]["row_comment"] == {
            "message": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "updated comment"}],
                    }
                ],
            },
            "created_on": "2020-01-02T12:00:00Z",
            "first_name": "test_user",
            "id": c.id,
            "user_id": user.id,
            "row_id": rows[0].id,
            "table_id": table.id,
            "updated_on": "2020-01-02T12:01:00Z",
            "edited": True,
            "trashed": False,
        }


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_row_comment_deleted(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("comment")

    with freeze_time("2020-01-02 12:00"):
        c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    with patch(
        "baserow.ws.registries.broadcast_to_channel_group"
    ) as mock_broadcast_to_channel_group:
        with freeze_time("2020-01-02 12:01"):
            RowCommentHandler.delete_comment(user, c)

        mock_broadcast_to_channel_group.delay.assert_called_once()
        args = mock_broadcast_to_channel_group.delay.call_args

        assert args[0][0] == f"table-{table.id}"
        assert args[0][1]["type"] == "row_comment_deleted"
        assert args[0][1]["row_comment"] == {
            "message": None,
            "created_on": "2020-01-02T12:00:00Z",
            "first_name": "test_user",
            "id": c.id,
            "user_id": user.id,
            "row_id": rows[0].id,
            "table_id": table.id,
            "updated_on": "2020-01-02T12:00:00Z",
            "edited": False,
            "trashed": True,
        }


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_row_comment_restored(premium_data_fixture):
    session_id = "test_session_id"
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True, session_id=session_id
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("comment")

    with freeze_time("2020-01-02 12:00"), transaction_atomic():
        row_comment = RowCommentHandler.create_comment(
            user, table.id, rows[0].id, message
        )
        TrashHandler.trash(user, table.database.workspace, table.database, row_comment)

    with patch(
        "baserow.ws.registries.broadcast_to_channel_group"
    ) as mock_broadcast_to_channel_group:
        with freeze_time("2020-01-02 12:01"), transaction_atomic():
            TrashHandler.restore_item(
                user, RowCommentTrashableItemType.type, row_comment.id
            )

        mock_broadcast_to_channel_group.delay.assert_called_once()
        args = mock_broadcast_to_channel_group.delay.call_args

        assert args[0][0] == f"table-{table.id}"
        assert args[0][1]["type"] == "row_comment_restored"
        assert args[0][1]["row_comment"] == {
            "message": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "comment"}],
                    }
                ],
            },
            "created_on": "2020-01-02T12:00:00Z",
            "first_name": "test_user",
            "id": row_comment.id,
            "user_id": user.id,
            "row_id": rows[0].id,
            "table_id": table.id,
            "updated_on": "2020-01-02T12:00:00Z",
            "edited": False,
            "trashed": False,
        }


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@override_settings(DEBUG=True)
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_row_comments_notification_mode_updated(
    mocked_broadcast_to_users,
    premium_data_fixture,
):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )

    mode = RowCommentsNotificationModes.MODE_ALL_COMMENTS.value
    RowCommentHandler.update_row_comments_notification_mode(
        user, table.id, rows[0].id, mode=mode
    )

    mocked_broadcast_to_users.assert_called_once()
    args = mocked_broadcast_to_users.call_args[0][0]
    assert args[0] == [user.id]
    assert args[1] == {
        "type": "row_comments_notification_mode_updated",
        "table_id": table.id,
        "row_id": rows[0].id,
        "mode": mode,
    }
    assert args[2] is None
