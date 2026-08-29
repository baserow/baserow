from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.handler import CoreHandler
from baserow.ws.registries import PageType

from ..operations import ListAgentChatsOperationType
from ..realtime import get_agent_application_group_name


class AgentApplicationPageType(PageType):
    type = "agent_application"
    parameters = ["agent_application_id"]

    def can_add(self, user, web_socket_id, agent_application_id, **kwargs):
        if not agent_application_id:
            return False

        try:
            application = CoreHandler().get_application(agent_application_id)
            CoreHandler().check_permissions(
                user,
                ListAgentChatsOperationType.type,
                workspace=application.workspace,
                context=application,
            )
        except (ApplicationDoesNotExist, PermissionException):
            return False

        return True

    def get_group_name(self, agent_application_id, **kwargs):
        return get_agent_application_group_name(agent_application_id)

    def get_permission_channel_group_name(self, agent_application_id, **kwargs):
        return f"permissions-agent_application-{agent_application_id}"
