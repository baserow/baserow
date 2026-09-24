import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from urllib.request import Request
from uuid import uuid4

from django.db import DEFAULT_DB_ALIAS
from django.http import StreamingHttpResponse

from asgiref.sync import sync_to_async
from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from loguru import logger
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
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
from baserow.api.sessions import (
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id_from_request_or_raise_if_invalid,
)
from baserow.config.db_routers import set_db_alias
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow_enterprise.assistant.assistant import set_assistant_cancellation_key
from baserow_enterprise.assistant.exceptions import (
    AssistantChatDoesNotExist,
    AssistantChatMessagePredictionDoesNotExist,
    AssistantConfiguredModelNotAvailableError,
    AssistantMessageCancelled,
    AssistantModelDisabledError,
    AssistantModelNotSupportedError,
)
from baserow_enterprise.assistant.handler import AssistantHandler
from baserow_enterprise.assistant.model_profiles import (
    check_lm_ready_or_raise,
    resolve_assistant_model,
)
from baserow_enterprise.assistant.models import AssistantChatPrediction
from baserow_enterprise.assistant.onboarding import (
    generate_onboarding_prompt_suggestions,
)
from baserow_enterprise.assistant.operations import ChatAssistantChatOperationType
from baserow_enterprise.assistant.types import (
    AiCancelledMessage,
    AiErrorMessage,
    AssistantMessageUnion,
    HumanMessage,
    UIContext,
)

from .errors import (
    ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST,
    ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE,
    ERROR_ASSISTANT_MODEL_DISABLED,
    ERROR_ASSISTANT_MODEL_NOT_SUPPORTED,
    ERROR_CANNOT_SUBMIT_MESSAGE_FEEDBACK,
)
from .serializers import (
    AssistantChatMessagesSerializer,
    AssistantChatSerializer,
    AssistantChatsRequestSerializer,
    AssistantMessageRequestSerializer,
    AssistantMessageSerializer,
    AssistantRateChatMessageSerializer,
    OnboardingPromptSuggestionsRequestSerializer,
    OnboardingPromptSuggestionsSerializer,
)


