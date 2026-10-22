from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models import Prefetch, QuerySet
from django.utils import timezone
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
from .models import AgentApplication, AgentConversation, AgentMessage, AgentTurn
from .operations import (
    CreateAgentMessageOperationType,
    ReadAgentConversationsOperationType,
)
from .types import (
    AgentConfiguration,
    AgentConfigurationUpdated,
    AgentMessageCreated,
    AgentReply,
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
        :return: The conversation and its first message, or None when nothing was
            accepted with this uuid before.
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
        return AgentMessageCreated(conversation, message, False)

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
        :return: The conversation and its first message, and whether they are new.
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
        return self.create_message(conversation, message_uuid, content, user)

    def get_message_retry(
        self, conversation: AgentConversation, uuid: UUID, content: str
    ) -> AgentMessageCreated | None:
        """
        Return the message already accepted for a message uuid.

        :param conversation: The conversation the message is sent to.
        :param uuid: The uuid of the message.
        :param content: The content of the message.
        :raises AgentMessageConflict: When the uuid was accepted with other content.
        :return: The conversation and the accepted message, or None when nothing was
            accepted with this uuid before.
        """

        message = conversation.messages.filter(uuid=uuid).first()
        if message is None:
            return None
        if message.content != content:
            raise AgentMessageConflict
        return AgentMessageCreated(conversation, message, False)

    def create_message(
        self,
        conversation: AgentConversation,
        uuid: UUID,
        content: str,
        author: AbstractUser,
    ) -> AgentMessageCreated:
        """
        Add a user message in a new turn and start the agent's reply to it.

        Call it in the transaction that checked the message, so a refused reply
        saves nothing.

        :param conversation: The conversation to add the message to.
        :param uuid: The uuid of the message.
        :param content: The content of the message.
        :param author: The user who sent the message.
        :raises ChatRunAlreadyActive: When the agent is still replying in this
            conversation.
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The conversation and the new message.
        """

        turn = AgentTurn.objects.create(conversation=conversation)
        message = AgentMessage.objects.create(
            conversation=conversation,
            uuid=uuid,
            content=content,
            turn=turn,
            author_user=author,
        )
        conversation.save(update_fields=["updated_on"])
        ChatRunHandler().start_run(
            AGENT_RUN_TYPE,
            conversation.id,
            conversation.agent.workspace,
            author,
            context={"turn_id": turn.id},
            created_event_data={},
        )
        return AgentMessageCreated(conversation, message, True)

    def get_active_turn_runs(self, conversation: AgentConversation) -> dict[int, UUID]:
        """
        Return the run still answering a turn of the conversation, if any.

        :param conversation: The conversation to look at.
        :return: The id of the active run by the id of the turn it answers, empty
            when the agent isn't replying.
        """

        run = ChatRunHandler().get_active_run(AGENT_RUN_TYPE, conversation.id)
        return {run.context["turn_id"]: run.id} if run else {}

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

        :param run: The run answering a turn.
        :raises AgentConversationDoesNotExist: When the turn no longer exists.
        :raises PermissionException: When the author doesn't own the conversation,
            the agent or its workspace is trashed, or the author may no longer send
            messages to the agent.
        :raises AgentNotReady: When the agent's configuration is no longer ready.
        :return: The instructions, the model, the prompt and the earlier messages.
        """

        turn = (
            AgentTurn.objects.select_related(
                "conversation__agent__workspace", "conversation__owner_user"
            )
            .filter(id=run.context["turn_id"])
            .first()
        )
        if turn is None:
            raise AgentConversationDoesNotExist
        conversation = turn.conversation
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
        prompt = turn.messages.get(role=AgentMessage.Role.USER)
        history = (
            conversation.messages.filter(id__lt=prompt.id)
            .select_related("turn")
            .order_by("-id")[:HISTORY_MESSAGE_LIMIT]
        )
        return AgentReplyRequest(
            turn_id=turn.id,
            workspace=agent.workspace,
            instructions=agent.instructions,
            provider_type=agent.provider_type,
            model_identifier=agent.model_identifier,
            prompt=prompt.content,
            history=list(reversed(history)),
        )

    def finish_turn(
        self,
        turn_id: int,
        status: str,
        error_code: str,
        reply: AgentReply | None,
    ) -> dict | None:
        """
        End a turn with how its reply ended, saving the reply's text as a message.
        NUL characters are dropped from the text and model messages, as
        PostgreSQL can't store them.

        :param turn_id: The id of the turn.
        :param status: The final status: completed, cancelled or failed.
        :param error_code: Why the reply failed, or an empty string.
        :param reply: What the reply produced, or None when it never started.
        :return: The ids of the turn and of the saved reply, or None when the turn
            no longer exists.
        """

        turn = (
            AgentTurn.objects.select_for_update(of=("self",))
            .select_related("conversation")
            .filter(id=turn_id)
            .first()
        )
        if turn is None:
            return None
        turn.status = AgentTurn.Status(status)
        turn.error_code = error_code
        turn.finished_on = timezone.now()
        message = None
        if reply is not None:
            text = remove_null_characters(reply.text)
            turn.provider_type = reply.provider_type
            turn.model_identifier = reply.model_identifier
            turn.model_messages = remove_null_characters(reply.model_messages)
            turn.usage = reply.usage
            if text.strip():
                message = AgentMessage.objects.create(
                    conversation=turn.conversation,
                    uuid=uuid4(),
                    role=AgentMessage.Role.ASSISTANT,
                    content=text,
                    turn=turn,
                )
        turn.save()
        turn.conversation.save(update_fields=["updated_on"])
        return {"turn_id": turn.id, "message_id": message.id if message else None}

    def mark_turn_interrupted(self, turn_id: int) -> None:
        """
        Show that a started reply did not complete, unless its turn already ended.

        :param turn_id: The id of the turn.
        """

        AgentTurn.objects.filter(
            id=turn_id,
            status__in=[AgentTurn.Status.QUEUED, AgentTurn.Status.RUNNING],
        ).update(
            status=AgentTurn.Status.FAILED,
            error_code=ChatRunErrorCode.INTERRUPTED,
            finished_on=timezone.now(),
        )

    def export_conversations(self, agent: AgentApplication) -> list[dict]:
        """
        Serialize the agent's conversations, turns and messages for an internal
        copy.

        :param agent: The agent whose conversations are exported.
        :return: The conversations, oldest first, each with its turns and its
            messages in the order they were sent, every message with the position of
            its turn and its author.
        """

        conversations = (
            AgentConversation.objects.filter(agent=agent)
            .order_by("id")
            .prefetch_related(
                Prefetch("messages", queryset=AgentMessage.objects.order_by("id")),
                Prefetch("turns", queryset=AgentTurn.objects.order_by("id")),
            )
        )
        return [
            self._export_conversation(conversation) for conversation in conversations
        ]

    @staticmethod
    def _export_conversation(conversation: AgentConversation) -> dict:
        """
        Serialize one conversation with its turns and messages.

        :param conversation: The conversation, with turns and messages prefetched.
        :return: The serialized conversation.
        """

        turns = list(conversation.turns.all())
        positions = {turn.id: index for index, turn in enumerate(turns)}
        return {
            "title": conversation.title,
            "owner_user_id": conversation.owner_user_id,
            "created_on": conversation.created_on.isoformat(),
            "updated_on": conversation.updated_on.isoformat(),
            "turns": [
                {
                    "status": turn.status,
                    "error_code": turn.error_code,
                    "provider_type": turn.provider_type,
                    "model_identifier": turn.model_identifier,
                    "model_messages": turn.model_messages,
                    "usage": turn.usage,
                    "created_on": turn.created_on.isoformat(),
                    "finished_on": (
                        turn.finished_on.isoformat() if turn.finished_on else None
                    ),
                }
                for turn in turns
            ],
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    "turn_position": positions.get(message.turn_id),
                    "author_user_id": message.author_user_id,
                    "created_on": message.created_on.isoformat(),
                    "updated_on": message.updated_on.isoformat(),
                }
                for message in conversation.messages.all()
            ],
        }

    @staticmethod
    def _import_turn(conversation: AgentConversation, data: dict) -> AgentTurn:
        """
        Copy a turn, ending any reply in progress: a copy never carries one.

        :param conversation: The copied conversation the turn belongs to.
        :param data: The serialized turn.
        :return: The unsaved turn.
        """

        live = data["status"] in (AgentTurn.Status.QUEUED, AgentTurn.Status.RUNNING)
        if live:
            finished_on = timezone.now()
        elif data["finished_on"]:
            finished_on = parse_datetime(data["finished_on"])
        else:
            finished_on = None
        return AgentTurn(
            conversation=conversation,
            status=AgentTurn.Status.FAILED if live else data["status"],
            error_code=ChatRunErrorCode.INTERRUPTED if live else data["error_code"],
            provider_type=data["provider_type"],
            model_identifier=data["model_identifier"],
            model_messages=data["model_messages"],
            usage=data["usage"],
            finished_on=finished_on,
        )

    def import_conversations(
        self, agent: AgentApplication, serialized_conversations: list[dict]
    ) -> None:
        """
        Copy conversations with their turns and messages into the agent with new
        uuids. Conversations of deleted owners are skipped, authors who were deleted
        are dropped, and a turn still replying is ended as interrupted.

        :param agent: The agent to copy the conversations into.
        :param serialized_conversations: The conversations from export_conversations.
        """

        referenced_user_ids = {
            data["owner_user_id"] for data in serialized_conversations
        } | {
            message["author_user_id"]
            for data in serialized_conversations
            for message in data["messages"]
            if message.get("author_user_id") is not None
        }
        existing_user_ids = set(
            get_user_model()
            .objects.filter(id__in=referenced_user_ids)
            .values_list("id", flat=True)
        )
        retained_data = [
            data
            for data in serialized_conversations
            if data["owner_user_id"] in existing_user_ids
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
        turns_by_conversation = []
        turns = []
        turn_data = []
        for conversation, data in zip(conversations, retained_data):
            conversation.created_on = parse_datetime(data["created_on"])
            conversation.updated_on = parse_datetime(data["updated_on"])
            conversation_turns = [
                self._import_turn(conversation, serialized_turn)
                for serialized_turn in data.get("turns", [])
            ]
            turns_by_conversation.append(conversation_turns)
            turns.extend(conversation_turns)
            turn_data.extend(data.get("turns", []))

        # auto_now overrides timestamps in bulk_create, so restore the captured ones.
        AgentConversation.objects.bulk_update(
            conversations, ["created_on", "updated_on"], batch_size=1000
        )
        AgentTurn.objects.bulk_create(turns, batch_size=1000)
        for turn, serialized_turn in zip(turns, turn_data):
            turn.created_on = parse_datetime(serialized_turn["created_on"])
        AgentTurn.objects.bulk_update(turns, ["created_on"], batch_size=1000)

        messages = []
        message_data = []
        for conversation, conversation_turns, data in zip(
            conversations, turns_by_conversation, retained_data
        ):
            for serialized_message in data["messages"]:
                position = serialized_message.get("turn_position")
                author_user_id = serialized_message.get("author_user_id")
                messages.append(
                    AgentMessage(
                        conversation=conversation,
                        uuid=uuid4(),
                        role=serialized_message["role"],
                        content=serialized_message["content"],
                        turn=None if position is None else conversation_turns[position],
                        author_user_id=author_user_id
                        if author_user_id in existing_user_ids
                        else None,
                    )
                )
                message_data.append(serialized_message)

        AgentMessage.objects.bulk_create(messages, batch_size=1000)
        for message, data in zip(messages, message_data):
            message.created_on = parse_datetime(data["created_on"])
            message.updated_on = parse_datetime(data["updated_on"])
        AgentMessage.objects.bulk_update(
            messages, ["created_on", "updated_on"], batch_size=1000
        )
