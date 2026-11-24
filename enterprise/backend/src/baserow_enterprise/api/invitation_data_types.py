from typing import Dict, List

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.api.workspaces.invitations.registries import InvitationDataType
from baserow.core.models import Workspace
from baserow_enterprise.role.handler import (
    RoleAssignmentHandler,
    get_assignable_scope_type,
)
from baserow_enterprise.teams.handler import TeamHandler


class InvitationScopeSerializer(serializers.Serializer):
    scope_type = serializers.CharField(
        help_text="The type of the object the role is granted on, for example "
        "`application`, `database_table` or `database_view`."
    )
    scope_id = serializers.IntegerField(
        help_text="The ID of the object the role is granted on."
    )
    name = serializers.CharField(help_text="The name of the object.")
    role = serializers.CharField(
        help_text="The uid of the role granted on the object once the invitation "
        "is accepted."
    )


class InvitationTeamSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="The ID of the team.")
    name = serializers.CharField(help_text="The name of the team.")


class EnterpriseInvitationScopesDataType(InvitationDataType):
    type = "scopes"

    def get_serializer_field(self) -> serializers.Field:
        return InvitationScopeSerializer(
            many=True,
            required=False,
            help_text="Enterprise or advanced only: the applications, tables and "
            "views the invitation grants a role on once accepted, limited to the "
            "ones whose roles the requesting user may read.",
        )

    def annotate_serialized_workspace_invitations_data(
        self,
        workspace: Workspace,
        serialized_data: List[Dict],
        user: AbstractUser,
    ) -> List[Dict]:
        scoped_invitations = RoleAssignmentHandler().get_readable_scoped_invitations(
            user, workspace, [invitation["id"] for invitation in serialized_data]
        )
        for invitation in serialized_data:
            invitation[self.type] = [
                {
                    "scope_type": get_assignable_scope_type(scope).type,
                    "scope_id": scope.id,
                    "name": scope.name,
                    "role": scoped_invitation.role.uid,
                }
                for scoped_invitation, scope in scoped_invitations.get(
                    invitation["id"], []
                )
            ]
        return serialized_data


class EnterpriseInvitationTeamsDataType(InvitationDataType):
    type = "teams"

    def get_serializer_field(self) -> serializers.Field:
        return InvitationTeamSerializer(
            many=True,
            required=False,
            help_text="Enterprise or advanced only: the teams the person joins once "
            "the invitation is accepted, limited to the ones the requesting user "
            "may read.",
        )

    def annotate_serialized_workspace_invitations_data(
        self,
        workspace: Workspace,
        serialized_data: List[Dict],
        user: AbstractUser,
    ) -> List[Dict]:
        teams = TeamHandler().get_readable_invited_teams(
            user, workspace, [invitation["id"] for invitation in serialized_data]
        )
        for invitation in serialized_data:
            invitation[self.type] = [
                {"id": team.id, "name": team.name}
                for team in teams.get(invitation["id"], [])
            ]
        return serialized_data
