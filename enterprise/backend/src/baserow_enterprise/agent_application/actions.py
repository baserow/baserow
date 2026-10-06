from dataclasses import dataclass, field
from typing import Any, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionType,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.trash.handler import TrashHandler

from .channels.handler import AgentChatChannelHandler
from .channels.registries import agent_chat_channel_type_registry
from .handler import AgentChatHandler
from .models import (
    AgentChat,
    AgentChatChannel,
    AgentDefinition,
    AgentTool,
    AgentTrigger,
)
from .service import AgentApplicationService
from .tools.handler import AgentToolHandler
from .tools.registries import agent_tool_type_registry
from .trash_types import (
    AgentChatChannelTrashableItemType,
    AgentToolTrashableItemType,
    AgentTriggerTrashableItemType,
)
from .triggers.handler import AgentTriggerHandler

AGENT_ACTION_CONTEXT = _('in application "%(application_name)s" (%(application_id)s).')


def _without_deleted_skills(values: dict) -> dict:
    """
    A skill deleted since the action was recorded cannot be linked again; the
    rest of the undo must still apply instead of failing on it.
    """

    if "skills" not in values:
        return values
    from baserow.core.skills.models import WorkspaceSkill

    skill_ids = [entry["skill_id"] for entry in values["skills"]]
    existing = set(
        WorkspaceSkill.objects.filter(id__in=skill_ids).values_list("id", flat=True)
    )
    return {
        **values,
        "skills": [e for e in values["skills"] if e["skill_id"] in existing],
    }


