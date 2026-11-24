from baserow.contrib.agent.operations import (
    ReadAgentConfigurationOperationType,
    ReadAgentConversationsOperationType,
)
from baserow.core.models import Template
from baserow.core.permission_manager import (
    AllowIfTemplatePermissionManagerType as CoreAllowIfTemplatePermissionManagerType,
)
from baserow.core.registries import PermissionManagerType


class AllowIfTemplatePermissionManagerType(CoreAllowIfTemplatePermissionManagerType):
    """
    Lets a template preview show an Agent's configuration, its triggers and its
    actions, and the conversations of an official template. Those are the
    examples its file came with, which are shared and belong to nobody. The
    conversations of a user template stay private to its workspace, however they
    got there.
    """

    AGENT_OPERATION_ALLOWED_ON_TEMPLATES = [
        ReadAgentConfigurationOperationType.type,
        ReadAgentConversationsOperationType.type,
    ]

    @property
    def OPERATION_ALLOWED_ON_TEMPLATES(self):
        return (
            self.prev_manager_type.OPERATION_ALLOWED_ON_TEMPLATES
            + self.AGENT_OPERATION_ALLOWED_ON_TEMPLATES
        )

    @property
    def LIVE_OPERATIONS_ON_TEMPLATES(self):
        return self.prev_manager_type.LIVE_OPERATIONS_ON_TEMPLATES

    def __init__(self, prev_manager_type: PermissionManagerType):
        self.prev_manager_type = prev_manager_type

    def check_multiple_permissions(self, checks, workspace=None, include_trash=False):
        result = super().check_multiple_permissions(
            checks, workspace=workspace, include_trash=include_trash
        )
        conversation_checks = [
            check
            for check in result
            if check.operation_name == ReadAgentConversationsOperationType.type
        ]
        if conversation_checks and Template.Type.USER in workspace.get_template_types():
            # Left to the next managers, which allow the members of the workspace.
            for check in conversation_checks:
                del result[check]
        return result
