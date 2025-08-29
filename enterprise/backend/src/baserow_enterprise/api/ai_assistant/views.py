import json
from urllib.request import Request

from django.db import transaction
from django.http import StreamingHttpResponse

from baserow_premium.license.handler import LicenseHandler
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.pagination import LimitOffsetPagination
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.service import CoreService
from baserow_enterprise.ai_assistant.exceptions import AiAssistantChatDoesNotExist
from baserow_enterprise.ai_assistant.handler import AiAssistantHandler
from baserow_enterprise.ai_assistant.models import AiAssistantChat
from baserow_enterprise.ai_assistant.operations import ChatAiAssistantChatOperationType
from baserow_enterprise.ai_assistant.types import BaseMessage, HumanMessage
from baserow_enterprise.api.ai_assistant.errors import (
    ERROR_AI_ASSISTANT_CHAT_DOES_NOT_EXIST,
)
from baserow_enterprise.features import AI_ASSISTANT

from .serializers import (
    AiAssistantChatSerializer,
    AiAssistantChatsRequestSerializer,
    AiAssistantMessageRequestSerializer,
    AiAssistantMessageSerializer,
)


class AiAssistantChatsView(APIView):
    @extend_schema(
        tags=["AI Assistant"],
        operation_id="list_ai_assistant_chats",
        description=(
            "List all AI assistant chats for the current user in the specified workspace."
            "\n\nThis is a **advanced/enterprise** feature."
        ),
        request=AiAssistantChatsRequestSerializer,
        responses={
            200: get_example_pagination_serializer_class(AiAssistantChatSerializer),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
        },
    )
    @validate_query_parameters(AiAssistantChatsRequestSerializer, return_validated=True)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, query_params) -> Response:
        workspace_id = query_params["workspace_id"]
        workspace = CoreService().get_workspace(request.user, workspace_id)

        LicenseHandler.raise_if_user_doesnt_have_feature(
            AI_ASSISTANT, request.user, workspace
        )

        CoreHandler().check_permissions(
            request.user,
            ChatAiAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        chats = AiAssistantChat.objects.filter(
            workspace=workspace, user=request.user
        ).order_by("-updated_on", "id")

        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(chats, request, self)

        serializer = AiAssistantChatSerializer(
            page, many=True, context={"user": request.user}
        )
        return paginator.get_paginated_response(serializer.data)


class AiAssistantChatView(APIView):
    @extend_schema(
        tags=["AI Assistant"],
        operation_id="send_message_to_ai_assistant_chat",
        description=(
            "Send a message to the specified AI assistant chat and stream back the response.\n\n"
            "This is an **advanced/enterprise** feature."
        ),
        request=AiAssistantMessageRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="A text/event-stream of the assistant’s partial responses",
                response=OpenApiTypes.STR,
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
        },
    )
    @validate_body(AiAssistantMessageRequestSerializer, return_validated=True)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            AiAssistantChatDoesNotExist: ERROR_AI_ASSISTANT_CHAT_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def post(self, request: Request, chat_uuid: str, data) -> StreamingHttpResponse:
        ui_context = data["ui_context"]
        workspace_id = ui_context["workspace"]["id"]
        workspace = CoreService().get_workspace(request.user, workspace_id)
        LicenseHandler.raise_if_user_doesnt_have_feature(
            AI_ASSISTANT, request.user, workspace
        )
        CoreHandler().check_permissions(
            request.user,
            ChatAiAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        handler = AiAssistantHandler()
        chat, _ = handler.get_or_create_chat(request.user, workspace, chat_uuid)

        async def stream_messages():
            assistant = handler.get_assistant(chat, HumanMessage(**data))

            async for msg in assistant.astream():
                yield self._stream_assistant_message(msg)

        return StreamingHttpResponse(
            stream_messages(),
            content_type="text/event-stream",
        )

    def _stream_assistant_message(self, message: BaseMessage) -> str:
        """Stream a message to the client."""

        message = AiAssistantMessageSerializer.from_assistant_message(message)

        return json.dumps(message.data) + "\n\n"

    @extend_schema(
        tags=["AI Assistant"],
        operation_id="list_ai_assistant_chat_messages",
        description=(
            "List all messages in the specified AI assistant chat.\n\n"
            "This is an **advanced/enterprise** feature."
        ),
        request=AiAssistantMessageRequestSerializer,
        responses={
            200: None,  # TODO
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            AiAssistantChatDoesNotExist: ERROR_AI_ASSISTANT_CHAT_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, chat_uuid: str) -> Response:
        handler = AiAssistantHandler()
        chat = handler.get_chat(request.user, chat_uuid)

        workspace = chat.workspace
        LicenseHandler.raise_if_user_doesnt_have_feature(
            AI_ASSISTANT, request.user, workspace
        )
        CoreHandler().check_permissions(
            request.user,
            ChatAiAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        messages = handler.get_chat_messages(chat)

        return Response(
            {
                "messages": [
                    AiAssistantMessageSerializer.from_assistant_message(msg).data
                    for msg in messages
                ],
            }
        )
