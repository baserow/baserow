from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.agent.models import AgentAction
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.service import AgentService
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow.core.integrations.operations import ReadIntegrationOperationType
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.services.registries import service_type_registry

from .handler import AgentActionHandler, AgentActionUpdated
from .inputs import validate_inputs, validate_name
from .registries import agent_action_type_registry
from .signals import agent_action_created, agent_action_deleted, agent_action_updated

WRITE_OPERATIONS = (
    UpdateApplicationOperationType.type,
    ReadAgentConfigurationOperationType.type,
)


class AgentActionService:
    """Configuration changes for users who may edit the owning Agent."""

    def __init__(self):
        self.handler = AgentActionHandler()
        self.agent_service = AgentService()

    def _get_authorized_action(
        self, user, agent_id, action_id, *operations, for_update=False
    ):
        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *operations, for_update=for_update
        )
        queryset = AgentAction.objects.filter(agent=agent)
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        return self.handler.get_action(action_id, queryset)

    def list_actions(self, user: AbstractUser, agent_id: int) -> list[AgentAction]:
        agent = self.agent_service.get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return list(self.handler.list_actions(agent))

    def get_action(
        self, user: AbstractUser, agent_id: int, action_id: int
    ) -> AgentAction:
        return self._get_authorized_action(
            user, agent_id, action_id, ReadAgentConfigurationOperationType.type
        )

    def _prepare_service_values(self, user, agent, service_type, values, instance=None):
        prepared = service_type.prepare_values(dict(values), user, instance)
        integration = prepared.get(
            "integration", getattr(instance, "integration", None)
        )
        # The integration and its credentials belong to this application, not the
        # editor's other applications or workspaces.
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
        self, user, agent_id, service_type_name, service_values=None, **values
    ):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *WRITE_OPERATIONS, for_update=True
        )
        self.handler.check_type_available(agent, service_type_name)
        adapter = agent_action_type_registry.get(service_type_name)
        defaults = adapter.get_defaults()
        initial_service = defaults.pop("service")
        defaults.update(values)
        defaults["name"] = (
            values["name"]
            if "name" in values
            else self.handler.unique_name(agent, defaults["name"])
        )
        validate_name(defaults["name"])
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
        self, user, agent_id, action_id, service_values=None, **values
    ) -> AgentActionUpdated:
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        action = self._get_authorized_action(
            user, agent_id, action_id, *WRITE_OPERATIONS, for_update=True
        )
        if "name" in values:
            validate_name(values["name"])
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
    def delete_action(self, user, agent_id, action_id) -> AgentAction:
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        action = self._get_authorized_action(
            user, agent_id, action_id, *WRITE_OPERATIONS, for_update=True
        )
        self.handler.delete_action(user, action)
        agent_action_deleted.send(self, action=action, user=user)
        return action
