from typing import TYPE_CHECKING, Any

from django.http import HttpRequest, HttpResponse

from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from ..models import AgentChat, AgentChatChannel


class AgentChatChannelType(Instance):
    """
    An external chat surface (Slack, Telegram, ...) through which users can
    talk to an agent. A channel type receives inbound webhook requests from
    the external service, turns them into agent chat messages, and posts the
    agent's answers back.

    Adding a new integration means implementing this interface and
    registering it; the inbound webhook URL, chat session bookkeeping and run
    lifecycle are shared.
    """

    def prepare_config(self, config: dict, existing_config: dict | None = None) -> dict:
        """
        Validates and normalizes the user-provided channel configuration.
        Because secrets are masked in the API, an omitted secret keeps the
        value from the existing configuration on update.

        :param config: The raw configuration dict.
        :param existing_config: The stored configuration when updating.
        :raises rest_framework.exceptions.ValidationError: When invalid.
        """

        return config

    def get_public_config(self, channel: "AgentChatChannel") -> dict:
        """
        The configuration as exposed through the API. Secrets are masked so
        they never leave the backend once stored.
        """

        return channel.config

    def handle_inbound(
        self, channel: "AgentChatChannel", request: HttpRequest
    ) -> HttpResponse:
        """
        Handles an inbound webhook request from the external service: verify
        its authenticity, answer protocol handshakes, and enqueue message
        processing. Must return quickly; the actual agent run happens in a
        background task.
        """

        raise NotImplementedError

    def send_response(
        self, channel: "AgentChatChannel", chat: "AgentChat", text: str
    ) -> None:
        """
        Posts the agent's answer back into the external conversation the
        chat belongs to.
        """

        raise NotImplementedError


class AgentChatChannelTypeRegistry(Registry[AgentChatChannelType]):
    name = "agent_chat_channel_type"


agent_chat_channel_type_registry = AgentChatChannelTypeRegistry()


def start_channel_chat(
    channel: "AgentChatChannel",
    session_key: str,
    text: str,
    sender_name: str = "",
) -> Any:
    """
    Shared inbound-message handling for every channel type: finds or creates
    the chat belonging to the external conversation, stores the message and
    starts an agent run. Returns the created message or None when the
    message was dropped (agent inactive or already running).
    """

    from ..exceptions import AgentChatAlreadyRunning, AgentChatAwaitingApproval
    from ..handler import AgentApplicationHandler, AgentChatHandler
    from ..models import AgentChat, AgentChatMessage

    application = channel.application
    if not channel.enabled or not application.active:
        return None

    agent = AgentApplicationHandler().get_main_agent(application)
    chat_handler = AgentChatHandler()

    chat = AgentChat.objects.filter(
        channel=channel, channel_session_key=session_key
    ).first()
    if chat is None:
        chat = AgentChat.objects.create(
            agent=agent,
            source=AgentChat.Source.CHANNEL,
            channel=channel,
            channel_session_key=session_key,
            title=f"{channel.name or channel.type}: {sender_name or session_key}"[
                : AgentChat.TITLE_MAX_LENGTH
            ],
        )

    content = f"{sender_name}: {text}" if sender_name else text
    message = chat_handler.create_message(chat, AgentChatMessage.Role.HUMAN, content)

    try:
        chat_handler.start_chat_run(chat, message)
    except (AgentChatAlreadyRunning, AgentChatAwaitingApproval):
        channel_type = agent_chat_channel_type_registry.get(channel.type)
        channel_type.send_response(
            channel,
            chat,
            "The agent is still busy with the previous message; please try "
            "again once it has answered.",
        )
        return None

    return message
