from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Prefetch, QuerySet
from django.utils.dateparse import parse_datetime

from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.ai_provider.resolution import ScopedAIProviderState
from baserow.core.chat_runs.constants import ChatRunErrorCode
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.exceptions import PermissionDenied
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.utils import extract_allowed, remove_null_characters

from .constants import AGENT_RUN_TYPE, HISTORY_MESSAGE_LIMIT
from .exceptions import (
    AgentConversationDoesNotExist,
    AgentMessageConflict,
    AgentNotReady,
)
from .models import AgentApplication, AgentConversation, AgentMessage
from .operations import (
    CreateAgentMessageOperationType,
    ReadAgentConversationsOperationType,
)
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
        :return: The conversation.
        """

        queryset = AgentConversation.objects.all()
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        try:
            return queryset.get(uuid=uuid, agent=agent, owner_user=owner)
        except AgentConversation.DoesNotExist as exc:
            raise AgentConversationDoesNotExist from exc

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
        """Validate both an existing identifier and a racing get_or_create result."""

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
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The conversation, its first message and its reply, and whether they
            are new.
        """

        conversation, created = AgentConversation.objects.get_or_create(
            uuid=uuid,
            defaults={
                "agent": agent,
                "owner_user": user,
                "title": " ".join(content.split())[:250],
            },
        )
        if not created:
            # get_or_create resolves a racing duplicate inside a savepoint.
            return self._get_first_message_retry(
                conversation, agent, user, message_uuid, content
            )
        return self.create_message(conversation, message_uuid, content)

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
        :raises ChatRunAlreadyActive: When the agent is still replying in this
            conversation.
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The conversation, the new message, its reply and the run writing
            it.
        """

        message = AgentMessage.objects.create(
            conversation=conversation, uuid=uuid, content=content
        )
        reply = AgentMessage.objects.create(
            conversation=conversation,
            uuid=uuid4(),
            role=AgentMessage.Role.ASSISTANT,
            content="",
            status=AgentMessage.Status.RUNNING,
        )
        conversation.save(update_fields=["updated_on"])
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

    def can_read_conversation(self, user: AbstractUser, conversation_id: int) -> bool:
        """
        Check that the user owns the conversation in an untrashed Agent and may
        still read the agent's conversations.

        :param user: The user asking.
        :param conversation_id: The id of the conversation.
        :return: Whether the user may read the conversation.
        """

        conversation = (
            self.get_accessible_conversations(user)
            .select_related("agent__workspace")
            .filter(id=conversation_id)
            .first()
        )
        if conversation is None:
            return False
        return CoreHandler().check_permissions(
            user,
            ReadAgentConversationsOperationType.type,
            workspace=conversation.agent.workspace,
            context=conversation.agent,
            raise_permission_exceptions=False,
        )

    def prepare_reply(self, run: ChatRun) -> AgentReplyRequest:
        """
        Load what a run answers, checking again that its author may still send it.

        :param run: The run writing a reply.
        :raises AgentConversationDoesNotExist: When the reply no longer exists.
        :raises PermissionException: When the author doesn't own the conversation,
            the agent or its workspace is trashed, or the author may no longer send
            messages to the agent.
        :raises AgentNotReady: When the agent's configuration is no longer ready.
        :return: The instructions, the model, the prompt and the earlier messages.
        """

        reply = (
            AgentMessage.objects.select_related(
                "conversation__agent__workspace", "conversation__owner_user"
            )
            .filter(id=run.context["reply_id"])
            .first()
        )
        if reply is None:
            raise AgentConversationDoesNotExist
        conversation = reply.conversation
        agent = conversation.agent
        if (
            run.created_by_id != conversation.owner_user_id
            or not self.get_accessible_conversations(conversation.owner_user)
            .filter(id=conversation.id)
            .exists()
        ):
            raise PermissionDenied
        CoreHandler().check_permissions(
            conversation.owner_user,
            CreateAgentMessageOperationType.type,
            workspace=agent.workspace,
            context=agent,
        )
        if self.get_configuration(agent)["readiness"] != "ready":
            raise AgentNotReady
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
    ) -> dict | None:
        """
        Save how a reply ended, with its text. NUL characters are dropped because
        PostgreSQL can't store them, and blank text is saved empty because some
        providers reject blank replies in the history.

        :param reply_id: The id of the reply.
        :param status: The final status: completed, cancelled or failed.
        :param error_code: Why the reply failed, or an empty string.
        :param text: What the reply produced, or None when it never started.
        :return: The id of the reply, or None when it no longer exists.
        """

        reply = (
            AgentMessage.objects.select_for_update(of=("self",))
            .select_related("conversation")
            .filter(id=reply_id)
            .first()
        )
        if reply is None:
            return None
        reply.status = AgentMessage.Status(status)
        reply.error_code = error_code
        content = remove_null_characters(text or "")
        reply.content = content if content.strip() else ""
        reply.save()
        reply.conversation.save(update_fields=["updated_on"])
        return {"message_id": reply.id}

    def refresh_unfinished_replies(
        self, messages: list[AgentMessage]
    ) -> list[AgentMessage]:
        """
        Read the replies that still look unfinished again from the primary database,
        where their runs are read: a lagging replica can show a reply as running
        after its run ended.

        :param messages: Messages, possibly read from a replica.
        :return: The same messages, with the unfinished replies read again.
        """

        unfinished = [
            message.id
            for message in messages
            if message.status
            in (AgentMessage.Status.QUEUED, AgentMessage.Status.RUNNING)
        ]
        if not unfinished:
            return messages
        fresh = AgentMessage.objects.using(DEFAULT_DB_ALIAS).in_bulk(unfinished)
        return [fresh.get(message.id, message) for message in messages]

    def mark_reply_interrupted(self, reply_id: int) -> None:
        """
        Show that a started reply did not complete, unless it already ended.

        :param reply_id: The id of the reply.
        """

        AgentMessage.objects.filter(
            id=reply_id,
            status__in=[AgentMessage.Status.QUEUED, AgentMessage.Status.RUNNING],
        ).update(
            status=AgentMessage.Status.FAILED,
            error_code=ChatRunErrorCode.INTERRUPTED,
        )

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

    @staticmethod
    def _import_message(conversation: AgentConversation, data: dict) -> AgentMessage:
        """
        Copy a message, ending a reply in progress: a copy never carries one.

        :param conversation: The copied conversation the message belongs to.
        :param data: The serialized message.
        :return: The unsaved message.
        """

        status = data.get("status")
        error_code = data.get("error_code", "")
        if status in (AgentMessage.Status.QUEUED, AgentMessage.Status.RUNNING):
            status = AgentMessage.Status.FAILED
            error_code = ChatRunErrorCode.INTERRUPTED
        return AgentMessage(
            conversation=conversation,
            uuid=uuid4(),
            role=data["role"],
            content=data["content"],
            status=status,
            error_code=error_code,
        )

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
                messages.append(self._import_message(conversation, serialized_message))
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
