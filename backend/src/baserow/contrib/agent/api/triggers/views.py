from typing import Any

from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, require_request_data_type
from baserow.api.mixins import RealtimeRecoveryPrimaryReadMixin
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import validate_data
from baserow.contrib.agent.api.views import AGENT_ID_PATH_PARAMETER
from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.triggers.actions import (
    CreateAgentTriggerActionType,
    DeleteAgentTriggerActionType,
    UpdateAgentTriggerActionType,
)
from baserow.contrib.agent.triggers.exceptions import (
    AgentTriggerDoesNotExist,
    AgentTriggerNoAccess,
    AgentTriggerTypeNotAvailable,
)
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.services.exceptions import (
    ServiceMisconfigured,
    ServiceTypeDoesNotExist,
)

from .errors import (
    ERROR_AGENT_TRIGGER_DOES_NOT_EXIST,
    ERROR_AGENT_TRIGGER_NO_ACCESS,
    ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE,
    ERROR_TRIGGER_SERVICE_MISCONFIGURED,
)
from .serializers import (
    AgentTriggerSerializer,
    AgentTriggerTypeSerializer,
    CreateAgentTriggerSerializer,
    UpdateAgentTriggerSerializer,
)

TRIGGER_ID_PATH_PARAMETER = OpenApiParameter(
    name="trigger_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the trigger.",
)
TRIGGER_EXCEPTIONS = {
    ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
    AgentTriggerDoesNotExist: ERROR_AGENT_TRIGGER_DOES_NOT_EXIST,
    AgentTriggerTypeNotAvailable: ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE,
    ServiceTypeDoesNotExist: ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE,
    ServiceMisconfigured: ERROR_TRIGGER_SERVICE_MISCONFIGURED,
    AgentTriggerNoAccess: ERROR_AGENT_TRIGGER_NO_ACCESS,
}
AGENT_ERRORS = {
    401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
    404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
}
TRIGGER_ERRORS = {
    **AGENT_ERRORS,
    404: get_error_schema(
        ["ERROR_APPLICATION_DOES_NOT_EXIST", "ERROR_AGENT_TRIGGER_DOES_NOT_EXIST"]
    ),
}
FEATURE_ERRORS = {403: get_error_schema(["ERROR_FEATURE_DISABLED"])}
# The message formula is validated against the agent's data provider registry.
SERIALIZER_CONTEXT = {"application_type": AgentApplicationType}


def pop_service_values(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Take the service values out of the validated payload. A payload leaving out
    `service` validates to just the pinned `type`, which must not run a no-op
    service update nor be audited as a change.

    :param data: The validated payload, which loses its `service`.
    :return: The values to set on the service, or None when the payload has none.
    """

    service_values = data.pop("service", {})
    # Pinned to `type` already, and no service model has a `type` field.
    service_values.pop("type", None)
    return service_values or None


class AgentTriggersView(RealtimeRecoveryPrimaryReadMixin, APIView):
    """Lists an Agent's triggers and adds new ones."""

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER],
        tags=["Agent applications"],
        operation_id="list_agent_triggers",
        description=(
            "Lists the triggers of the agent with their service, message and the "
            "schema of the payload each event provides. Requires permission to "
            "read the agent's configuration."
        ),
        responses={200: AgentTriggerSerializer(many=True), **AGENT_ERRORS},
    )
    @map_exceptions(TRIGGER_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        """Responds with the triggers if the user can read the configuration."""

        triggers = AgentTriggerService().list_triggers(request.user, agent_id)
        return Response(AgentTriggerSerializer(triggers, many=True).data)

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=["Agent applications"],
        operation_id="create_agent_trigger",
        description=(
            "Adds a trigger of one of the configuration's available_trigger_types "
            "to the agent, with initial values for its service. A configured "
            "service starts receiving events right away. Requires permission to "
            "update the agent and read its configuration."
        ),
        request=CreateAgentTriggerSerializer,
        responses={
            200: AgentTriggerSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE",
                    "ERROR_TRIGGER_SERVICE_MISCONFIGURED",
                    "ERROR_AGENT_TRIGGER_NO_ACCESS",
                ]
            ),
            **FEATURE_ERRORS,
            **AGENT_ERRORS,
        },
    )
    @transaction.atomic
    @map_exceptions(TRIGGER_EXCEPTIONS)
    @require_request_data_type(dict)
    def post(self, request: Request, agent_id: int) -> Response:
        """Validates the service values against the type the payload names."""

        data = validate_data(
            CreateAgentTriggerSerializer,
            request.data,
            return_validated=True,
            context={
                **SERIALIZER_CONTEXT,
                "service_type_name": request.data.get("type"),
            },
        )
        trigger = action_type_registry.get_by_type(CreateAgentTriggerActionType).do(
            request.user,
            agent_id,
            data["type"],
            message=data["message"],
            enabled=data["enabled"],
            service=pop_service_values(data),
            on_overlap=data.get("on_overlap"),
            batch_size=data["batch_size"],
            name=data["name"],
        )
        return Response(AgentTriggerSerializer(trigger).data)


