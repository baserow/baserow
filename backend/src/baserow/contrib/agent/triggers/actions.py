from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.contrib.agent.models import AgentTrigger
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.formula.types import BaserowFormulaObject

from .service import AgentTriggerService


class CreateAgentTriggerActionType(ActionType):
    """Adds a trigger to an Agent; not undoable, like the rest of its configuration."""

    type = "create_agent_trigger"
    description = ActionTypeDescription(
        _("Create agent trigger"),
        _(
            "Trigger (%(trigger_id)s) of type %(trigger_type)s created in agent "
            "(%(agent_id)s)."
        ),
    )
    analytics_params = ["agent_id", "trigger_type"]

    @dataclass
    class Params:
        agent_id: int
        trigger_id: int
        trigger_type: str

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        service_type_name: str,
        message: BaserowFormulaObject | str = "",
        enabled: bool = True,
        service: dict | None = None,
        on_overlap: str = AgentTrigger.OnOverlap.SKIP,
        name: str = "",
    ) -> AgentTrigger:
        """
        Add a trigger to an Agent and audit its type.

        :param user: The user adding the trigger.
        :param agent_id: The id of the Agent.
        :param service_type_name: The service type of the trigger.
        :param message: The formula whose text opens each conversation it starts.
        :param enabled: Whether the trigger starts conversations right away.
        :param service: Initial values of the service, by field name, or None.
        :param on_overlap: What a firing does while a reply of the trigger is still
            going.
        :param name: The trigger's name, or blank for the type's default.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not update the Agent or read
            its configuration.
        :raises AgentTriggerTypeNotAvailable: When the Agent doesn't offer the type.
        :raises ServiceMisconfigured: When the service values are invalid.
        :return: The created trigger.
        """

        trigger = AgentTriggerService().create_trigger(
            user,
            agent_id,
            service_type_name,
            message=message,
            enabled=enabled,
            service_values=service,
            on_overlap=on_overlap,
            name=name,
        )
        cls.register_action(
            user,
            cls.Params(agent_id, trigger.id, service_type_name),
            cls.scope(agent_id),
            trigger.agent.workspace,
        )
        return trigger

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        """
        Scope the action to the Agent whose triggers it changes.

        :param agent_id: The id of the Agent.
        :return: The application scope of the Agent.
        """

        return ApplicationActionScopeType.value(agent_id)


class UpdateAgentTriggerActionType(ActionType):
    """Changes a trigger's switch, message, overlap rule or service; not undoable."""

    type = "update_agent_trigger"
    description = ActionTypeDescription(
        _("Update agent trigger"),
        _("Trigger (%(trigger_id)s) updated in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "trigger_type", "changed_fields"]

    @dataclass
    class Params:
        agent_id: int
        trigger_id: int
        trigger_type: str
        changed_fields: list[str]

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        trigger_id: int,
        enabled: bool | None = None,
        message: BaserowFormulaObject | str | None = None,
        service: dict | None = None,
        on_overlap: str | None = None,
        name: str | None = None,
    ) -> AgentTrigger:
        """
        Change a trigger and audit which of its parts changed, never their values:
        the message and service values are configuration. An update that changes
        nothing isn't audited.

        :param user: The user updating the trigger.
        :param agent_id: The id of the Agent the trigger belongs to.
        :param trigger_id: The id of the trigger.
        :param enabled: The new switch state, or None to keep it.
        :param message: The new message formula, or None to keep it.
        :param service: The service values to set, by field name, or None.
        :param on_overlap: The new overlap rule, or None to keep it.
        :param name: The new name, blank for the type's default, or None to keep
            it.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not update the Agent or read
            its configuration.
        :raises AgentTriggerDoesNotExist: When the Agent has no such trigger.
        :raises AgentTriggerTypeNotAvailable: When it would switch on or reschedule
            a trigger of a type the Agent doesn't offer.
        :raises ServiceMisconfigured: When the service values are invalid.
        :return: The updated trigger.
        """

        updated = AgentTriggerService().update_trigger(
            user,
            agent_id,
            trigger_id,
            enabled=enabled,
            message=message,
            service_values=service,
            on_overlap=on_overlap,
            name=name,
        )
        trigger = updated.trigger
        if updated.changed_fields:
            cls.register_action(
                user,
                cls.Params(
                    trigger.agent_id,
                    trigger.id,
                    trigger.service.get_type().type,
                    updated.changed_fields,
                ),
                cls.scope(trigger.agent_id),
                trigger.agent.workspace,
            )
        return trigger

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        """
        Scope the action to the Agent whose triggers it changes.

        :param agent_id: The id of the Agent.
        :return: The application scope of the Agent.
        """

        return ApplicationActionScopeType.value(agent_id)


class DeleteAgentTriggerActionType(ActionType):
    """Trashes a trigger with its service; restored from the trash."""

    type = "delete_agent_trigger"
    description = ActionTypeDescription(
        _("Delete agent trigger"),
        _("Trigger (%(trigger_id)s) deleted in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "trigger_type"]

    @dataclass
    class Params:
        agent_id: int
        trigger_id: int
        trigger_type: str

    @classmethod
    @transaction.atomic
    def do(cls, user: AbstractUser, agent_id: int, trigger_id: int) -> None:
        """
        Move a trigger to the trash and audit its type.

        :param user: The user deleting the trigger.
        :param agent_id: The id of the Agent the trigger belongs to.
        :param trigger_id: The id of the trigger.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not update the Agent or read
            its configuration.
        :raises AgentTriggerDoesNotExist: When the Agent has no such trigger.
        """

        trigger = AgentTriggerService().delete_trigger(user, agent_id, trigger_id)
        cls.register_action(
            user,
            cls.Params(trigger.agent_id, trigger.id, trigger.service.get_type().type),
            cls.scope(trigger.agent_id),
            trigger.agent.workspace,
        )

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        """
        Scope the action to the Agent whose triggers it changes.

        :param agent_id: The id of the Agent.
        :return: The application scope of the Agent.
        """

        return ApplicationActionScopeType.value(agent_id)
