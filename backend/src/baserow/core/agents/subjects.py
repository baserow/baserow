from typing import List

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db.models import CharField, F, IntegerField, Value
from django.db.models.functions import Cast
from django.utils.translation import gettext_lazy as _

from baserow.core.agents.operations import ListAgentsWorkspaceOperationType
from baserow.core.models import Agent, Workspace
from baserow.core.registries import SubjectType
from baserow.core.types import Subject


class AgentSubjectType(SubjectType):
    type = "core.Agent"
    model_class = Agent
    display_name_field = "name"
    options_list_operation_type = ListAgentsWorkspaceOperationType.type

    has_direct_workspace_roles = True

    def get_type_display_name(self):
        return _("Agent")

    def get_display_name(self, subject: Agent) -> str:
        return subject.name

    def get_queryset(self, workspace_id=None):
        queryset = Agent.objects.all()
        if workspace_id is not None:
            queryset = queryset.filter(workspace_id=workspace_id)
        return queryset.order_by("name")

    def get_options_queryset(
        self,
        workspace: Workspace | None = None,
        search: str = "",
        exclude_ids: List[int] | None = None,
    ):
        """Return searchable agent options, optionally scoped to a workspace."""

        queryset = Agent.objects.exclude(id__in=exclude_ids or [])
        if workspace is not None:
            queryset = queryset.filter(workspace=workspace)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.annotate(
            subject_id=F("id"),
            subject_type=Value(self.type, output_field=CharField()),
            subject_name=F("name"),
            subject_label=F("name"),
            subject_email=Value(None, output_field=CharField()),
            subject_count=Cast(Value(None), output_field=IntegerField()),
        ).values(
            "subject_id",
            "subject_type",
            "subject_name",
            "subject_label",
            "subject_email",
            "subject_count",
        )

    def _get_workspace_agents(self, workspace: Workspace, include_trash: bool):
        """Return agents using the requested agent and parent-workspace visibility."""

        manager = Agent.objects_and_trash if include_trash else Agent.objects
        queryset = manager.filter(workspace=workspace)
        if not include_trash:
            queryset = queryset.filter(workspace__trashed=False)
        return queryset

    def get_workspace_subjects(self, workspace: Workspace, include_trash=False):
        return self._get_workspace_agents(workspace, include_trash)

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

        return dict(
            self._get_workspace_agents(workspace, include_trash)
            .filter(
                id__in=[subject.id for subject in subjects],
            )
            .values_list("id", "role_uid")
        )

    def is_workspace_role_fallback(self, role_uid: str) -> bool:
        return role_uid == getattr(
            settings, "NO_ROLE_LOW_PRIORITY_UID", "NO_ROLE_LOW_PRIORITY"
        )

    def are_workspace_roles_available(
        self, subjects: List[Subject], workspace: Workspace
    ) -> List[bool]:
        """Return whether each stored role is supported by the current edition."""

        from baserow.core.agents.registries import agent_extension_type_registry

        return [
            agent_extension_type_registry.role_uid_exists(subject.role_uid, workspace)
            for subject in subjects
        ]

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        ids = set(
            self._get_workspace_agents(workspace, include_trash)
            .filter(id__in=[subject.id for subject in subjects])
            .values_list("id", flat=True)
        )
        return [subject.id in ids for subject in subjects]

    def get_serializer(self, model_instance, **kwargs):
        from baserow.api.agents.serializers import AgentSubjectSerializer

        return AgentSubjectSerializer(model_instance, **kwargs)

    def get_users_included_in_subject(self, subject: Agent) -> List[AbstractUser]:
        return []
