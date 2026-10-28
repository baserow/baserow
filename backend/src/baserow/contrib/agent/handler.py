from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, IntegrityError, transaction
from django.db.models import Prefetch, QuerySet
from django.utils.dateparse import parse_datetime

from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.ai_provider.resolution import ScopedAIProviderState
from baserow.core.chat_runs.constants import ChatRunErrorCode
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ACTIVE_CHAT_RUN_STATUSES, ChatRunStatus
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.utils import extract_allowed, remove_null_characters

from .constants import AGENT_RUN_TYPE, HISTORY_MESSAGE_LIMIT
from .exceptions import AgentConversationDoesNotExist, AgentMessageConflict
from .models import AgentApplication, AgentConversation, AgentMessage
from .types import (
    AgentConfiguration,
    AgentConfigurationUpdated,
    AgentMessageCreated,
    AgentReplyRequest,
)


class AgentHandler:
    configuration_fields = ["instructions", "provider_type", "model_identifier"]

    def get_agent(self, agent_id: int, for_update: bool = False) -> AgentApplication:
        """
        Fetch an Agent that belongs to a workspace.

        :param agent_id: The id of the Agent.
        :param for_update: Whether to lock the Agent until the transaction ends.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist, is trashed or
            has no workspace.
        :return: The Agent.
        """

        # Snapshots keep workspace-less copies of applications. Exclude them because
        # editor permissions need a workspace scope.
        queryset = AgentApplication.objects.filter(workspace__isnull=False)
        if for_update:
            # Lock the parent first to match normal application updates.
            CoreHandler().get_application(
                agent_id,
                base_queryset=queryset.select_for_update(of=("application_ptr",)),
            )
            queryset = queryset.select_for_update(of=("self",))
        return CoreHandler().get_application(agent_id, base_queryset=queryset)

    def get_configuration(
        self,
        agent: AgentApplication,
        provider_state: ScopedAIProviderState | None = None,
    ) -> AgentConfiguration:
        """
        Return the configuration, its readiness and each blocking field error.

        :param agent: The Agent to read.
        :param provider_state: The AI provider state of the Agent's workspace, when
            the caller already loaded it.
        :return: The configuration values, the readiness and the error of
            each field that keeps the Agent from being ready.
        """

        errors = {}
        for field in self.configuration_fields:
            if not (getattr(agent, field) or "").strip():
                errors[field] = "required"

        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            agent.workspace,
            feature_type=AI_PROVIDER_FEATURE_AI_AGENT,
            state=provider_state,
        )
        if agent.provider_type:
            if agent.provider_type not in models:
                errors["provider_type"] = "unavailable"
            if agent.model_identifier and agent.model_identifier not in models.get(
                agent.provider_type, []
            ):
                errors["model_identifier"] = "unavailable"

        if "required" in errors.values():
            readiness = "incomplete"
        elif errors:
            readiness = "unavailable"
        else:
            readiness = "ready"
        return {
            **{field: getattr(agent, field) for field in self.configuration_fields},
            "readiness": readiness,
            "errors": errors,
        }

    def update_configuration(
        self, agent: AgentApplication, **values: str | None
    ) -> AgentConfigurationUpdated:
        """
        Save part of the configuration, accepting blank values as a draft.

        :param agent: The Agent to update.
        :param values: The configuration values to set, by field name. The caller
            must validate their types and lengths beforehand. Unknown field names
            are ignored.
        :return: The Agent, the names of the fields that changed and the
            resulting configuration.
        """

        values = extract_allowed(values, self.configuration_fields)
        changed_fields = []
        for field, value in values.items():
            if field in ("provider_type", "model_identifier"):
                value = (value or "").strip() or None
            if getattr(agent, field) != value:
                setattr(agent, field, value)
                changed_fields.append(field)
        if changed_fields:
            agent.save(update_fields=[*changed_fields, "updated_on"])
        return AgentConfigurationUpdated(
            agent, changed_fields, self.get_configuration(agent)
        )

    def list_conversations(
        self, agent: AgentApplication, owner: AbstractUser
    ) -> QuerySet[AgentConversation]:
        """
        Return the owner's conversations with the agent.

        :param agent: The agent the conversations belong to.
        :param owner: The user whose conversations are returned.
        :return: The owner's conversations, most recently updated first.
        """

        return AgentConversation.objects.filter(agent=agent, owner_user=owner)

    def get_conversation(
        self,
        agent: AgentApplication,
        owner: AbstractUser,
        uuid: UUID,
        for_update: bool = False,
    ) -> AgentConversation:
        """
        Return one of the owner's conversations with the agent.

        :param agent: The agent the conversation belongs to.
        :param owner: The user who owns the conversation.
        :param uuid: The uuid of the conversation.
        :param for_update: Whether to lock the conversation until the transaction ends.
        :raises AgentConversationDoesNotExist: When the conversation doesn't exist,
            also when it belongs to another owner or agent.
        :return: The conversation, with the agent and the owner it was found for.
        """

        queryset = AgentConversation.objects.all()
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        try:
            conversation = queryset.get(uuid=uuid, agent=agent, owner_user=owner)
        except AgentConversation.DoesNotExist as exc:
            raise AgentConversationDoesNotExist from exc
        conversation.agent, conversation.owner_user = agent, owner
        return conversation

    def get_creation_retry(
        self,
        agent: AgentApplication,
        owner: AbstractUser,
        uuid: UUID,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated | None:
        """
        Return the first message already accepted for a conversation uuid.

        :param agent: The agent the conversation is created in.
        :param owner: The user creating the conversation.
        :param uuid: The uuid of the conversation.
        :param message_uuid: The uuid of the first message.
        :param content: The content of the first message.
        :raises AgentConversationDoesNotExist: When the uuid belongs to another
            owner's or agent's conversation.
        :raises AgentMessageConflict: When the conversation was created with another
            first message.
        :return: The conversation, its first message, its reply and the run writing
            it, or None when nothing was accepted with this uuid before.
        """

        conversation = AgentConversation.objects.filter(uuid=uuid).first()
        if conversation is None:
            return None
        return self._get_first_message_retry(
            conversation, agent, owner, message_uuid, content
        )

    def _get_first_message_retry(
        self,
        conversation: AgentConversation,
        agent: AgentApplication,
        owner: AbstractUser,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """Validate an existing identifier, also one a racing request just created."""

        if conversation.agent_id != agent.id or conversation.owner_user_id != owner.id:
            raise AgentConversationDoesNotExist
        message = conversation.messages.order_by("id").first()
        if (
            message is None
            or message.uuid != message_uuid
            or message.content != content
        ):
            raise AgentMessageConflict
        return self._accepted(conversation, message)

    def _accepted(
        self, conversation: AgentConversation, message: AgentMessage
    ) -> AgentMessageCreated:
        """
        Return an already accepted message with the reply created right after it,
        and the run still writing that reply. The run is read first: a run's end
        saves its reply in the same transaction, so the reply read next is never
        still running without its run.

        :param conversation: The conversation of the message.
        :param message: The accepted message.
        :return: The conversation, the message, its reply and the run writing it.
        """

        runs = self.get_active_reply_runs(conversation)
        reply = conversation.messages.filter(id__gt=message.id).order_by("id").first()
        if reply is not None and reply.role != AgentMessage.Role.ASSISTANT:
            reply = None
        run_id = runs.get(reply.id) if reply else None
        return AgentMessageCreated(conversation, message, reply, run_id, False)

    def create_conversation(
        self,
        agent: AgentApplication,
        user: AbstractUser,
        uuid: UUID,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """
        Create a private conversation, titled after its first message.

        :param agent: The agent to create the conversation in.
        :param user: The user who owns the conversation.
        :param uuid: The uuid of the conversation.
        :param message_uuid: The uuid of the first message.
        :param content: The content of the first message.
        :raises AgentConversationDoesNotExist: When a concurrent request created a
            conversation with this uuid for another owner or agent.
        :raises AgentMessageConflict: When a concurrent request created it with
            another first message.
        :return: The conversation, its first message and its reply, and whether they
            are new.
        """

        try:
            with transaction.atomic():
                conversation = AgentConversation.objects.create(
                    uuid=uuid,
                    agent=agent,
                    owner_user=user,
                    title=" ".join(content.split())[:250],
                )
        except IntegrityError:
            # A concurrent request created this uuid after the retry check.
            return self._get_first_message_retry(
                AgentConversation.objects.get(uuid=uuid),
                agent,
                user,
                message_uuid,
                content,
            )
        return self._add_message(conversation, message_uuid, content)

    def get_message_retry(
        self, conversation: AgentConversation, uuid: UUID, content: str
    ) -> AgentMessageCreated | None:
        """
        Return the message already accepted for a message uuid.

        :param conversation: The conversation the message is sent to.
        :param uuid: The uuid of the message.
        :param content: The content of the message.
        :raises AgentMessageConflict: When the uuid was accepted with other content.
        :return: The conversation, the accepted message, its reply and the run
            writing it, or None when nothing was accepted with this uuid before.
        """

        message = conversation.messages.filter(uuid=uuid).first()
        if message is None:
            return None
        if message.content != content:
            raise AgentMessageConflict
        return self._accepted(conversation, message)

    def create_message(
        self, conversation: AgentConversation, uuid: UUID, content: str
    ) -> AgentMessageCreated:
        """
        Add a user message with an empty reply, and start the run writing it.

        Call it in the transaction that checked the message, so a refused reply
        saves nothing.

        :param conversation: The conversation to add the message to.
        :param uuid: The uuid of the message.
        :param content: The content of the message.
        :return: The conversation, the new message, its reply and the run writing
            it.
        """

        conversation.save(update_fields=["updated_on"])
        return self._add_message(conversation, uuid, content)

    def _add_message(
        self, conversation: AgentConversation, uuid: UUID, content: str
    ) -> AgentMessageCreated:
        """Add the message and its empty reply, and start the run writing it."""

        message = AgentMessage.objects.create(
            conversation=conversation, uuid=uuid, content=content
        )
        reply = AgentMessage.objects.create(
            conversation=conversation,
            uuid=uuid4(),
            role=AgentMessage.Role.ASSISTANT,
            content="",
            status=ChatRunStatus.RUNNING,
        )
        run = ChatRunHandler().start_run(
            AGENT_RUN_TYPE,
            conversation.id,
            conversation.agent.workspace,
            conversation.owner_user,
            context={"reply_id": reply.id},
            created_event_data={},
        )
        return AgentMessageCreated(conversation, message, reply, run.id, True)

    def get_active_reply_runs(self, conversation: AgentConversation) -> dict[int, UUID]:
        """
        Return the run still writing a reply of the conversation, if any.

        :param conversation: The conversation to look at.
        :return: The id of the active run by the id of the reply it writes, empty
            when the agent isn't replying.
        """

        run = ChatRunHandler().get_active_run(AGENT_RUN_TYPE, conversation.id)
        return {run.context["reply_id"]: run.id} if run else {}

    def get_conversation_runs(self, conversation_ids: list[int]) -> dict[int, UUID]:
        """
        Return the runs writing a reply in the given conversations.

        :param conversation_ids: The ids of the conversations to look at.
        :return: The id of the active run by the id of its conversation, only for
            the conversations where the agent is replying.
        """

        return dict(
            ChatRunHandler()
            .runs.filter(
                run_type=AGENT_RUN_TYPE,
                chat_id__in=conversation_ids,
                status__in=ACTIVE_CHAT_RUN_STATUSES,
            )
            .values_list("chat_id", "id")
        )

    def get_accessible_conversations(
        self, owner: AbstractUser
    ) -> QuerySet[AgentConversation]:
        """
        Return the owner's conversations in untrashed Agents and workspaces, while
        the owner is still a member of the workspace.

        :param owner: The user who owns the conversations.
        :return: The conversations.
        """

        return AgentConversation.objects.filter(
            owner_user_id=owner.id,
            agent__trashed=False,
            agent__workspace__trashed=False,
            agent__workspace__workspaceuser__user_id=owner.id,
        )

    def get_reply(self, reply_id: int) -> AgentMessage:
        """
        Fetch a reply with its conversation, the conversation's owner and its agent.

        :param reply_id: The id of the reply.
        :raises AgentConversationDoesNotExist: When the reply no longer exists.
        :return: The reply.
        """

        reply = (
            AgentMessage.objects.select_related(
                "conversation__agent__workspace", "conversation__owner_user"
            )
            .filter(id=reply_id)
            .first()
        )
        if reply is None:
            raise AgentConversationDoesNotExist
        return reply

    def get_reply_request(self, reply: AgentMessage) -> AgentReplyRequest:
        """
        Collect what the model needs to write a reply.

        :param reply: The reply, with its conversation and agent.
        :return: The instructions, the model, the prompt and the earlier messages.
        """

        conversation = reply.conversation
        agent = conversation.agent
        # The prompt is the message right before its reply.
        prompt, *history = conversation.messages.filter(id__lt=reply.id).order_by(
            "-id"
        )[: HISTORY_MESSAGE_LIMIT + 1]
        return AgentReplyRequest(
            reply_id=reply.id,
            workspace=agent.workspace,
            instructions=agent.instructions,
            provider_type=agent.provider_type,
            model_identifier=agent.model_identifier,
            prompt=prompt.content,
            history=list(reversed(history)),
        )

    def finish_reply(
        self,
        reply_id: int,
        status: str,
        error_code: str,
        text: str | None,
    ) -> AgentMessage | None:
        """
        Save how a reply ended, with its text, unless the reply no longer exists.
        NUL characters are dropped because PostgreSQL can't store them, and blank
        text is saved empty.

        :param reply_id: The id of the reply.
        :param status: The final status: completed, cancelled or failed.
        :param error_code: Why the reply failed, or an empty string.
        :param text: What the reply produced, or None when it never started.
        :return: The saved reply with its conversation, or None when it no longer
            exists.
        """

        # The caller's lock on the run already serializes everything ending a reply.
        reply = (
            AgentMessage.objects.select_related("conversation")
            .filter(id=reply_id)
            .first()
        )
        if reply is None:
            return None
        reply.status = status
        reply.error_code = error_code
        content = remove_null_characters(text or "")
        reply.content = content if content.strip() else ""
        reply.save(update_fields=["status", "error_code", "content", "updated_on"])
        reply.conversation.save(update_fields=["updated_on"])
        return reply

    def refresh_unfinished_replies(
        self, messages: list[AgentMessage], active_runs: dict[int, UUID]
    ) -> list[AgentMessage]:
        """
        Read again, from the primary database, the replies that still look
        unfinished although no run writes them any more: the messages were read
        before the runs, maybe from a lagging replica.

        :param messages: Messages, possibly read from a replica.
        :param active_runs: The active run by reply id, read after the messages.
        :return: The same messages, with the replies whose run ended read again.
        """

        ended = [
            message.id
            for message in messages
            if message.status in ACTIVE_CHAT_RUN_STATUSES
            and message.id not in active_runs
        ]
        if not ended:
            return messages
        fresh = AgentMessage.objects.using(DEFAULT_DB_ALIAS).in_bulk(ended)
        return [fresh.get(message.id, message) for message in messages]

    def mark_reply_interrupted(self, reply_id: int) -> AgentConversation | None:
        """
        Show that a started reply did not complete, unless it already ended.

        :param reply_id: The id of the reply.
        :return: The reply's conversation when this ended the reply, else None.
        """

        ended = AgentMessage.objects.filter(
            id=reply_id,
            status__in=ACTIVE_CHAT_RUN_STATUSES,
        ).update(
            status=ChatRunStatus.FAILED,
            error_code=ChatRunErrorCode.INTERRUPTED,
        )
        if not ended:
            return None
        return AgentConversation.objects.filter(messages__id=reply_id).first()

    def export_conversations(self, agent: AgentApplication) -> list[dict]:
        """
        Serialize the agent's conversations and messages for an internal copy.

        :param agent: The agent whose conversations are exported.
        :return: The conversations, oldest first, each with its messages in the order
            they were sent.
        """

        conversations = (
            AgentConversation.objects.filter(agent=agent)
            .order_by("id")
            .prefetch_related(
                Prefetch("messages", queryset=AgentMessage.objects.order_by("id"))
            )
        )
        return [
            {
                "title": conversation.title,
                "owner_user_id": conversation.owner_user_id,
                "created_on": conversation.created_on.isoformat(),
                "updated_on": conversation.updated_on.isoformat(),
                "messages": [
                    {
                        "role": message.role,
                        "content": message.content,
                        "status": message.status,
                        "error_code": message.error_code,
                        "created_on": message.created_on.isoformat(),
                        "updated_on": message.updated_on.isoformat(),
                    }
                    for message in conversation.messages.all()
                ],
            }
            for conversation in conversations
        ]

    def import_conversations(
        self, agent: AgentApplication, serialized_conversations: list[dict]
    ) -> None:
        """
        Copy conversations with their messages into the agent with new uuids.
        Conversations of deleted owners are skipped, and a reply still being
        written is ended as interrupted.

        :param agent: The agent to copy the conversations into.
        :param serialized_conversations: The conversations from export_conversations.
        """

        existing_owner_ids = set(
            get_user_model()
            .objects.filter(
                id__in=[data["owner_user_id"] for data in serialized_conversations]
            )
            .values_list("id", flat=True)
        )
        retained_data = [
            data
            for data in serialized_conversations
            if data["owner_user_id"] in existing_owner_ids
        ]
        conversations = [
            AgentConversation(
                agent=agent,
                uuid=uuid4(),
                title=data["title"],
                owner_user_id=data["owner_user_id"],
            )
            for data in retained_data
        ]

        AgentConversation.objects.bulk_create(conversations, batch_size=1000)
        messages = []
        message_data = []
        for conversation, data in zip(conversations, retained_data):
            conversation.created_on = parse_datetime(data["created_on"])
            conversation.updated_on = parse_datetime(data["updated_on"])
            for serialized_message in data["messages"]:
                status = serialized_message["status"]
                error_code = serialized_message["error_code"]
                if status in ACTIVE_CHAT_RUN_STATUSES:
                    status = ChatRunStatus.FAILED
                    error_code = ChatRunErrorCode.INTERRUPTED
                messages.append(
                    AgentMessage(
                        conversation=conversation,
                        uuid=uuid4(),
                        role=serialized_message["role"],
                        content=serialized_message["content"],
                        status=status,
                        error_code=error_code,
                    )
                )
                message_data.append(serialized_message)

        # auto_now overrides timestamps in bulk_create, so restore the captured ones.
        AgentConversation.objects.bulk_update(
            conversations, ["created_on", "updated_on"], batch_size=1000
        )
        AgentMessage.objects.bulk_create(messages, batch_size=1000)
        for message, data in zip(messages, message_data):
            message.created_on = parse_datetime(data["created_on"])
            message.updated_on = parse_datetime(data["updated_on"])
        AgentMessage.objects.bulk_update(
            messages, ["created_on", "updated_on"], batch_size=1000
        )
