from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_builder.handler import AgentHandler
from baserow_enterprise.agent_builder.operations import (
    CreateAgentOperationType,
    DeleteAgentOperationType,
    ListAgentsOperationType,
    OrderAgentsOperationType,
    ReadAgentOperationType,
    UpdateAgentOperationType,
)
from baserow_enterprise.agent_builder.signals import (
    agent_created,
    agent_updated,
    agents_reordered,
)


class AgentService:
    def __init__(self):
        self.handler = AgentHandler()

    def get_agent(self, user, agent_id: int):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent = self.handler.get_agent(agent_id)
        CoreHandler().check_permissions(
            user,
            ReadAgentOperationType.type,
            workspace=agent.agent_builder.workspace,
            context=agent,
        )
        return agent

    def list_agents(self, user, agent_builder_id: int):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent_builder = self.handler.get_agent_builder(agent_builder_id)
        queryset = CoreHandler().filter_queryset(
            user,
            ListAgentsOperationType.type,
            self.handler.get_agents(agent_builder),
            workspace=agent_builder.workspace,
        )
        return CoreHandler().filter_queryset(
            user,
            ReadAgentOperationType.type,
            queryset,
            workspace=agent_builder.workspace,
        )

    def create_agent(self, user, agent_builder_id: int, name: str):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent_builder = self.handler.get_agent_builder(agent_builder_id)
        CoreHandler().check_permissions(
            user,
            CreateAgentOperationType.type,
            workspace=agent_builder.workspace,
            context=agent_builder,
        )
        agent = self.handler.create_agent(agent_builder, name)
        agent_created.send(self, agent=agent, user=user)
        return agent

    def update_agent(self, user, agent_id: int, **kwargs):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent = self.handler.get_agent(agent_id)
        CoreHandler().check_permissions(
            user,
            UpdateAgentOperationType.type,
            workspace=agent.agent_builder.workspace,
            context=agent,
        )
        updated_agent = self.handler.update_agent(agent, **kwargs)
        agent_updated.send(self, agent=updated_agent.agent, user=user)
        return updated_agent

    def delete_agent(self, user, agent_id: int):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent = self.handler.get_agent(agent_id)
        CoreHandler().check_permissions(
            user,
            DeleteAgentOperationType.type,
            workspace=agent.agent_builder.workspace,
            context=agent,
        )
        # The trash type sends the deletion signal for direct deletes and undo alike.
        self.handler.delete_agent(user, agent)
        return agent

    def order_agents(self, user, agent_builder_id: int, order: list[int]):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent_builder = self.handler.get_agent_builder(agent_builder_id)
        CoreHandler().check_permissions(
            user,
            OrderAgentsOperationType.type,
            workspace=agent_builder.workspace,
            context=agent_builder,
        )
        user_agents = self.list_agents(user, agent_builder_id)
        ordered_ids = self.handler.order_agents(agent_builder, order, user_agents)
        agents_reordered.send(
            self, agent_builder=agent_builder, order=ordered_ids, user=user
        )
        return ordered_ids
