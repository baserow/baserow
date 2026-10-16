from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models import Prefetch, QuerySet
from django.utils.dateparse import parse_datetime

from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.utils import extract_allowed

from .exceptions import AgentConversationDoesNotExist, AgentMessageConflict
from .models import AgentApplication, AgentConversation, AgentMessage
from .types import AgentConfiguration, AgentConfigurationUpdated, AgentMessageCreated
from .validators import validate_configuration_values


class AgentHandler:
    configuration_fields = [
        "name",
        "instructions",
        "provider_type",
        "model_identifier",
    ]

    def get_agent(self, agent_id: int, for_update: bool = False) -> AgentApplication:
        """Fetch a live Agent subtype, optionally locking its configuration rows."""

        queryset = AgentApplication.objects.filter(workspace__isnull=False)
        if for_update:
            # Settings and message writes share this lock, so sends see saved settings.
            queryset = queryset.select_for_update(of=("self", "application_ptr"))
        return CoreHandler().get_application(agent_id, base_queryset=queryset)

    def get_configuration(self, agent: AgentApplication) -> AgentConfiguration:
        """Resolve draft completeness and current eligible models without execution."""

        errors = {}
        for field in self.configuration_fields:
            if not (getattr(agent, field) or "").strip():
                errors[field] = "required"

        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            agent.workspace, feature_type=AI_PROVIDER_FEATURE_AI_AGENT
        )
        if agent.provider_type:
            if agent.provider_type not in models:
                errors["provider_type"] = "unavailable"
            if agent.model_identifier and agent.model_identifier not in models.get(
                agent.provider_type, []
            ):
                errors["model_identifier"] = "unavailable"

        if "required" in errors.values():
            state = "incomplete"
        elif errors:
            state = "unavailable"
        else:
            state = "ready"
        return {
            **{field: getattr(agent, field) for field in self.configuration_fields},
            "state": state,
            "errors": errors,
        }

    def update_configuration(
        self, agent: AgentApplication, **values
    ) -> AgentConfigurationUpdated:
        """Persist a partial static draft and identify its changed field names."""

        values = extract_allowed(values, self.configuration_fields)
        validate_configuration_values(values)
        changed_fields = []
        for field, value in values.items():
            if field in ("provider_type", "model_identifier"):
                value = (value or "").strip() or None
            if getattr(agent, field) != value:
                setattr(agent, field, value)
                changed_fields.append(field)
        if changed_fields:
            agent.save(update_fields=[*changed_fields, "updated_on"])
        return AgentConfigurationUpdated(agent, changed_fields)

    def list_conversations(
        self, agent: AgentApplication, owner: AbstractUser
    ) -> QuerySet[AgentConversation]:
        """Return only the private owner's activity in this agent."""

        return AgentConversation.objects.filter(agent=agent, owner_user=owner)

    def get_conversation(
        self, agent: AgentApplication, owner: AbstractUser, uuid: UUID
    ) -> AgentConversation:
        """Treat cross-owner or cross-agent conversation identifiers as missing."""

        try:
            return AgentConversation.objects.get(
                uuid=uuid, agent=agent, owner_user=owner
            )
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
        """Return the accepted first message; other owners' UUIDs look missing."""

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
        """Create a private thread and safely resolve concurrent global UUID reuse."""

        conversation, created = AgentConversation.objects.get_or_create(
            uuid=uuid,
            defaults={
                "agent": agent,
                "owner_user": user,
                "initiated_by": user,
                "title": " ".join(content.split())[:250],
            },
        )
        if not created:
            # get_or_create resolves a racing duplicate inside a savepoint.
            return self._get_first_message_retry(
                conversation, agent, user, message_uuid, content
            )
        return self.create_message(conversation, user, message_uuid, content)

    def get_message_retry(
        self, conversation: AgentConversation, uuid: UUID, content: str
    ) -> AgentMessageCreated | None:
        """An accepted UUID may be replayed only with identical content."""

        message = conversation.messages.filter(uuid=uuid).first()
        if message is None:
            return None
        if message.content != content:
            raise AgentMessageConflict
        return AgentMessageCreated(conversation, message, False)

    def create_message(
        self,
        conversation: AgentConversation,
        user: AbstractUser,
        uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """Append server-attributed content and refresh the thread's activity time."""

        message = AgentMessage.objects.create(
            conversation=conversation, uuid=uuid, author_user=user, content=content
        )
        conversation.save(update_fields=["updated_on"])
        return AgentMessageCreated(conversation, message, True)

    def export_conversations(self, agent: AgentApplication) -> list[dict]:
        """Capture private history, in message order, for an internal copy."""

        conversations = (
            AgentConversation.objects.filter(agent=agent, owner_user__isnull=False)
            .order_by("id")
            .prefetch_related(
                Prefetch("messages", queryset=AgentMessage.objects.order_by("id"))
            )
        )
        return [
            {
                "title": conversation.title,
                "source_type": conversation.source_type,
                "visibility": conversation.visibility,
                "owner_user_id": conversation.owner_user_id,
                "initiated_by_id": conversation.initiated_by_id,
                "created_on": conversation.created_on.isoformat(),
                "updated_on": conversation.updated_on.isoformat(),
                "messages": [
                    {
                        "role": message.role,
                        "content": message.content,
                        "author_user_id": message.author_user_id,
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
        """Copy history to new IDs, keeping existing owners and skipping deleted."""

        actor_ids = set()
        for data in serialized_conversations:
            actor_ids.update((data.get("owner_user_id"), data.get("initiated_by_id")))
            actor_ids.update(
                message.get("author_user_id") for message in data["messages"]
            )
        actor_ids.discard(None)
        existing_actor_ids = set(
            get_user_model()
            .objects.filter(id__in=actor_ids)
            .values_list("id", flat=True)
        )

        conversations = []
        retained_data = []
        for data in serialized_conversations:
            owner_id = data.get("owner_user_id")
            if owner_id not in existing_actor_ids:
                continue
            initiated_by_id = data.get("initiated_by_id")
            conversations.append(
                AgentConversation(
                    agent=agent,
                    uuid=uuid4(),
                    title=data["title"],
                    source_type=data["source_type"],
                    visibility=data["visibility"],
                    owner_user_id=owner_id,
                    initiated_by_id=(
                        initiated_by_id
                        if initiated_by_id in existing_actor_ids
                        else None
                    ),
                )
            )
            retained_data.append(data)

        AgentConversation.objects.bulk_create(conversations, batch_size=1000)
        messages = []
        message_data = []
        for conversation, data in zip(conversations, retained_data):
            conversation.created_on = parse_datetime(data["created_on"])
            conversation.updated_on = parse_datetime(data["updated_on"])
            for serialized_message in data["messages"]:
                author_id = serialized_message.get("author_user_id")
                messages.append(
                    AgentMessage(
                        conversation=conversation,
                        uuid=uuid4(),
                        role=serialized_message["role"],
                        content=serialized_message["content"],
                        author_user_id=(
                            author_id if author_id in existing_actor_ids else None
                        ),
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
