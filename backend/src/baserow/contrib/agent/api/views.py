from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.core.exceptions import ApplicationDoesNotExist

from ..actions import UpdateAgentConfigurationActionType
from ..handler import AgentHandler
from ..service import AgentService
from .serializers import (
    AgentConfigurationSerializer,
    AgentConfigurationUpdateSerializer,
    AgentReadinessSerializer,
)

AGENT_EXCEPTIONS = {ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST}
READ_ERRORS = {
    401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
    404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
}


class AgentReadinessView(APIView):
    @extend_schema(
        tags=["Agents"],
        operation_id="get_agent_readiness",
        responses={200: AgentReadinessSerializer, **READ_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        """Expose a coarse state without disclosing configuration values."""

        return Response(AgentService().get_readiness(request.user, agent_id))


class AgentConfigurationView(APIView):
    @extend_schema(
        tags=["Agents"],
        operation_id="get_agent_configuration",
        responses={200: AgentConfigurationSerializer, **READ_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        """Load settings only after the application-scoped Builder permission check."""

        return Response(AgentService().get_configuration(request.user, agent_id))

    @extend_schema(
        tags=["Agents"],
        operation_id="update_agent_configuration",
        request=AgentConfigurationUpdateSerializer,
        responses={
            200: AgentConfigurationSerializer,
            **READ_ERRORS,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(
        AgentConfigurationUpdateSerializer, partial=True, return_validated=True
    )
    def patch(self, request: Request, agent_id: int, data: dict) -> Response:
        """Save one partial draft and return the privileged validation envelope."""

        agent = UpdateAgentConfigurationActionType.do(request.user, agent_id, **data)
        return Response(AgentHandler().get_configuration(agent))
