from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from baserow.core.agents.exceptions import AgentDoesNotExist
from baserow.core.agents.registries import agent_extension_registry
from baserow.core.models import Agent, Workspace


class AgentHandler:
    """Handles agent persistence and domain-level queries."""

    allowed_fields = {"name", "role_uid"}

    def get_queryset(self, workspace: Workspace) -> QuerySet[Agent]:
        """
        Returns the agents in the workspace with all registered extensions applied.

        :param workspace: The workspace whose agents should be returned.
        :return: A queryset containing the workspace agents.
        """

        queryset = Agent.objects.filter(workspace=workspace)
        return agent_extension_registry.enhance_queryset(queryset, workspace)

    def get_agent(self, agent_id: int, base_queryset=None) -> Agent:
        """
        Returns the agent with the given ID.

        :param agent_id: The ID of the agent to return.
        :param base_queryset: An optional queryset to use when retrieving the agent.
        :raises AgentDoesNotExist: If an agent with the given ID does not exist in
            the queryset.
        :return: The requested agent.
        """

        queryset = base_queryset if base_queryset is not None else Agent.objects
        try:
            return queryset.select_related("workspace").get(id=agent_id)
        except Agent.DoesNotExist as exc:
            raise AgentDoesNotExist() from exc

    def create_agent(self, workspace: Workspace, **values: Any) -> Agent:
        """
        Creates an agent in the workspace using the allowed core field values.

        :param workspace: The workspace in which to create the agent.
        :param values: The agent field values.
        :return: The newly created agent.
        """

        core_values = {key: values[key] for key in self.allowed_fields if key in values}
        return Agent.objects.create(workspace=workspace, **core_values)

    def update_agent(self, agent: Agent, **values: Any) -> Agent:
        """
        Updates the allowed core fields on an agent.

        :param agent: The agent to update.
        :param values: The agent field values to update.
        :return: The updated agent.
        """

        update_fields = []
        for key in self.allowed_fields:
            if key in values:
                setattr(agent, key, values[key])
                update_fields.append(key)
        if update_fields:
            agent.save(update_fields=[*update_fields, "updated_on"])
        return agent

    def update_last_active(self, agent: Agent) -> Agent:
        """
        Sets the agent's last active time to the current time.

        :param agent: The agent whose last active time should be updated.
        :return: The updated agent.
        """

        agent.last_active = timezone.now()
        agent.save(update_fields=["last_active"])
        return agent

    def delete_agent(self, user, agent: Agent) -> None:
        """
        Moves an agent to the trash.

        :param user: The user deleting the agent.
        :param agent: The agent to delete.
        """

        from baserow.core.trash.handler import TrashHandler

        TrashHandler.trash(user, agent.workspace, None, agent)
