from collections import defaultdict

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from baserow.contrib.agent.operations import (
    ApproveAgentToolCallsOperationType,
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
)
from baserow.core.exceptions import PermissionDenied
from baserow.core.registries import PermissionManagerType
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
}


class AgentParticipationPermissionManager(PermissionManagerType):
    type = "agent_participation"
    supported_actor_types = [UserSubjectType.type]

    def check_multiple_permissions(self, checks, workspace=None, include_trash=False):
        checks = [check for check in checks if check.operation_name in CAPABILITY]
        if (
            not checks
            or not workspace
            or not RolePermissionManagerType().is_enabled(workspace)
        ):
            return {}
        rules = AgentParticipationRule.objects.filter(
            agent__workspace=workspace, agent_id__in={c.context.pk for c in checks}
        ).prefetch_related("users", "teams")
        by_capability = {(rule.agent_id, rule.capability): rule for rule in rules}
        if not by_capability:
            return {}
        checks = [
            c
            for c in checks
            if (c.context.pk, CAPABILITY[c.operation_name]) in by_capability
        ]
        if not checks:
            return {}
        actors = {check.actor for check in checks}
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
        denied = {}
        scope_cache = {}
        for check in checks:
            rule = by_capability[check.context.pk, CAPABILITY[check.operation_name]]
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
                denied[check] = PermissionDenied()
        return denied

    def get_permissions_object(self, actor, workspace=None):
        if not workspace or not RolePermissionManagerType().is_enabled(workspace):
            return None
        checks = [
            PermissionCheck(actor, operation, rule.agent)
            for rule in AgentParticipationRule.objects.filter(
                agent__workspace=workspace
            ).select_related("agent")
            for operation, capability in CAPABILITY.items()
            if capability == rule.capability
        ]
        denied = defaultdict(list)
        for check in self.check_multiple_permissions(checks, workspace):
            denied[check.operation_name].append(check.context.pk)
        return dict(denied) or None
