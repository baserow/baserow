from typing import List

from django.conf import settings
from django.contrib.auth.models import AbstractUser

from baserow.core.models import Agent, Workspace
from baserow.core.registries import SubjectType
from baserow.core.types import Subject


class AgentSubjectType(SubjectType):
    type = "core.Agent"
    model_class = Agent
    display_name_field = "name"

    has_direct_workspace_roles = True

    def get_workspace_subjects(self, workspace: Workspace, include_trash=False):
        manager = Agent.objects_and_trash if include_trash else Agent.objects
        return manager.filter(workspace=workspace)

    def set_workspace_role_uid(
        self,
        subject: Agent,
        workspace: Workspace,
        role_uid: str,
        send_signals: bool = True,
    ):
        """Persist the agent role and notify clients about its updated permissions."""
        from baserow.core.agents.handler import AgentHandler
        from baserow.core.agents.signals import agent_updated
        from baserow.core.signals import permissions_updated

        AgentHandler().update_agent(subject, role_uid=role_uid)
        if send_signals:
            agent_updated.send(self, user=None, agent=subject)
            permissions_updated.send(self, subject=subject, workspace=workspace)

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
        return role_uid == getattr(
            settings, "NO_ROLE_LOW_PRIORITY_UID", "NO_ROLE_LOW_PRIORITY"
        )

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
