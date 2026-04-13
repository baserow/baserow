from abc import ABC

from baserow.core.registries import OperationType


class WhiteboardOperationType(OperationType, ABC):
    context_scope_name = "whiteboard"


class ReadWhiteboardOperationType(WhiteboardOperationType):
    type = "whiteboard.read"


class UpdateWhiteboardContentOperationType(WhiteboardOperationType):
    type = "whiteboard.update_content"
