from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import QuerySet, Sum

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.models import Agent
from baserow.core.utils import extract_allowed

from .exceptions import (
    AgentChatAlreadyRunning,
    AgentChatAwaitingApproval,
    AgentChatDoesNotExist,
    AgentDefinitionDoesNotExist,
    AgentToolApprovalDoesNotExist,
    AgentTriggerDoesNotExist,
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

    def pick_default_model(self, workspace) -> Optional[tuple[str, str]]:
        """The workspace's first enabled generative AI model, if any."""

        from baserow.core.generative_ai.registries import (
            generative_ai_model_type_registry,
        )

        enabled_models = generative_ai_model_type_registry.get_enabled_models_per_type(
            workspace
        )
        return next(
            (
                (ai_type, models[0])
                for ai_type, models in enabled_models.items()
                if models
            ),
            None,
        )

    def apply_setup(
        self,
        user: AbstractUser,
        application: AgentApplication,
        setup: dict,
        agent_identity_id: Optional[int] = None,
    ) -> None:
        """
        Applies the choices of the create wizard to a freshly created
        application: instructions, identity, workspace tool access, web
        search and a schedule. Runs inside the create transaction.

        :raises DRFValidationError: When the identity is not in the workspace.
        """

        from baserow.contrib.integrations.core.constants import (
            PERIODIC_INTERVAL_DAY,
            PERIODIC_INTERVAL_WEEK,
        )
        from baserow.core.agents.exceptions import AgentDoesNotExist
        from baserow.core.agents.handler import AgentHandler
        from baserow.core.agents.registries import agent_extension_registry
        from baserow.core.agents.service import AgentService

        from .tools.handler import AgentToolHandler
        from .tools.rules import ACCESS_EVERYTHING, ACCESS_READ_ONLY
        from .triggers.handler import AgentTriggerHandler

        workspace = application.workspace
        try:
            agent = self.get_main_agent(application)
        except AgentDefinitionDoesNotExist:
            agent = self.create_main_agent(
                application, name=application.name, description=application.description
            )

        agent_values = {}
        if setup.get("instructions"):
            agent_values["instructions"] = setup["instructions"]
        if not agent.ai_generative_ai_type:
            default_model = self.pick_default_model(workspace)
            if default_model is not None:
                agent_values["ai_generative_ai_type"] = default_model[0]
                agent_values["ai_generative_ai_model"] = default_model[1]
        if agent_values:
            self.update_agent(agent, **agent_values)

        if agent_identity_id is not None:
            try:
                identity = AgentHandler().get_agent(
                    agent_identity_id,
                    base_queryset=Agent.objects.filter(workspace_id=workspace.id),
                )
            except AgentDoesNotExist as exc:
                raise DRFValidationError(
                    detail=f"The agent with ID {agent_identity_id} does not "
                    "exist in the application's workspace.",
                    code="invalid_agent",
                ) from exc
            self.set_agent_identity(application, identity)
        elif setup.get("create_identity"):
            role_uid = (
                "BUILDER"
                if agent_extension_registry.role_uid_exists("BUILDER", workspace)
                else agent_extension_registry.get_default_role_uid(workspace)
            )
            identity = AgentService().create_agent(
                user, workspace, name=application.name, role_uid=role_uid
            )
            self.set_agent_identity(application, identity)

        permissions = setup.get("permissions")
        if permissions:
            AgentToolHandler().create_tool(
                user,
                agent,
                "workspace",
                config={
                    "access": (
                        ACCESS_READ_ONLY
                        if permissions == "read_only"
                        else ACCESS_EVERYTHING
                    ),
                    "require_write_approval": permissions != "free",
                    "tool_rules": {},
                },
            )

        if setup.get("web_search"):
            AgentToolHandler().create_tool(user, agent, "web_search")

        run_mode = setup.get("run_mode")
        if run_mode in ("daily", "weekly"):
            service_values = {
                "interval": PERIODIC_INTERVAL_DAY
                if run_mode == "daily"
                else PERIODIC_INTERVAL_WEEK,
                "hour": 9,
                "minute": 0,
            }
            if run_mode == "weekly":
                service_values["day_of_week"] = 0
            AgentTriggerHandler().create_trigger(
                user, application, "periodic", service_values=service_values
            )

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
            # The serialized model history can be hundreds of KB and is only
            # read by the runner, which loads the chat by id itself.
            return (
                queryset.select_related(
                    "agent__application__workspace",
                    "agent__application__agent_identity",
                )
                .defer("message_history")
                .get(uuid=chat_uuid)
            )
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
        return agent.chats.defer("message_history").order_by("-pinned", "-updated_on")

    def update_chat(
        self,
        chat: AgentChat,
        title: Optional[str] = None,
        pinned: Optional[bool] = None,
    ) -> AgentChat:
        from .realtime import broadcast_chat_updated

        values = {}
        if title is not None:
            values["title"] = title[: AgentChat.TITLE_MAX_LENGTH]
        if pinned is not None:
            values["pinned"] = pinned
        if not values:
            return chat
        # A queryset update skips `auto_now`, so renaming or pinning doesn't
        # bump `updated_on` and move the conversation to the top of the list.
        AgentChat.objects.filter(id=chat.id).update(**values)
        for field, value in values.items():
            setattr(chat, field, value)
        transaction.on_commit(lambda: broadcast_chat_updated(chat))
        return chat

    def run_trigger_once(self, user: AbstractUser, application) -> AgentChat:
        """
        Starts a conversation for the application's first enabled trigger as
        if it had fired, without event data. Lets the user try a triggered
        agent before the trigger fires (or while the agent is turned off).

        :raises AgentTriggerDoesNotExist: When the application has no enabled
            trigger.
        """

        from .triggers.registries import agent_trigger_type_registry

        trigger = (
            application.triggers.filter(enabled=True)
            .select_related("service")
            .order_by("id")
            .first()
        )
        if trigger is None:
            raise AgentTriggerDoesNotExist(
                f"The application {application.id} has no enabled trigger."
            )

        trigger_type = agent_trigger_type_registry.get_by_service_type(
            trigger.service.specific.get_type().type
        )
        agent = AgentApplicationHandler().get_main_agent(application)
        chat = self.create_triggered_chat(agent, trigger_type.type, user=user)
        message = self.create_message(
            chat,
            AgentChatMessage.Role.SYSTEM,
            trigger_type.get_opening_prompt(trigger, None),
        )
        self.start_chat_run(chat, message)
        return chat

    def get_last_run_on(self, application):
        from django.db.models import Max

        return AgentChat.objects.filter(
            agent__application=application,
            source=AgentChat.Source.TRIGGER,
            completed_on__isnull=False,
        ).aggregate(last_run_on=Max("completed_on"))["last_run_on"]

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
        :param decisions: Dicts with `id`, `approved`, optional `reason` and
            optional `dont_ask_again`, which lets the tool run without
            approval from now on.
        :raises AgentToolApprovalDoesNotExist: When a decision references an
            approval that doesn't exist or isn't pending anymore.
        """

        from django.utils import timezone

        from .chat_types import ApprovalDecidedMessage
        from .realtime import (
            broadcast_chat_event,
            broadcast_chat_updated,
            broadcast_configuration_updated,
        )
        from .tasks import resume_agent_chat
        from .tools.handler import AgentToolHandler

        decision_by_id = {decision["id"]: decision for decision in decisions}
        approvals = list(
            chat.tool_approvals.filter(
                id__in=decision_by_id.keys(),
                status=AgentChatToolApproval.Status.PENDING,
            )
        )
        missing = decision_by_id.keys() - {approval.id for approval in approvals}
        if missing:
            raise AgentToolApprovalDoesNotExist(
                f"The pending tool approval {min(missing)} does not exist."
            )

        now = timezone.now()
        dont_ask_again_names = set()
        for approval in approvals:
            decision = decision_by_id[approval.id]
            approval.status = (
                AgentChatToolApproval.Status.APPROVED
                if decision["approved"]
                else AgentChatToolApproval.Status.REJECTED
            )
            approval.reason = decision.get("reason") or ""
            approval.decided_by = user
            approval.decided_at = now
            approval.updated_on = now
            if decision["approved"] and decision.get("dont_ask_again"):
                dont_ask_again_names.add(approval.tool_name)
        AgentChatToolApproval.objects.bulk_update(
            approvals,
            ["status", "reason", "decided_by", "decided_at", "updated_on"],
        )
        decided = approvals
        for approval in approvals:
            broadcast_chat_event(
                chat,
                ApprovalDecidedMessage(
                    id=approval.id, status=approval.status, reason=approval.reason
                ).model_dump(),
            )
        configuration_changed = False
        if dont_ask_again_names:
            tool_handler = AgentToolHandler()
            tools = list(tool_handler.list_tools(chat.agent))
            for tool_name in dont_ask_again_names:
                if tool_handler.dont_ask_again(chat.agent, tool_name, tools=tools):
                    configuration_changed = True

        if configuration_changed:
            broadcast_configuration_updated(chat.agent.application)

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
        from django.db.models import Count

        totals = agent.chats.aggregate(
            total_input_tokens=Sum("total_input_tokens"),
            total_output_tokens=Sum("total_output_tokens"),
            chat_count=Count("id"),
        )
        return {
            "total_input_tokens": totals["total_input_tokens"] or 0,
            "total_output_tokens": totals["total_output_tokens"] or 0,
            "chat_count": totals["chat_count"],
        }
