from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.core.agents.registries import AgentExtension
from baserow.core.models import Agent
from baserow_enterprise.features import RBAC, TEAMS
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.models import Team, TeamSubject
from baserow_premium.license.handler import LicenseHandler


class AgentTeamsField(serializers.Field):
    def to_representation(self, agent):
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

    def role_uid_exists(self, role_uid, workspace):
        if not LicenseHandler.workspace_has_feature(RBAC, workspace):
            return role_uid in {"ADMIN", "MEMBER"}
        return (
            Role.objects.filter(uid=role_uid, hidden=False)
            .filter(Q(workspace__isnull=True) | Q(workspace=workspace))
            .exists()
        )

    def get_default_role_uid(self, workspace):
        if LicenseHandler.workspace_has_feature(RBAC, workspace):
            return "NO_ACCESS"
        return None

    def _sync_teams(self, agent, team_ids, user):
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
        TeamSubject.objects.filter(
            subject_type=subject_type, subject_id=agent.id
        ).exclude(team_id__in=team_ids).delete()
        existing_ids = set(
            TeamSubject.objects.filter(
                subject_type=subject_type,
                subject_id=agent.id,
                team_id__in=team_ids,
            ).values_list("team_id", flat=True)
        )
        TeamSubject.objects.bulk_create(
            [
                TeamSubject(team=team, subject=agent)
                for team in teams
                if team.id not in existing_ids
            ]
        )

    def create(self, agent, values, user):
        self._sync_teams(agent, values.get("team_ids"), user)

    def update(self, agent, values, user):
        self._sync_teams(agent, values.get("team_ids"), user)

    def before_delete(self, agent, user):
        TeamSubject.objects.filter(
            subject_type=ContentType.objects.get_for_model(Agent),
            subject_id=agent.id,
        ).delete()
