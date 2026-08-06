from typing import List

from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.utils.translation import gettext_lazy as _

from baserow.core.models import User, Workspace, WorkspaceUser
from baserow.core.registries import SubjectType
from baserow.core.types import Subject


class UserSubjectType(SubjectType):
    type = "auth.User"
    model_class = User
    is_interactive_user = True
    display_name_field = "first_name"

    def get_type_display_name(self):
        return _("User")

    def get_display_name(self, subject: AbstractUser) -> str:
        return subject.first_name

    def get_queryset(self, workspace_id=None):
        queryset = User.objects.all()
        if workspace_id is not None:
            queryset = queryset.filter(workspaceuser__workspace_id=workspace_id)
        return queryset.order_by("email")

    def get_label(self, subject: AbstractUser) -> str:
        return subject.email

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

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        """
        Check whether the given subjects ar member of the given workspace.
        """

        workspace_user_manager = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        user_ids_in_workspace = workspace_user_manager.filter(
            user__in=subjects,
            workspace=workspace,
            user__profile__to_be_deleted=False,
            user__is_active=True,
        ).values_list("user_id", flat=True)

        return [s.id in user_ids_in_workspace for s in subjects]

    def get_serializer(self, model_instance, **kwargs):
        from baserow.api.user.serializers import SubjectUserSerializer

        return SubjectUserSerializer(model_instance, **kwargs)

    def get_users_included_in_subject(
        self, subject: AbstractUser
    ) -> List[AbstractUser]:
        return [subject]


class AnonymousUserSubjectType(SubjectType):
    type = "anonymous"
    model_class = AnonymousUser

    def get_type_display_name(self):
        return _("Anonymous user")

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
