from typing import List

from django.contrib.auth.models import AbstractUser

from baserow.core.models import Workspace
from baserow.core.registries import SubjectType
from baserow.core.types import Subject
from baserow.core.user_sources.user_source_user import UserSourceUser


class UserSourceUserSubjectType(SubjectType):
    """
    The user source user subject.
    """

    type = "user_source.user"
    model_class = UserSourceUser

    def get_display_name(self, subject: UserSourceUser) -> str:
        return subject.username

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        """
        Check whether the given subjects are member of the given workspace.
        """

        return [False for _ in subjects]

    def get_serializer(self, model_instance, **kwargs):
        return None

    def get_users_included_in_subject(
        self, subject: AbstractUser
    ) -> List[AbstractUser]:
        return [subject]
