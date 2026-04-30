from baserow.contrib.whiteboard.operations import ReadWhiteboardOperationType
from baserow.core.permission_manager import (
    AllowIfTemplatePermissionManagerType as CoreAllowIfTemplatePermissionManagerType,
)
from baserow.core.registries import PermissionManagerType


class AllowIfTemplatePermissionManagerType(CoreAllowIfTemplatePermissionManagerType):
    """
    Allows the read operation on whiteboards that live inside a template
    workspace, so that anonymous (and any signed-in) users can preview
    template whiteboards in the templates modal without being a member
    of the template's workspace.
    """

    WHITEBOARD_OPERATION_ALLOWED_ON_TEMPLATES = [
        ReadWhiteboardOperationType.type,
    ]

    @property
    def OPERATION_ALLOWED_ON_TEMPLATES(self):
        return (
            self.prev_manager_type.OPERATION_ALLOWED_ON_TEMPLATES
            + self.WHITEBOARD_OPERATION_ALLOWED_ON_TEMPLATES
        )

    def __init__(self, prev_manager_type: PermissionManagerType):
        self.prev_manager_type = prev_manager_type
