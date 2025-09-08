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
from baserow.core.feature_flags import FF_ASSISTANT, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow.core.service import CoreService
from baserow_enterprise.api.assistant.errors import ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST
from baserow_enterprise.assistant.exceptions import AssistantChatDoesNotExist
from baserow_enterprise.assistant.handler import AssistantHandler
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.operations import ChatAssistantChatOperationType
from baserow_enterprise.assistant.types import BaseMessage, HumanMessage
from baserow_enterprise.features import ASSISTANT

from .serializers import (
    AssistantChatSerializer,
    AssistantChatsRequestSerializer,
    AssistantMessageRequestSerializer,
    AssistantMessageSerializer,
)


class AssistantChatsView(APIView):
    @extend_schema(
        tags=["AI Assistant"],
        operation_id="list_assistant_chats",
        description=(
            "List all AI assistant chats for the current user in the specified workspace."
            "\n\nThis is a **advanced/enterprise** feature."
        ),
        request=AssistantChatsRequestSerializer,
        responses={
            200: get_example_pagination_serializer_class(AssistantChatSerializer),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
        },
    )
    @validate_query_parameters(AssistantChatsRequestSerializer, return_validated=True)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, query_params) -> Response:
        feature_flag_is_enabled(FF_ASSISTANT, raise_if_disabled=True)

        workspace_id = query_params["workspace_id"]
        workspace = CoreService().get_workspace(request.user, workspace_id)

        LicenseHandler.raise_if_user_doesnt_have_feature(
            ASSISTANT, request.user, workspace
        )

        CoreHandler().check_permissions(
            request.user,
            ChatAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        chats = AssistantChat.objects.filter(
            workspace=workspace, user=request.user
        ).order_by("-updated_on", "id")

        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(chats, request, self)

        serializer = AssistantChatSerializer(
            page, many=True, context={"user": request.user}
        )
        return paginator.get_paginated_response(serializer.data)


class AssistantChatView(APIView):
    @extend_schema(
        tags=["AI Assistant"],
        operation_id="send_message_to_assistant_chat",
        description=(
            "Send a message to the specified AI assistant chat and stream back the response.\n\n"
            "This is an **advanced/enterprise** feature."
        ),
        request=AssistantMessageRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="A text/event-stream of the assistant’s partial responses",
                response=OpenApiTypes.STR,
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
        },
    )
    @validate_body(AssistantMessageRequestSerializer, return_validated=True)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            AssistantChatDoesNotExist: ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def post(self, request: Request, chat_uuid: str, data) -> StreamingHttpResponse:
        feature_flag_is_enabled(FF_ASSISTANT, raise_if_disabled=True)

        ui_context = data["ui_context"]
        workspace_id = ui_context["workspace"]["id"]
        workspace = CoreService().get_workspace(request.user, workspace_id)
        LicenseHandler.raise_if_user_doesnt_have_feature(
            ASSISTANT, request.user, workspace
        )
        CoreHandler().check_permissions(
            request.user,
            ChatAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        handler = AssistantHandler()
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

        message = AssistantMessageSerializer.from_assistant_message(message)

        return json.dumps(message.data) + "\n\n"

    @extend_schema(
        tags=["AI Assistant"],
        operation_id="list_assistant_chat_messages",
        description=(
            "List all messages in the specified AI assistant chat.\n\n"
            "This is an **advanced/enterprise** feature."
        ),
        request=AssistantMessageRequestSerializer,
        responses={
            200: None,  # TODO
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            AssistantChatDoesNotExist: ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, chat_uuid: str) -> Response:
        feature_flag_is_enabled(FF_ASSISTANT, raise_if_disabled=True)

        handler = AssistantHandler()
        chat = handler.get_chat(request.user, chat_uuid)

        workspace = chat.workspace
        LicenseHandler.raise_if_user_doesnt_have_feature(
            ASSISTANT, request.user, workspace
        )
        CoreHandler().check_permissions(
            request.user,
            ChatAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        messages = handler.get_chat_messages(chat)

        return Response(
            {
                "messages": [
                    AssistantMessageSerializer.from_assistant_message(msg).data
                    for msg in messages
                ],
            }
        )
