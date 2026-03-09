from django.contrib.auth import get_user_model

from baserow.contrib.automation.nodes.operations import ListAutomationNodeOperationType
from baserow.contrib.automation.operations import ListAutomationWorkflowsOperationType
from baserow.core.permission_manager import (
    AllowIfTemplatePermissionManagerType as CoreAllowIfTemplatePermissionManagerType,
)
from baserow.core.registries import PermissionManagerType

User = get_user_model()


class AllowIfTemplatePermissionManagerType(CoreAllowIfTemplatePermissionManagerType):
    """
    Allows read operation on templates.
    """

    AUTOMATION_OPERATION_ALLOWED_ON_TEMPLATES = [
        ListAutomationWorkflowsOperationType.type,
        ListAutomationNodeOperationType.type,
    ]

    @property
    def OPERATION_ALLOWED_ON_TEMPLATES(self):
        return (
            self.prev_manager_type.OPERATION_ALLOWED_ON_TEMPLATES
            + self.AUTOMATION_OPERATION_ALLOWED_ON_TEMPLATES
        )

    def __init__(self, prev_manager_type: PermissionManagerType):
        self.prev_manager_type = prev_manager_type