class AgentTriggerTypesView(APIView):
    """Lists the trigger types an Agent may use, as its run identity sees them."""

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER],
        tags=["Agent applications"],
        operation_id="list_agent_trigger_types",
        description=(
            "Lists the trigger types the agent may use, each with what its form "
            "may choose from for the agent's run identity, such as the tables it "
            "can read, and the overlap rule a new trigger of it gets. Requires "
            "permission to read the agent's configuration."
        ),
        responses={200: AgentTriggerTypeSerializer(many=True), **AGENT_ERRORS},
    )
    @map_exceptions(TRIGGER_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        """Responds with the types if the user can read the configuration."""

        trigger_types = AgentTriggerService().list_trigger_types(request.user, agent_id)
        return Response(AgentTriggerTypeSerializer(trigger_types, many=True).data)


class AgentTriggerView(APIView):
    """Changes or trashes one of an Agent's triggers."""

    @extend_schema(
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            TRIGGER_ID_PATH_PARAMETER,
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent applications"],
        operation_id="update_agent_trigger",
        description=(
            "Updates the provided fields of the trigger: its name, its switch, "
            "its message, its overlap rule, its batch size, its type and the "
            "values of its service. Another type replaces the service with a new "
            "one of that type. Switching it off cancels its queued replies. "
            "Requires permission to update the agent and read its configuration."
        ),
        request=UpdateAgentTriggerSerializer,
        responses={
            200: AgentTriggerSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE",
                    "ERROR_TRIGGER_SERVICE_MISCONFIGURED",
                    "ERROR_AGENT_TRIGGER_NO_ACCESS",
                ]
            ),
            **FEATURE_ERRORS,
            **TRIGGER_ERRORS,
        },
    )
    @transaction.atomic
    @map_exceptions(TRIGGER_EXCEPTIONS)
    @require_request_data_type(dict)
    def patch(self, request: Request, agent_id: int, trigger_id: int) -> Response:
        """
        Validates service values against the type the payload names, else the
        trigger's own type, which only they need to look up.
        """

        service_type_name = request.data.get("type")
        if service_type_name is None and "service" in request.data:
            trigger = AgentTriggerService().get_trigger(
                request.user, agent_id, trigger_id
            )
            service_type_name = trigger.service.get_type().type
        data = validate_data(
            UpdateAgentTriggerSerializer,
            request.data,
            partial=True,
            return_validated=True,
            context={**SERIALIZER_CONTEXT, "service_type_name": service_type_name},
        )
        service_values = pop_service_values(data)
        service_type_name = data.pop("type", None)
        trigger = action_type_registry.get_by_type(UpdateAgentTriggerActionType).do(
            request.user,
            agent_id,
            trigger_id,
            service=service_values,
            service_type_name=service_type_name,
            **data,
        )
        return Response(AgentTriggerSerializer(trigger).data)

    @extend_schema(
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            TRIGGER_ID_PATH_PARAMETER,
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent applications"],
        operation_id="delete_agent_trigger",
        description=(
            "Moves the trigger to the trash, where it can be restored. Requires "
            "permission to update the agent and read its configuration."
        ),
        responses={204: None, **FEATURE_ERRORS, **TRIGGER_ERRORS},
    )
    @transaction.atomic
    @map_exceptions(TRIGGER_EXCEPTIONS)
    def delete(self, request: Request, agent_id: int, trigger_id: int) -> Response:
        """Trashes the trigger if the user can update the agent."""

        action_type_registry.get_by_type(DeleteAgentTriggerActionType).do(
            request.user, agent_id, trigger_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
