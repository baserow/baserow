import pytest

from baserow.contrib.whiteboard.comments.exceptions import (
    InvalidWhiteboardCommentMessage,
    WhiteboardCommentDoesNotExist,
    WhiteboardCommentNotAuthor,
    WhiteboardCommentParentMismatch,
)
from baserow.contrib.whiteboard.comments.handler import WhiteboardCommentHandler
from baserow.contrib.whiteboard.comments.models import WhiteboardComment


def _doc(text="hello"):
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _doc_with_mention(target_user, text=" hi"):
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "mention",
                        "attrs": {
                            "id": str(target_user.id),
                            "label": target_user.first_name,
                        },
                    },
                    {"type": "text", "text": text},
                ],
            }
        ],
    }


@pytest.mark.django_db
def test_create_top_level_comment(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    comment = WhiteboardCommentHandler().create_comment(
        user=user,
        whiteboard_id=whiteboard.id,
        message=_doc(),
        x=120.5,
        y=42.0,
    )
    assert comment.id is not None
    assert comment.parent_comment_id is None
    assert comment.x == 120.5
    assert comment.y == 42.0
    assert comment.user_id == user.id
    assert list(comment.mentions.all()) == []


@pytest.mark.django_db
def test_create_reply_inherits_parent_thread(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    handler = WhiteboardCommentHandler()
    parent = handler.create_comment(user, whiteboard.id, _doc(), x=1.0, y=2.0)

    # Replies ignore x/y and inherit position from the thread root.
    reply = handler.create_comment(
        user,
        whiteboard.id,
        _doc("reply"),
        x=999.0,
        y=999.0,
        parent_comment_id=parent.id,
    )
    assert reply.parent_comment_id == parent.id
    assert reply.x is None
    assert reply.y is None


@pytest.mark.django_db
def test_create_extracts_mentions(data_fixture):
    author = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=author)
    target = data_fixture.create_user(workspace=workspace)
    outsider = data_fixture.create_user()  # different workspace
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)

    message = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "mention",
                        "attrs": {"id": str(target.id), "label": target.first_name},
                    },
                    {
                        "type": "mention",
                        "attrs": {"id": str(outsider.id), "label": outsider.first_name},
                    },
                ],
            }
        ],
    }
    comment = WhiteboardCommentHandler().create_comment(
        user=author, whiteboard_id=whiteboard.id, message=message, x=0.0, y=0.0
    )
    mention_ids = set(comment.mentions.values_list("id", flat=True))
    # Only workspace members are recorded as mentions.
    assert mention_ids == {target.id}


@pytest.mark.django_db
def test_reply_to_reply_is_rejected(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    handler = WhiteboardCommentHandler()
    parent = handler.create_comment(user, whiteboard.id, _doc(), x=0.0, y=0.0)
    reply = handler.create_comment(
        user, whiteboard.id, _doc(), x=0.0, y=0.0, parent_comment_id=parent.id
    )
    with pytest.raises(WhiteboardCommentParentMismatch):
        handler.create_comment(
            user, whiteboard.id, _doc(), x=0.0, y=0.0, parent_comment_id=reply.id
        )


@pytest.mark.django_db
def test_create_invalid_prosemirror_rejected(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    with pytest.raises(InvalidWhiteboardCommentMessage):
        WhiteboardCommentHandler().create_comment(
            user, whiteboard.id, message={"not": "valid"}, x=0.0, y=0.0
        )


@pytest.mark.django_db
def test_update_only_by_author(data_fixture):
    author = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=author)
    intruder = data_fixture.create_user(workspace=workspace)
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)
    handler = WhiteboardCommentHandler()
    comment = handler.create_comment(author, whiteboard.id, _doc(), x=0.0, y=0.0)

    with pytest.raises(WhiteboardCommentNotAuthor):
        handler.update_comment(intruder, comment, _doc("changed"))

    updated = handler.update_comment(author, comment, _doc("changed"))
    assert updated.message["content"][0]["content"][0]["text"] == "changed"


