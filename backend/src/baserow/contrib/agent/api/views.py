from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.core.exceptions import ApplicationDoesNotExist

from ..actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
    UpdateAgentConfigurationActionType,
)
from ..exceptions import (
    AgentConfigurationInvalid,
    AgentConversationDoesNotExist,
    AgentMessageConflict,
)
from ..handler import AgentHandler
from ..service import AgentService
from .errors import (
    ERROR_AGENT_CONFIGURATION_INVALID,
    ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST,
    ERROR_AGENT_MESSAGE_CONFLICT,
)
from .serializers import (
    AgentConfigurationSerializer,
    AgentConfigurationUpdateSerializer,
    AgentConversationCreateSerializer,
    AgentConversationPagination,
    AgentConversationSerializer,
    AgentMessageCreatedSerializer,
    AgentMessageCreateSerializer,
    AgentMessagePagination,
    AgentMessageSerializer,
    AgentReadinessSerializer,
)

AGENT_EXCEPTIONS = {
    ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
    AgentConversationDoesNotExist: ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST,
    AgentConfigurationInvalid: ERROR_AGENT_CONFIGURATION_INVALID,
    AgentMessageConflict: ERROR_AGENT_MESSAGE_CONFLICT,
}
READ_ERRORS = {
    401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
    404: get_error_schema(
        ["ERROR_APPLICATION_DOES_NOT_EXIST", "ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST"]
    ),
}
WRITE_ERRORS = {
    **READ_ERRORS,
    400: get_error_schema(
        ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_AGENT_CONFIGURATION_INVALID"]
    ),
    409: get_error_schema(["ERROR_AGENT_MESSAGE_CONFLICT"]),
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


class AgentConversationsView(APIView):
    @extend_schema(
        tags=["Agents"],
        operation_id="list_agent_conversations",
        parameters=[
            OpenApiParameter("page", OpenApiTypes.INT, default=1),
            OpenApiParameter(
                "size",
                OpenApiTypes.INT,
                default=20,
                description="Number of conversations per page, up to 100.",
            ),
        ],
        responses={
            200: get_example_pagination_serializer_class(AgentConversationSerializer),
            **READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        """Paginate only the authenticated owner's conversations."""

        conversations = AgentService().list_conversations(request.user, agent_id)
        paginator = AgentConversationPagination(limit_page_size=100)
        page = paginator.paginate_queryset(conversations, request, self)
        return paginator.get_paginated_response(
            AgentConversationSerializer(page, many=True).data
        )

    @extend_schema(
        tags=["Agents"],
        operation_id="create_agent_conversation",
        request=AgentConversationCreateSerializer,
        responses={200: AgentMessageCreatedSerializer, **WRITE_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(AgentConversationCreateSerializer, return_validated=True)
    def post(self, request: Request, agent_id: int, data: dict) -> Response:
        """Persist a private thread and its first message through the creation action."""

        result = CreateAgentConversationActionType.do(request.user, agent_id, **data)
        return Response(AgentMessageCreatedSerializer(result).data)


class AgentMessagesView(APIView):
    @extend_schema(
        tags=["Agents"],
        operation_id="list_agent_messages",
        parameters=[
            OpenApiParameter("page", OpenApiTypes.INT, default=1),
            OpenApiParameter(
                "size",
                OpenApiTypes.INT,
                default=50,
                description="Number of messages per page, up to 100.",
            ),
        ],
        responses={
            200: get_example_pagination_serializer_class(AgentMessageSerializer),
            **READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request: Request, agent_id: int, conversation_uuid: UUID) -> Response:
        """Return newest history pages in chronological display order."""

        messages = AgentService().list_messages(
            request.user, agent_id, conversation_uuid
        )
        paginator = AgentMessagePagination(limit_page_size=100)
        page = paginator.paginate_queryset(messages, request, self)
        return paginator.get_paginated_response(
            AgentMessageSerializer(list(reversed(page)), many=True).data
        )

    @extend_schema(
        tags=["Agents"],
        operation_id="create_agent_message",
        request=AgentMessageCreateSerializer,
        responses={200: AgentMessageCreatedSerializer, **WRITE_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(AgentMessageCreateSerializer, return_validated=True)
    def post(
        self, request: Request, agent_id: int, conversation_uuid: UUID, data: dict
    ) -> Response:
        """Accept an authorized owner's message or recover its identical retry."""

        result = CreateAgentMessageActionType.do(
            request.user, agent_id, conversation_uuid, **data
        )
        return Response(AgentMessageCreatedSerializer(result).data)
