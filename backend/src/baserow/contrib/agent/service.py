from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.core.handler import CoreHandler
from baserow.core.operations import (
    ReadApplicationOperationType,
    UpdateApplicationOperationType,
)
from baserow.core.signals import application_updated

from .handler import AgentHandler
from .models import AgentApplication
from .operations import ReadAgentSettingsOperationType
from .types import AgentConfiguration, AgentConfigurationUpdated, AgentReadiness


class AgentService:
    def __init__(self):
        self.handler = AgentHandler()

    def _get_authorized_agent(
        self,
        user: AbstractUser,
        agent_id: int,
        operation: str,
        for_update: bool = False,
    ) -> AgentApplication:
        """Authorize at the owning application's scope, never a thread scope."""

        agent = self.handler.get_agent(agent_id, for_update=for_update)
        CoreHandler().check_permissions(
            user, operation, workspace=agent.workspace, context=agent
        )
        return agent

    def get_readiness(self, user: AbstractUser, agent_id: int) -> AgentReadiness:
        """Expose only coarse readiness to ordinary application readers."""

        agent = self._get_authorized_agent(
            user, agent_id, ReadApplicationOperationType.type
        )
        return {"state": self.handler.get_configuration(agent)["state"]}

    def get_configuration(
        self, user: AbstractUser, agent_id: int
    ) -> AgentConfiguration:
        """Return actual setting values only with the privileged settings operation."""

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentSettingsOperationType.type
        )
        return self.handler.get_configuration(agent)

    @transaction.atomic
    def update_configuration(
        self, user: AbstractUser, agent_id: int, **values
    ) -> AgentConfigurationUpdated:
        """Save an authorized partial draft and emit a name-only application update."""

        agent = self._get_authorized_agent(
            user, agent_id, UpdateApplicationOperationType.type, for_update=True
        )
        updated = self.handler.update_configuration(agent, **values)
        if updated.changed_fields:
            # The existing serializer deliberately carries only public name metadata.
            application_updated.send(self, application=agent, user=user)
        return updated
