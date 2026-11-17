from collections import defaultdict
from collections.abc import Callable
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
    Q,
    QuerySet,
    Value,
    When,
)
from django.db.models.functions import Cast

from baserow.core.identities.registries import identity_extension_type_registry
from baserow.core.identities.signals import identity_updated
from baserow.core.models import User, UserProfile, Workspace, WorkspaceUser
from baserow.core.operations import ListWorkspaceUsersWorkspaceOperationType
from baserow.core.registries import SubjectType
from baserow.core.types import Subject
from baserow.core.user.identity import (
    active_identity_q,
    is_identity,
    load_user_types,
)


def _memberships(include_trash: bool) -> QuerySet[WorkspaceUser]:
    """
    Returns the memberships of users and identities that permission checks consider.

    :param include_trash: Whether memberships in trashed workspaces are included.
    :return: The membership queryset.
    """

    manager = (
        WorkspaceUser.objects_and_identities_and_trash
        if include_trash
        else WorkspaceUser.objects_and_identities
    )
    return manager.all()


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
    """
    The type that people and identities are stored under. What differs between them
    lives in `HumanSubjectType` and `IdentitySubjectType`, which override every method
    this class forwards. `get_specific_type` is the only place that tells them apart.
    """

    type = "auth.User"
    model_class = User
    display_name_field = "first_name"
    lookup_fields = (*SubjectType.lookup_fields, "email")
    options_list_operation_type = ListWorkspaceUsersWorkspaceOperationType.type

    has_direct_workspace_roles = True

    @property
    def is_interactive_user(self) -> bool:
        # It differs per subject, so an answer here would be wrong for one of them.
        raise NotImplementedError(
            "Read it from subject_type_registry.get_specific_type(subject)."
        )

    def get_specific_type(self, subject: AbstractUser) -> "UserSubjectType":
        return identity_subject_type if is_identity(subject) else human_subject_type

    def _ask_specific_types(
        self,
        subjects: List[AbstractUser],
        ask: Callable[["UserSubjectType", List[AbstractUser]], List[bool]],
    ) -> List[bool]:
        """
        Asks each specific type about its own subjects.

        :param subjects: The people and identities to ask about.
        :param ask: Returns the answers of one specific type for its subjects.
        :return: One answer per subject, in the order of the given subjects.
        """

        load_user_types(subjects)
        subjects_per_type = defaultdict(list)
        for subject in subjects:
            subjects_per_type[self.get_specific_type(subject)].append(subject)
        answers = {}
        for specific_type, type_subjects in subjects_per_type.items():
            answers.update(
                zip(
                    (subject.id for subject in type_subjects),
                    ask(specific_type, type_subjects),
                    strict=True,
                )
            )
        return [answers[subject.id] for subject in subjects]

    def track_usage(self, subject: AbstractUser) -> None:
        self.get_specific_type(subject).track_usage(subject)

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

        self.get_specific_type(subject).set_workspace_role_uid(
            subject, workspace, role_uid, send_signals=send_signals
        )

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
        return self.get_specific_type(subject).get_label(subject)

    def get_options_queryset(
        self,
        workspace: Workspace | None = None,
        search: str = "",
        exclude_ids: List[int] | None = None,
        include_inactive_and_scheduled_for_deletion: bool = False,
    ):
        """Return searchable user options, optionally scoped to a workspace."""

        queryset = User.objects_and_identities.exclude(id__in=exclude_ids or [])
        if not include_inactive_and_scheduled_for_deletion:
            queryset = queryset.filter(
                is_active=True, profile__to_be_deleted=False, profile__trashed=False
            )
        if workspace is not None:
            queryset = queryset.filter(workspaceuser__workspace=workspace)
        if search:
            # The email and username of an identity are an internal key.
            is_person = ~Q(profile__user_type=UserProfile.UserType.IDENTITY)
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | is_person
                & (Q(username__icontains=search) | Q(email__icontains=search))
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
            subject_count=Cast(Value(None), output_field=IntegerField()),
        ).values(
            "subject_id",
            "subject_type",
            "subject_name",
            "subject_label",
            "subject_email",
            "subject_count",
            "subject_user_type",
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

    def are_workspace_roles_available(
        self, subjects: List[AbstractUser], workspace: Workspace
    ) -> List[bool]:
        return self._ask_specific_types(
            subjects,
            lambda specific_type, type_subjects: (
                specific_type.are_workspace_roles_available(type_subjects, workspace)
            ),
        )

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        return self._ask_specific_types(
            subjects,
            lambda specific_type, type_subjects: specific_type.are_in_workspace(
                type_subjects, workspace, include_trash=include_trash
            ),
        )

    def get_serializer(self, model_instance, **kwargs):
        from baserow.api.user.serializers import SubjectUserSerializer

        return SubjectUserSerializer(model_instance, **kwargs)

    def get_users_included_in_subject(
        self, subject: AbstractUser
    ) -> List[AbstractUser]:
        return self.get_specific_type(subject).get_users_included_in_subject(subject)


class HumanSubjectType(UserSubjectType):
    """Holds what is specific to a person."""

    is_interactive_user = True

    def get_specific_type(self, subject: AbstractUser) -> "HumanSubjectType":
        return self

    def track_usage(self, subject: AbstractUser) -> None:
        pass

    def set_workspace_role_uid(
        self,
        subject: AbstractUser,
        workspace: Workspace,
        role_uid: str,
        send_signals: bool = True,
    ) -> None:
        from baserow.core.handler import CoreHandler

        workspace_user = workspace.get_workspace_user(subject)
        CoreHandler().force_update_workspace_user(
            None,
            workspace_user,
            permissions=CoreHandler.get_stored_workspace_role_uid(role_uid),
        )

    def get_label(self, subject: AbstractUser) -> str:
        return subject.email

    def are_workspace_roles_available(
        self, subjects: List[AbstractUser], workspace: Workspace
    ) -> List[bool]:
        return [True] * len(subjects)

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        prefetched = getattr(workspace, "_prefetched_objects_cache", {})
        if not include_trash and "workspaceuser_set" in prefetched:
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

        memberships = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        # Reused tool contexts can hold stale users, so eligibility is re-read.
        user_ids = set(
            memberships.filter(
                workspace=workspace,
                user_id__in=[subject.id for subject in subjects],
                user__is_active=True,
                user__profile__to_be_deleted=False,
            ).values_list("user_id", flat=True)
        )
        return [subject.id in user_ids for subject in subjects]

    def get_users_included_in_subject(
        self, subject: AbstractUser
    ) -> List[AbstractUser]:
        return [subject]


class IdentitySubjectType(UserSubjectType):
    """Holds what is specific to an identity."""

    is_interactive_user = False
    # The email of an identity is an internal key, so nobody selects it by email.
    lookup_fields = SubjectType.lookup_fields

    def get_specific_type(self, subject: AbstractUser) -> "IdentitySubjectType":
        return self

    def track_usage(self, subject: AbstractUser) -> None:
        from baserow.core.identities.handler import IdentityHandler

        IdentityHandler().update_last_active(subject)

    def set_workspace_role_uid(
        self,
        subject: AbstractUser,
        workspace: Workspace,
        role_uid: str,
        send_signals: bool = True,
    ) -> None:
        from baserow.core.identities.handler import IdentityHandler

        # Fails when the identity is not in this workspace, as it does for a person.
        workspace.get_workspace_user(subject)
        IdentityHandler().update_identity(subject, role_uid=role_uid)
        if send_signals:
            identity_updated.send(self, user=None, identity=subject)

    def get_label(self, subject: AbstractUser) -> str:
        return subject.first_name

    def are_workspace_roles_available(
        self, subjects: List[AbstractUser], workspace: Workspace
    ) -> List[bool]:
        roles = self.get_workspace_role_uids(subjects, workspace, include_trash=True)
        available = {
            uid: identity_extension_type_registry.role_uid_exists(uid, workspace)
            for uid in set(roles.values())
        }
        return [available.get(roles.get(subject.id), False) for subject in subjects]

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        # A trashed workspace never authorizes an identity, even with include_trash.
        active_here = Q(workspace=workspace, workspace__trashed=False)
        # Memberships in trashed workspaces count: a second one must not add scope.
        identity_ids = set(
            WorkspaceUser.objects_and_identities_and_trash.filter(
                user_id__in=[subject.id for subject in subjects]
            )
            .values("user_id")
            .annotate(
                memberships=Count("id"),
                active_memberships=Count(
                    "id", filter=active_here & active_identity_q("user__")
                ),
            )
            .filter(memberships=1, active_memberships=1)
            .values_list("user_id", flat=True)
        )
        return [subject.id in identity_ids for subject in subjects]

    def get_users_included_in_subject(
        self, subject: AbstractUser
    ) -> List[AbstractUser]:
        return []


human_subject_type = HumanSubjectType()
identity_subject_type = IdentitySubjectType()


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
