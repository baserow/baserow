from django.contrib.auth.models import AbstractUser

from baserow.core.handler import CoreHandler

from .handler import AgentApplicationHandler
from .models import AgentDefinition
from .operations import (
    ReadAgentDefinitionOperationType,
    UpdateAgentDefinitionOperationType,
)
from .signals import agent_definition_updated


class AgentApplicationService:
    def __init__(self):
        self.handler = AgentApplicationHandler()

    def get_agent(self, user: AbstractUser, agent_id: int) -> AgentDefinition:
        agent = self.handler.get_agent(agent_id)

        CoreHandler().check_permissions(
            user,
            ReadAgentDefinitionOperationType.type,
            workspace=agent.application.workspace,
            context=agent.application.application_ptr,
        )

        return agent

    def update_agent(
        self, user: AbstractUser, agent_id: int, **kwargs
    ) -> AgentDefinition:
        agent = self.handler.get_agent(agent_id)

        CoreHandler().check_permissions(
            user,
            UpdateAgentDefinitionOperationType.type,
            workspace=agent.application.workspace,
            context=agent.application.application_ptr,
        )

        skills = kwargs.pop("skills", None)
        agent = self.handler.update_agent(agent, **kwargs)
        if skills is not None:
            self.handler.set_agent_skills(agent, skills)

        agent_definition_updated.send(self, user=user, agent=agent)

        return agent
