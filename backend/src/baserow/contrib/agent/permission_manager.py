from typing import Optional

from baserow.contrib.agent.operations import (
    ContinueAgentTriggeredConversationOperationType,
    ReadAgentConfigurationOperationType,
    ReadAgentConversationsOperationType,
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
    actions, and its conversations. A template only gets conversations as the
    examples its content came with: shared, pinned and belonging to nobody.
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


class AgentParticipationPermissionManagerType(PermissionManagerType):
    """
    Nobody continues a conversation a trigger started. The enterprise version
    replaces this one to apply each agent's participation rules. It runs before
    `basic`, which would otherwise allow it to every workspace member.
    """

    type = "agent_participation"
    supported_actor_types = [UserSubjectType.type]

    def check_multiple_permissions(
        self,
        checks: list[PermissionCheck],
        workspace: Optional[Workspace] = None,
        include_trash: bool = False,
    ) -> dict[PermissionCheck, bool | PermissionDenied]:
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
    ) -> Optional[dict[str, dict[str, list[int]]]]:
        """
        Give the client what it needs to answer agent participation checks:
        `{"denied": {<operation>: [<agent id>, ...]}, "allowed": {<operation>:
        [<agent id>, ...]}}`. An operation in `allowed` is decided here, allowed
        only on the listed agents. An operation in `denied` is denied on the listed
        agents and left to the next managers elsewhere.

        :param actor: The actor to describe permissions for.
        :param workspace: The workspace of the agents.
        :return: The object above, or None without a workspace, since agent
            operations are only checked in one.
        """

        if workspace is None:
            return None
        return {
            "denied": {},
            "allowed": {ContinueAgentTriggeredConversationOperationType.type: []},
        }
