from typing import Dict

from django.conf import settings
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.contrib.automation.api.workflows.errors import (
    ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
    ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE,
    ERROR_AUTOMATION_WORKFLOW_NOT_IN_AUTOMATION,
)
from baserow.contrib.automation.api.workflows.serializers import (
    AutomationWorkflowHistorySerializer,
    AutomationWorkflowSerializer,
    CreateAutomationWorkflowSerializer,
    OrderAutomationWorkflowsSerializer,
    UpdateAutomationWorkflowSerializer,
)
from baserow.contrib.automation.history.service import AutomationHistoryService
from baserow.contrib.automation.workflows.actions import (
    CreateAutomationWorkflowActionType,
    DeleteAutomationWorkflowActionType,
    OrderAutomationWorkflowActionType,
    UpdateAutomationWorkflowActionType,
)
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNameNotUnique,
    AutomationWorkflowNotInAutomation,
)
from baserow.contrib.automation.workflows.job_types import (
    DuplicateAutomationWorkflowJobType,
)
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry

AUTOMATION_WORKFLOWS_TAG = "Automation workflows"


class AutomationWorkflowsView(APIView):
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
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="create_automation_workflow",
        description="Creates a new Automation Workflow.",
        request=CreateAutomationWorkflowSerializer,
        responses={
            200: AutomationWorkflowSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AutomationWorkflowNameNotUnique: ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE,
        }
    )
    @validate_body(CreateAutomationWorkflowSerializer, return_validated=True)
    def post(self, request, data: Dict, automation_id: int):
        workflow = CreateAutomationWorkflowActionType.do(
            request.user, automation_id, data
        )

        serializer = AutomationWorkflowSerializer(workflow)
        return Response(serializer.data)


class AutomationWorkflowView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="get_automation_workflow",
        description="Retrieve a single workflow of an automation.",
        responses={
            200: AutomationWorkflowSerializer,
            404: get_error_schema(
                [
                    "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
        }
    )
    def get(self, request, workflow_id: int):
        workflow = AutomationWorkflowService().get_workflow(request.user, workflow_id)
        return Response(AutomationWorkflowSerializer(workflow).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="update_automation_workflow",
        description="Updates an existing workflow of an automation.",
        request=UpdateAutomationWorkflowSerializer,
        responses={
            200: AutomationWorkflowSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AutomationWorkflowNameNotUnique: ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE,
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
        }
    )
    @validate_body(UpdateAutomationWorkflowSerializer, return_validated=True)
    def patch(self, request, data: Dict, workflow_id: int):
        workflow = UpdateAutomationWorkflowActionType.do(
            request.user, workflow_id, data
        )

        serializer = AutomationWorkflowSerializer(workflow)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="delete_automation_workflow",
        description="Deletes an existing workflow of an automation.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            404: get_error_schema(["ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
        }
    )
    def delete(self, request, workflow_id: int):
        DeleteAutomationWorkflowActionType.do(request.user, workflow_id)

        return Response(status=204)


class AutomationWorkflowHistoryView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="get_automation_workflow_history",
        description="Retrieve the history for a workflow.",
        responses={
            200: get_example_pagination_serializer_class(
                AutomationWorkflowHistorySerializer
            ),
            404: get_error_schema(
                [
                    "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
        }
    )
    def get(self, request, workflow_id: int):
        queryset = AutomationHistoryService().get_workflow_history(
            request.user, workflow_id
        )

        paginator = PageNumberPagination(
            limit_page_size=settings.AUTOMATION_HISTORY_PAGE_SIZE_LIMIT
        )
        page = paginator.paginate_queryset(queryset, request, self)
        serializer = AutomationWorkflowHistorySerializer(
            page,
            many=True,
        )

        return paginator.get_paginated_response(serializer.data)


class OrderAutomationWorkflowsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="automation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The automation the workflow belongs to.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="order_automation_workflows",
        description="Apply a new order to the workflows of an automation.",
        request=OrderAutomationWorkflowsSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_AUTOMATION_WORKFLOW_NOT_IN_AUTOMATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                    "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
            AutomationWorkflowNotInAutomation: ERROR_AUTOMATION_WORKFLOW_NOT_IN_AUTOMATION,
        }
    )
    @validate_body(OrderAutomationWorkflowsSerializer)
    def post(self, request, data: Dict, automation_id: int):
        OrderAutomationWorkflowActionType.do(
            request.user, automation_id, data["workflow_ids"]
        )

        return Response(status=204)


class AsyncAutomationDuplicateWorkflowView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workflow to duplicate.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="duplicate_automation_workflow_async",
        description=(
            "Start a job to duplicate the workflow with the provided "
            "`workflow_id` parameter if the authorized user has access to the "
            "automation's workspace."
        ),
        request=None,
        responses={
            202: DuplicateAutomationWorkflowJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    def post(self, request, workflow_id):
        """Creates a job to duplicate a workflow in an automation."""

        job = JobHandler().create_and_start_job(
            request.user,
            DuplicateAutomationWorkflowJobType.type,
            workflow_id=workflow_id,
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=HTTP_202_ACCEPTED)


class AsyncPublishAutomationWorkflowView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workflow id the user wants to publish.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="publish_automation_workflow",
        description=(
            "This endpoint starts an asynchronous job to publish the "
            "automation workflow. The job clones the current version of "
            "the given automation and publishes it for the given workflow."
        ),
        request=None,
        responses={
            202: HTTP_202_ACCEPTED,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
        }
    )
    def post(self, request, workflow_id: int):
        """
        Starts an async job to publish an automation workflow.
        """

        job = AutomationWorkflowService().async_publish(request.user, workflow_id)

        serializer = job_type_registry.get_serializer(job, JobSerializer)

        return Response(serializer.data, status=HTTP_202_ACCEPTED)


class AutomationTestWorkflowView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workflow id the user wants to test.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_WORKFLOWS_TAG],
        operation_id="test_automation_workflow",
        description=(
            "This endpoint plan the execution of a test run for this workflow."
        ),
        request=None,
        responses={
            202: HTTP_202_ACCEPTED,
            404: get_error_schema(["ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
        }
    )
    def post(self, request, workflow_id: int):
        """
        Start the workflow asynchronously in test mode.
        """

        AutomationWorkflowService().toggle_test_run(
            request.user, workflow_id=workflow_id
        )

        return Response(status=HTTP_202_ACCEPTED)
