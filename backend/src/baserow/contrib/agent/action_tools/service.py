from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.agent.models import AgentAction, AgentApplication
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.service import AgentService
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow.core.integrations.operations import ReadIntegrationOperationType
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType, service_type_registry

from .handler import AgentActionHandler, AgentActionUpdated
from .inputs import validate_action_name, validate_inputs
from .registries import agent_action_type_registry
from .signals import agent_action_created, agent_action_deleted, agent_action_updated

WRITE_OPERATIONS = (
    UpdateApplicationOperationType.type,
    ReadAgentConfigurationOperationType.type,
)


class AgentActionService:
    """Configuration changes for users who may edit the owning Agent."""

    def __init__(self) -> None:
        self.handler = AgentActionHandler()
        self.agent_service = AgentService()

    def _get_authorized_action(
        self,
        user: AbstractUser,
        agent_id: int,
        action_id: int,
        *operations: str,
        for_update: bool = False,
    ) -> AgentAction:
        """
        :param user: The user asking.
        :param agent_id: The id of the Agent.
        :param action_id: The id of one of its actions.
        :param operations: The operation type names the user needs on the Agent.
        :param for_update: Whether to lock the Agent and the action.
        :return: The action.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *operations, for_update=for_update
        )
        queryset = AgentAction.objects.filter(agent=agent)
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        return self.handler.get_action(action_id, queryset)

    def list_actions(self, user: AbstractUser, agent_id: int) -> list[AgentAction]:
        """
        :param user: The user asking, who must be able to read the configuration.
        :param agent_id: The id of the Agent.
        :return: The Agent's actions, oldest first.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return self.handler.list_actions(agent)

    def get_action(
        self, user: AbstractUser, agent_id: int, action_id: int
    ) -> AgentAction:
        """
        :param user: The user asking, who must be able to read the configuration.
        :param agent_id: The id of the Agent.
        :param action_id: The id of one of its actions.
        :return: The action.
        """

        return self._get_authorized_action(
            user, agent_id, action_id, ReadAgentConfigurationOperationType.type
        )

    def _prepare_service_values(
        self,
        user: AbstractUser,
        agent: AgentApplication,
        service_type: ServiceType,
        values: dict[str, Any],
        instance: Service | None = None,
    ) -> dict[str, Any]:
        """
        :param user: The user saving the action.
        :param agent: The Agent.
        :param service_type: The type of the action's service.
        :param values: The service values to save.
        :param instance: The existing service, when it is updated.
        :return: The values prepared by the service type, whose integration
            belongs to the Agent and is readable by the user.
        """

        prepared = service_type.prepare_values(dict(values), user, instance)
        integration = prepared.get(
            "integration", getattr(instance, "integration", None)
        )
        # An integration's credentials stay within the application that owns it.
        service_type.check_integration(agent, {"integration": integration})
        if integration is not None:
            CoreHandler().check_permissions(
                user,
                ReadIntegrationOperationType.type,
                workspace=agent.workspace,
                context=integration,
            )
        return prepared

    @transaction.atomic
    def create_action(
        self,
        user: AbstractUser,
        agent_id: int,
        service_type_name: str,
        service_values: dict[str, Any] | None = None,
        **values: Any,
    ) -> AgentAction:
        """
        Add an action of a type to the Agent, starting from the type's defaults.

        :param user: The user adding the action, who must be able to edit the
            Agent.
        :param agent_id: The id of the Agent.
        :param service_type_name: The service type the action is of.
        :param service_values: Service values replacing the type's defaults.
        :param values: Editable fields replacing the type's defaults.
        :return: The new action.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *WRITE_OPERATIONS, for_update=True
        )
        self.handler.check_type_available(agent, service_type_name)
        defaults = agent_action_type_registry.get(service_type_name).get_defaults()
        initial_service = defaults.pop("service")
        defaults.update(values)
        defaults["name"] = (
            values["name"]
            if "name" in values
            else self.handler.unique_name(agent, defaults["name"])
        )
        validate_action_name(defaults["name"])
        defaults["inputs"] = validate_inputs(defaults["inputs"])
        initial_service.update(service_values or {})
        service_type = service_type_registry.get(service_type_name)
        prepared = self._prepare_service_values(
            user, agent, service_type, initial_service
        )
        action = self.handler.create_action(agent, service_type, prepared, **defaults)
        agent_action_created.send(self, action=action, user=user)
        return action

    @transaction.atomic
    def update_action(
        self,
        user: AbstractUser,
        agent_id: int,
        action_id: int,
        service_values: dict[str, Any] | None = None,
        **values: Any,
    ) -> AgentActionUpdated:
        """
        :param user: The user changing the action, who must be able to edit the
            Agent.
        :param agent_id: The id of the Agent.
        :param action_id: The id of one of its actions.
        :param service_values: The service values to change, if any.
        :param values: The editable fields to change.
        :return: The action and what changed.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        action = self._get_authorized_action(
            user, agent_id, action_id, *WRITE_OPERATIONS, for_update=True
        )
        if "name" in values:
            validate_action_name(values["name"])
        if "inputs" in values:
            values["inputs"] = validate_inputs(values["inputs"])
        prepared = None
        if service_values is not None:
            service = action.service.specific
            prepared = self._prepare_service_values(
                user, action.agent, service.get_type(), service_values, service
            )
        updated = self.handler.update_action(
            action, prepared_service_values=prepared, **values
        )
        if updated.changed_fields:
            agent_action_updated.send(self, action=action, user=user)
        return updated

    @transaction.atomic
    def delete_action(
        self, user: AbstractUser, agent_id: int, action_id: int
    ) -> AgentAction:
        """
        :param user: The user deleting the action, who must be able to edit the
            Agent.
        :param agent_id: The id of the Agent.
        :param action_id: The id of one of its actions.
        :return: The trashed action.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        action = self._get_authorized_action(
            user, agent_id, action_id, *WRITE_OPERATIONS, for_update=True
        )
        self.handler.delete_action(user, action)
        agent_action_deleted.send(self, action=action, user=user)
        return action
