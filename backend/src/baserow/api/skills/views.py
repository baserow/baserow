from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_USER_INVALID_GROUP_PERMISSIONS,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.schemas import get_error_schema
from baserow.core.exceptions import (
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.handler import CoreHandler
from baserow.core.skills.exceptions import (
    WorkspaceSkillDoesNotExist,
    WorkspaceSkillNameNotUnique,
)
from baserow.core.skills.service import WorkspaceSkillService

from .errors import (
    ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST,
    ERROR_WORKSPACE_SKILL_NAME_NOT_UNIQUE,
)
from .serializers import (
    UpdateWorkspaceSkillRequestSerializer,
    WorkspaceSkillRequestSerializer,
    WorkspaceSkillSerializer,
)

SKILL_ERRORS = {
    WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
    UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
    UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
    WorkspaceSkillDoesNotExist: ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST,
    WorkspaceSkillNameNotUnique: ERROR_WORKSPACE_SKILL_NAME_NOT_UNIQUE,
}


class WorkspaceSkillsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Workspace skills"],
        operation_id="list_workspace_skills",
        description=(
            "Lists the skills of the workspace: reusable markdown instructions "
            "that agents of the workspace can follow."
        ),
        responses={
            200: WorkspaceSkillSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(SKILL_ERRORS)
    def get(self, request, workspace_id):
        workspace = CoreHandler().get_workspace(workspace_id)
        skills = WorkspaceSkillService().list_skills(request.user, workspace)
        return Response(WorkspaceSkillSerializer(skills, many=True).data)

    @extend_schema(
        tags=["Workspace skills"],
        operation_id="create_workspace_skill",
        description="Creates a skill in the workspace.",
        request=WorkspaceSkillRequestSerializer,
        responses={
            200: WorkspaceSkillSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_WORKSPACE_SKILL_NAME_NOT_UNIQUE",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(WorkspaceSkillRequestSerializer)
    @map_exceptions(SKILL_ERRORS)
    def post(self, request, data, workspace_id):
        workspace = CoreHandler().get_workspace(workspace_id)
        skill = WorkspaceSkillService().create_skill(request.user, workspace, **data)
        return Response(WorkspaceSkillSerializer(skill).data)


class WorkspaceSkillView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Workspace skills"],
        operation_id="get_workspace_skill",
        description="Returns a single skill.",
        responses={
            200: WorkspaceSkillSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(SKILL_ERRORS)
    def get(self, request, skill_id):
        skill = WorkspaceSkillService().get_skill(request.user, skill_id)
        return Response(WorkspaceSkillSerializer(skill).data)

    @extend_schema(
        tags=["Workspace skills"],
        operation_id="update_workspace_skill",
        description="Updates the name, description or content of a skill.",
        request=UpdateWorkspaceSkillRequestSerializer,
        responses={
            200: WorkspaceSkillSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_WORKSPACE_SKILL_NAME_NOT_UNIQUE",
                ]
            ),
            404: get_error_schema(["ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateWorkspaceSkillRequestSerializer)
    @map_exceptions(SKILL_ERRORS)
    def patch(self, request, data, skill_id):
        service = WorkspaceSkillService()
        skill = service.get_skill(request.user, skill_id)
        skill = service.update_skill(request.user, skill, **data)
        return Response(WorkspaceSkillSerializer(skill).data)

    @extend_schema(
        tags=["Workspace skills"],
        operation_id="delete_workspace_skill",
        description="Deletes a skill. Agents using it stop using it.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(SKILL_ERRORS)
    def delete(self, request, skill_id):
        service = WorkspaceSkillService()
        skill = service.get_skill(request.user, skill_id)
        service.delete_skill(request.user, skill)
        return Response(status=HTTP_204_NO_CONTENT)
