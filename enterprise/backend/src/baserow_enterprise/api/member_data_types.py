from collections import defaultdict
from typing import List, OrderedDict

from django.contrib.auth.models import AbstractUser, User
from django.contrib.contenttypes.models import ContentType

from rest_framework import serializers

from baserow.api.user.registries import MemberDataType
from baserow.core.models import Workspace
from baserow_enterprise.api.teams.serializers import (
    WorkspaceUserEnterpriseTeamSerializer,
)
from baserow_enterprise.models import TeamSubject


class EnterpriseMemberTeamsDataType(MemberDataType):
    type = "teams"

    def get_request_serializer_field(self) -> serializers.Field:
        return WorkspaceUserEnterpriseTeamSerializer(
            many=True,
            required=False,
            help_text="Enterprise only: a list of team IDs and names, which this "
            "workspace user belongs to in this workspace.",
        )

    def annotate_serialized_workspace_members_data(
        self,
        workspace: Workspace,
        serialized_data: List[OrderedDict],
        user: AbstractUser,
    ) -> List[OrderedDict]:
        """
        Responsible for annotating team data on `WorkspaceUser` responses.
        Primarily used to inform API consumers of which teams workspace members
        belong to.
        """

        subject_team_data = defaultdict(list)
        user_ct = ContentType.objects.get_for_model(User)
        subject_ids = [member["user_id"] for member in serialized_data]
        all_team_data = TeamSubject.objects.filter(
            subject_id__in=subject_ids,
            subject_type=user_ct,
            team__workspace_id=workspace.id,
            team__trashed=False,
        ).values("team_id", "team__name", "subject_id")
        for team_data in all_team_data:
            subject_team_data[team_data["subject_id"]].append(
                {"id": team_data["team_id"], "name": team_data["team__name"]}
            )

        for member in serialized_data:
            member[self.type] = subject_team_data.get(member["user_id"], [])

        return serialized_data
