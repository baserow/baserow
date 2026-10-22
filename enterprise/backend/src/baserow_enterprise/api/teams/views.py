from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.mixins import SearchableViewMixin, SortableViewMixin
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.trash.errors import ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.trash.exceptions import CannotDeleteAlreadyDeletedItem
from baserow_enterprise.api.errors import (
    ERROR_ROLE_DOES_NOT_EXIST,
    ERROR_SUBJECT_BAD_REQUEST,
    ERROR_SUBJECT_DOES_NOT_EXIST,
    ERROR_SUBJECT_NOT_IN_GROUP,
    ERROR_SUBJECT_TYPE_UNSUPPORTED,
    ERROR_TEAM_DOES_NOT_EXIST,
    ERROR_TEAM_NAME_NOT_UNIQUE,
)
from baserow_enterprise.api.teams.serializers import (
    GetTeamsViewParamsSerializer,
    TeamListResponseSerializer,
    TeamResponseSerializer,
    TeamSerializer,
    TeamSubjectResponseSerializer,
    TeamSubjectSerializer,
)
from baserow_enterprise.exceptions import RoleNotExist, RoleUnsupported
from baserow_enterprise.role.constants import NO_ACCESS_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.teams.actions import (
    CreateTeamActionType,
    CreateTeamSubjectActionType,
    DeleteTeamActionType,
    DeleteTeamSubjectActionType,
    UpdateTeamActionType,
)
from baserow_enterprise.teams.exceptions import (
    TeamDoesNotExist,
    TeamNameNotUnique,
    TeamSubjectBadRequest,
    TeamSubjectDoesNotExist,
    TeamSubjectNotInGroup,
    TeamSubjectTypeUnsupported,
)
from baserow_enterprise.teams.handler import TeamHandler
from baserow_enterprise.teams.operations import (
    CreateTeamOperationType,
    CreateTeamSubjectOperationType,
    DeleteTeamOperationType,
    DeleteTeamSubjectOperationType,
    ListTeamsOperationType,
    ListTeamSubjectsOperationType,
    ReadTeamOperationType,
    ReadTeamSubjectOperationType,
    UpdateTeamOperationType,
)


class TeamsView(APIView, SearchableViewMixin, SortableViewMixin):
    permission_classes = (IsAuthenticated,)

    search_fields = ["name"]
    sort_field_mapping = {
        "name": "name",
        "default_role": "_annotated_default_role_uid",
        "subject_sample": "subject_count",
    }

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Lists all teams in a given workspace.",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Search for teams by their name.",
            ),
            OpenApiParameter(
                name="sorts",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Sort teams by name or subjects.",
            ),
        ],
        tags=["Teams"],
        operation_id="workspace_list_teams",
        description=("Lists all teams in a given workspace."),
        responses={
            200: TeamListResponseSerializer(many=True),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST})
    @validate_query_parameters(GetTeamsViewParamsSerializer)
    def get(self, request, workspace_id: int, query_params):
        """Responds with a list of teams in a specific workspace."""

        search = query_params.get("search")
        sorts = query_params.get("sorts")

        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            request.user,
            ListTeamsOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        teams = TeamHandler().list_teams_in_workspace(request.user, workspace)
        teams = list(
            self.apply_sorts_or_default_sort(sorts, self.apply_search(search, teams))
        )
        role_assignment_counts = RoleAssignmentHandler().count_subject_role_assignments(
            request.user, workspace, teams
        )

        serializer = TeamListResponseSerializer(
            teams,
            many=True,
            context={"role_assignment_counts": role_assignment_counts},
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=["Teams"],
        operation_id="workspace_create_team",
        description=("Creates a new team."),
        request=TeamSerializer,
        responses={
            200: TeamResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_SUBJECT_BAD_REQUEST",
                    "ERROR_TEAM_NAME_NOT_UNIQUE",
                    "ERROR_SUBJECT_NOT_IN_GROUP",
                    "ERROR_SUBJECT_TYPE_UNSUPPORTED",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_SUBJECT_DOES_NOT_EXIST",
                    "ERROR_ROLE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            RoleUnsupported: ERROR_ROLE_DOES_NOT_EXIST,
            RoleNotExist: ERROR_ROLE_DOES_NOT_EXIST,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            TeamNameNotUnique: ERROR_TEAM_NAME_NOT_UNIQUE,
            TeamSubjectBadRequest: ERROR_SUBJECT_BAD_REQUEST,
            TeamSubjectDoesNotExist: ERROR_SUBJECT_DOES_NOT_EXIST,
            TeamSubjectNotInGroup: ERROR_SUBJECT_NOT_IN_GROUP,
            TeamSubjectTypeUnsupported: ERROR_SUBJECT_TYPE_UNSUPPORTED,
        }
    )
    @transaction.atomic
    @validate_body(TeamSerializer)
    def post(self, request, workspace_id: int, data):
        """Creates a new team for a user."""

        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            request.user,
            CreateTeamOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        default_role = data.get("default_role", NO_ACCESS_ROLE_UID)
        if default_role:
            default_role = RoleAssignmentHandler().get_role_by_uid(default_role)

        team = action_type_registry.get_by_type(CreateTeamActionType).do(
            request.user, data["name"], workspace, data["subjects"], default_role
        )
        return Response(TeamResponseSerializer(team).data)


