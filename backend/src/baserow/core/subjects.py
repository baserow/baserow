from copy import copy
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
    QuerySet,
    Subquery,
    Value,
    When,
    prefetch_related_objects,
)
from django.db.models.functions import Cast

from baserow.core.models import User, UserProfile, Workspace, WorkspaceUser
from baserow.core.operations import ListWorkspaceUsersWorkspaceOperationType
from baserow.core.registries import SubjectType
from baserow.core.types import Subject
from baserow.core.user.identity import is_human, is_identity


def _memberships(include_trash: bool) -> QuerySet[WorkspaceUser]:
    """
    Returns the memberships of users and identities that permission checks consider.

    :param include_trash: Whether memberships in trashed workspaces are included.
    :return: The membership queryset.
    """

    memberships = WorkspaceUser.objects_and_identities.all()
    if not include_trash:
        memberships = memberships.filter(workspace__trashed=False)
    return memberships


def without_prefetched_memberships(workspace: Workspace) -> Workspace:
    """
    Copies the workspace without its prefetched memberships, so membership checks
    read the current database state instead of a snapshot.

    :param workspace: The workspace, which is left untouched.
    :return: The copy to run permission checks against.
    """

    fresh_workspace = copy(workspace)
    prefetched = getattr(workspace, "_prefetched_objects_cache", {})
    fresh_workspace._prefetched_objects_cache = {
        name: objects
        for name, objects in prefetched.items()
        if name != "workspaceuser_set"
    }
    return fresh_workspace


