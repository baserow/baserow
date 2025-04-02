from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.contrib.automation.api.workflows.serializers import (
    AutomationWorkflowSerializer,
    CreateAutomationWorkflowSerializer,
)
from baserow.contrib.automation.api.workflows.errors import (
    ERROR_WORKFLOW_NAME_NOT_UNIQUE,
)
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.contrib.automation.handler import AutomationHandler
from baserow.contrib.automation.workflows.exceptions import AutomationWorkflowNameNotUnique


class WorkflowsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="automation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a new Automation Workflow.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Automation workflows"],
        operation_id="create_automation_workflow",
        description="Creates a new Automation Workflow.",
        request=CreateAutomationWorkflowSerializer,
        responses={
            200: AutomationWorkflowSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_WORKFLOW_NAME_NOT_UNIQUE",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AutomationWorkflowNameNotUnique: ERROR_WORKFLOW_NAME_NOT_UNIQUE,
        }
    )
    @validate_body(CreateAutomationWorkflowSerializer, return_validated=True)
    def post(self, request, data: Dict, automation_id: int):
        automation = AutomationHandler().get_automation(automation_id)

        workflow = AutomationWorkflowService().create_workflow(
            request.user,
            automation,
            data["name"],
        )

        serializer = AutomationWorkflowSerializer(workflow)
        return Response(serializer.data)