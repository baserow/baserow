from typing import Any

from django.db import IntegrityError
from django.db.models import QuerySet

from baserow.core.models import Workspace
from baserow.core.utils import extract_allowed

from .exceptions import WorkspaceSkillDoesNotExist, WorkspaceSkillNameNotUnique
from .models import WorkspaceSkill


class WorkspaceSkillHandler:
    allowed_fields = ("name", "description", "content")

    def get_queryset(self, workspace: Workspace) -> QuerySet[WorkspaceSkill]:
        return WorkspaceSkill.objects.filter(workspace=workspace).select_related(
            "workspace"
        )

    def get_skill(self, skill_id: int, base_queryset=None) -> WorkspaceSkill:
        queryset = (
            base_queryset
            if base_queryset is not None
            else WorkspaceSkill.objects.select_related("workspace")
        )
        try:
            return queryset.get(id=skill_id)
        except WorkspaceSkill.DoesNotExist:
            raise WorkspaceSkillDoesNotExist(
                f"The skill with id {skill_id} does not exist."
            )

    def create_skill(
        self, workspace: Workspace, created_by=None, **values: Any
    ) -> WorkspaceSkill:
        allowed = extract_allowed(values, self.allowed_fields)
        try:
            return WorkspaceSkill.objects.create(
                workspace=workspace, created_by=created_by, **allowed
            )
        except IntegrityError:
            raise WorkspaceSkillNameNotUnique()

    def update_skill(self, skill: WorkspaceSkill, **values: Any) -> WorkspaceSkill:
        allowed = extract_allowed(values, self.allowed_fields)
        for key, value in allowed.items():
            setattr(skill, key, value)
        try:
            skill.save(update_fields=list(allowed.keys()) + ["updated_on"])
        except IntegrityError:
            raise WorkspaceSkillNameNotUnique()
        return skill

    def delete_skill(self, skill: WorkspaceSkill) -> None:
        skill.delete()
