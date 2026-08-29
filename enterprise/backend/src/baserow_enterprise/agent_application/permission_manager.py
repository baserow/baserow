from baserow.core.permission_manager import (
    AllowIfTemplatePermissionManagerType as CoreAllowIfTemplatePermissionManagerType,
)
from baserow.core.registries import PermissionManagerType

from .operations import (
    ListAgentChatsOperationType,
    ListAgentToolsOperationType,
    ReadAgentChatOperationType,
    ReadAgentDefinitionOperationType,
    ReadAgentTriggerOperationType,
    ReadAgentUsageOperationType,
)


class AllowIfTemplatePermissionManagerType(CoreAllowIfTemplatePermissionManagerType):
    """
    Allows the read operations of the agent application on template
    workspaces, so an agent can be previewed as part of a template.
    """

    AGENT_OPERATION_ALLOWED_ON_TEMPLATES = [
        ReadAgentDefinitionOperationType.type,
        ReadAgentTriggerOperationType.type,
        ListAgentToolsOperationType.type,
        ListAgentChatsOperationType.type,
        ReadAgentChatOperationType.type,
        ReadAgentUsageOperationType.type,
    ]

    @property
    def OPERATION_ALLOWED_ON_TEMPLATES(self):
        return (
            self.prev_manager_type.OPERATION_ALLOWED_ON_TEMPLATES
            + self.AGENT_OPERATION_ALLOWED_ON_TEMPLATES
        )

    def __init__(self, prev_manager_type: PermissionManagerType):
        self.prev_manager_type = prev_manager_type
