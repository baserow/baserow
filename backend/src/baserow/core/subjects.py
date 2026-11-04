from typing import List

from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db.models import (
    Case,
    CharField,
    Count,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Cast

from baserow.core.models import User, UserProfile, Workspace, WorkspaceUser
from baserow.core.operations import ListWorkspaceUsersWorkspaceOperationType
from baserow.core.registries import SubjectType
from baserow.core.types import Subject
from baserow.core.user.identity import is_agent_user, is_human_user


class UserSubjectType(SubjectType):
    type = "auth.User"
    model_class = User

    def is_interactive_user(self, subject):
        return is_human_user(subject)

    def track_usage(self, subject):
        if is_agent_user(subject):
            from baserow.core.agents.handler import AgentHandler

            AgentHandler().update_last_active(subject)

    display_name_field = "first_name"
    lookup_fields = (*SubjectType.lookup_fields, "email")
    options_list_operation_type = ListWorkspaceUsersWorkspaceOperationType.type

    has_direct_workspace_roles = True

    def get_workspace_subjects(self, workspace: Workspace, include_trash=False):
        manager = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        return [
            membership.user
            for membership in manager.filter(workspace=workspace).select_related(
                "user__profile"
            )
            if include_trash or not membership.user.profile.trashed
        ]

    def set_workspace_role_uid(
        self,
        subject: AbstractUser,
        workspace: Workspace,
        role_uid: str,
        send_signals: bool = True,
    ):
        """Store workspace roles on membership records, retaining basic role names."""
        from baserow.core.handler import CoreHandler

        # Keep roles on WorkspaceUser.permissions so switching permission managers
        # does not lose or duplicate information. Basic permissions call BUILDER MEMBER.
        workspace_user = workspace.get_workspace_user(subject)
        permissions = "MEMBER" if role_uid == "BUILDER" else role_uid
        CoreHandler().force_update_workspace_user(
            None, workspace_user, permissions=permissions
        )
        getattr(subject, "_prefetched_objects_cache", {}).pop("workspaceuser_set", None)
        if is_agent_user(subject) and send_signals:
            from baserow.core.agents.signals import agent_updated

            agent_updated.send(self, user=None, agent=subject)

    def get_type_display_name(self):
        return "User"

    def get_display_name(self, subject: AbstractUser) -> str:
        return subject.first_name

    def get_queryset(self, workspace_id=None):
        queryset = User.objects_and_agents.all()
        if workspace_id is not None:
            queryset = queryset.filter(workspaceuser__workspace_id=workspace_id)
        return queryset.order_by("email")

    def get_label(self, subject: AbstractUser) -> str:
        return subject.first_name if is_agent_user(subject) else subject.email

    def get_options_queryset(
        self,
        workspace: Workspace | None = None,
        search: str = "",
        exclude_ids: List[int] | None = None,
        include_inactive_and_scheduled_for_deletion: bool = False,
        identity_type: str | None = None,
    ):
        """Return searchable user options, optionally scoped to a workspace."""

        queryset = User.objects_and_agents.exclude(id__in=exclude_ids or [])
        if identity_type is not None:
            queryset = queryset.filter(profile__identity_type=identity_type)
        if not include_inactive_and_scheduled_for_deletion:
            queryset = queryset.filter(
                is_active=True, profile__to_be_deleted=False, profile__trashed=False
            )
        if workspace is not None:
            queryset = queryset.filter(workspaceuser__workspace=workspace)
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(username__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset.annotate(
            subject_id=F("id"),
            subject_type=Value(self.type, output_field=CharField()),
            subject_name=Case(
                When(first_name="", then=F("email")),
                default=F("first_name"),
                output_field=CharField(),
            ),
            subject_label=Case(
                When(
                    profile__identity_type=UserProfile.IdentityType.AGENT,
                    then=F("first_name"),
                ),
                default=F("email"),
                output_field=CharField(),
            ),
            subject_email=Case(
                When(
                    profile__identity_type=UserProfile.IdentityType.AGENT,
                    then=Value(None),
                ),
                default=F("email"),
                output_field=CharField(),
            ),
            subject_identity_type=F("profile__identity_type"),
            subject_role_uid=Case(
                When(
                    profile__identity_type=UserProfile.IdentityType.AGENT,
                    then=Subquery(
                        WorkspaceUser.objects_and_trash.filter(
                            user_id=OuterRef("pk"),
                            **({"workspace": workspace} if workspace else {}),
                        ).values("permissions")[:1]
                    ),
                ),
                default=Value(None),
                output_field=CharField(),
            ),
            subject_count=Cast(Value(None), output_field=IntegerField()),
        ).values(
            "subject_id",
            "subject_type",
            "subject_name",
            "subject_label",
            "subject_email",
            "subject_count",
            "subject_identity_type",
            "subject_role_uid",
        )

    def get_historical_options_queryset(
        self,
        workspace: Workspace | None = None,
        search: str = "",
        exclude_ids: List[int] | None = None,
    ):
        """Return users retained for historical records after access is removed."""

        return self.get_options_queryset(
            workspace=workspace,
            search=search,
            exclude_ids=exclude_ids,
            include_inactive_and_scheduled_for_deletion=True,
        )

    def get_workspace_role_uids(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> dict[int, str]:
        """Return workspace membership permissions keyed by User ID."""

        workspace_user_manager = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        if not include_trash:
            workspace_user_manager = workspace_user_manager.filter(
                user__profile__trashed=False
            )
        return dict(
            workspace_user_manager.filter(
                workspace=workspace,
                user_id__in=[subject.id for subject in subjects],
            ).values_list("user_id", "permissions")
        )

    def is_workspace_role_fallback(self, role_uid: str) -> bool:
        return role_uid == getattr(
            settings, "NO_ROLE_LOW_PRIORITY_UID", "NO_ROLE_LOW_PRIORITY"
        )

    def are_workspace_roles_available(self, subjects, workspace):
        from baserow.core.agents.registries import agent_extension_type_registry

        agents = [subject for subject in subjects if is_agent_user(subject)]
        if not agents:
            return [True] * len(subjects)
        roles = self.get_workspace_role_uids(agents, workspace, include_trash=True)
        available = {
            uid: agent_extension_type_registry.role_uid_exists(uid, workspace)
            for uid in set(roles.values())
        }
        return [
            not is_agent_user(subject) or available.get(roles.get(subject.id), False)
            for subject in subjects
        ]

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        manager = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        prefetched = getattr(workspace, "_prefetched_objects_cache", {})
        if not include_trash and "workspaceuser_set" in prefetched:
            user_ids = {
                membership.user_id for membership in workspace.workspaceuser_set.all()
            }
            missing = {subject.id for subject in subjects} - user_ids
            if missing:
                user_ids.update(
                    manager.filter(
                        workspace=workspace, user_id__in=missing
                    ).values_list("user_id", flat=True)
                )
        else:
            user_ids = set(
                manager.filter(workspace=workspace, user__in=subjects).values_list(
                    "user_id", flat=True
                )
            )

        agent_ids = [subject.id for subject in subjects if is_agent_user(subject)]
        # Include trashed memberships: an extra membership must never expand an agent's scope.
        agent_memberships = (
            dict(
                WorkspaceUser.objects_and_trash.filter(user_id__in=agent_ids)
                .values("user_id")
                .annotate(count=Count("id"))
                .values_list("user_id", "count")
            )
            if agent_ids
            else {}
        )
        return [
            subject.id in user_ids
            and subject.is_active
            and (is_human_user(subject) or is_agent_user(subject))
            and not subject.profile.to_be_deleted
            and (
                is_human_user(subject)
                or (
                    agent_memberships.get(subject.id) == 1
                    and not subject.profile.trashed
                    and not workspace.trashed
                )
            )
            for subject in subjects
        ]

    def get_serializer(self, model_instance, **kwargs):
        from baserow.api.user.serializers import SubjectUserSerializer

        return SubjectUserSerializer(model_instance, **kwargs)

    def get_users_included_in_subject(
        self, subject: AbstractUser
    ) -> List[AbstractUser]:
        return [subject] if is_human_user(subject) else []


class AnonymousUserSubjectType(SubjectType):
    type = "anonymous"
    model_class = AnonymousUser

    def get_type_display_name(self):
        return "Anonymous user"

    def get_display_name(self, subject: AnonymousUser) -> str:
        # Row history persists this as a stable fallback. Clients translate the
        # anonymous actor label at render time so it uses the viewer's language.
        return "Anonymous User"

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        """
        Anonymous users are never member of any workspace.
        """

        return [False for _ in subjects]

    def get_serializer(self, model_instance, **kwargs):
        return None

    def get_users_included_in_subject(
        self, subject: AnonymousUser
    ) -> List[AbstractUser]:
        return []
