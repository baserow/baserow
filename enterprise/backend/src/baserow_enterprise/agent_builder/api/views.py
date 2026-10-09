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
from baserow_enterprise.agent_builder.actions import (
    CreateAgentActionType,
    DeleteAgentActionType,
    OrderAgentsActionType,
    UpdateAgentActionType,
)
from baserow_enterprise.agent_builder.api.errors import (
    ERROR_AGENT_DOES_NOT_EXIST,
    ERROR_AGENT_NOT_IN_AGENT_BUILDER,
)
from baserow_enterprise.agent_builder.api.serializers import (
    AgentSerializer,
    CreateAgentSerializer,
    OrderAgentsSerializer,
    UpdateAgentSerializer,
)
from baserow_enterprise.agent_builder.exceptions import (
    AgentDoesNotExist,
    AgentNotInAgentBuilder,
)
from baserow_enterprise.agent_builder.service import AgentService

AGENTS_TAG = "Agent builder agents"
AGENT_BUILDER_ID_PARAMETER = OpenApiParameter(
    name="agent_builder_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The ID of the agent builder application.",
)
AGENT_ID_PARAMETER = OpenApiParameter(
    name="agent_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The ID of the agent.",
)


class AgentsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[AGENT_BUILDER_ID_PARAMETER],
        tags=[AGENTS_TAG],
        operation_id="list_agent_builder_agents",
        description="Lists the agents the user can read in an agent builder.",
        responses={
            200: AgentSerializer(many=True),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
        },
    )
    @map_exceptions({ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST})
    def get(self, request, agent_builder_id):
        agents = AgentService().list_agents(request.user, agent_builder_id)
        return Response(AgentSerializer(agents, many=True).data)

    @extend_schema(
        parameters=[AGENT_BUILDER_ID_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=[AGENTS_TAG],
        operation_id="create_agent_builder_agent",
        description="Creates an empty agent in an agent builder.",
        request=CreateAgentSerializer,
        responses={
            200: AgentSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
        },
    )
    @transaction.atomic
    @map_exceptions({ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST})
    @validate_body(CreateAgentSerializer, return_validated=True)
    def post(self, request, data, agent_builder_id):
        agent = CreateAgentActionType.do(request.user, agent_builder_id, data)
        return Response(AgentSerializer(agent).data)


class AgentView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[AGENT_ID_PARAMETER],
        tags=[AGENTS_TAG],
        operation_id="get_agent_builder_agent",
        description="Retrieves an agent in an agent builder.",
        responses={
            200: AgentSerializer,
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_AGENT_DOES_NOT_EXIST"]),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
        },
    )
    @map_exceptions({AgentDoesNotExist: ERROR_AGENT_DOES_NOT_EXIST})
    def get(self, request, agent_id):
        agent = AgentService().get_agent(request.user, agent_id)
        return Response(AgentSerializer(agent).data)

    @extend_schema(
        parameters=[AGENT_ID_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=[AGENTS_TAG],
        operation_id="update_agent_builder_agent",
        description="Updates an agent's name.",
        request=UpdateAgentSerializer,
        responses={
            200: AgentSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_AGENT_DOES_NOT_EXIST"]),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
        },
    )
    @transaction.atomic
    @map_exceptions({AgentDoesNotExist: ERROR_AGENT_DOES_NOT_EXIST})
    @validate_body(UpdateAgentSerializer, return_validated=True)
    def patch(self, request, data, agent_id):
        agent = UpdateAgentActionType.do(request.user, agent_id, data)
        return Response(AgentSerializer(agent).data)

    @extend_schema(
        parameters=[AGENT_ID_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=[AGENTS_TAG],
        operation_id="delete_agent_builder_agent",
        description="Moves an agent to the trash. The action can be undone.",
        responses={
            204: None,
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_AGENT_DOES_NOT_EXIST"]),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
        },
    )
    @transaction.atomic
    @map_exceptions({AgentDoesNotExist: ERROR_AGENT_DOES_NOT_EXIST})
    def delete(self, request, agent_id):
        DeleteAgentActionType.do(request.user, agent_id)
        return Response(status=204)


class OrderAgentsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[AGENT_BUILDER_ID_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=[AGENTS_TAG],
        operation_id="order_agent_builder_agents",
        description="Orders the agents visible to the user in an agent builder.",
        request=OrderAgentsSerializer,
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_AGENT_NOT_IN_AGENT_BUILDER"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AgentNotInAgentBuilder: ERROR_AGENT_NOT_IN_AGENT_BUILDER,
        }
    )
    @validate_body(OrderAgentsSerializer, return_validated=True)
    def post(self, request, data, agent_builder_id):
        OrderAgentsActionType.do(request.user, agent_builder_id, data["agent_ids"])
        return Response(status=204)
