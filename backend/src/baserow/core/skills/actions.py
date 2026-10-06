from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import ActionType, ActionTypeDescription
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    WorkspaceActionScopeType,
)
from baserow.core.models import Workspace

from .models import WorkspaceSkill
from .service import WorkspaceSkillService


class _SkillActionType(ActionType):
    @dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        skill_id: int
        skill_name: str

    @classmethod
    def _register(cls, user: AbstractUser, workspace: Workspace, skill_id, name):
        cls.register_action(
            user=user,
            params=cls.Params(workspace.id, workspace.name, skill_id, name),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )

    @classmethod
    def scope(cls, workspace_id):
        return WorkspaceActionScopeType.value(workspace_id)


class CreateWorkspaceSkillActionType(_SkillActionType):
    type = "create_workspace_skill"
    description = ActionTypeDescription(
        _("Create skill"),
        _('Skill "%(skill_name)s" (%(skill_id)s) created'),
        WORKSPACE_ACTION_CONTEXT,
    )

    @classmethod
    def do(cls, user: AbstractUser, workspace: Workspace, **values) -> WorkspaceSkill:
        skill = WorkspaceSkillService().create_skill(user, workspace, **values)
        cls._register(user, workspace, skill.id, skill.name)
        return skill


class UpdateWorkspaceSkillActionType(_SkillActionType):
    type = "update_workspace_skill"
    description = ActionTypeDescription(
        _("Update skill"),
        _('Skill "%(skill_name)s" (%(skill_id)s) updated'),
        WORKSPACE_ACTION_CONTEXT,
    )

    @classmethod
    def do(cls, user: AbstractUser, skill: WorkspaceSkill, **values) -> WorkspaceSkill:
        skill = WorkspaceSkillService().update_skill(user, skill, **values)
        cls._register(user, skill.workspace, skill.id, skill.name)
        return skill


class DeleteWorkspaceSkillActionType(_SkillActionType):
    type = "delete_workspace_skill"
    description = ActionTypeDescription(
        _("Delete skill"),
        _('Skill "%(skill_name)s" (%(skill_id)s) deleted'),
        WORKSPACE_ACTION_CONTEXT,
    )

    @classmethod
    def do(cls, user: AbstractUser, skill: WorkspaceSkill) -> None:
        workspace, skill_id, name = skill.workspace, skill.id, skill.name
        WorkspaceSkillService().delete_skill(user, skill)
        cls._register(user, workspace, skill_id, name)
