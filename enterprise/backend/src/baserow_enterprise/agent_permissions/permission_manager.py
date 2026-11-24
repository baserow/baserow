from collections import defaultdict
from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType

from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.agent.operations import (
    ApproveAgentToolCallsOperationType,
    ContinueAgentTriggeredConversationOperationType,
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
)
from baserow.contrib.agent.permission_manager import (
    AgentParticipationPermissionManagerType as CoreAgentParticipationPermissionManagerType,
)
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.operations import ListApplicationsWorkspaceOperationType
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck
from baserow_enterprise.field_permissions.permission_manager import ALLOWED_ROLES_MAP
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.permission_manager import RolePermissionManagerType
from baserow_enterprise.teams.models import TeamSubject

from .models import AgentParticipationRule

CAPABILITY = {
    CreateAgentConversationOperationType.type: AgentParticipationRule.Capability.CHAT,
    CreateAgentMessageOperationType.type: AgentParticipationRule.Capability.CHAT,
    ApproveAgentToolCallsOperationType.type: AgentParticipationRule.Capability.APPROVE,
    ContinueAgentTriggeredConversationOperationType.type: (
        AgentParticipationRule.Capability.CONTINUE
    ),
}

# No role includes their operations, so only a rule can grant them.
GRANTED_BY_RULE = {AgentParticipationRule.Capability.CONTINUE}


class AgentParticipationPermissionManagerType(
    CoreAgentParticipationPermissionManagerType
):
    """
    Applies an agent's participation rules when the workspace has RBAC, and the
    core behaviour otherwise. Chat and approve rules only narrow what roles allow.
    Continue rules decide every check, denying it without a rule.
    """

    def check_multiple_permissions(
        self,
        checks: list[PermissionCheck],
        workspace: Optional[Workspace] = None,
        include_trash: bool = False,
    ) -> dict[PermissionCheck, bool | PermissionDenied]:
        """
        Decide the checks of agent operations that have a participation rule, and
        every continue check.

        :param checks: The checks to decide.
        :param workspace: The workspace of the checks.
        :param include_trash: Whether trashed roles count.
        :return: A denial, or True for an allowed continue check, by check.
        """

        if not workspace or not RolePermissionManagerType().is_enabled(workspace):
            return super().check_multiple_permissions(checks, workspace, include_trash)
        checks = [check for check in checks if check.operation_name in CAPABILITY]
        if not checks:
            return {}
        rules = AgentParticipationRule.objects.filter(
            agent__workspace=workspace, agent_id__in={c.context.pk for c in checks}
        ).prefetch_related("users", "teams")
        by_capability = {(rule.agent_id, rule.capability): rule for rule in rules}
        result = {}
        ruled_checks = []
        for check in checks:
            if (check.context.pk, CAPABILITY[check.operation_name]) in by_capability:
                ruled_checks.append(check)
            elif CAPABILITY[check.operation_name] in GRANTED_BY_RULE:
                result[check] = PermissionDenied()
        if not ruled_checks:
            return result
        actors = {check.actor for check in ruled_checks}
        role_handler = RoleAssignmentHandler()
        roles = role_handler.get_roles_per_scope_for_actors(
            workspace, UserSubjectType(), actors, include_trash=include_trash
        )
        teams_by_user = defaultdict(set)
        selected = {}
        for rule in by_capability.values():
            if rule.role == "CUSTOM":
                selected[rule.pk] = (
                    {user.pk for user in rule.users.all()},
                    {team.pk for team in rule.teams.all()},
                )
        if selected:
            memberships = TeamSubject.objects.filter(
                team__workspace=workspace,
                team__trashed=False,
                subject_type=ContentType.objects.get_for_model(get_user_model()),
                subject_id__in=[user.pk for user in actors],
            )
            for user_id, team_id in memberships.values_list("subject_id", "team_id"):
                teams_by_user[user_id].add(team_id)
        scope_cache = {}
        for check in ruled_checks:
            capability = CAPABILITY[check.operation_name]
            rule = by_capability[check.context.pk, capability]
            threshold = rule.role
            if threshold == "CUSTOM":
                users, teams = selected[rule.pk]
                threshold = (
                    "EDITOR"
                    if check.actor.pk in users
                    or teams.intersection(teams_by_user[check.actor.pk])
                    else "NOBODY"
                )
            allowed_roles = ALLOWED_ROLES_MAP.get(threshold, set())
            if not allowed_roles or not any(
                role.uid in allowed_roles
                for role in role_handler.get_computed_roles(
                    roles[check.actor], check.context, scope_cache
                )
            ):
                result[check] = PermissionDenied()
            elif capability in GRANTED_BY_RULE:
                result[check] = True
        return result

    def get_permissions_object(
        self, actor: AbstractUser, workspace: Optional[Workspace] = None
    ) -> Optional[dict[str, dict[str, list[int]]]]:
        """
        :param actor: The actor to describe permissions for.
        :param workspace: The workspace of the agents.
        :return: The core manager's object, computed from the rules of the agents
            the actor may list when the workspace has RBAC.
        """

        if not workspace or not RolePermissionManagerType().is_enabled(workspace):
            return super().get_permissions_object(actor, workspace)
        listed_agents = CoreHandler().filter_queryset(
            actor,
            ListApplicationsWorkspaceOperationType.type,
            AgentApplication.objects.filter(workspace=workspace, trashed=False),
            workspace=workspace,
        )
        checks = [
            PermissionCheck(actor, operation, rule.agent)
            for rule in AgentParticipationRule.objects.filter(
                agent__in=listed_agents
            ).select_related("agent")
            for operation, capability in CAPABILITY.items()
            if capability == rule.capability
        ]
        denied = defaultdict(list)
        allowed = {
            operation: []
            for operation, capability in CAPABILITY.items()
            if capability in GRANTED_BY_RULE
        }
        for check, outcome in self.check_multiple_permissions(
            checks, workspace
        ).items():
            if outcome is True:
                allowed[check.operation_name].append(check.context.pk)
            elif CAPABILITY[check.operation_name] not in GRANTED_BY_RULE:
                denied[check.operation_name].append(check.context.pk)
        return {"denied": dict(denied), "allowed": allowed}
