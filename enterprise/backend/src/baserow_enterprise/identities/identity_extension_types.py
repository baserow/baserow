from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import JSONField, OuterRef, Value
from django.db.models.functions import JSONObject

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.core.handler import CoreHandler
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.registries import IdentityExtensionType
from baserow.core.models import User
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


class IdentityTeamSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


@extend_schema_field(IdentityTeamSummarySerializer(many=True))
class IdentityTeamsField(serializers.Field):
    def to_representation(self, identity):
        # List querysets annotate this after one license check for the whole page.
        if hasattr(identity, "_identity_teams"):
            return identity._identity_teams
        if not LicenseHandler.workspace_has_feature(
            TEAMS, IdentityHandler().get_workspace(identity)
        ):
            return []
        return list(
            Team.objects.filter(
                subjects__subject_type=ContentType.objects.get_for_model(User),
                subjects__subject_id=identity.id,
            ).values("id", "name")
        )


class EnterpriseIdentityExtensionType(IdentityExtensionType):
    type = "enterprise_permissions"
    request_fields = {
        "team_ids": serializers.ListField(
            child=serializers.IntegerField(), required=False
        )
    }
    response_fields = {"teams": IdentityTeamsField(source="*", read_only=True)}
    list_response_fields = {
        "role_assignment_count": serializers.IntegerField(
            read_only=True,
            required=False,
            help_text="Enterprise or advanced only: the number of roles this identity "
            "holds on databases, tables and restricted views whose roles the "
            "requesting user may read.",
        )
    }

    def enhance_queryset(self, queryset, workspace):
        """Load team summaries with the Identities instead of querying each Identity."""

        if not LicenseHandler.workspace_has_feature(TEAMS, workspace):
            # Keep the annotation so serialization does not repeat the feature
            # check for every identity in a disabled workspace.
            return queryset.annotate(
                _identity_teams=Value([], output_field=JSONField())
            )
        teams = (
            Team.objects.filter(
                subjects__subject_type=ContentType.objects.get_for_model(User),
                subjects__subject_id=OuterRef("pk"),
            )
            .annotate(summary=JSONObject(id="id", name="name"))
            .values("summary")
        )
        return queryset.annotate(_identity_teams=ArraySubquery(teams))

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

    def annotate_serialized_identities(
        self, workspace, identities, serialized_identities, user
    ):
        """
        Annotates every identity with the number of roles it holds on databases, tables
        and restricted views, as listed by the subject role assignments endpoint.
        """

        counts = RoleAssignmentHandler().count_subject_role_assignments(
            user, workspace, list(identities)
        )
        if counts:
            for identity, serialized_identity in zip(identities, serialized_identities):
                serialized_identity["role_assignment_count"] = counts[identity]
        return serialized_identities

    def _sync_teams(self, identity, team_ids, user):
        """Authorize all membership changes before replacing an identity's teams."""

        if team_ids is None:
            return
        LicenseHandler.raise_if_user_doesnt_have_feature(
            TEAMS, user, IdentityHandler().get_workspace(identity)
        )
        teams = list(
            Team.objects.filter(
                id__in=set(team_ids),
                workspace=IdentityHandler().get_workspace(identity),
            )
        )
        if len(teams) != len(set(team_ids)):
            raise ValidationError(
                {"team_ids": "Every team must belong to the identity's workspace."}
            )
        subject_type = ContentType.objects.get_for_model(User)
        memberships = list(
            TeamSubject.objects.filter(
                subject_type=subject_type, subject_id=identity.id
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
            checks,
            workspace=IdentityHandler().get_workspace(identity),
            raise_exception=True,
        )
        TeamSubject.objects.filter(
            id__in=[membership.id for membership in removed_memberships]
        ).delete()
        TeamSubject.objects.bulk_create(
            [TeamSubject(team=team, subject=identity) for team in added_teams]
        )

    def create(self, identity, values, user):
        self._sync_teams(identity, values.get("team_ids"), user)

    def update(self, identity, values, user):
        self._sync_teams(identity, values.get("team_ids"), user)