class TeamView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="team_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the team related to the provided value.",
            )
        ],
        tags=["Teams"],
        operation_id="get_team",
        description=("Returns the information related to the provided team id."),
        responses={
            200: TeamResponseSerializer,
            404: get_error_schema(["ERROR_TEAM_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({TeamDoesNotExist: ERROR_TEAM_DOES_NOT_EXIST})
    def get(self, request, team_id: int):
        """Responds with a single team."""

        team = TeamHandler().get_team(request.user, team_id)
        CoreHandler().check_permissions(
            request.user,
            ReadTeamOperationType.type,
            workspace=team.workspace,
            context=team,
        )

        serializer = TeamResponseSerializer(team)
        return Response(serializer.data)

    @extend_schema(
        parameters=[CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=["Teams"],
        operation_id="update_team",
        description=("Updates an existing team with a new name."),
        request=TeamSerializer,
        responses={
            200: TeamResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_TEAM_NAME_NOT_UNIQUE",
                    'ERROR_SUBJECT_BAD_REQUEST"',
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_TEAM_DOES_NOT_EXIST",
                    "ERROR_SUBJECT_DOES_NOT_EXIST",
                    "ERROR_ROLE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @validate_body(TeamSerializer)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            RoleUnsupported: ERROR_ROLE_DOES_NOT_EXIST,
            TeamNameNotUnique: ERROR_TEAM_NAME_NOT_UNIQUE,
            TeamDoesNotExist: ERROR_TEAM_DOES_NOT_EXIST,
            TeamSubjectBadRequest: ERROR_SUBJECT_BAD_REQUEST,
            TeamSubjectDoesNotExist: ERROR_SUBJECT_DOES_NOT_EXIST,
        }
    )
    def put(self, request, data, team_id: int):
        """Updates the team if the user belongs to the workspace."""

        team = TeamHandler().get_team_for_update(request.user, team_id)
        CoreHandler().check_permissions(
            request.user,
            UpdateTeamOperationType.type,
            workspace=team.workspace,
            context=team,
        )

        default_role = data.get("default_role", NO_ACCESS_ROLE_UID)
        if default_role:
            default_role = RoleAssignmentHandler().get_role_by_uid(default_role)

        team = action_type_registry.get_by_type(UpdateTeamActionType).do(
            request.user, team, data["name"], data["subjects"], default_role
        )

        return Response(TeamResponseSerializer(team).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="team_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the team related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Teams"],
        operation_id="delete_team",
        description=(
            "Deletes a team if the authorized user is in the team's "
            "workspace. All the related children (e.g. subjects) are also going to be deleted."
        ),
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM",
                ]
            ),
            404: get_error_schema(["ERROR_TEAM_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TeamDoesNotExist: ERROR_TEAM_DOES_NOT_EXIST,
            CannotDeleteAlreadyDeletedItem: ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM,
        }
    )
    def delete(self, request, team_id: int):
        """Deletes an existing team if the user belongs to the workspace."""

        team = TeamHandler().get_team_for_update(request.user, team_id)
        CoreHandler().check_permissions(
            request.user,
            DeleteTeamOperationType.type,
            workspace=team.workspace,
            context=team,
        )

        action_type_registry.get_by_type(DeleteTeamActionType).do(request.user, team)

        return Response(status=204)


class TeamSubjectsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Teams"],
        operation_id="list_team_subjects",
        description=("Lists all team subjects in a given team."),
        responses={
            200: TeamSubjectResponseSerializer(many=True),
            400: get_error_schema(["ERROR_TEAM_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TeamDoesNotExist: ERROR_TEAM_DOES_NOT_EXIST,
        }
    )
    def get(self, request, team_id: int):
        """Responds with a list of team subjects in a specific team."""

        team = TeamHandler().get_team(request.user, team_id)
        CoreHandler().check_permissions(
            request.user,
            ListTeamSubjectsOperationType.type,
            workspace=team.workspace,
            context=team,
        )

        subjects = TeamHandler().list_subjects_in_team(team_id)
        serializer = TeamSubjectResponseSerializer(subjects, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=["Teams"],
        operation_id="create_subject",
        description=("Creates a new team subject."),
        request=TeamSubjectSerializer,
        responses={
            200: TeamSubjectResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_SUBJECT_NOT_IN_GROUP",
                    "ERROR_SUBJECT_TYPE_UNSUPPORTED",
                    "ERROR_SUBJECT_BAD_REQUEST",
                ]
            ),
            404: get_error_schema(
                ["ERROR_TEAM_DOES_NOT_EXIST", "ERROR_SUBJECT_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            TeamDoesNotExist: ERROR_TEAM_DOES_NOT_EXIST,
            TeamSubjectBadRequest: ERROR_SUBJECT_BAD_REQUEST,
            TeamSubjectNotInGroup: ERROR_SUBJECT_NOT_IN_GROUP,
            TeamSubjectDoesNotExist: ERROR_SUBJECT_DOES_NOT_EXIST,
            TeamSubjectTypeUnsupported: ERROR_SUBJECT_TYPE_UNSUPPORTED,
        }
    )
    @transaction.atomic
    @validate_body(TeamSubjectSerializer)
    def post(self, request, team_id: int, data):
        team = TeamHandler().get_team(request.user, team_id)
        CoreHandler().check_permissions(
            request.user,
            CreateTeamSubjectOperationType.type,
            workspace=team.workspace,
            context=team,
        )

        subject_lookup = {"id": data["subject_id"]}
        if data["subject_user_email"]:
            subject_lookup = {"email": data["subject_user_email"]}

        subject = action_type_registry.get_by_type(CreateTeamSubjectActionType).do(
            request.user, subject_lookup, data["subject_type"], team
        )
        return Response(TeamSubjectResponseSerializer(subject).data)


class TeamSubjectView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="subject_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the subject related to the provided value.",
            )
        ],
        tags=["Teams"],
        operation_id="get_subject",
        description=("Returns the information related to the provided subject id"),
        responses={
            200: TeamSubjectResponseSerializer,
            404: get_error_schema(
                ["ERROR_TEAM_DOES_NOT_EXIST", "ERROR_SUBJECT_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            TeamDoesNotExist: ERROR_TEAM_DOES_NOT_EXIST,
            TeamSubjectDoesNotExist: ERROR_SUBJECT_DOES_NOT_EXIST,
        }
    )
    def get(self, request, team_id: int, subject_id: int):
        """Responds with a single subject."""

        team = TeamHandler().get_team(request.user, team_id)
        subject = TeamHandler().get_subject(subject_id, team)

        CoreHandler().check_permissions(
            request.user,
            ReadTeamSubjectOperationType.type,
            workspace=team.workspace,
            context=subject,
        )

        serializer = TeamSubjectResponseSerializer(subject)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="team_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The team id which the subject will be removed from.",
            ),
            OpenApiParameter(
                name="subject_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The subject id to remove from the team.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Teams"],
        operation_id="delete_subject",
        description=(
            "Deletes a subject if the authorized user is in the team's workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM"]),
            404: get_error_schema(
                ["ERROR_TEAM_DOES_NOT_EXIST", "ERROR_SUBJECT_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            TeamDoesNotExist: ERROR_TEAM_DOES_NOT_EXIST,
            TeamSubjectDoesNotExist: ERROR_SUBJECT_DOES_NOT_EXIST,
            CannotDeleteAlreadyDeletedItem: ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM,
        }
    )
    @transaction.atomic
    def delete(self, request, team_id: int, subject_id: int):
        """Deletes an existing team subject if the user belongs to the workspace."""

        team = TeamHandler().get_team(request.user, team_id)
        subject = TeamHandler().get_subject_for_update(subject_id, team)

        CoreHandler().check_permissions(
            request.user,
            DeleteTeamSubjectOperationType.type,
            workspace=team.workspace,
            context=subject,
        )

        action_type_registry.get_by_type(DeleteTeamSubjectActionType).do(
            request.user, subject
        )

        return Response(status=204)
