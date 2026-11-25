from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.agent.models import AgentAction, AgentApplication
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.service import AgentService
from baserow.core.integrations.service import IntegrationService
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.services.models import Service

from .exceptions import AgentActionTypeNotAvailable
from .handler import AgentActionHandler, AgentActionTypeOptions, AgentActionUpdated
from .inputs import validate_action_name, validate_inputs
from .registries import AgentActionType, agent_action_type_registry
from .signals import agent_action_created, agent_action_deleted, agent_action_updated

WRITE_OPERATIONS = (
    UpdateApplicationOperationType.type,
    ReadAgentConfigurationOperationType.type,
)
LOCKED_ACTION_EDITABLE_FIELDS = {"name", "enabled"}


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

    def list_action_types(
        self, user: AbstractUser, agent_id: int
    ) -> list[AgentActionTypeOptions]:
        """
        Describe the action types as the Agent's run identity sees them, to a user
        allowed to read its configuration.

        :param user: The user configuring actions.
        :param agent_id: The id of the Agent.
        :return: One entry per available type, in registry order.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return self.handler.list_action_types(
            agent, self.handler.get_run_identity(agent)
        )

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
        action_type: AgentActionType,
        values: dict[str, Any],
        instance: Service | None = None,
    ) -> dict[str, Any]:
        """
        :param user: The user saving the action.
        :param agent: The Agent.
        :param action_type: The type of the action, whose service is saved.
        :param values: The service values to save.
        :param instance: The existing service, when it is updated.
        :return: The values prepared by the service type, whose integration
            the Agent and the user may use, its own or a workspace integration.
            A type that acts as the Agent's run identity never has one.
        """

        values = dict(values)
        service_type = action_type.service_type
        if action_type.acts_as_run_identity:
            values.pop("integration_id", None)
        values = service_type.resolve_integration(agent, values)
        prepared = service_type.prepare_values(values, user, instance)
        integration = prepared.get(
            "integration", getattr(instance, "integration", None)
        )
        # The integration must be the Agent's own or a workspace integration of its
        # workspace, so its credentials never reach another workspace.
        service_type.check_integration(agent, {"integration": integration})
        if integration is not None:
            IntegrationService().check_can_use_integration(user, integration, agent)
        return prepared

    @transaction.atomic
    def create_action(
        self,
        user: AbstractUser,
        agent_id: int,
        type_name: str,
        service_values: dict[str, Any] | None = None,
        **values: Any,
    ) -> AgentAction:
        """
        Add an action of a type to the Agent, starting from the type's defaults.

        :param user: The user adding the action, who must be able to edit the
            Agent.
        :param agent_id: The id of the Agent.
        :param type_name: The action type the action is of.
        :param service_values: Service values replacing the type's defaults.
        :param values: Editable fields replacing the type's defaults.
        :return: The new action.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *WRITE_OPERATIONS, for_update=True
        )
        self.handler.check_type_usable(agent, type_name)
        action_type = agent_action_type_registry.get(type_name)
        defaults = action_type.get_defaults()
        initial_service = defaults.pop("service")
        defaults.setdefault("ask_first", action_type.changes_data)
        defaults.update(values)
        defaults["name"] = (
            values["name"]
            if "name" in values
            else self.handler.unique_name(agent, defaults["name"])
        )
        validate_action_name(defaults["name"])
        defaults["inputs"] = validate_inputs(defaults["inputs"])
        initial_service.update(service_values or {})
        service_type = action_type.service_type
        if not action_type.acts_as_run_identity:
            initial_service = service_type.with_default_integration(
                initial_service, user, agent
            )
        prepared = self._prepare_service_values(
            user, agent, action_type, initial_service
        )
        action = self.handler.create_action(agent, type_name, prepared, **defaults)
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
        :raises AgentActionTypeNotAvailable: When it would change more than the
            name or the switch of an action whose type can't be used in the
            workspace.
        """

        action = self._get_authorized_action(
            user, agent_id, action_id, *WRITE_OPERATIONS, for_update=True
        )
        self._check_locked_change(action, service_values, values)
        if "name" in values:
            validate_action_name(values["name"])
        if "inputs" in values:
            values["inputs"] = validate_inputs(values["inputs"])
        prepared = None
        if service_values is not None:
            service = action.service.specific
            prepared = self._prepare_service_values(
                user,
                action.agent,
                agent_action_type_registry.get(action.get_type_name()),
                service_values,
                service,
            )
        updated = self.handler.update_action(
            action, prepared_service_values=prepared, **values
        )
        if updated.changed_fields:
            agent_action_updated.send(self, action=action, user=user)
        return updated

    def _check_locked_change(
        self,
        action: AgentAction,
        service_values: dict[str, Any] | None,
        values: dict[str, Any],
    ) -> None:
        """
        A locked action can still be renamed, switched or deleted, so it's
        ready again when its type becomes usable.

        :param action: The action, with its agent and workspace.
        :param service_values: The service values to change, if any.
        :param values: The editable fields to change.
        :raises AgentActionTypeNotAvailable: When anything else would change and
            the action's type can't be used in the workspace.
        """

        changes_settings = service_values is not None or bool(
            set(values) - LOCKED_ACTION_EDITABLE_FIELDS
        )
        type_name = action.get_type_name()
        action_type = agent_action_type_registry.get(type_name)
        if changes_settings and not action_type.is_usable(action.agent.workspace):
            raise AgentActionTypeNotAvailable(type_name)

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

        action = self._get_authorized_action(
            user, agent_id, action_id, *WRITE_OPERATIONS, for_update=True
        )
        self.handler.delete_action(user, action)
        agent_action_deleted.send(self, action=action, user=user)
        return action
