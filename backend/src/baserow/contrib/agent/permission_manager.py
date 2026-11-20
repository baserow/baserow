from typing import Optional

from baserow.contrib.agent.operations import (
    ContinueAgentTriggeredConversationOperationType,
    ReadAgentConfigurationOperationType,
)
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import Workspace
from baserow.core.permission_manager import (
    AllowIfTemplatePermissionManagerType as CoreAllowIfTemplatePermissionManagerType,
)
from baserow.core.registries import PermissionManagerType
from baserow.core.subjects import UserSubjectType
from baserow.core.types import Actor, PermissionCheck


class AllowIfTemplatePermissionManagerType(CoreAllowIfTemplatePermissionManagerType):
    """
    Lets a template preview show an Agent's configuration, its triggers and its
    actions. Its conversations stay private to the template's workspace.
    """

    AGENT_OPERATION_ALLOWED_ON_TEMPLATES = [
        ReadAgentConfigurationOperationType.type,
    ]

    @property
    def OPERATION_ALLOWED_ON_TEMPLATES(self):
        return (
            self.prev_manager_type.OPERATION_ALLOWED_ON_TEMPLATES
            + self.AGENT_OPERATION_ALLOWED_ON_TEMPLATES
        )

    def __init__(self, prev_manager_type: PermissionManagerType):
        self.prev_manager_type = prev_manager_type


class AgentTriggeredConversationsPermissionManagerType(PermissionManagerType):
    """
    Nobody continues a conversation a trigger started unless an earlier manager,
    such as the enterprise participation rules, allows it. It runs right before
    `basic`, which would otherwise allow it to every workspace member.
    """

    type = "agent_triggered_conversations"
    supported_actor_types = [UserSubjectType.type]

    def check_multiple_permissions(
        self,
        checks: list[PermissionCheck],
        workspace: Optional[Workspace] = None,
        include_trash: bool = False,
    ) -> dict[PermissionCheck, PermissionDenied]:
        """
        Deny every check of the continue operation.

        :param checks: The checks to decide.
        :param workspace: The workspace of the checks.
        :param include_trash: Unused, nothing is looked up.
        :return: A denial for each continue check.
        """

        return {
            check: PermissionDenied()
            for check in checks
            if check.operation_name
            == ContinueAgentTriggeredConversationOperationType.type
        }

    def get_permissions_object(
        self, actor: Actor, workspace: Optional[Workspace] = None
    ) -> Optional[dict[str, list[str]]]:
        """
        Tell the client which operations this manager always denies.

        :param actor: The actor asking.
        :param workspace: The workspace asked about.
        :return: `{"denied_operations": [<operation type>, ...]}`, or None without
            a workspace, since agent operations are only checked in one.
        """

        if workspace is None:
            return None
        return {
            "denied_operations": [ContinueAgentTriggeredConversationOperationType.type]
        }
