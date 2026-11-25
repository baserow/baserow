from uuid import UUID

from django.db import DEFAULT_DB_ALIAS, transaction

from baserow.config.db_routers import set_db_alias
from baserow.contrib.agent.constants import (
    AGENT_RUN_TYPE,
    AGENT_VISITOR_HISTORY_SIZE,
    AgentReadinessState,
)
from baserow.contrib.agent.exceptions import (
    AgentConversationWaitingForApproval,
    AgentNotReady,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentChannel,
    AgentConversation,
    AgentMessage,
)
from baserow.contrib.agent.signals import agent_conversation_activity
from baserow.contrib.agent.types import AgentMessageCreated, AgentVisitorConversation
from baserow.contrib.agent.validators import validate_message_content
from baserow.core.chat_runs.exceptions import ChatRunDoesNotExist
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus

from .exceptions import AgentChannelDoesNotExist
from .handler import AgentChannelHandler

VISITOR_ROLES = (AgentMessage.Role.VISITOR, AgentMessage.Role.ASSISTANT)


class AgentVisitorService:
    """
    What an anonymous visitor of a channel may do. The caller has already checked
    that the visitor may use the channel and which conversation is theirs.
    """

    def __init__(self) -> None:
        self.handler = AgentHandler()

    def require_available(self, channel: AgentChannel) -> None:
        """
        Refuse a channel that can't be used, with the same answer for every reason,
        so a link tells nothing about it.

        :param channel: The channel, with its agent and the agent's workspace.
        :raises AgentChannelDoesNotExist: When the channel is off or trashed, its
            agent is trashed, its workspace is gone or trashed, or its type is
            locked in the workspace.
        """

        agent = channel.agent
        workspace = agent.workspace
        if (
            not channel.enabled
            or channel.trashed
            or agent.trashed
            or workspace is None
            or workspace.trashed
            or AgentChannelHandler().is_type_locked(channel, workspace)
        ):
            raise AgentChannelDoesNotExist

    @transaction.atomic
    def start_conversation(
        self, channel: AgentChannel, content: str
    ) -> AgentMessageCreated:
        """
        Start a conversation from a visitor's first message.

        :param channel: The channel the visitor writes through, with its agent.
        :param content: The visitor's first message.
        :raises ValidationError: When the content is blank or too long.
        :raises AgentNotReady: When the agent isn't ready for a new conversation.
        :raises ChatRunLimitReached: When a reply limit is reached; nothing is saved.
        :return: The new conversation, the visitor's message, its reply and the run
            writing it.
        """

        validate_message_content(content)
        self._require_ready(channel.agent)
        result = self.handler.start_channel_conversation(channel, content)
        agent_conversation_activity.send(
            self, conversation=result.conversation, user=None, run_id=result.run_id
        )
        return result

    @transaction.atomic
    def send_message(
        self, channel: AgentChannel, conversation_uuid: UUID, content: str
    ) -> AgentMessageCreated:
        """
        Add a visitor's next message to their conversation.

        :param channel: The channel the visitor writes through.
        :param conversation_uuid: The uuid of the visitor's conversation.
        :param content: The content of the message.
        :raises AgentConversationDoesNotExist: When the channel has no such
            conversation.
        :raises ValidationError: When the content is blank or too long.
        :raises AgentConversationWaitingForApproval: When the latest reply waits
            for a member to decide its held calls.
        :raises ApplicationDoesNotExist: When the agent was trashed meanwhile.
        :raises AgentNotReady: When the agent isn't ready for a new message.
        :raises ChatRunAlreadyActive: When the agent is still replying.
        :raises ChatRunLimitReached: When a reply limit is reached.
        :return: The conversation, the new message, its reply and the run writing it.
        """

        conversation = self.handler.get_channel_conversation(
            channel, conversation_uuid, for_update=True
        )
        validate_message_content(content)
        if self.handler.get_waiting_reply(conversation) is not None:
            raise AgentConversationWaitingForApproval
        # Configuration may have changed while waiting for the conversation lock.
        self._require_ready(self.handler.get_agent(conversation.agent_id))
        result = self.handler.create_visitor_message(conversation, content)
        agent_conversation_activity.send(
            self, conversation=result.conversation, user=None, run_id=result.run_id
        )
        return result

    def get_conversation(
        self, channel: AgentChannel, conversation_uuid: UUID
    ) -> AgentVisitorConversation:
        """
        :param channel: The channel the visitor writes through.
        :param conversation_uuid: The uuid of the visitor's conversation.
        :raises AgentConversationDoesNotExist: When the channel has no such
            conversation.
        :return: The latest messages of the visitor and the agent, and the run
            writing a reply now.
        """

        conversation = self._get_conversation(channel, conversation_uuid)
        newest = list(
            conversation.messages.filter(role__in=VISITOR_ROLES).defer("steps")[
                :AGENT_VISITOR_HISTORY_SIZE
            ]
        )
        runs = self.handler.get_active_reply_runs(conversation)
        newest = self.handler.refresh_unfinished_replies(newest, runs)
        return AgentVisitorConversation(
            conversation, list(reversed(newest)), next(iter(runs.values()), None)
        )

    def get_run(
        self, channel: AgentChannel, conversation_uuid: UUID, run_id: UUID
    ) -> ChatRun:
        """
        :param channel: The channel the visitor writes through.
        :param conversation_uuid: The uuid of the visitor's conversation.
        :param run_id: The id of the run to follow.
        :raises AgentConversationDoesNotExist: When the channel has no such
            conversation.
        :raises ChatRunDoesNotExist: When the run doesn't write a reply of that
            conversation.
        :return: The run.
        """

        conversation = self._get_conversation(channel, conversation_uuid)
        run = ChatRunHandler().get_run(run_id)
        if run.run_type != AGENT_RUN_TYPE or run.chat_id != conversation.id:
            raise ChatRunDoesNotExist
        return run

    def stop_reply(
        self, channel: AgentChannel, conversation_uuid: UUID
    ) -> ChatRunStatus | None:
        """
        :param channel: The channel the visitor writes through.
        :param conversation_uuid: The uuid of the visitor's conversation.
        :raises AgentConversationDoesNotExist: When the channel has no such
            conversation.
        :return: The status of the run writing the reply after the stop request, or
            None when the agent isn't replying.
        """

        conversation = self._get_conversation(channel, conversation_uuid)
        run = ChatRunHandler().get_active_run(AGENT_RUN_TYPE, conversation.id)
        if run is None:
            return None
        return ChatRunHandler().request_cancel(run.id)

    def _get_conversation(
        self, channel: AgentChannel, conversation_uuid: UUID
    ) -> AgentConversation:
        """
        :param channel: The channel the visitor writes through.
        :param conversation_uuid: The uuid of the visitor's conversation.
        :raises AgentConversationDoesNotExist: When the channel has no such
            conversation.
        :return: The conversation, read from the primary database with the rest
            of the request.
        """

        # A replica can lag behind what the visitor's previous request wrote.
        set_db_alias(DEFAULT_DB_ALIAS)
        return self.handler.get_channel_conversation(channel, conversation_uuid)

    def _require_ready(self, agent: AgentApplication) -> None:
        """
        :param agent: The agent, with its workspace.
        :raises AgentNotReady: When its configuration isn't ready, without saying
            why.
        """

        readiness, _ = self.handler.get_configuration_readiness(agent)
        if readiness != AgentReadinessState.READY:
            raise AgentNotReady
