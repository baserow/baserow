from django.db.models import Q

from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow.core.trash.registries import TrashableItemType
from baserow_enterprise.agent_builder.models import AgentDefinition
from baserow_enterprise.agent_builder.operations import (
    ReadAgentOperationType,
    RestoreAgentOperationType,
)
from baserow_enterprise.agent_builder.signals import agent_created, agent_deleted


class AgentTrashableItemType(TrashableItemType):
    type = "agent_builder_agent"
    model_class = AgentDefinition

    def filter_trash_contents(self, user, workspace, queryset):
        if not feature_flag_is_enabled(FF_AGENT_BUILDER):
            return queryset.exclude(trash_item_type=self.type)
        agents = CoreHandler().filter_queryset(
            user,
            ReadAgentOperationType.type,
            AgentDefinition.objects_and_trash.filter(
                agent_builder__workspace=workspace
            ),
            workspace=workspace,
        )
        return queryset.filter(
            ~Q(trash_item_type=self.type) | Q(trash_item_id__in=agents.values("id"))
        )

    def get_parent(self, trashed_item):
        return trashed_item.agent_builder

    def get_name(self, trashed_item):
        return trashed_item.name

    def trash(self, item_to_trash, requesting_user, trash_entry):
        super().trash(item_to_trash, requesting_user, trash_entry)
        agent_deleted.send(self, agent=item_to_trash, user=requesting_user)

    def restore(self, trashed_item, trash_entry):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        super().restore(trashed_item, trash_entry)
        agent_created.send(self, agent=trashed_item, user=None)

    def permanently_delete_item(self, trashed_item, trash_item_lookup_cache=None):
        trashed_item.delete()

    def get_restore_operation_type(self):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        return RestoreAgentOperationType.type
