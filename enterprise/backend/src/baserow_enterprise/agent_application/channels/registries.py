from typing import TYPE_CHECKING, Any

from django.db import transaction
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

    # Whether people talking through this channel may change the agent's
    # memory (`remember`). Internal channels like Slack may; public ones not.
    allows_memory_updates = True
    # Config keys that must never leave the backend, not even into the undo
    # history. `prepare_config` keeps a stored secret when it is omitted, so
    # undoing a config change can simply leave them out.
    secret_config_keys: tuple = ()

    def get_undoable_config(self, channel: "AgentChatChannel") -> dict:
        return {
            key: value
            for key, value in (channel.config or {}).items()
            if key not in self.secret_config_keys
        }

    def get_system_notes(self, channel: "AgentChatChannel") -> list[str]:
        """
        Extra notes for the agent's system prompt when a conversation comes in
        through this channel, e.g. to describe who it is talking to.
        """

        return []

    def is_rate_limited(self, channel: "AgentChatChannel") -> bool:
        """
        Channel-wide limit on inbound messages per minute, shared by every
        conversation of the channel, so one busy integration can't exhaust
        the agent.
        """

        from django.conf import settings

        from loguru import logger

        limit = settings.AGENT_APPLICATION_CHANNEL_RATE_LIMIT_PER_MINUTE
        cache_key = f"agent_application:channel:{channel.id}:rate"
        from ..triggers.registries import _count_in_window

        count = _count_in_window(cache_key)
        if count > limit:
            logger.warning(
                "Chat channel {} exceeded {} messages per minute", channel.id, limit
            )
            return True
        return False

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

    def prepare_imported_config(self, config: dict) -> dict:
        """
        The configuration for a copy of the channel (duplicate, snapshot
        restore). Types with per-channel identifiers renew them here so the
        copy never answers to the original's address.
        """

        return dict(config or {})

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

    def get_manifest(self, channel: "AgentChatChannel", events_url: str) -> dict | None:
        """
        A ready-made app definition for the external service, when it
        supports one, so users can create the app without clicking through
        its settings.
        """

        return None

    def on_run_starting(self, channel: "AgentChatChannel", chat: "AgentChat") -> None:
        """
        Called right before an inbound message starts a run, so the channel
        can show that the agent is working on an answer. May be called again
        for the same chat when the start is retried.
        """

        return None


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
    message was dropped (agent inactive, channel disabled or the chat is
    waiting for an approval).

    :raises AgentChatAlreadyRunning: When the chat is still answering the
        previous message. Nothing is stored, so the caller can retry later.
    """

    from ..exceptions import AgentChatAlreadyRunning, AgentChatAwaitingApproval
    from ..handler import AgentApplicationHandler, AgentChatHandler
    from ..models import AgentChat, AgentChatMessage

    application = channel.application
    if (
        not channel.enabled
        or not application.active
        or application.trashed
        or application.workspace.trashed
    ):
        return None

    agent = AgentApplicationHandler().get_main_agent(application)
    chat_handler = AgentChatHandler()
    channel_type = agent_chat_channel_type_registry.get(channel.type)

    # Two quick replies in a new thread arrive as two tasks; the lock on the
    # channel row makes the second one find the chat the first created.
    with transaction.atomic():
        list(type(channel).objects.select_for_update().filter(id=channel.id))
        chat = AgentChat.objects.filter(
            channel=channel, channel_session_key=session_key
        ).first()
        if chat is None:
            chat = AgentChat.objects.create(
                agent=agent,
                source=AgentChat.Source.CHANNEL,
                channel=channel,
                channel_session_key=session_key,
                title=f"{channel.name or channel.type}: {text}"[
                    : AgentChat.TITLE_MAX_LENGTH
                ],
            )

    # Checked up front so nothing is stored or posted for a message the
    # chat cannot take yet; the run start below guards the remaining race.
    if chat.status == AgentChat.Status.AWAITING_APPROVAL:
        channel_type.send_response(channel, chat, _AWAITING_APPROVAL_TEXT)
        return None
    if chat.status in (AgentChat.Status.IN_PROGRESS, AgentChat.Status.CANCELING):
        raise AgentChatAlreadyRunning(f"The chat {chat.id} is already running.")

    content = f"{sender_name}: {text}" if sender_name else text
    message = chat_handler.create_message(chat, AgentChatMessage.Role.HUMAN, content)
    channel_type.on_run_starting(channel, chat)

    try:
        chat_handler.start_chat_run(chat, message)
    except AgentChatAwaitingApproval:
        message.delete()
        channel_type.send_response(channel, chat, _AWAITING_APPROVAL_TEXT)
        return None
    except AgentChatAlreadyRunning:
        message.delete()
        raise

    return message


_AWAITING_APPROVAL_TEXT = (
    "The agent is waiting for a team member to review a step in Baserow "
    "before it can continue."
)
