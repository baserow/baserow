from typing import List

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.preview import BuilderPreviewActor
from baserow.core.models import Workspace
from baserow.core.registries import SubjectType
from baserow.core.types import Subject


class BuilderPreviewActorSubjectType(SubjectType):
    type = "builder_preview_actor"
    model_class = BuilderPreviewActor

    def are_in_workspace(
        self, subjects: List[Subject], workspace: Workspace
    ) -> List[bool]:
        return [subject.workspace_id == workspace.id for subject in subjects]

    def get_serializer(self, model_instance, **kwargs):
        return None

    def get_users_included_in_subject(
        self, subject: BuilderPreviewActor
    ) -> List[AbstractUser]:
        return []