class UpdateAgentDefinitionActionType(UndoableActionType):
    type = "update_agent_definition"
    description = ActionTypeDescription(
        _("Update agent"),
        _('Agent "%(agent_name)s" (%(agent_id)s) updated'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        agent_id: int
        agent_name: str
        original_values: dict
        new_values: dict

    @classmethod
    def _skills(cls, agent: AgentDefinition) -> list[dict]:
        return [
            {"skill_id": link.skill_id, "mode": link.mode}
            for link in agent.agent_skills.order_by("order", "id")
        ]

    @classmethod
    def _values(cls, agent: AgentDefinition, keys) -> dict:
        service = AgentApplicationService()
        values = {
            key: getattr(agent, key)
            for key in keys
            if key in service.handler.allowed_agent_fields
        }
        if "skills" in keys:
            values["skills"] = cls._skills(agent)
        return values

    @classmethod
    def do(cls, user: AbstractUser, agent_id: int, new_values: dict) -> AgentDefinition:
        service = AgentApplicationService()
        agent = service.get_agent(user, agent_id)
        original_values = cls._values(agent, new_values.keys())

        agent = service.update_agent(user, agent_id, **new_values)
        applied_values = cls._values(agent, original_values.keys())

        # A request that changes nothing must not use up an undo step.
        if applied_values == original_values:
            return agent

        cls.register_action(
            user=user,
            params=cls.Params(
                agent.application_id,
                agent.application.name,
                agent.id,
                agent.name,
                original_values,
                applied_values,
            ),
            scope=cls.scope(agent.application_id),
            workspace=agent.application.workspace,
        )
        return agent

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        AgentApplicationService().update_agent(
            user, params.agent_id, **_without_deleted_skills(params.original_values)
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        AgentApplicationService().update_agent(
            user, params.agent_id, **_without_deleted_skills(params.new_values)
        )


def _service_values(service) -> Optional[dict]:
    if service is None:
        return None
    service = service.specific
    return service.get_type().export_prepared_values(service)


def _restore(user: AbstractUser, trash_type: str, item_id: int) -> None:
    TrashHandler.restore_item(user, trash_type, item_id)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class CreateAgentToolActionType(UndoableActionType):
    type = "create_agent_tool"
    description = ActionTypeDescription(
        _("Create agent tool"),
        _('Tool "%(tool_name)s" (%(tool_id)s) of type %(tool_type)s created'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        tool_id: int
        tool_type: str
        tool_name: str
        service_type: Optional[str]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        agent: AgentDefinition,
        tool_type_str: str,
        name: str = "",
        config: Optional[dict] = None,
        service_type_str: Optional[str] = None,
        service_values: Optional[dict] = None,
    ) -> AgentTool:
        tool = AgentToolHandler().create_tool(
            user,
            agent,
            tool_type_str,
            name=name,
            config=config,
            service_type_str=service_type_str,
            service_values=service_values,
        )
        application = agent.application
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                tool.id,
                tool.type,
                tool.name,
                service_type_str,
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )
        return tool

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        tool = AgentTool.objects.select_related("agent__application").get(
            id=params.tool_id
        )
        AgentToolHandler().trash_tool(user, tool)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        _restore(user, AgentToolTrashableItemType.type, params.tool_id)


class UpdateAgentToolActionType(UndoableActionType):
    type = "update_agent_tool"
    description = ActionTypeDescription(
        _("Update agent tool"),
        _('Tool "%(tool_name)s" (%(tool_id)s) updated'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        tool_id: int
        tool_name: str
        original_values: dict
        new_values: dict

    @classmethod
    def _values(cls, tool: AgentTool, with_service: bool) -> dict:
        values: dict[str, Any] = {
            "name": tool.name,
            # Credentials stay out of the action params (undo history, audit
            # log); the handler keeps the stored ones when a config omits them.
            "config": agent_tool_type_registry.get(tool.type).get_undoable_config(tool),
            "identity_id": tool.identity_id,
        }
        if with_service and tool.service_id is not None:
            values["service"] = _service_values(tool.service)
        return values

    @classmethod
    def _apply(cls, user: AbstractUser, tool_id: int, values: dict) -> AgentTool:
        tool = AgentToolHandler().get_tool(tool_id)
        return AgentToolHandler().update_tool(
            user,
            tool,
            name=values.get("name"),
            config=values.get("config"),
            service_values=values.get("service"),
            identity_id=values.get("identity_id"),
        )

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        tool: AgentTool,
        name: Optional[str] = None,
        config: Optional[dict] = None,
        service_values: Optional[dict] = None,
        **kwargs,
    ) -> AgentTool:
        with_service = service_values is not None
        original_values = cls._values(tool, with_service)
        tool = AgentToolHandler().update_tool(
            user,
            tool,
            name=name,
            config=config,
            service_values=service_values,
            **kwargs,
        )
        new_values = cls._values(tool, with_service)
        application = tool.agent.application
        if new_values != original_values:
            cls.register_action(
                user=user,
                params=cls.Params(
                    application.id,
                    application.name,
                    tool.id,
                    tool.name,
                    original_values,
                    new_values,
                ),
                scope=cls.scope(application.id),
                workspace=application.workspace,
            )
        return tool

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._apply(user, params.tool_id, params.original_values)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._apply(user, params.tool_id, params.new_values)


class DeleteAgentToolActionType(UndoableActionType):
    type = "delete_agent_tool"
    description = ActionTypeDescription(
        _("Delete agent tool"),
        _('Tool "%(tool_name)s" (%(tool_id)s) deleted'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        tool_id: int
        tool_name: str

    @classmethod
    def do(cls, user: AbstractUser, tool: AgentTool) -> None:
        application = tool.agent.application
        AgentToolHandler().trash_tool(user, tool)
        cls.register_action(
            user=user,
            params=cls.Params(application.id, application.name, tool.id, tool.name),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        _restore(user, AgentToolTrashableItemType.type, params.tool_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        tool = AgentTool.objects.select_related("agent__application").get(
            id=params.tool_id
        )
        AgentToolHandler().trash_tool(user, tool)


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------


class CreateAgentTriggerActionType(UndoableActionType):
    type = "create_agent_trigger"
    description = ActionTypeDescription(
        _("Create agent trigger"),
        _("Trigger (%(trigger_id)s) of type %(service_type)s created"),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        trigger_id: int
        service_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        application,
        service_type_str: str,
        service_values: Optional[dict] = None,
        enabled: bool = True,
        config: Optional[dict] = None,
    ) -> AgentTrigger:
        trigger = AgentTriggerHandler().create_trigger(
            user,
            application,
            service_type_str,
            service_values=service_values,
            enabled=enabled,
            config=config,
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id, application.name, trigger.id, service_type_str
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )
        return trigger

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        trigger = AgentTrigger.objects.select_related("application").get(
            id=params.trigger_id
        )
        AgentTriggerHandler().trash_trigger(user, trigger)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        _restore(user, AgentTriggerTrashableItemType.type, params.trigger_id)


class UpdateAgentTriggerActionType(UndoableActionType):
    type = "update_agent_trigger"
    description = ActionTypeDescription(
        _("Update agent trigger"),
        _("Trigger (%(trigger_id)s) updated"),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        trigger_id: int
        original_values: dict
        new_values: dict

    @classmethod
    def _values(cls, trigger: AgentTrigger, with_service: bool) -> dict:
        values: dict[str, Any] = {
            "enabled": trigger.enabled,
            "config": trigger.config or {},
        }
        if with_service:
            values["service"] = _service_values(trigger.service)
        return values

    @classmethod
    def _apply(cls, user: AbstractUser, trigger_id: int, values: dict) -> AgentTrigger:
        trigger = AgentTriggerHandler().get_trigger(trigger_id)
        return AgentTriggerHandler().update_trigger(
            user,
            trigger,
            service_values=values.get("service"),
            enabled=values.get("enabled"),
            config=values.get("config"),
        )

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        trigger: AgentTrigger,
        service_values: Optional[dict] = None,
        enabled: Optional[bool] = None,
        config: Optional[dict] = None,
    ) -> AgentTrigger:
        with_service = service_values is not None
        original_values = cls._values(trigger, with_service)
        trigger = AgentTriggerHandler().update_trigger(
            user, trigger, service_values=service_values, enabled=enabled, config=config
        )
        new_values = cls._values(trigger, with_service)
        application = trigger.application
        if new_values != original_values:
            cls.register_action(
                user=user,
                params=cls.Params(
                    application.id,
                    application.name,
                    trigger.id,
                    original_values,
                    new_values,
                ),
                scope=cls.scope(application.id),
                workspace=application.workspace,
            )
        return trigger

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._apply(user, params.trigger_id, params.original_values)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._apply(user, params.trigger_id, params.new_values)


class DeleteAgentTriggerActionType(UndoableActionType):
    type = "delete_agent_trigger"
    description = ActionTypeDescription(
        _("Delete agent trigger"),
        _("Trigger (%(trigger_id)s) deleted"),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        trigger_id: int

    @classmethod
    def do(cls, user: AbstractUser, trigger: AgentTrigger) -> None:
        application = trigger.application
        AgentTriggerHandler().trash_trigger(user, trigger)
        cls.register_action(
            user=user,
            params=cls.Params(application.id, application.name, trigger.id),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        _restore(user, AgentTriggerTrashableItemType.type, params.trigger_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        trigger = AgentTrigger.objects.select_related("application").get(
            id=params.trigger_id
        )
        AgentTriggerHandler().trash_trigger(user, trigger)


# ---------------------------------------------------------------------------
# Chat channels
# ---------------------------------------------------------------------------


class CreateAgentChatChannelActionType(UndoableActionType):
    type = "create_agent_chat_channel"
    description = ActionTypeDescription(
        _("Create agent chat channel"),
        _(
            'Chat channel "%(channel_name)s" (%(channel_id)s) of type %(channel_type)s created'
        ),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        channel_id: int
        channel_type: str
        channel_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        application,
        channel_type_str: str,
        name: str = "",
        config: Optional[dict] = None,
        enabled: bool = True,
    ) -> AgentChatChannel:
        channel = AgentChatChannelHandler().create_channel(
            application,
            channel_type_str,
            name=name,
            config=config,
            enabled=enabled,
            user=user,
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                channel.id,
                channel.type,
                channel.name,
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )
        return channel

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        channel = AgentChatChannel.objects.select_related("application").get(
            id=params.channel_id
        )
        AgentChatChannelHandler().trash_channel(user, channel)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        _restore(user, AgentChatChannelTrashableItemType.type, params.channel_id)


class UpdateAgentChatChannelActionType(UndoableActionType):
    """
    Secrets (tokens, password hashes, public links) never enter the undo
    history: only the non-secret config keys are stored, and re-applying
    them keeps whatever secret is stored at that time.
    """

    type = "update_agent_chat_channel"
    description = ActionTypeDescription(
        _("Update agent chat channel"),
        _('Chat channel "%(channel_name)s" (%(channel_id)s) updated'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        channel_id: int
        channel_name: str
        original_values: dict
        new_values: dict

    @classmethod
    def _values(cls, channel: AgentChatChannel) -> dict:
        channel_type = agent_chat_channel_type_registry.get(channel.type)
        return {
            "name": channel.name,
            "enabled": channel.enabled,
            "config": channel_type.get_undoable_config(channel),
        }

    @classmethod
    def _apply(cls, user, channel_id: int, values: dict) -> AgentChatChannel:
        channel = AgentChatChannelHandler().get_channel(channel_id)
        return AgentChatChannelHandler().update_channel(
            channel,
            name=values.get("name"),
            config=values.get("config"),
            enabled=values.get("enabled"),
            user=user,
        )

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        channel: AgentChatChannel,
        name: Optional[str] = None,
        config: Optional[dict] = None,
        enabled: Optional[bool] = None,
    ) -> AgentChatChannel:
        original_values = cls._values(channel)
        channel = AgentChatChannelHandler().update_channel(
            channel, name=name, config=config, enabled=enabled, user=user
        )
        new_values = cls._values(channel)
        application = channel.application
        if new_values != original_values:
            cls.register_action(
                user=user,
                params=cls.Params(
                    application.id,
                    application.name,
                    channel.id,
                    channel.name,
                    original_values,
                    new_values,
                ),
                scope=cls.scope(application.id),
                workspace=application.workspace,
            )
        return channel

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._apply(user, params.channel_id, params.original_values)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._apply(user, params.channel_id, params.new_values)


class DeleteAgentChatChannelActionType(UndoableActionType):
    type = "delete_agent_chat_channel"
    description = ActionTypeDescription(
        _("Delete agent chat channel"),
        _('Chat channel "%(channel_name)s" (%(channel_id)s) deleted'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        channel_id: int
        channel_name: str

    @classmethod
    def do(cls, user: AbstractUser, channel: AgentChatChannel) -> None:
        application = channel.application
        AgentChatChannelHandler().trash_channel(user, channel)
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id, application.name, channel.id, channel.name
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        _restore(user, AgentChatChannelTrashableItemType.type, params.channel_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        channel = AgentChatChannel.objects.select_related("application").get(
            id=params.channel_id
        )
        AgentChatChannelHandler().trash_channel(user, channel)


class RotateAgentChatChannelLinkActionType(ActionType):
    """Audited, deliberately not undoable: the old link must stay dead."""

    type = "rotate_agent_chat_channel_link"
    description = ActionTypeDescription(
        _("Rotate agent chat channel link"),
        _('Public link of chat channel "%(channel_name)s" (%(channel_id)s) renewed'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        channel_id: int
        channel_name: str

    @classmethod
    def do(cls, user: AbstractUser, channel: AgentChatChannel) -> AgentChatChannel:
        from .channels.web import WebAgentChatChannelType
        from .signals import agent_chat_channel_updated

        application = channel.application
        channel = WebAgentChatChannelType().rotate_slug(channel)
        agent_chat_channel_updated.send(cls, channel=channel, user=user)
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id, application.name, channel.id, channel.name
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )
        return channel

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)


# ---------------------------------------------------------------------------
# Conversations and approvals: audited, never undoable (runs have side effects)
# ---------------------------------------------------------------------------


class _ChatActionType(ActionType):
    @dataclass
    class Params:
        application_id: int
        application_name: str
        chat_id: int
        chat_uuid: str
        chat_title: str

    @classmethod
    def _params(cls, chat: AgentChat, **extra):
        application = chat.agent.application
        return cls.Params(
            application.id,
            application.name,
            chat.id,
            str(chat.uuid),
            chat.title or "",
            **extra,
        )

    @classmethod
    def _register(cls, user: AbstractUser, chat: AgentChat, **extra) -> None:
        application = chat.agent.application
        cls.register_action(
            user=user,
            params=cls._params(chat, **extra),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)


class DecideAgentToolApprovalActionType(_ChatActionType):
    type = "decide_agent_tool_approval"
    description = ActionTypeDescription(
        _("Decide agent tool approval"),
        _(
            'Tool call "%(tool_name)s" (%(approval_id)s) in conversation '
            '"%(chat_title)s" %(decision)s'
        ),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params(_ChatActionType.Params):
        approval_id: int = 0
        tool_name: str = ""
        approved: bool = False
        decision: str = ""
        reason: str = ""
        dont_ask_again: bool = False

    @classmethod
    def do(cls, user: AbstractUser, chat: AgentChat, decisions: list[dict]) -> list:
        decided = AgentChatHandler().decide_tool_approvals(chat, user, decisions)
        by_id = {decision["id"]: decision for decision in decisions}
        for approval in decided:
            decision = by_id.get(approval.id, {})
            cls._register(
                user,
                chat,
                approval_id=approval.id,
                tool_name=approval.tool_name,
                approved=bool(decision.get("approved")),
                decision="approved" if decision.get("approved") else "rejected",
                reason=decision.get("reason") or "",
                dont_ask_again=bool(decision.get("dont_ask_again")),
            )
        return decided


class CancelAgentChatRunActionType(_ChatActionType):
    type = "cancel_agent_chat_run"
    description = ActionTypeDescription(
        _("Cancel agent run"),
        _('Run of conversation "%(chat_title)s" (%(chat_id)s) cancelled'),
        AGENT_ACTION_CONTEXT,
    )

    @classmethod
    def do(cls, user: AbstractUser, chat: AgentChat) -> None:
        AgentChatHandler().cancel_chat_run(chat, user)
        cls._register(user, chat)


class RetryAgentChatRunActionType(_ChatActionType):
    type = "retry_agent_chat_run"
    description = ActionTypeDescription(
        _("Retry agent run"),
        _('Run of conversation "%(chat_title)s" (%(chat_id)s) retried'),
        AGENT_ACTION_CONTEXT,
    )

    @classmethod
    def do(cls, user: AbstractUser, chat: AgentChat):
        message = AgentChatHandler().retry_chat_run(chat)
        cls._register(user, chat)
        return message


class RunAgentOnceActionType(_ChatActionType):
    type = "run_agent_once"
    description = ActionTypeDescription(
        _("Run agent once"),
        _('Agent run once manually, conversation "%(chat_title)s" (%(chat_id)s)'),
        AGENT_ACTION_CONTEXT,
    )

    @classmethod
    def do(cls, user: AbstractUser, application) -> AgentChat:
        chat = AgentChatHandler().run_trigger_once(user, application)
        cls._register(user, chat)
        return chat


class DeleteAgentChatActionType(_ChatActionType):
    type = "delete_agent_chat"
    description = ActionTypeDescription(
        _("Delete agent conversation"),
        _('Conversation "%(chat_title)s" (%(chat_id)s) deleted'),
        AGENT_ACTION_CONTEXT,
    )

    @classmethod
    def do(cls, user: AbstractUser, chat: AgentChat) -> None:
        params = cls._params(chat)
        application = chat.agent.application
        AgentChatHandler().delete_chat(chat)
        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )


class UpdateAgentChatActionType(_ChatActionType):
    type = "update_agent_chat"
    description = ActionTypeDescription(
        _("Update agent conversation"),
        _('Conversation "%(chat_title)s" (%(chat_id)s) renamed or pinned'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params(_ChatActionType.Params):
        values: dict = field(default_factory=dict)

    @classmethod
    def do(cls, user: AbstractUser, chat: AgentChat, **values) -> AgentChat:
        chat = AgentChatHandler().update_chat(chat, **values)
        cls._register(user, chat, values=values)
        return chat


# ---------------------------------------------------------------------------
# What the agent itself does: audited with the agent (or the acting user) as
# actor, never undoable.
# ---------------------------------------------------------------------------


class DispatchAgentToolActionType(ActionType):
    """
    Local Baserow services run through row actions that are audited on their
    own; every other action service (email, HTTP, Slack, ...) only leaves a
    trace through this action.
    """

    type = "dispatch_agent_tool"
    description = ActionTypeDescription(
        _("Agent ran a tool"),
        _(
            'Tool "%(tool_name)s" (%(tool_id)s, %(service_type)s) ran in '
            'conversation "%(chat_title)s"'
        ),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        tool_id: int
        tool_name: str
        service_type: str
        chat_id: int
        chat_uuid: str
        chat_title: str

    @classmethod
    def do(cls, actor, tool: AgentTool, service_type: str, chat: AgentChat) -> None:
        application = chat.agent.application
        cls.register_action(
            user=actor,
            params=cls.Params(
                application.id,
                application.name,
                tool.id,
                tool.name or service_type,
                service_type,
                chat.id,
                str(chat.uuid),
                chat.title or "",
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)


class UpdateAgentMemoryActionType(ActionType):
    type = "update_agent_memory"
    description = ActionTypeDescription(
        _("Agent updated its memory"),
        _('Memory of agent "%(agent_name)s" (%(agent_id)s) %(mode)s'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        agent_id: int
        agent_name: str
        mode: str
        memory_length: int

    @classmethod
    def do(cls, actor, agent: AgentDefinition, mode: str) -> None:
        application = agent.application
        cls.register_action(
            user=actor,
            params=cls.Params(
                application.id,
                application.name,
                agent.id,
                agent.name,
                mode,
                len(agent.memory or ""),
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)
