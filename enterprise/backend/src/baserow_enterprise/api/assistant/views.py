import json
from urllib.request import Request

from django.http import StreamingHttpResponse

from baserow_premium.license.handler import LicenseHandler
from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
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
from baserow_enterprise.api.assistant.errors import (
    ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST,
    ERROR_ASSISTANT_MODEL_NOT_SUPPORTED,
)
from baserow_enterprise.assistant.exceptions import (
    AssistantChatDoesNotExist,
    AssistantModelNotSupportedError,
)
from baserow_enterprise.assistant.handler import AssistantHandler
from baserow_enterprise.assistant.operations import ChatAssistantChatOperationType
from baserow_enterprise.assistant.types import (
    AssistantMessageUnion,
    HumanMessage,
    UIContext,
)
from baserow_enterprise.features import ASSISTANT

from .serializers import (
    AssistantChatMessagesSerializer,
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
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                type=OpenApiTypes.INT,
                required=True,
                description="The ID of the workspace.",
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                default=100,
                required=False,
                description="The number of results to return per page.",
            ),
            OpenApiParameter(
                name="offset",
                type=OpenApiTypes.INT,
                default=0,
                required=False,
                description="The initial index from which to return the results.",
            ),
        ],
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
        workspace = CoreHandler().get_workspace(workspace_id)

        LicenseHandler.raise_if_user_doesnt_have_feature(
            ASSISTANT, request.user, workspace
        )

        CoreHandler().check_permissions(
            request.user,
            ChatAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        chats = AssistantHandler().list_chats(request.user, workspace_id)

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
            AssistantModelNotSupportedError: ERROR_ASSISTANT_MODEL_NOT_SUPPORTED,
        }
    )
    def post(self, request: Request, chat_uuid: str, data) -> StreamingHttpResponse:
        feature_flag_is_enabled(FF_ASSISTANT, raise_if_disabled=True)

        ui_context = UIContext.from_validate_request(request, data["ui_context"])
        workspace_id = ui_context.workspace.id
        workspace = CoreHandler().get_workspace(workspace_id)
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

        # Clearing the user websocket_id will make sure real-time updates are sent
        chat.user.web_socket_id = None
        # FIXME: As long as we don't allow users to change it, temporarily set the
        # timezone to the one provided in the UI context
        chat.user.profile.timezone = ui_context.timezone

        assistant = handler.get_assistant(chat)
        human_message = HumanMessage(content=data["content"], ui_context=ui_context)

        async def stream_assistant_messages():
            async for msg in assistant.astream_messages(human_message):
                yield self._stream_assistant_message(msg)

        response = StreamingHttpResponse(
            stream_assistant_messages(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # helpful behind Nginx
        return response

    def _stream_assistant_message(self, message: AssistantMessageUnion) -> str:
        if AssistantMessageSerializer.can_serialize(message):
            serializer = AssistantMessageSerializer(message)
            return json.dumps(serializer.data) + "\n\n"

    @extend_schema(
        tags=["AI Assistant"],
        operation_id="list_assistant_chat_messages",
        description=(
            "List all messages in the specified AI assistant chat.\n\n"
            "This is an **advanced/enterprise** feature."
        ),
        responses={
            200: AssistantChatMessagesSerializer,
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

        messages = handler.list_chat_messages(chat)

        # Pass the messages as an instance for serialization
        serializer = AssistantChatMessagesSerializer({"messages": messages})

        return Response(serializer.data)
