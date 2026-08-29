from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import QuerySet, Sum

from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.models import Agent
from baserow.core.utils import extract_allowed

from .exceptions import (
    AgentChatAlreadyRunning,
    AgentChatAwaitingApproval,
    AgentChatDoesNotExist,
    AgentDefinitionDoesNotExist,
    AgentToolApprovalDoesNotExist,
)
from .models import (
    AgentApplication,
    AgentChat,
    AgentChatMessage,
    AgentChatToolApproval,
    AgentDefinition,
)


class AgentApplicationHandler:
    allowed_agent_fields = [
        "name",
        "description",
        "instructions",
        "memory",
        "ai_generative_ai_type",
        "ai_generative_ai_model",
        "ai_temperature",
    ]

    def get_agent(
        self, agent_id: int, base_queryset: Optional[QuerySet] = None
    ) -> AgentDefinition:
        """
        Returns the agent definition with the given id.

        :param agent_id: The id of the agent definition.
        :param base_queryset: Optional queryset to fetch the agent from.
        :raises AgentDefinitionDoesNotExist: When the agent doesn't exist.
        """

        queryset = (
            base_queryset
            if base_queryset is not None
            else AgentDefinition.objects.all()
        )

        try:
            return queryset.select_related("application__workspace").get(id=agent_id)
        except AgentDefinition.DoesNotExist:
            raise AgentDefinitionDoesNotExist(
                f"The agent with id {agent_id} does not exist."
            )

    def get_main_agent(self, application: AgentApplication) -> AgentDefinition:
        """
        Returns the application's main agent.

        :param application: The agent application.
        :raises AgentDefinitionDoesNotExist: When the application has no agent.
        """

        agent = application.agents.first()

        if agent is None:
            raise AgentDefinitionDoesNotExist(
                f"The application {application.id} has no agent."
            )

        return agent

    def create_main_agent(
        self, application: AgentApplication, name: str, description: str = ""
    ) -> AgentDefinition:
        return AgentDefinition.objects.create(
            application=application, name=name, description=description
        )

    def update_agent(self, agent: AgentDefinition, **kwargs) -> AgentDefinition:
        allowed_values = extract_allowed(kwargs, self.allowed_agent_fields)

        for key, value in allowed_values.items():
            setattr(agent, key, value)

        agent.save(update_fields=list(allowed_values.keys()) + ["updated_on"])
        return agent

    def set_agent_identity(
        self, application: AgentApplication, agent_identity: Optional[Agent]
    ) -> AgentApplication:
        application.agent_identity = agent_identity
        application.save(update_fields=["agent_identity"])
        self.sync_agent_identity(application)
        return application

    def sync_agent_identity(self, application: AgentApplication) -> None:
        """
        Keeps the application's integrations acting as the application's agent
        identity, so that trigger and tool services resolve their permissions
        against the same subject as the agent itself.
        """

        LocalBaserowIntegration.objects.filter(application=application).update(
            authorized_agent=application.agent_identity
        )


