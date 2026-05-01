from unittest.mock import patch

import pytest

from baserow.contrib.whiteboard.comments.handler import WhiteboardCommentHandler


def _doc(text="hello"):
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _mention_doc(target):
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "mention",
                        "attrs": {"id": str(target.id), "label": target.first_name},
                    }
                ],
            }
        ],
    }


@pytest.mark.django_db(transaction=True)
def test_mention_notification_fired_on_create(data_fixture):
    author = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=author)
    target = data_fixture.create_user(workspace=workspace)
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)

    with (
        patch(
            "baserow.contrib.whiteboard.comments.notification_types."
            "WhiteboardCommentMentionNotificationType.notify_mentioned_users"
        ) as mention_mock,
        patch(
            "baserow.contrib.whiteboard.comments.notification_types."
            "WhiteboardCommentReplyNotificationType.notify_thread_participants"
        ) as reply_mock,
    ):
        WhiteboardCommentHandler().create_comment(
            user=author,
            whiteboard_id=whiteboard.id,
            message=_mention_doc(target),
            x=0.0,
            y=0.0,
        )

    mention_mock.assert_called_once()
    args = mention_mock.call_args.args
    mentioned_ids = [u.id for u in args[1]]
    assert mentioned_ids == [target.id]
    # Top-level: no reply notification.
    reply_mock.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_reply_notifies_thread_participants_excluding_just_mentioned(data_fixture):
    """
    Author of the parent thread + previously mentioned users get a reply
    notification. The new mention's recipient gets the mention notification
    only, never both.
    """

    author = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=author)
    parent_mentioned = data_fixture.create_user(workspace=workspace)
    new_mention = data_fixture.create_user(workspace=workspace)
    replier = data_fixture.create_user(workspace=workspace)
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)
    handler = WhiteboardCommentHandler()

    parent = handler.create_comment(
        user=author,
        whiteboard_id=whiteboard.id,
        message=_mention_doc(parent_mentioned),
        x=0.0,
        y=0.0,
    )

    with (
        patch(
            "baserow.contrib.whiteboard.comments.notification_types."
            "WhiteboardCommentMentionNotificationType.notify_mentioned_users"
        ) as mention_mock,
        patch(
            "baserow.contrib.whiteboard.comments.notification_types."
            "WhiteboardCommentReplyNotificationType.notify_thread_participants"
        ) as reply_mock,
    ):
        handler.create_comment(
            user=replier,
            whiteboard_id=whiteboard.id,
            message=_mention_doc(new_mention),
            x=0.0,
            y=0.0,
            parent_comment_id=parent.id,
        )

    # Mention notification went to `new_mention`.
    mention_mock.assert_called_once()
    mention_recipients = [u.id for u in mention_mock.call_args.args[1]]
    assert mention_recipients == [new_mention.id]

    # Reply notification ran with the right exclude set: replier + new_mention.
    reply_mock.assert_called_once()
    _, exclude = reply_mock.call_args.args
    assert exclude == {replier.id, new_mention.id}


@pytest.mark.django_db
def test_reply_notification_excludes_replier_and_mentioned(data_fixture):
    """End-to-end: the participants query inside notify_thread_participants
    must include the parent author and previously mentioned users, but not
    the replier nor the user who just got the mention notification."""

    author = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=author)
    parent_mentioned = data_fixture.create_user(workspace=workspace)
    new_mention = data_fixture.create_user(workspace=workspace)
    replier = data_fixture.create_user(workspace=workspace)
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)
    handler = WhiteboardCommentHandler()

    parent = handler.create_comment(
        user=author,
        whiteboard_id=whiteboard.id,
        message=_mention_doc(parent_mentioned),
        x=0.0,
        y=0.0,
    )
    reply = handler.create_comment(
        user=replier,
        whiteboard_id=whiteboard.id,
        message=_mention_doc(new_mention),
        x=0.0,
        y=0.0,
        parent_comment_id=parent.id,
    )

    from baserow.contrib.whiteboard.comments.notification_types import (
        WhiteboardCommentReplyNotificationType,
    )

    with patch(
        "baserow.core.notifications.handler.NotificationHandler"
        ".create_direct_notification_for_users"
    ) as create_mock:
        WhiteboardCommentReplyNotificationType.notify_thread_participants(
            reply, exclude_user_ids={replier.id, new_mention.id}
        )

    create_mock.assert_called_once()
    recipients = create_mock.call_args.kwargs["recipients"]
    recipient_ids = sorted(u.id for u in recipients)
    # Must include the original poster and the previously-mentioned user;
    # must NOT include the replier or the just-mentioned user.
    assert recipient_ids == sorted([author.id, parent_mentioned.id])
