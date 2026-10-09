from baserow.core.permission_manager import (
    AllowIfTemplatePermissionManagerType as CoreAllowIfTemplatePermissionManagerType,
)
from baserow.core.registries import PermissionManagerType
from baserow_enterprise.agent_builder.operations import (
    ListAgentsOperationType,
    ReadAgentOperationType,
)


class AllowIfTemplatePermissionManagerType(CoreAllowIfTemplatePermissionManagerType):
    """Allow agents to be read in template previews."""

    @property
    def OPERATION_ALLOWED_ON_TEMPLATES(self):
        return self.prev_manager_type.OPERATION_ALLOWED_ON_TEMPLATES + [
            ListAgentsOperationType.type,
            ReadAgentOperationType.type,
        ]

    def __init__(self, prev_manager_type: PermissionManagerType):
        self.prev_manager_type = prev_manager_type
