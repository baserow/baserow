from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.agent.constants import AGENT_TRIGGER_DEFAULT_BATCH_SIZE
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentTrigger
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.types import AgentTriggerTypeOptions, AgentTriggerUpdated
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.services.registries import service_type_registry

from .handler import AgentTriggerHandler

WRITE_OPERATIONS = (
    UpdateApplicationOperationType.type,
    ReadAgentConfigurationOperationType.type,
)


class AgentTriggerService:
    """Trigger changes for a user allowed to make them on the trigger's Agent."""

    def __init__(self) -> None:
        self.handler = AgentTriggerHandler()
        self.agent_service = AgentService()

    def _get_authorized_trigger(
        self,
        user: AbstractUser,
        agent_id: int,
        trigger_id: int,
        *operations: str,
        for_update: bool = False,
    ) -> AgentTrigger:
        """
        Check each operation on a live Agent, then fetch one of its triggers.

        :param user: The user asking for the trigger.
        :param agent_id: The id of the Agent.
        :param trigger_id: The id of the trigger.
        :param operations: The operation type names the user needs on the Agent.
        :param for_update: Whether to lock the Agent and the trigger.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises PermissionException: When the user lacks any of the operations.
        :raises AgentTriggerDoesNotExist: When the Agent has no such trigger.
        :return: The trigger with its Agent and service.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *operations, for_update=for_update
        )
        queryset = AgentTrigger.objects.filter(agent=agent)
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        return self.handler.get_trigger(trigger_id, base_queryset=queryset)

    def list_triggers(self, user: AbstractUser, agent_id: int) -> list[AgentTrigger]:
        """
        Return the Agent's triggers to a user allowed to read its configuration.

        :param user: The user listing the triggers.
        :param agent_id: The id of the Agent.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not read the configuration.
        :return: The triggers, oldest first.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return list(self.handler.list_triggers(agent))

    def list_trigger_types(
        self, user: AbstractUser, agent_id: int
    ) -> list[AgentTriggerTypeOptions]:
        """
        Describe the trigger types the Agent may use, as its run identity sees
        them, to a user allowed to read its configuration.

        :param user: The user configuring triggers.
        :param agent_id: The id of the Agent.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not read the configuration.
        :return: One entry per available type, in registry order.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return self.handler.list_trigger_types(
            agent, AgentHandler().get_run_identity(agent)
        )

    def get_trigger(
        self, user: AbstractUser, agent_id: int, trigger_id: int
    ) -> AgentTrigger:
        """
        Return one trigger to a user allowed to read its Agent's configuration.

        :param user: The user reading the trigger.
        :param agent_id: The id of the Agent the trigger belongs to.
        :param trigger_id: The id of the trigger.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises AgentTriggerDoesNotExist: When the Agent has no such trigger or it
            is trashed.
        :raises PermissionException: When the user may not read the configuration.
        :return: The trigger with its Agent and service.
        """

        return self._get_authorized_trigger(
            user, agent_id, trigger_id, ReadAgentConfigurationOperationType.type
        )

    @transaction.atomic
    def create_trigger(
        self,
        user: AbstractUser,
        agent_id: int,
        service_type_name: str,
        message: BaserowFormulaObject | str = "",
        enabled: bool = True,
        service_values: dict | None = None,
        on_overlap: str | None = None,
        batch_size: int = AGENT_TRIGGER_DEFAULT_BATCH_SIZE,
        name: str = "",
    ) -> AgentTrigger:
        """
        Add a trigger of an available type to the Agent, for a user who may update
        and read its configuration.

        :param user: The user adding the trigger.
        :param agent_id: The id of the Agent.
        :param service_type_name: The service type of the trigger.
        :param message: The formula whose text opens each conversation it starts.
        :param enabled: Whether the trigger starts conversations right away.
        :param service_values: Initial values of the service, by field name, or
            None to leave it unconfigured.
        :param on_overlap: What a firing does while a reply of the trigger is still
            going, or None for the type's default.
        :param batch_size: How many records of a list payload one conversation
            receives.
        :param name: The trigger's name, or blank for the type's default.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not update the Agent or read
            its configuration.
        :raises AgentTriggerTypeNotAvailable: When the type isn't one the Agent's
            configuration offers.
        :raises ServiceMisconfigured: When the service values are invalid.
        :raises AgentTriggerNoAccess: When the Agent's run identity can't read what
            the trigger watches; nothing is saved.
        :return: The created trigger, armed when its service is configured.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *WRITE_OPERATIONS, for_update=True
        )
        self.handler.check_type_available(agent, service_type_name)
        service_type = service_type_registry.get(service_type_name)
        prepared_service_values = service_type.prepare_values(
            service_values or {}, user
        )
        trigger = self.handler.create_trigger(
            agent,
            service_type,
            prepared_service_values,
            message=message,
            enabled=enabled,
            on_overlap=on_overlap,
            batch_size=batch_size,
            name=name,
        )
        self.handler.check_identity_can_read(
            trigger, AgentHandler().get_run_identity(agent)
        )
        return trigger

    @transaction.atomic
    def update_trigger(
        self,
        user: AbstractUser,
        agent_id: int,
        trigger_id: int,
        enabled: bool | None = None,
        message: BaserowFormulaObject | str | None = None,
        service_values: dict | None = None,
        on_overlap: str | None = None,
        batch_size: int | None = None,
        name: str | None = None,
        service_type_name: str | None = None,
    ) -> AgentTriggerUpdated:
        """
        Change a trigger's name, switch, message, overlap rule, batch size, type or
        service values, for a user who may update and read its Agent's
        configuration. Switching it off cancels its queued replies. Another type
        replaces the service with a new one, as on create. A new service or a
        switch-on must be readable by the Agent's run identity.

        :param user: The user updating the trigger.
        :param agent_id: The id of the Agent the trigger belongs to.
        :param trigger_id: The id of the trigger.
        :param enabled: The new switch state, or None to keep it.
        :param message: The new message formula, or None to keep it.
        :param service_values: The service values to set, by field name, or None.
        :param on_overlap: The new overlap rule, or None to keep it.
        :param batch_size: The new batch size, or None to keep it.
        :param name: The new name, blank for the type's default, or None to keep
            it.
        :param service_type_name: The service type the trigger should have, whose
            service then starts from `service_values`, or None to keep its own.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises AgentTriggerDoesNotExist: When the Agent has no such trigger or it
            is trashed.
        :raises PermissionException: When the user may not update the Agent or read
            its configuration.
        :raises AgentTriggerTypeNotAvailable: When it would change to, switch on or
            reschedule a type the Agent's configuration doesn't offer.
        :raises ServiceMisconfigured: When the service values are invalid.
        :raises AgentTriggerNoAccess: When a new service or a switch-on isn't
            readable by the Agent's run identity; nothing is saved.
        :return: The updated trigger and the names of the parts that changed.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        # Locked so two debounced saves of one card can't lose each other's fields.
        trigger = self._get_authorized_trigger(
            user, agent_id, trigger_id, *WRITE_OPERATIONS, for_update=True
        )
        service_type = trigger.service.get_type()
        changes_type = service_type_name not in (None, service_type.type)
        prepared_service_values = None
        if changes_type:
            self.handler.check_type_available(trigger.agent, service_type_name)
            service_type = service_type_registry.get(service_type_name)
            prepared_service_values = service_type.prepare_values(
                service_values or {}, user, None
            )
        elif service_values is not None:
            prepared_service_values = service_type.prepare_values(
                service_values, user, trigger.service.specific
            )
        updated = self.handler.update_trigger(
            trigger,
            enabled=enabled,
            message=message,
            prepared_service_values=prepared_service_values,
            on_overlap=on_overlap,
            batch_size=batch_size,
            name=name,
            service_type=service_type if changes_type else None,
        )
        changed = updated.changed_fields
        if "service" in changed or ("enabled" in changed and trigger.enabled):
            self.handler.check_identity_can_read(
                trigger, AgentHandler().get_run_identity(trigger.agent)
            )
        return updated

    @transaction.atomic
    def delete_trigger(
        self, user: AbstractUser, agent_id: int, trigger_id: int
    ) -> AgentTrigger:
        """
        Move a trigger to the trash, for a user who may update and read its Agent's
        configuration.

        :param user: The user deleting the trigger.
        :param agent_id: The id of the Agent the trigger belongs to.
        :param trigger_id: The id of the trigger.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises AgentTriggerDoesNotExist: When the Agent has no such trigger or it
            is trashed already.
        :raises PermissionException: When the user may not update the Agent or read
            its configuration.
        :return: The trashed trigger.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        trigger = self._get_authorized_trigger(
            user, agent_id, trigger_id, *WRITE_OPERATIONS, for_update=True
        )
        self.handler.delete_trigger(user, trigger)
        return trigger
