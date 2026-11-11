from django.db.models import QuerySet

from baserow.contrib.agent.models import AgentApplication
from baserow.core.operations import ListApplicationsWorkspaceOperationType
from baserow.core.registries import LastViewedItemType


class AgentLastViewedItemType(LastViewedItemType):
    """
    An agent has no sub pages, so the application itself is the leaf. Its rows are
    removed by the foreign key cascade when the application is deleted.
    """

    type = "agent"
    model_class = AgentApplication
    list_operation_type = ListApplicationsWorkspaceOperationType.type

    def get_visible_queryset(self) -> QuerySet:
        return AgentApplication.objects.all()

    def get_queryset_for_user(self, user_id: int) -> QuerySet:
        return self.get_visible_queryset().filter(
            workspace__trashed=False, workspace__workspaceuser__user_id=user_id
        )

    def get_application_id(self, instance: AgentApplication) -> int:
        return instance.id

    def get_workspace_id(self, instance: AgentApplication) -> int:
        return instance.workspace_id
