from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.contrib.automation.api.history.errors import (
    ERROR_AUTOMATION_NODE_HISTORY_DOES_NOT_EXIST,
    ERROR_AUTOMATION_NODE_RESULT_DOES_NOT_EXIST,
    ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST,
)
from baserow.contrib.automation.api.history.serializers import (
    AutomationNodeHistorySerializer,
    AutomationNodeResultSerializer,
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
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_HISTORY_TAG],
        operation_id="get_automation_node_histories",
        description="Returns all node histories for the given workflow history.",
        responses={
            200: AutomationNodeHistorySerializer(many=True),
            404: get_error_schema(["ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AutomationWorkflowHistoryDoesNotExist: (
                ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST
            ),
        }
    )
    def get(self, request, workflow_history_id: int):
        service = AutomationHistoryService()
        node_histories = service.get_node_histories(request.user, workflow_history_id)
        edge_labels = service.get_edge_labels(request.user, node_histories)
        serializer = AutomationNodeHistorySerializer(
            node_histories,
            many=True,
            context={"edge_labels": edge_labels},
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
        description="Returns the node history's result JSON.",
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
