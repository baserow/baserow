from unittest.mock import patch

import pytest

from baserow.contrib.whiteboard.comments.handler import WhiteboardCommentHandler


def _doc():
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}],
    }


@pytest.mark.django_db(transaction=True)
def test_create_broadcasts_via_whiteboard_page(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    with patch(
        "baserow.contrib.whiteboard.ws.pages.WhiteboardPageType.broadcast"
    ) as broadcast:
        WhiteboardCommentHandler().create_comment(
            user=user,
            whiteboard_id=whiteboard.id,
            message=_doc(),
            x=0.0,
            y=0.0,
        )

    assert broadcast.called
    args, kwargs = broadcast.call_args
    assert args[0]["type"] == "whiteboard_comment_created"
    assert args[0]["whiteboard_id"] == whiteboard.id
    assert kwargs["whiteboard_id"] == whiteboard.id


@pytest.mark.django_db(transaction=True)
def test_resolve_broadcasts(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    comment = data_fixture.create_whiteboard_comment(user=user, whiteboard=whiteboard)

    with patch(
        "baserow.contrib.whiteboard.ws.pages.WhiteboardPageType.broadcast"
    ) as broadcast:
        WhiteboardCommentHandler().resolve_comment(user, comment, True)

    payloads = [c.args[0]["type"] for c in broadcast.call_args_list]
    assert "whiteboard_comment_resolved" in payloads


@pytest.mark.django_db(transaction=True)
def test_delete_broadcasts(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    comment = data_fixture.create_whiteboard_comment(user=user, whiteboard=whiteboard)
    # Capture the id before the delete; Django sets `instance.pk = None`
    # after `.delete()` so reading `comment.id` afterwards returns None.
    comment_id = comment.id

    with patch(
        "baserow.contrib.whiteboard.ws.pages.WhiteboardPageType.broadcast"
    ) as broadcast:
        WhiteboardCommentHandler().delete_comment(user, comment)

    args, kwargs = broadcast.call_args
    assert args[0]["type"] == "whiteboard_comment_deleted"
    assert args[0]["comment_id"] == comment_id
