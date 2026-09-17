from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import JSONField, OuterRef, Value
from django.db.models.functions import JSONObject

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.core.agents.registries import AgentExtension
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import RBAC, TEAMS
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.models import Team, TeamSubject
from baserow_enterprise.teams.operations import (
    CreateTeamSubjectOperationType,
    DeleteTeamSubjectOperationType,
)
from baserow_premium.license.handler import LicenseHandler


class AgentTeamSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


@extend_schema_field(AgentTeamSummarySerializer(many=True))
class AgentTeamsField(serializers.Field):
    def to_representation(self, agent):
        # Enhanced list querysets only set this annotation after checking the
        # workspace license once. Read it first to avoid one cache read per agent;
        # standalone agents fall through to the explicit license check below.
        if hasattr(agent, "_agent_teams"):
            return agent._agent_teams
        if not LicenseHandler.workspace_has_feature(TEAMS, agent.workspace):
            return []
        return list(
            Team.objects.filter(
                subjects__subject_type=ContentType.objects.get_for_model(Agent),
                subjects__subject_id=agent.id,
            ).values("id", "name")
        )


class EnterpriseAgentExtension(AgentExtension):
    type = "enterprise_teams"
    request_fields = {
        "team_ids": serializers.ListField(
            child=serializers.IntegerField(), required=False
        )
    }
    response_fields = {"teams": AgentTeamsField(source="*", read_only=True)}

    def enhance_queryset(self, queryset, workspace):
        """Load team summaries with the Agents instead of querying each Agent."""

        if not LicenseHandler.workspace_has_feature(TEAMS, workspace):
            # Keep the annotation so serialization does not repeat the feature
            # check for every agent in a disabled workspace.
            return queryset.annotate(_agent_teams=Value([], output_field=JSONField()))
        teams = (
            Team.objects.filter(
                subjects__subject_type=ContentType.objects.get_for_model(Agent),
                subjects__subject_id=OuterRef("pk"),
            )
            .annotate(summary=JSONObject(id="id", name="name"))
            .values("summary")
        )
        return queryset.annotate(_agent_teams=ArraySubquery(teams))

    def role_uid_exists(self, role_uid, workspace):
        """Validate selectable roles using the same aliases as role resolution."""
        if not LicenseHandler.workspace_has_feature(RBAC, workspace):
            return role_uid in {"ADMIN", "MEMBER"}
        # Use the permission resolver so aliases such as MEMBER -> BUILDER have
        # the same meaning during validation and permission checks.
        try:
            role = RoleAssignmentHandler().get_role_by_uid(role_uid)
        except Role.DoesNotExist:
            return False
        return not role.hidden and role.workspace_id in (None, workspace.id)

    def get_default_role_uid(self, workspace):
        if LicenseHandler.workspace_has_feature(RBAC, workspace):
            return "NO_ACCESS"
        return None

    def _sync_teams(self, agent, team_ids, user):
        """Authorize all membership changes before replacing an agent's teams."""

        if team_ids is None:
            return
        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, agent.workspace)
        teams = list(
            Team.objects.filter(id__in=set(team_ids), workspace=agent.workspace)
        )
        if len(teams) != len(set(team_ids)):
            raise ValidationError(
                {"team_ids": "Every team must belong to the agent's workspace."}
            )
        subject_type = ContentType.objects.get_for_model(Agent)
        memberships = list(
            TeamSubject.objects.filter(
                subject_type=subject_type, subject_id=agent.id
            ).select_related("team__workspace")
        )
        existing_ids = {membership.team_id for membership in memberships}
        added_teams = [team for team in teams if team.id not in existing_ids]
        removed_memberships = [
            membership
            for membership in memberships
            if membership.team_id not in team_ids
        ]
        # Match the team-subject endpoints' scopes and authorize the whole diff
        # before writing. Retained memberships require no extra permissions.
        checks = [
            PermissionCheck(user, CreateTeamSubjectOperationType.type, team)
            for team in added_teams
        ] + [
            PermissionCheck(user, DeleteTeamSubjectOperationType.type, membership)
            for membership in removed_memberships
        ]
        CoreHandler().check_multiple_permissions(
            checks, workspace=agent.workspace, raise_exception=True
        )
        TeamSubject.objects.filter(
            id__in=[membership.id for membership in removed_memberships]
        ).delete()
        TeamSubject.objects.bulk_create(
            [TeamSubject(team=team, subject=agent) for team in added_teams]
        )

    def create(self, agent, values, user):
        self._sync_teams(agent, values.get("team_ids"), user)

    def update(self, agent, values, user):
        self._sync_teams(agent, values.get("team_ids"), user)
