"""Views for AI assistant API endpoints."""
import asyncio
import json
import uuid
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from asgiref.sync import sync_to_async, async_to_sync
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from django.db import connection, transaction
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from django.conf import settings

from baserow.api.decorators import (
    validate_body,
    map_exceptions,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.sessions import (
    set_client_undo_redo_action_group_id,
    set_user_websocket_id,
    set_untrusted_client_session_id,
)
from baserow.api.user.views import UNDO_REDO_EXCEPTIONS_MAP
from baserow.core.action.handler import ActionHandler
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler

from baserow.core.operations import ReadWorkspaceOperationType
from baserow.core.service import CoreService
from baserow_enterprise.ai_assistant.models import AssistantChat
from baserow_enterprise.ai_assistant.assistant import BaserowAssistant
from .serializers import (
    ChatRequestSerializer,
    AssistantChatSerializer,
    ChatsRequestSerializer,
)


class AIAssistantChatView(APIView):
    """API view for AI assistant chat functionality."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get(self, request, chat_uid):
        try:
            chat = (
                AssistantChat.objects.filter(user=request.user)
                .select_related("workspace")
                .get(uid=chat_uid)
            )
        except AssistantChat.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        db = settings.DATABASES["default"]
        db_uri = f"postgres://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"

        @async_to_sync
        async def get_messages():
            async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
                assistant = BaserowAssistant(
                    user=request.user,
                    workspace=chat.workspace,
                    chat=chat,
                    checkpointer=checkpointer,
                )

                config = assistant.get_config()
                graph = await assistant.aget_graph()
                current_state = await graph.aget_state(config)

                if current_state and current_state.values:
                    # Extract messages from the state
                    messages = current_state.values.get("messages", [])
                    return messages

                return []

        messages = get_messages()

        # Format messages for response
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage) and msg.content:
                msg_type = "user"
            elif isinstance(msg, AIMessage) and msg.content:
                msg_type = "assistant"
            elif isinstance(msg, ToolMessage) and msg.additional_kwargs.get(
                "visualization"
            ):
                msg_type = "assistant"
            else:
                continue

            formatted_messages.append(
                {
                    "id": msg.id,
                    "role": msg_type,
                    "content": msg.content,
                    "action": msg.additional_kwargs,
                }
            )

        return Response({"messages": formatted_messages}, status=status.HTTP_200_OK)

    @validate_body(ChatRequestSerializer)
    @map_exceptions({UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP})
    def post(self, request, chat_uid, data):
        """
        TODO: finish docstring and redoc
        """

        # TODO add feature flag; check feature is available

        workspace = CoreService().get_workspace(request.user, data["workspace_id"])
        try:
            chat = AssistantChat.objects.get(uid=chat_uid, user=request.user)
        except AssistantChat.DoesNotExist:
            chat = AssistantChat.objects.create(
                uid=chat_uid, user=request.user, workspace=workspace
            )

        message = data["message"]
        # Set it to the chat uid so it can be undone only by the assistant, without interfeering with normal user actions
        set_untrusted_client_session_id(request.user, chat.uid)
        set_user_websocket_id(request.user, None)
        # Ensure all undoable operations are grouped
        set_client_undo_redo_action_group_id(request.user, str(uuid.uuid4()))

        # Get database config in sync context
        db = settings.DATABASES["default"]
        db_uri = f"postgres://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"

        async def generate_response():
            try:
                message_uid = str(uuid.uuid4())
                chat_uid = str(chat.uid)
                yield self._format_chunk(
                    "message_start",
                    {
                        "message_id": message_uid,
                        "chat_uid": chat_uid,
                    },
                )

                async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
                    await checkpointer.setup()  # TODO: call this only once when the app starts

                    assistant = BaserowAssistant(
                        user=request.user,
                        workspace=workspace,
                        chat=chat,
                        new_message=message,
                        context=data.get("context"),
                        checkpointer=checkpointer,
                    )

                    async for msg in assistant.astream():
                        yield self._format_chunk(
                            "content_delta",
                            {
                                "message_id": message_uid,
                                "content": msg.content,
                                "timestamp": timezone.now().isoformat(),
                                "action": msg.additional_kwargs,
                            },
                        )

                yield self._format_chunk(
                    "message_end",
                    {
                        "message_id": message_uid,
                        "success": True,
                        "chat_title": chat.title,
                        "latest_action_is_undoable": chat.latest_action_is_undoable,
                    },
                )

            except Exception as e:
                raise e
                yield self._format_chunk(
                    "error", {"error": str(e), "type": "processing_error"}
                )

        chat.status = AssistantChat.Status.IN_PROGRESS
        chat.save(update_fields=["status"])

        response = StreamingHttpResponse(
            generate_response(), content_type="application/x-ndjson"
        )
        response["X-Accel-Buffering"] = "no"
        response["Cache-Control"] = "no-cache"

        # Status reset happens after streaming completes
        chat.status = AssistantChat.Status.IDLE
        chat.save(update_fields=["status"])

        return response

    def _format_chunk(self, chunk_type, data=None):
        """Format a streaming response chunk."""
        chunk = {"type": chunk_type, "timestamp": timezone.now().isoformat()}
        chunk["data"] = data

        return json.dumps(chunk) + "\n\n"

    def delete(self, request, chat_uid):
        try:
            chat = AssistantChat.objects.get(uid=chat_uid, user=request.user)
            chat.delete()
        except AssistantChat.DoesNotExist:
            return Response(
                {"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND
            )

        db = settings.DATABASES["default"]
        db_uri = f"postgres://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"

        @async_to_sync
        async def delete_messages():
            async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
                await checkpointer.adelete_thread(chat_uid)

        delete_messages()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AIAssistantChatsView(APIView):
    """API view for managing AI assistant chats."""

    @validate_query_parameters(ChatsRequestSerializer, return_validated=True)
    @map_exceptions({UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP})
    def get(self, request, query_params):
        workspace_id = query_params["workspace_id"]
        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            request.user,
            ReadWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        chats = AssistantChat.objects.filter(
            workspace=workspace, user=request.user
        ).order_by("-updated_on")[: query_params["limit"]]

        serializer = AssistantChatSerializer(chats, many=True)
        return Response(serializer.data)


class AIAssistantChatUndoView(APIView):
    @map_exceptions(UNDO_REDO_EXCEPTIONS_MAP)
    @transaction.atomic
    def post(self, request, chat_uid):
        try:
            chat = AssistantChat.objects.get(uid=chat_uid, user=request.user)
        except AssistantChat.DoesNotExist:
            return Response(
                {"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND
            )

        scopes = []  # All scopes
        ActionHandler.undo(request.user, scopes, chat.uid)
        return Response(status=204)