class UserSubjectType(SubjectType):
    type = "auth.User"
    model_class = User

    def is_interactive_user(self, subject):
        return is_human(subject)

    def track_usage(self, subject):
        if is_identity(subject):
            from baserow.core.identities.handler import IdentityHandler

            IdentityHandler().update_last_active(subject)

    display_name_field = "first_name"
    lookup_fields = (*SubjectType.lookup_fields, "email")
    options_list_operation_type = ListWorkspaceUsersWorkspaceOperationType.type

    has_direct_workspace_roles = True

    def get_workspace_subjects(self, workspace: Workspace, include_trash=False):
        return [
            membership.user
            for membership in _memberships(include_trash)
            .filter(workspace=workspace)
            .select_related("user__profile")
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
        if is_identity(subject) and send_signals:
            from baserow.core.identities.signals import identity_updated

            identity_updated.send(self, user=None, identity=subject)

    def get_type_display_name(self):
        return "User"

    def get_display_name(self, subject: AbstractUser) -> str:
        return subject.first_name

    def get_queryset(self, include_trash: bool = False) -> QuerySet[User]:
        users = User.objects_and_identities.select_related("profile")
        if not include_trash:
            users = users.filter(profile__trashed=False)
        return users

    def get_trashed_subjects_queryset(self) -> QuerySet[User]:
        return User.objects_and_identities.filter(profile__trashed=True)

    def get_label(self, subject: AbstractUser) -> str:
        return subject.first_name if is_identity(subject) else subject.email

    def get_options_queryset(
        self,
        workspace: Workspace | None = None,
        search: str = "",
        exclude_ids: List[int] | None = None,
        include_inactive_and_scheduled_for_deletion: bool = False,
        user_type: str | None = None,
    ):
        """Return searchable user options, optionally scoped to a workspace."""

        queryset = User.objects_and_identities.exclude(id__in=exclude_ids or [])
        if user_type is not None:
            queryset = queryset.filter(profile__user_type=user_type)
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
                    profile__user_type=UserProfile.UserType.IDENTITY,
                    then=F("first_name"),
                ),
                default=F("email"),
                output_field=CharField(),
            ),
            subject_email=Case(
                When(
                    profile__user_type=UserProfile.UserType.IDENTITY,
                    then=Value(None),
                ),
                default=F("email"),
                output_field=CharField(),
            ),
            subject_user_type=F("profile__user_type"),
            subject_role_uid=Case(
                When(
                    profile__user_type=UserProfile.UserType.IDENTITY,
                    then=Subquery(
                        WorkspaceUser.objects_and_identities.filter(
                            user_id=OuterRef("pk")
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
            "subject_user_type",
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

        memberships = _memberships(include_trash)
        if not include_trash:
            memberships = memberships.filter(user__profile__trashed=False)
        return dict(
            memberships.filter(
                workspace=workspace,
                user_id__in=[subject.id for subject in subjects],
            ).values_list("user_id", "permissions")
        )

    def is_workspace_role_fallback(self, role_uid: str) -> bool:
        return role_uid == getattr(
            settings, "NO_ROLE_LOW_PRIORITY_UID", "NO_ROLE_LOW_PRIORITY"
        )

    def are_workspace_roles_available(self, subjects, workspace):
        from baserow.core.identities.registries import identity_extension_type_registry

        identities = [subject for subject in subjects if is_identity(subject)]
        if not identities:
            return [True] * len(subjects)
        roles = self.get_workspace_role_uids(identities, workspace, include_trash=True)
        available = {
            uid: identity_extension_type_registry.role_uid_exists(uid, workspace)
            for uid in set(roles.values())
        }
        return [
            not is_identity(subject) or available.get(roles.get(subject.id), False)
            for subject in subjects
        ]

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        # Loads missing profiles in one query, keeping those already loaded.
        prefetch_related_objects(list(subjects), "profile")
        prefetched = getattr(workspace, "_prefetched_objects_cache", {})
        if (
            not include_trash
            and "workspaceuser_set" in prefetched
            and all(is_human(subject) for subject in subjects)
        ):
            # The prefetch only holds humans, so it can't answer for an identity.
            user_ids = {
                membership.user_id for membership in workspace.workspaceuser_set.all()
            }
            missing = {subject.id for subject in subjects} - user_ids
            if missing:
                user_ids.update(
                    WorkspaceUser.objects.filter(
                        workspace=workspace, user_id__in=missing
                    ).values_list("user_id", flat=True)
                )
            return [
                subject.id in user_ids
                and subject.is_active
                and not subject.profile.to_be_deleted
                for subject in subjects
            ]

        # Reused tool contexts can hold stale users, so eligibility is re-read.
        current_user_types = dict(
            _memberships(include_trash)
            .filter(
                Q(user__profile__user_type=UserProfile.UserType.HUMAN)
                | Q(
                    user__profile__user_type=UserProfile.UserType.IDENTITY,
                    user__profile__trashed=False,
                    workspace__trashed=False,
                ),
                workspace=workspace,
                user_id__in=[subject.id for subject in subjects],
                user__is_active=True,
                user__profile__to_be_deleted=False,
            )
            .values_list("user_id", "user__profile__user_type")
        )

        identity_ids = [subject.id for subject in subjects if is_identity(subject)]
        # Include trashed memberships: extra memberships must not expand identity scope.
        identity_memberships = (
            dict(
                WorkspaceUser.objects_and_identities.filter(user_id__in=identity_ids)
                .values("user_id")
                .annotate(count=Count("id"))
                .values_list("user_id", "count")
            )
            if identity_ids
            else {}
        )
        return [
            (
                is_human(subject)
                and current_user_types.get(subject.id) == UserProfile.UserType.HUMAN
            )
            or (
                is_identity(subject)
                and current_user_types.get(subject.id) == UserProfile.UserType.IDENTITY
                and identity_memberships.get(subject.id) == 1
            )
            for subject in subjects
        ]

    def get_serializer(self, model_instance, **kwargs):
        from baserow.api.user.serializers import SubjectUserSerializer

        return SubjectUserSerializer(model_instance, **kwargs)

    def get_users_included_in_subject(
        self, subject: AbstractUser
    ) -> List[AbstractUser]:
        return [subject] if is_human(subject) else []


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