class AgentChatHandler:
    def get_chat_by_uuid(
        self, chat_uuid, base_queryset: Optional[QuerySet] = None
    ) -> AgentChat:
        queryset = (
            base_queryset if base_queryset is not None else AgentChat.objects.all()
        )

        try:
            return queryset.select_related(
                "agent__application__workspace",
                "agent__application__agent_identity",
            ).get(uuid=chat_uuid)
        except AgentChat.DoesNotExist:
            raise AgentChatDoesNotExist(
                f"The chat with uuid {chat_uuid} does not exist."
            )

    def get_or_create_manual_chat(
        self, agent: AgentDefinition, user: AbstractUser, chat_uuid
    ) -> AgentChat:
        chat = AgentChat.objects.filter(uuid=chat_uuid).first()

        if chat is not None:
            if chat.agent_id != agent.id:
                raise AgentChatDoesNotExist(
                    f"The chat with uuid {chat_uuid} does not exist for this agent."
                )
            return chat

        return AgentChat.objects.create(
            uuid=chat_uuid,
            agent=agent,
            user=user,
            source=AgentChat.Source.MANUAL,
        )

    def create_triggered_chat(
        self,
        agent: AgentDefinition,
        trigger_type: str,
        event_payload=None,
        source: str = AgentChat.Source.TRIGGER,
        user: Optional[AbstractUser] = None,
    ) -> AgentChat:
        return AgentChat.objects.create(
            agent=agent,
            source=source,
            trigger_type=trigger_type,
            event_payload=event_payload,
            user=user,
        )

    def create_message(
        self,
        chat: AgentChat,
        role: str,
        content: str,
        attachments: Optional[list] = None,
    ) -> AgentChatMessage:
        from .realtime import broadcast_chat_event

        message = AgentChatMessage.objects.create(
            chat=chat, role=role, content=content, attachments=attachments or []
        )
        # Other users watching this conversation must see new human/system
        # messages appear live; AI events are broadcast by the runner.
        broadcast_chat_event(
            chat,
            {
                "type": role,
                "id": message.id,
                "content": content,
                "attachments": message.attachments,
            },
        )
        return message

    def list_chats(self, agent: AgentDefinition) -> QuerySet:
        return agent.chats.order_by("-updated_on")

    def list_messages(self, chat: AgentChat) -> QuerySet:
        return chat.messages.order_by("id")

    def start_chat_run(self, chat: AgentChat, prompt_message: AgentChatMessage) -> None:
        """
        Marks the chat as running and enqueues the background run after the
        current transaction commits.

        :raises AgentChatAlreadyRunning: When a run is already in progress.
        """

        from .realtime import broadcast_chat_updated
        from .tasks import run_agent_chat

        if chat.status == AgentChat.Status.AWAITING_APPROVAL:
            # Starting a new turn now would leave the pending tool calls in
            # the history unanswered, which breaks the model conversation.
            raise AgentChatAwaitingApproval(
                f"The chat {chat.id} has pending tool approvals."
            )

        updated = (
            AgentChat.objects.filter(id=chat.id)
            .exclude(
                status__in=[
                    AgentChat.Status.IN_PROGRESS,
                    AgentChat.Status.CANCELING,
                    AgentChat.Status.AWAITING_APPROVAL,
                ]
            )
            .update(status=AgentChat.Status.IN_PROGRESS)
        )

        if not updated:
            raise AgentChatAlreadyRunning(f"The chat {chat.id} is already running.")

        chat.status = AgentChat.Status.IN_PROGRESS
        broadcast_chat_updated(chat)

        transaction.on_commit(lambda: run_agent_chat.delay(chat.id, prompt_message.id))

    def retry_chat_run(self, chat: AgentChat) -> AgentChatMessage:
        """
        Re-runs the turn of a chat that ended in an error, using its last
        prompt message.

        :param chat: The chat to retry.
        :raises AgentChatNotRetryable: When the chat is not in an error state
            or has no prompt message to retry.
        :return: The prompt message the retried run is based on.
        """

        from .exceptions import AgentChatNotRetryable

        if chat.status != AgentChat.Status.ERROR:
            raise AgentChatNotRetryable(
                f"The chat {chat.id} did not fail, so there is nothing to retry."
            )

        prompt_message = (
            chat.messages.filter(
                role__in=[AgentChatMessage.Role.HUMAN, AgentChatMessage.Role.SYSTEM]
            )
            .order_by("-id")
            .first()
        )
        if prompt_message is None:
            raise AgentChatNotRetryable(
                f"The chat {chat.id} has no prompt message to retry."
            )

        self.start_chat_run(chat, prompt_message)
        return prompt_message

    def cancel_chat_run(self, chat: AgentChat, user: Optional[AbstractUser] = None):
        from .realtime import broadcast_chat_updated
        from .runner import set_agent_chat_cancellation_key

        if chat.is_awaiting_approval:
            # Cancelling a paused run means rejecting everything still
            # pending; the run is resumed with the rejections so the model
            # conversation is closed properly.
            pending = list(
                chat.tool_approvals.filter(
                    status=AgentChatToolApproval.Status.PENDING
                ).values_list("id", flat=True)
            )
            if pending:
                self.decide_tool_approvals(
                    chat,
                    user,
                    [
                        {"id": approval_id, "approved": False, "reason": ""}
                        for approval_id in pending
                    ],
                )
            return

        if not chat.is_running:
            return

        set_agent_chat_cancellation_key(chat.uuid)
        chat.status = AgentChat.Status.CANCELING
        chat.save(update_fields=["status", "updated_on"])
        broadcast_chat_updated(chat)

    def list_tool_approvals(self, chat: AgentChat) -> QuerySet:
        return chat.tool_approvals.order_by("id")

    def list_pending_approvals(self, application) -> QuerySet:
        """
        All pending tool approvals of the application across every
        conversation, newest first, for the approval overview.
        """

        return (
            AgentChatToolApproval.objects.filter(
                chat__agent__application=application,
                status=AgentChatToolApproval.Status.PENDING,
            )
            .select_related("chat")
            .order_by("-id")
        )

    def get_pending_approvals_count(self, application) -> int:
        return AgentChatToolApproval.objects.filter(
            chat__agent__application=application,
            status=AgentChatToolApproval.Status.PENDING,
        ).count()

    def decide_tool_approvals(
        self,
        chat: AgentChat,
        user: Optional[AbstractUser],
        decisions: list[dict],
    ) -> list[AgentChatToolApproval]:
        """
        Applies approve/reject decisions to pending tool approvals of the
        chat. Once no pending approvals remain, the paused run is resumed
        with the decisions.

        :param chat: The chat whose approvals are decided.
        :param user: The deciding user.
        :param decisions: Dicts with `id`, `approved` and optional `reason`.
        :raises AgentToolApprovalDoesNotExist: When a decision references an
            approval that doesn't exist or isn't pending anymore.
        """

        from django.utils import timezone

        from .chat_types import ApprovalDecidedMessage
        from .realtime import broadcast_chat_event, broadcast_chat_updated
        from .tasks import resume_agent_chat

        decided = []
        for decision in decisions:
            approval = chat.tool_approvals.filter(
                id=decision["id"], status=AgentChatToolApproval.Status.PENDING
            ).first()
            if approval is None:
                raise AgentToolApprovalDoesNotExist(
                    f"The pending tool approval {decision['id']} does not exist."
                )
            approval.status = (
                AgentChatToolApproval.Status.APPROVED
                if decision["approved"]
                else AgentChatToolApproval.Status.REJECTED
            )
            approval.reason = decision.get("reason") or ""
            approval.decided_by = user
            approval.decided_at = timezone.now()
            approval.save(
                update_fields=[
                    "status",
                    "reason",
                    "decided_by",
                    "decided_at",
                    "updated_on",
                ]
            )
            decided.append(approval)
            broadcast_chat_event(
                chat,
                ApprovalDecidedMessage(
                    id=approval.id, status=approval.status, reason=approval.reason
                ).model_dump(),
            )

        has_pending = chat.tool_approvals.filter(
            status=AgentChatToolApproval.Status.PENDING
        ).exists()
        if not has_pending:
            updated = AgentChat.objects.filter(
                id=chat.id, status=AgentChat.Status.AWAITING_APPROVAL
            ).update(status=AgentChat.Status.IN_PROGRESS)
            if updated:
                chat.status = AgentChat.Status.IN_PROGRESS
                broadcast_chat_updated(chat)
                transaction.on_commit(lambda: resume_agent_chat.delay(chat.id))

        if decided:
            from .realtime import broadcast_pending_approvals_updated

            broadcast_pending_approvals_updated(chat.agent.application)

        return decided

    def delete_chat(self, chat: AgentChat) -> None:
        from .realtime import broadcast_chat_deleted

        application_id = chat.agent.application_id
        chat_id = chat.id
        chat.delete()
        broadcast_chat_deleted(application_id, chat_id)

    def get_agent_usage(self, agent: AgentDefinition) -> dict:
        totals = agent.chats.aggregate(
            total_input_tokens=Sum("total_input_tokens"),
            total_output_tokens=Sum("total_output_tokens"),
        )
        return {
            "total_input_tokens": totals["total_input_tokens"] or 0,
            "total_output_tokens": totals["total_output_tokens"] or 0,
            "chat_count": agent.chats.count(),
        }
