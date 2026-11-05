from typing import List

from django.contrib.auth.models import AbstractUser, AnonymousUser

from baserow.core.models import Workspace
from baserow.core.subject.registries import SubjectType
from baserow.core.types import Subject


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
