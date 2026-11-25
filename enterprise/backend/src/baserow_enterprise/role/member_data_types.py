from typing import Dict, List, OrderedDict, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.api.user.registries import MemberDataType
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.operations import ListWorkspaceUsersWorkspaceOperationType
from baserow.core.registries import permission_manager_type_registry, plugin_registry
from baserow_enterprise.api.role.serializers import (
    RoleField,
    TeamWorkspaceRoleSerializer,
)
from baserow_enterprise.role.constants import (
    NO_ROLE_LOW_PRIORITY_ROLE_UID,
    ROLE_ASSIGNABLE_OBJECT_MAP,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_premium.plugins import PremiumPlugin

User = get_user_model()


class EnterpriseRolesDataType(MemberDataType):
    type = "role"

    def get_request_serializer_field(
        self,
    ) -> Union[serializers.Field, Dict[str, serializers.Field]]:
        return {
            "role_uid": RoleField(
                model=Role,
                required=False,
                allow_null=True,
                help_text=(
                    "Enterprise or advanced only: the uid of the role that is assigned "
                    "to this workspace user in this workspace."
                ),
            ),
            "highest_role_uid": RoleField(
                model=Role,
                required=False,
                allow_null=True,
                help_text=(
                    "Enterprise or advanced only: the highest role uid assigned to "
                    "this user in this workspace on anything, including roles from "
                    "teams."
                ),
            ),
        }

    def annotate_serialized_workspace_members_data(
        self,
        workspace: Workspace,
        serialized_data: List[OrderedDict],
        user: AbstractUser,
    ) -> List[OrderedDict]:
        """
        Responsible for annotating team data on `GroupUser` responses.
        Primarily used to inform API consumers of which teams workspace members
        belong to.
        """

        if (
            "role" not in settings.PERMISSION_MANAGERS
            or not permission_manager_type_registry.get("role").is_enabled(workspace)
        ):
            return serialized_data

        if not CoreHandler().check_permissions(
            user,
            ListWorkspaceUsersWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
            raise_permission_exceptions=False,
        ):
            return serialized_data

        license_plugin = plugin_registry.get_by_type(PremiumPlugin).get_license_plugin()

        usage = license_plugin.get_seat_usage_for_workspace(workspace)
        if usage:
            highest_role_per_user = usage.highest_role_per_user_id
        else:
            highest_role_per_user = None

        for member in serialized_data:
            role = RoleAssignmentHandler().get_role_by_uid(
                role_uid=member["permissions"], use_fallback=True
            )
            member["highest_role_uid"] = highest_role_per_user.get(
                member["user_id"], None
            )
            member["role_uid"] = role.uid

        return serialized_data

    def annotate_serialized_admin_users_data(
        self,
        user_ids: List[int],
        serialized_data: List[OrderedDict],
        user: AbstractUser,
    ) -> List[OrderedDict]:
        """
        Responsible for annotating team data on `GroupUser` responses.
        Primarily used to inform API consumers of which teams workspace members
        belong to.
        """

        license_plugin = plugin_registry.get_by_type(PremiumPlugin).get_license_plugin()

        usage = license_plugin.get_seat_usage_for_specific_users(user_ids)
        if usage:
            highest_role_per_user = usage.highest_role_per_user_id
            for user in serialized_data:
                user["highest_role_uid"] = highest_role_per_user.get(user["id"], None)

        return serialized_data


class EnterpriseRoleAssignmentCountDataType(MemberDataType):
    type = "role_assignment_count"

    def get_request_serializer_field(self) -> serializers.Field:
        return serializers.IntegerField(
            required=False,
            help_text=(
                "Enterprise or advanced only: the number of roles this workspace user "
                "holds on databases, tables and restricted views whose roles the "
                "requesting user may read."
            ),
        )

    def annotate_serialized_workspace_members_data(
        self,
        workspace: Workspace,
        serialized_data: List[OrderedDict],
        user: AbstractUser,
    ) -> List[OrderedDict]:
        """
        Annotates every workspace member with the number of roles they hold on
        databases, tables and restricted views, as listed by the subject role
        assignments endpoint.
        """

        users = list(
            User.objects.filter(
                id__in=[member["user_id"] for member in serialized_data]
            )
        )
        counts = RoleAssignmentHandler().count_subject_role_assignments(
            user, workspace, users
        )
        if not counts:
            return serialized_data

        count_per_user_id = {member.id: count for member, count in counts.items()}
        for member in serialized_data:
            member["role_assignment_count"] = count_per_user_id.get(
                member["user_id"], 0
            )

        return serialized_data


class EnterpriseTeamWorkspaceRoleDataType(MemberDataType):
    type = "team_workspace_role"

    def get_request_serializer_field(self) -> serializers.Field:
        return TeamWorkspaceRoleSerializer(
            required=False,
            allow_null=True,
            help_text=(
                "Enterprise or advanced only: for a member whose own workspace role "
                "is 'No role', the role they effectively hold on the workspace "
                "through their teams, and the teams it comes through. Null when no "
                "team gives them a role on the workspace."
            ),
        )

    def annotate_serialized_workspace_members_data(
        self,
        workspace: Workspace,
        serialized_data: List[OrderedDict],
        user: AbstractUser,
    ) -> List[OrderedDict]:
        """
        Annotates every member whose stored workspace role is "No role" with the
        workspace role they take from their teams, resolved as the effective access
        of the workspace is. Only those who may read the roles of the workspace get
        it, and the teams are limited to the ones whose members they may list.
        """

        if (
            "role" not in settings.PERMISSION_MANAGERS
            or not permission_manager_type_registry.get("role").is_enabled(workspace)
        ):
            return serialized_data

        for member in serialized_data:
            member[self.type] = None

        no_role_user_ids = {
            member["user_id"]
            for member in serialized_data
            if member["permissions"] == NO_ROLE_LOW_PRIORITY_ROLE_UID
        }
        if not no_role_user_ids:
            return serialized_data

        if not CoreHandler().check_permissions(
            user,
            ROLE_ASSIGNABLE_OBJECT_MAP["workspace"]["READ"],
            workspace=workspace,
            context=workspace,
            raise_permission_exceptions=False,
        ):
            return serialized_data

        effective_access = RoleAssignmentHandler().get_effective_access(
            workspace,
            workspace,
            subjects=list(User.objects.filter(id__in=no_role_user_ids)),
        )
        # Only a role through teams is shown: a member with "No role" and no team
        # role on the workspace isn't in the effective access at all.
        effective_access = [access for access in effective_access if access.teams]
        if not effective_access:
            return serialized_data

        visible_team_ids = (
            RoleAssignmentHandler().get_visible_effective_access_team_ids(
                user, workspace, effective_access
            )
        )

        team_workspace_role_per_user_id = {
            access.subject.id: {
                "role_uid": access.role.uid,
                "teams": [
                    {"id": team.id, "name": team.name}
                    for team in access.teams
                    if team.id in visible_team_ids
                ],
            }
            for access in effective_access
        }
        for member in serialized_data:
            member[self.type] = team_workspace_role_per_user_id.get(
                member["user_id"], None
            )

        return serialized_data