@pytest.mark.django_db
def test_update_returns_only_new_mentions(data_fixture):
    author = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=author)
    a = data_fixture.create_user(workspace=workspace)
    b = data_fixture.create_user(workspace=workspace)
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)
    handler = WhiteboardCommentHandler()

    captured = []

    from baserow.contrib.whiteboard.comments.signals import whiteboard_comment_updated

    def _capture(sender, comment, whiteboard, user, new_mentions, **kwargs):
        captured.append([m.id for m in new_mentions])

    whiteboard_comment_updated.connect(_capture)
    try:
        comment = handler.create_comment(
            author, whiteboard.id, _doc_with_mention(a), x=0.0, y=0.0
        )
        # Edit: keep `a` mentioned, add `b`. Only `b` should be in the delta.
        handler.update_comment(
            author,
            comment,
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "mention",
                                "attrs": {"id": str(a.id), "label": a.first_name},
                            },
                            {
                                "type": "mention",
                                "attrs": {"id": str(b.id), "label": b.first_name},
                            },
                        ],
                    }
                ],
            },
        )
    finally:
        whiteboard_comment_updated.disconnect(_capture)

    assert captured == [[b.id]]


@pytest.mark.django_db
def test_delete_only_by_author(data_fixture):
    author = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=author)
    intruder = data_fixture.create_user(workspace=workspace)
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)
    handler = WhiteboardCommentHandler()
    comment = handler.create_comment(author, whiteboard.id, _doc(), x=0.0, y=0.0)

    with pytest.raises(WhiteboardCommentNotAuthor):
        handler.delete_comment(intruder, comment)

    handler.delete_comment(author, comment)
    assert not WhiteboardComment.objects.filter(id=comment.id).exists()


@pytest.mark.django_db
def test_delete_top_level_cascades_to_replies(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    handler = WhiteboardCommentHandler()
    parent = handler.create_comment(user, whiteboard.id, _doc(), x=0.0, y=0.0)
    reply = handler.create_comment(
        user, whiteboard.id, _doc(), x=0.0, y=0.0, parent_comment_id=parent.id
    )

    handler.delete_comment(user, parent)
    assert not WhiteboardComment.objects.filter(id=parent.id).exists()
    assert not WhiteboardComment.objects.filter(id=reply.id).exists()


@pytest.mark.django_db
def test_resolve_only_top_level(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    handler = WhiteboardCommentHandler()
    parent = handler.create_comment(user, whiteboard.id, _doc(), x=0.0, y=0.0)
    reply = handler.create_comment(
        user, whiteboard.id, _doc(), x=0.0, y=0.0, parent_comment_id=parent.id
    )

    with pytest.raises(WhiteboardCommentParentMismatch):
        handler.resolve_comment(user, reply, True)

    resolved = handler.resolve_comment(user, parent, True)
    assert resolved.resolved is True
    assert resolved.resolved_by_id == user.id
    assert resolved.resolved_at is not None

    reopened = handler.resolve_comment(user, parent, False)
    assert reopened.resolved is False
    assert reopened.resolved_by_id is None
    assert reopened.resolved_at is None


@pytest.mark.django_db
def test_get_comment_does_not_exist(data_fixture):
    with pytest.raises(WhiteboardCommentDoesNotExist):
        WhiteboardCommentHandler().get_comment(999999)


@pytest.mark.django_db
def test_list_orders_top_level_then_replies(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    handler = WhiteboardCommentHandler()
    a = handler.create_comment(user, whiteboard.id, _doc("a"), x=0.0, y=0.0)
    b = handler.create_comment(user, whiteboard.id, _doc("b"), x=0.0, y=0.0)
    a_reply = handler.create_comment(
        user, whiteboard.id, _doc("a-reply"), x=0.0, y=0.0, parent_comment_id=a.id
    )

    listed = handler.list_comments(user, whiteboard.id)
    assert [c.id for c in listed] == [a.id, a_reply.id, b.id]
