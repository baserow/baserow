class WhiteboardCommentDoesNotExist(Exception):
    """Raised when a whiteboard comment can't be found."""


class WhiteboardCommentNotAuthor(Exception):
    """Raised when a non-author tries to update or delete a comment."""


class InvalidWhiteboardCommentMessage(Exception):
    """Raised when the supplied message body is not a valid ProseMirror doc."""


class WhiteboardCommentParentMismatch(Exception):
    """Raised when a reply's parent doesn't belong to the same whiteboard or
    when the parent is itself a reply (we only support depth-1 threading)."""
