from abc import ABC

from baserow.core.registries import OperationType


class WhiteboardCommentOperationType(OperationType, ABC):
    context_scope_name = "whiteboard"


class ListWhiteboardCommentsOperationType(WhiteboardCommentOperationType):
    type = "whiteboard.list_comments"


class CreateWhiteboardCommentOperationType(WhiteboardCommentOperationType):
    type = "whiteboard.create_comment"


class UpdateWhiteboardCommentOperationType(WhiteboardCommentOperationType):
    type = "whiteboard.update_comment"


class DeleteWhiteboardCommentOperationType(WhiteboardCommentOperationType):
    type = "whiteboard.delete_comment"


class ResolveWhiteboardCommentOperationType(WhiteboardCommentOperationType):
    type = "whiteboard.resolve_comment"
