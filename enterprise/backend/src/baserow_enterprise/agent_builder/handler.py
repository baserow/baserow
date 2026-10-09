from django.db import transaction
from django.db.models import Case, QuerySet, Value, When

from baserow.core.exceptions import IdDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import extract_allowed
from baserow_enterprise.agent_builder.exceptions import (
    AgentDoesNotExist,
    AgentNotInAgentBuilder,
)
from baserow_enterprise.agent_builder.models import AgentBuilder, AgentDefinition
from baserow_enterprise.agent_builder.types import UpdatedAgent


class AgentHandler:
    allowed_fields = ["name"]

    def get_agent_builder(self, agent_builder_id: int) -> AgentBuilder:
        return CoreHandler().get_application(
            agent_builder_id,
            base_queryset=AgentBuilder.objects.select_related("workspace"),
        )

    def get_agent(
        self, agent_id: int, base_queryset: QuerySet | None = None
    ) -> AgentDefinition:
        if base_queryset is None:
            base_queryset = AgentDefinition.objects.all()
        try:
            return base_queryset.select_related("agent_builder__workspace").get(
                id=agent_id
            )
        except AgentDefinition.DoesNotExist:
            raise AgentDoesNotExist()

    def get_agents(self, agent_builder: AgentBuilder) -> QuerySet:
        return AgentDefinition.objects.filter(
            agent_builder=agent_builder
        ).select_related("agent_builder__workspace")

    @transaction.atomic
    def create_agent(self, agent_builder: AgentBuilder, name: str) -> AgentDefinition:
        AgentBuilder.objects.select_for_update().get(pk=agent_builder.pk)
        return AgentDefinition.objects.create(
            agent_builder=agent_builder,
            name=name,
            order=AgentDefinition.get_last_order(agent_builder),
        )

    def update_agent(self, agent: AgentDefinition, **kwargs) -> UpdatedAgent:
        values = extract_allowed(kwargs, self.allowed_fields)
        original_values = {field: getattr(agent, field) for field in values}
        for field, value in values.items():
            setattr(agent, field, value)
        agent.save()
        return UpdatedAgent(agent, original_values, values)

    def delete_agent(self, user, agent: AgentDefinition):
        TrashHandler.trash(
            user, agent.agent_builder.workspace, agent.agent_builder, agent
        )

    def get_agents_order(self, agent_builder: AgentBuilder) -> list[int]:
        return list(self.get_agents(agent_builder).values_list("id", flat=True))

    @transaction.atomic
    def order_agents(
        self, agent_builder: AgentBuilder, order: list[int], base_queryset=None
    ) -> list[int]:
        AgentBuilder.objects.select_for_update().get(pk=agent_builder.pk)
        if base_queryset is None:
            base_queryset = self.get_agents(agent_builder)
        # Reorder only the user's visible positions, keeping hidden and trashed
        # agents at their existing positions in the application's full ordering.
        full_queryset = AgentDefinition.objects_and_trash.filter(
            agent_builder=agent_builder
        )
        full_order = list(full_queryset.values_list("id", "order"))
        normalize = len({value for _, value in full_order}) != len(full_order)
        positions = {
            agent_id: index if normalize else value
            for index, (agent_id, value) in enumerate(full_order, start=1)
        }
        visible_ids = list(base_queryset.values_list("id", flat=True))
        order_values = [positions[agent_id] for agent_id in visible_ids]
        try:
            ordered_ids = AgentDefinition.order_objects(base_queryset, order)
        except IdDoesNotExist as exc:
            raise AgentNotInAgentBuilder(exc.not_existing_id)
        if ordered_ids:
            if normalize:
                # Old/imported collisions need distinct slots before a requested
                # ordering can be persisted. Preserve hidden agents' relative slots.
                positions.update(zip(ordered_ids, order_values))
                queryset_to_update = full_queryset
            else:
                positions = dict(zip(ordered_ids, order_values))
                queryset_to_update = base_queryset
            queryset_to_update.update(
                order=Case(
                    *[
                        When(id=agent_id, then=Value(order_value))
                        for agent_id, order_value in positions.items()
                    ]
                )
            )
        return ordered_ids
