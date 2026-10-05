from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.handler import CoreHandler
from baserow.ws.registries import PageType

from ..operations import ListAgentChatsOperationType
from ..realtime import get_agent_application_group_name, get_public_chat_group_name


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


class PublicAgentChatPageType(PageType):
    """
    Anonymous subscription of a visitor to their own public web chat
    conversation. Only the public-safe events are ever sent to this group
    (see `realtime.public_chat_event`).
    """

    type = "public_agent_chat"
    parameters = ["slug", "token", "conversation"]

    def can_add(self, user, web_socket_id, slug, token, conversation, **kwargs):
        from ..channels.web import WebAgentChatChannelType
        from ..handler import AgentChatHandler

        channel = AgentChatHandler().get_public_web_channel(slug)
        if channel is None:
            return False
        channel_type = WebAgentChatChannelType()
        if channel_type.has_password(channel) and not channel_type.is_token_valid(
            channel, token
        ):
            return False
        return AgentChatHandler().get_public_chat(channel, conversation) is not None

    def get_group_name(self, conversation, **kwargs):
        return get_public_chat_group_name(conversation)