class AssistantStreamingHttpResponse(StreamingHttpResponse):
    """Propagate ASGI response closure to the assistant's root generator.

    Django wraps async streaming content with delegating generators that don't
    forward ``aclose()``. Owning the root iterator here ensures a client
    disconnect reaches the assistant's task and provider cleanup immediately.
    """

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Iterate response bytes while owning the root async iterator.

        :yield: Response body bytes.
        :return: An async iterator of response body bytes.
        """

        iterator = self._iterator
        if not self.is_async or not hasattr(iterator, "aclose"):
            async for part in super().__aiter__():
                yield part
            return

        async with aclosing(iterator) as content:
            async for part in content:
                yield self.make_bytes(part)


class AssistantChatsView(APIView):
    @extend_schema(
        tags=["AI Assistant"],
        operation_id="list_assistant_chats",
        description=(
            "List all AI assistant chats for the current user in the specified workspace."
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
        workspace_id = query_params["workspace_id"]
        workspace = CoreHandler().get_workspace(workspace_id)

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
        ),
        request=AssistantMessageRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="A text/event-stream of the assistant’s partial responses",
                response=OpenApiTypes.STR,
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_ASSISTANT_MODEL_DISABLED",
                    "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED",
                    "ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE",
                ]
            ),
            404: get_error_schema(["ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(AssistantMessageRequestSerializer, return_validated=True)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            AssistantChatDoesNotExist: ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST,
            AssistantModelDisabledError: ERROR_ASSISTANT_MODEL_DISABLED,
            AssistantConfiguredModelNotAvailableError: (
                ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE
            ),
            AssistantModelNotSupportedError: ERROR_ASSISTANT_MODEL_NOT_SUPPORTED,
        }
    )
    def post(
        self, request: Request, chat_uuid: str, data
    ) -> AssistantStreamingHttpResponse:
        """Authorize, validate, and stream one assistant message.

        :param request: The authenticated API request.
        :param chat_uuid: The client-generated chat identifier.
        :param data: The validated message and UI-context payload.
        :return: A streaming response containing assistant events.
        """

        # The selected model and its credentials are security-sensitive execution
        # inputs. Read them from primary so a replica cannot revive a just-disabled
        # model or superseded credential for the lifetime of this streamed request.
        set_db_alias(DEFAULT_DB_ALIAS)

        ui_context = UIContext.from_validate_request(request, data["ui_context"])
        workspace_id = ui_context.workspace.id
        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            request.user,
            ChatAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        handler = AssistantHandler()
        chat = handler.get_existing_chat(request.user, workspace, chat_uuid)
        model_profile = resolve_assistant_model(workspace=workspace)
        check_lm_ready_or_raise(model_profile=model_profile)
        if chat is None:
            chat, _ = handler.get_or_create_chat(request.user, workspace, chat_uuid)

        # Clearing the user websocket_id will make sure real-time updates are sent
        chat.user.web_socket_id = None

        # The actions run by the assistant are registered against chat.user (a
        # freshly fetched user that doesn't carry the request's session data).
        # Copy the client session id from the request onto it so the actions are
        # registered under the same session the client undoes with — otherwise
        # undo can't find them ("No more actions to undo").
        set_untrusted_client_session_id_from_request_or_raise_if_invalid(
            chat.user, request
        )

        # Used to group all the actions done to produce this message together
        # so they can be undone in one go.
        set_client_undo_redo_action_group_id(chat.user, str(uuid4()))

        # As long as we don't allow users to change it, temporarily set the timezone to
        # the one provided in the UI context so tools can use it if needed.
        chat.user.profile.timezone = ui_context.timezone

        human_message = HumanMessage(content=data["content"], ui_context=ui_context)

        async def stream_assistant_messages() -> AsyncIterator[str]:
            """Stream serialized assistant events from the lazy model run.

            :yield: Serialized assistant events.
            :return: An async iterator of serialized assistant events.
            """

            try:
                assistant = await sync_to_async(handler.get_assistant)(
                    chat, model_profile=model_profile
                )
                async with aclosing(
                    assistant.astream_messages(human_message)
                ) as messages:
                    async for msg in messages:
                        yield self._stream_assistant_message(msg)
            except AssistantMessageCancelled as exc:
                yield self._stream_assistant_message(
                    AiCancelledMessage(message_id=exc.message_id)
                )
            except Exception:
                logger.exception("Error while streaming assistant messages")
                yield self._stream_assistant_message(
                    AiErrorMessage(
                        content=(
                            "Oops, something went wrong and I cannot continue the conversation. "
                            "Please try again."
                        )
                    )
                )

        response = AssistantStreamingHttpResponse(
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
        description=("List all messages in the specified AI assistant chat.\n\n"),
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
        handler = AssistantHandler()
        chat = handler.get_chat(request.user, chat_uuid)

        workspace = chat.workspace
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

    @extend_schema(
        tags=["AI Assistant"],
        operation_id="cancel_assistant_message",
        description=(
            "Cancel an ongoing assistant message generation in the specified chat.\n\n"
        ),
        responses={
            204: OpenApiResponse(description="Message generation cancelled"),
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
    def delete(self, request: Request, chat_uuid: str) -> Response:
        handler = AssistantHandler()
        chat = handler.get_chat(request.user, chat_uuid)

        workspace = chat.workspace
        CoreHandler().check_permissions(
            request.user,
            ChatAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        set_assistant_cancellation_key(chat.uuid)

        return Response(status=HTTP_204_NO_CONTENT)


class AssistantChatMessageFeedbackView(APIView):
    @extend_schema(
        tags=["AI Assistant"],
        operation_id="submit_assistant_message_feedback",
        description=(
            "Provide sentiment and feedback for the given AI assistant chat message.\n\n"
        ),
        responses={
            200: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_CANNOT_SUBMIT_MESSAGE_FEEDBACK"]
            ),
        },
    )
    @validate_body(AssistantRateChatMessageSerializer, return_validated=True)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            AssistantChatDoesNotExist: ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST,
            AssistantChatMessagePredictionDoesNotExist: ERROR_CANNOT_SUBMIT_MESSAGE_FEEDBACK,
        }
    )
    def put(self, request: Request, message_id: int, data) -> Response:
        handler = AssistantHandler()
        message = handler.get_chat_message_by_id(request.user, message_id)
        try:
            prediction: AssistantChatPrediction = message.prediction
        except AttributeError:
            raise AssistantChatMessagePredictionDoesNotExist(
                f"Message with ID {message_id} does not have an associated prediction."
            )

        prediction.human_sentiment = data["sentiment"]
        prediction.human_feedback = data.get("feedback") or ""
        prediction.save(
            update_fields=["human_sentiment", "human_feedback", "updated_on"]
        )
        return Response(status=HTTP_204_NO_CONTENT)


class AssistantOnboardingPromptSuggestionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI Assistant"],
        operation_id="get_assistant_onboarding_prompt_suggestions",
        description=(
            "Suggests databases the user could create during the onboarding, based "
            "on the industry and team they provided. The first suggestion is the "
            "most relevant one.\n\n"
        ),
        request=OnboardingPromptSuggestionsRequestSerializer,
        responses={
            200: OnboardingPromptSuggestionsSerializer,
            400: get_error_schema(
                [
                    "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED",
                    "ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE",
                    "ERROR_ASSISTANT_MODEL_DISABLED",
                ]
            ),
        },
    )
    @validate_body(OnboardingPromptSuggestionsRequestSerializer, return_validated=True)
    @map_exceptions(
        {
            AssistantModelDisabledError: ERROR_ASSISTANT_MODEL_DISABLED,
            AssistantConfiguredModelNotAvailableError: (
                ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE
            ),
            AssistantModelNotSupportedError: ERROR_ASSISTANT_MODEL_NOT_SUPPORTED,
        }
    )
    def post(self, request: Request, data) -> Response:
        """Generate onboarding prompt suggestions with the resolved assistant model.

        :param request: The authenticated API request.
        :param data: The validated onboarding answers and requested language.
        :return: A response containing the generated prompt suggestions.
        """

        # This endpoint executes the instance-selected model without performing a
        # write first, so explicitly avoid resolving it from a lagging replica.
        set_db_alias(DEFAULT_DB_ALIAS)

        model_profile = resolve_assistant_model()
        check_lm_ready_or_raise(model_profile=model_profile)

        suggestions = generate_onboarding_prompt_suggestions(
            industry=data["industry"],
            team=data["team"],
            language=data["language"] or request.user.profile.language,
            model_profile=model_profile,
        )

        serializer = OnboardingPromptSuggestionsSerializer(
            {"suggestions": [s.model_dump() for s in suggestions]}
        )
        return Response(serializer.data)
