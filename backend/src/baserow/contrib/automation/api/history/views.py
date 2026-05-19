from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_query_parameters
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.contrib.automation.api.history.errors import (
    ERROR_AUTOMATION_NODE_HISTORY_DOES_NOT_EXIST,
    ERROR_AUTOMATION_NODE_RESULT_DOES_NOT_EXIST,
    ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST,
)
from baserow.contrib.automation.api.history.serializers import (
    AutomationNodeHistorySerializer,
    AutomationNodeResultSerializer,
    NodeHistoriesQueryParamsSerializer,
)
from baserow.contrib.automation.history.exceptions import (
    AutomationNodeHistoryDoesNotExist,
    AutomationWorkflowHistoryDoesNotExist,
    AutomationWorkflowHistoryNodeResultDoesNotExist,
)
from baserow.contrib.automation.history.service import AutomationHistoryService

AUTOMATION_HISTORY_TAG = "Automation history"


class AutomationNodeHistoriesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_history_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow history.",
            ),
            OpenApiParameter(
                name="parent_node_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                required=False,
                description=(
                    "When provided, returns the immediate child node histories "
                    "of the workflow node with this id. When omitted, returns "
                    "the root node histories."
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_HISTORY_TAG],
        operation_id="get_automation_node_histories",
        description=(
            "Returns the immediate children of the given parent workflow node "
            "(or the roots, if no parent is supplied) for the workflow history. "
        ),
        responses={
            200: AutomationNodeHistorySerializer(many=True),
            404: get_error_schema(["ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationWorkflowHistoryDoesNotExist: (
                ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST
            ),
        }
    )
    @validate_query_parameters(NodeHistoriesQueryParamsSerializer)
    def get(self, request, workflow_history_id: int, query_params):
        (
            queryset,
            parent_map,
            error_ancestor_ids,
        ) = AutomationHistoryService().get_child_node_histories(
            request.user,
            workflow_history_id,
            query_params.get("parent_node_id"),
        )

        serializer = AutomationNodeHistorySerializer(
            queryset,
            many=True,
            context={
                "parent_map": parent_map,
                "error_ancestor_ids": error_ancestor_ids,
            },
        )
        return Response(serializer.data)


class AutomationNodeResultView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="node_history_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the node history.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_HISTORY_TAG],
        operation_id="get_automation_node_result",
        description="Returns the result of the node history.",
        responses={
            200: AutomationNodeResultSerializer,
            404: get_error_schema(
                [
                    "ERROR_AUTOMATION_NODE_HISTORY_DOES_NOT_EXIST",
                    "ERROR_AUTOMATION_NODE_RESULT_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            AutomationNodeHistoryDoesNotExist: (
                ERROR_AUTOMATION_NODE_HISTORY_DOES_NOT_EXIST
            ),
            AutomationWorkflowHistoryNodeResultDoesNotExist: (
                ERROR_AUTOMATION_NODE_RESULT_DOES_NOT_EXIST
            ),
        }
    )
    def get(self, request, node_history_id: int):
        node_result = AutomationHistoryService().get_node_history_result(
            request.user, node_history_id
        )
        serializer = AutomationNodeResultSerializer(node_result)
        return Response(serializer.data)
