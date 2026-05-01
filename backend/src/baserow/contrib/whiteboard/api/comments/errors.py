from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

ERROR_WHITEBOARD_COMMENT_DOES_NOT_EXIST = (
    "ERROR_WHITEBOARD_COMMENT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested whiteboard comment does not exist.",
)

ERROR_WHITEBOARD_COMMENT_NOT_AUTHOR = (
    "ERROR_WHITEBOARD_COMMENT_NOT_AUTHOR",
    HTTP_401_UNAUTHORIZED,
    "Only the author of a comment may update or delete it.",
)

ERROR_INVALID_WHITEBOARD_COMMENT_MESSAGE = (
    "ERROR_INVALID_WHITEBOARD_COMMENT_MESSAGE",
    HTTP_400_BAD_REQUEST,
    "The supplied message is not a valid ProseMirror document.",
)

ERROR_WHITEBOARD_COMMENT_PARENT_MISMATCH = (
    "ERROR_WHITEBOARD_COMMENT_PARENT_MISMATCH",
    HTTP_400_BAD_REQUEST,
    (
        "The parent comment does not belong to this whiteboard or is itself a "
        "reply (only depth-1 threads are supported)."
    ),
)
