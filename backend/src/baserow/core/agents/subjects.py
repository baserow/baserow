from typing import List

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import CharField, F, IntegerField, Q, TextField, Value
from django.db.models.functions import Cast
from django.db.models.signals import post_delete

from baserow.core.agents.handler import AgentHandler
from baserow.core.agents.operations import ListAgentsWorkspaceOperationType
from baserow.core.models import Agent, Workspace
from baserow.core.registries import SubjectType
from baserow.core.types import Subject


class AgentSubjectType(SubjectType):
    type = "core.Agent"
    model_class = Agent
    display_name_field = "name"
    options_list_operation_type = ListAgentsWorkspaceOperationType.type

    supports_persistent_subjects = True
    persistent_subject_disabled_message = (
        "Agent field references have not been activated."
    )

    def register_lifecycle_signals(self):
        """Retain Agent attribution on permanent deletion, including cascades."""
        post_delete.connect(
            self._retain_deleted_agent_subject,
            sender=self.model_class,
            dispatch_uid=f"{self.type}.retain_subject",
            weak=False,
        )

    def _retain_deleted_agent_subject(self, sender, instance, using, **kwargs):
        self.retain_persistent_subject(instance.subject_id, using=using)

    def synchronize_persistent_subject(self, actor, *, using="default"):
        """Keep the independent Agent ID and its cached identity transactionally linked."""
        from baserow.core.models import Subject as PersistentSubject
        from baserow.core.subject.handler import allocate_subject_id

        with transaction.atomic(using=using):
            agent = (
                Agent._base_manager.using(using).select_for_update().get(pk=actor.pk)
            )
            subject_id = agent.subject_id
            if subject_id is None:
                subject_id = allocate_subject_id(using=using)
            subject, created = PersistentSubject.objects.using(using).get_or_create(
                pk=subject_id,
                defaults={
                    "type": self.type,
                    "name": agent.name,
                    "uid": str(agent.uid),
                    "state": "trashed" if agent.trashed else "live",
                },
            )
            if subject.type != self.type:
                raise ValueError("Agent Subject ID belongs to another identity type.")
            subject.name, subject.uid = agent.name, str(agent.uid)
            subject.state = "trashed" if agent.trashed else "live"
            if not created:
                subject.save(using=using, update_fields=["name", "uid", "state"])
            if agent.subject_id is None:
                Agent._base_manager.using(using).filter(pk=agent.pk).update(
                    subject_id=subject_id
                )
            actor.subject = subject

    def persistent_subject_references_enabled(self):
        """Require both the Agent feature flag and persisted rollout activation."""
        from baserow.core.feature_flags import FF_AGENTS, feature_flag_is_enabled
        from baserow.core.models import SubjectRollout

        return (
            feature_flag_is_enabled(FF_AGENTS)
            and SubjectRollout.objects.filter(
                pk=1, agent_references_enabled=True
            ).exists()
        )

    def get_persistent_subject_workspace_filter(self, workspace_id, *, selectable=True):
        query = Q(agent__workspace_id=workspace_id)
        if selectable:
            query &= Q(agent__trashed=False, agent__workspace__trashed=False)
        return query

    def has_invalid_persistent_subjects(self):
        """Verify Agent linkage, UUID, name and trash state without actor lookups."""
        return (
            Agent.objects_and_trash.annotate(uid_text=Cast("uid", TextField()))
            .filter(
                Q(subject_id__isnull=True)
                | ~Q(subject__type=self.type)
                | ~Q(subject__name=F("name"))
                | ~Q(subject__uid=F("uid_text"))
                | (Q(trashed=True) & ~Q(subject__state="trashed"))
                | (Q(trashed=False) & ~Q(subject__state="live"))
            )
            .exists()
        )

    def _get_persistent_subject(self, actor):
        return actor.subject

    def resolve_persistent_subject(self, subject):
        return Agent.objects.filter(subject=subject, workspace__trashed=False).first()

    has_direct_workspace_roles = True

    def track_usage(self, subject: Agent) -> None:
        """Track agent service usage by updating its last-active timestamp."""

        AgentHandler().update_last_active(subject)

    def get_type_display_name(self):
        return "Agent"

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
        include_trash: bool = False,
    ):
        """Return searchable agent options, optionally scoped to a workspace.

        :param include_trash: Whether trashed agents should be included.
        """

        manager = Agent.objects_and_trash if include_trash else Agent.objects
        queryset = manager.exclude(id__in=exclude_ids or [])
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

    def get_historical_options_queryset(
        self,
        workspace: Workspace | None = None,
        search: str = "",
        exclude_ids: List[int] | None = None,
    ):
        """Return agents retained for historical records after being trashed."""

        return self.get_options_queryset(
            workspace=workspace,
            search=search,
            exclude_ids=exclude_ids,
            include_trash=True,
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
