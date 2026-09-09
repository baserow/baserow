from typing import List

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.models import Agent, Workspace
from baserow.core.registries import SubjectType
from baserow.core.types import Subject


class AgentSubjectType(SubjectType):
    type = "core.Agent"
    model_class = Agent
    display_name_field = "name"

    def get_type_display_name(self):
        return _("Agent")

    def get_display_name(self, subject: Agent) -> str:
        return subject.name

    def get_queryset(self, workspace_id=None):
        queryset = Agent.objects.all()
        if workspace_id is not None:
            queryset = queryset.filter(workspace_id=workspace_id)
        return queryset.order_by("name")

    def get_workspace_role_uids(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> dict[int, str]:
        """Return direct Agent role UIDs keyed by Agent ID."""

        agent_manager = Agent.objects_and_trash if include_trash else Agent.objects
        return dict(
            agent_manager.filter(
                workspace=workspace,
                id__in=[subject.id for subject in subjects],
            ).values_list("id", "role_uid")
        )

    def is_workspace_role_fallback(self, role_uid: str) -> bool:
        return role_uid == getattr(settings, "NO_ACCESS_ROLE_UID", "NO_ACCESS")

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        agent_manager = Agent.objects_and_trash if include_trash else Agent.objects
        ids = set(
            agent_manager.filter(
                id__in=[subject.id for subject in subjects], workspace=workspace
            ).values_list("id", flat=True)
        )
        return [subject.id in ids for subject in subjects]

    def get_serializer(self, model_instance, **kwargs):
        from baserow.api.agents.serializers import AgentSubjectSerializer

        return AgentSubjectSerializer(model_instance, **kwargs)

    def get_users_included_in_subject(self, subject: Agent) -> List[AbstractUser]:
        return []
