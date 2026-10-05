from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace

from .handler import WorkspaceSkillHandler
from .models import WorkspaceSkill
from .operations import (
    CreateWorkspaceSkillOperationType,
    DeleteWorkspaceSkillOperationType,
    ListWorkspaceSkillsOperationType,
    UpdateWorkspaceSkillOperationType,
)
from .signals import skill_created, skill_deleted, skill_updated


class WorkspaceSkillService:
    """Permission-aware operations on workspace skills."""

    def list_skills(self, user: AbstractUser, workspace: Workspace):
        CoreHandler().check_permissions(
            user,
            ListWorkspaceSkillsOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        return WorkspaceSkillHandler().get_queryset(workspace)

    def get_skill(self, user: AbstractUser, skill_id: int) -> WorkspaceSkill:
        skill = WorkspaceSkillHandler().get_skill(skill_id)
        CoreHandler().check_permissions(
            user,
            ListWorkspaceSkillsOperationType.type,
            workspace=skill.workspace,
            context=skill.workspace,
        )
        return skill

    def create_skill(
        self, user: AbstractUser, workspace: Workspace, **values: Any
    ) -> WorkspaceSkill:
        CoreHandler().check_permissions(
            user,
            CreateWorkspaceSkillOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        skill = WorkspaceSkillHandler().create_skill(
            workspace, created_by=user, **values
        )
        skill_created.send(self, skill=skill, user=user)
        return skill

    @transaction.atomic
    def update_skill(
        self, user: AbstractUser, skill: WorkspaceSkill, **values: Any
    ) -> WorkspaceSkill:
        CoreHandler().check_permissions(
            user,
            UpdateWorkspaceSkillOperationType.type,
            workspace=skill.workspace,
            context=skill.workspace,
        )
        skill = WorkspaceSkillHandler().update_skill(skill, **values)
        skill_updated.send(self, skill=skill, user=user)
        return skill

    @transaction.atomic
    def delete_skill(self, user: AbstractUser, skill: WorkspaceSkill) -> None:
        CoreHandler().check_permissions(
            user,
            DeleteWorkspaceSkillOperationType.type,
            workspace=skill.workspace,
            context=skill.workspace,
        )
        skill_id, workspace = skill.id, skill.workspace
        WorkspaceSkillHandler().delete_skill(skill)
        skill_deleted.send(self, skill_id=skill_id, workspace=workspace, user=user)
