from typing import Any

from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, require_request_data_type
from baserow.api.exceptions import RequestBodyValidationException
from baserow.api.mixins import RealtimeRecoveryPrimaryReadMixin
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import serialize_validation_errors_recursive, validate_data
from baserow.contrib.agent.action_tools.actions import (
    CreateAgentActionActionType,
    DeleteAgentActionActionType,
    UpdateAgentActionActionType,
)
from baserow.contrib.agent.action_tools.exceptions import (
    AgentActionDoesNotExist,
    AgentActionLimitReached,
    AgentActionTypeNotAvailable,
)
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.api.views import AGENT_ID_PATH_PARAMETER
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.services.exceptions import ServiceTypeDoesNotExist

from .errors import (
    ERROR_AGENT_ACTION_DOES_NOT_EXIST,
    ERROR_AGENT_ACTION_LIMIT_REACHED,
    ERROR_AGENT_ACTION_TYPE_NOT_AVAILABLE,
)
from .serializers import (
    ActionFormulaContextType,
    AgentActionSerializer,
    CreateAgentActionSerializer,
    UpdateAgentActionSerializer,
)

ACTION_ID_PARAMETER = OpenApiParameter(
    name="action_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the configured agent action.",
)


def request_validation_error(exc: ValidationError) -> None:
    """
    :param exc: A validation error of the action's own fields.
    :raises RequestBodyValidationException: Always, with the same details.
    """

    raise RequestBodyValidationException(
        serialize_validation_errors_recursive(exc.detail)
    ) from exc


ACTION_EXCEPTIONS = {
    ValidationError: request_validation_error,
    ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
    AgentActionDoesNotExist: ERROR_AGENT_ACTION_DOES_NOT_EXIST,
    AgentActionTypeNotAvailable: ERROR_AGENT_ACTION_TYPE_NOT_AVAILABLE,
    AgentActionLimitReached: ERROR_AGENT_ACTION_LIMIT_REACHED,
    ServiceTypeDoesNotExist: ERROR_AGENT_ACTION_TYPE_NOT_AVAILABLE,
}
ERRORS = {
    400: get_error_schema(
        [
            "ERROR_REQUEST_BODY_VALIDATION",
            "ERROR_AGENT_ACTION_TYPE_NOT_AVAILABLE",
            "ERROR_AGENT_ACTION_LIMIT_REACHED",
        ]
    ),
    401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
    403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
    404: get_error_schema(
        ["ERROR_APPLICATION_DOES_NOT_EXIST", "ERROR_AGENT_ACTION_DOES_NOT_EXIST"]
    ),
}


def pop_service_values(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    :param data: The validated request, which loses its service values.
    :return: The service values without the pinned type, or None when there are
        none to save.
    """

    values = data.pop("service", {})
    values.pop("type", None)
    return values or None


class AgentActionsView(RealtimeRecoveryPrimaryReadMixin, APIView):
    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER],
        tags=["Agent applications"],
        operation_id="list_agent_actions",
        responses={200: AgentActionSerializer(many=True), **ERRORS},
    )
    @map_exceptions(ACTION_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        actions = AgentActionService().list_actions(request.user, agent_id)
        return Response(AgentActionSerializer(actions, many=True).data)

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=["Agent applications"],
        operation_id="create_agent_action",
        request=CreateAgentActionSerializer,
        responses={200: AgentActionSerializer, **ERRORS},
    )
    @transaction.atomic
    @map_exceptions(ACTION_EXCEPTIONS)
    @require_request_data_type(dict)
    def post(self, request: Request, agent_id: int) -> Response:
        data = validate_data(
            CreateAgentActionSerializer,
            request.data,
            return_validated=True,
            context={
                "application_type": ActionFormulaContextType,
                "service_type_name": request.data.get("type"),
            },
        )
        service_type_name = data.pop("type")
        service_values = pop_service_values(data)
        action = action_type_registry.get_by_type(CreateAgentActionActionType).do(
            request.user, agent_id, service_type_name, service=service_values, **data
        )
        return Response(AgentActionSerializer(action).data)


class AgentActionView(APIView):
    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER, ACTION_ID_PARAMETER],
        tags=["Agent applications"],
        operation_id="get_agent_action",
        responses={200: AgentActionSerializer, **ERRORS},
    )
    @map_exceptions(ACTION_EXCEPTIONS)
    def get(self, request: Request, agent_id: int, action_id: int) -> Response:
        action = AgentActionService().get_action(request.user, agent_id, action_id)
        return Response(AgentActionSerializer(action).data)

    @extend_schema(
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            ACTION_ID_PARAMETER,
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent applications"],
        operation_id="update_agent_action",
        request=UpdateAgentActionSerializer,
        responses={200: AgentActionSerializer, **ERRORS},
    )
    @transaction.atomic
    @map_exceptions(ACTION_EXCEPTIONS)
    @require_request_data_type(dict)
    def patch(self, request: Request, agent_id: int, action_id: int) -> Response:
        action = AgentActionService().get_action(request.user, agent_id, action_id)
        data = validate_data(
            UpdateAgentActionSerializer,
            request.data,
            partial=True,
            return_validated=True,
            context={
                "application_type": ActionFormulaContextType,
                "service_type_name": action.service.get_type().type,
            },
        )
        service_values = pop_service_values(data)
        action = action_type_registry.get_by_type(UpdateAgentActionActionType).do(
            request.user, agent_id, action_id, service=service_values, **data
        )
        return Response(AgentActionSerializer(action).data)

    @extend_schema(
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            ACTION_ID_PARAMETER,
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent applications"],
        operation_id="delete_agent_action",
        responses={204: None, **ERRORS},
    )
    @transaction.atomic
    @map_exceptions(ACTION_EXCEPTIONS)
    def delete(self, request: Request, agent_id: int, action_id: int) -> Response:
        action_type_registry.get_by_type(DeleteAgentActionActionType).do(
            request.user, agent_id, action_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
