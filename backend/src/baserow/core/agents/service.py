from django.contrib.auth.models import AbstractUser

from baserow.core.agents.exceptions import AgentRoleDoesNotExist
from baserow.core.agents.handler import AgentHandler
from baserow.core.agents.operations import (
    CreateAgentOperationType,
    DeleteAgentOperationType,
    ListAgentsWorkspaceOperationType,
    UpdateAgentOperationType,
)
from baserow.core.agents.registries import agent_extension_registry
from baserow.core.agents.signals import agent_created, agent_deleted, agent_updated
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent, Workspace


class AgentService:
    """Provides permission-aware operations for managing workspace agents."""

    def list_agents(self, user: AbstractUser, workspace: Workspace):
        """
        Lists the agents in a workspace that the user is allowed to access.

        :param user: The user requesting the agents.
        :param workspace: The workspace whose agents should be returned.
        :return: A queryset containing the workspace agents.
        """

        CoreHandler().check_permissions(
            user,
            ListAgentsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        return AgentHandler().get_queryset(workspace)

    def create_agent(self, user: AbstractUser, workspace: Workspace, **values) -> Agent:
        """
        Creates an agent and its registered extension data in a workspace.

        :param user: The user creating the agent.
        :param workspace: The workspace in which to create the agent.
        :param values: The core and extension field values for the agent.
        :raises AgentRoleDoesNotExist: If the requested role does not exist.
        :return: The newly created agent with its extension data loaded.
        """

        CoreHandler().check_permissions(
            user, CreateAgentOperationType.type, workspace=workspace, context=workspace
        )
        values.setdefault(
            "role_uid", agent_extension_registry.get_default_role_uid(workspace)
        )
        if not agent_extension_registry.role_uid_exists(values["role_uid"], workspace):
            raise AgentRoleDoesNotExist()
        agent = AgentHandler().create_agent(workspace, **values)
        for extension in agent_extension_registry.get_all():
            extension.create(agent, values, user)
        agent = AgentHandler().get_agent(
            agent.id, AgentHandler().get_queryset(workspace)
        )
        agent_created.send(self, user=user, agent=agent)
        return agent

    def update_agent(self, user: AbstractUser, agent: Agent, **values) -> Agent:
        """
        Updates an agent and its registered extension data.

        :param user: The user updating the agent.
        :param agent: The agent to update.
        :param values: The core and extension field values to update.
        :raises AgentRoleDoesNotExist: If the requested role does not exist.
        :return: The updated agent with its extension data loaded.
        """

        CoreHandler().check_permissions(
            user,
            UpdateAgentOperationType.type,
            workspace=agent.workspace,
            context=agent.workspace,
        )
        if "role_uid" in values and not agent_extension_registry.role_uid_exists(
            values["role_uid"], agent.workspace
        ):
            raise AgentRoleDoesNotExist()
        AgentHandler().update_agent(agent, **values)
        for extension in agent_extension_registry.get_all():
            extension.update(agent, values, user)
        agent = AgentHandler().get_agent(
            agent.id, AgentHandler().get_queryset(agent.workspace)
        )
        agent_updated.send(self, user=user, agent=agent)
        return agent

    def delete_agent(self, user: AbstractUser, agent: Agent) -> None:
        """
        Deletes an agent after preparing all registered extensions for deletion.

        :param user: The user deleting the agent.
        :param agent: The agent to delete.
        """

        CoreHandler().check_permissions(
            user,
            DeleteAgentOperationType.type,
            workspace=agent.workspace,
            context=agent.workspace,
        )
        for extension in agent_extension_registry.get_all():
            extension.before_delete(agent, user)
        AgentHandler().delete_agent(user, agent)
        agent_deleted.send(self, user=user, agent=agent)
