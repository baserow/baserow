from typing import Any
from uuid import UUID

from django.db import DEFAULT_DB_ALIAS
from django.http import StreamingHttpResponse

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.chat_runs.errors import (
    ERROR_CHAT_RUN_DOES_NOT_EXIST,
    ERROR_CHAT_RUN_IN_PROGRESS,
    ERROR_CHAT_RUN_LIMIT,
)
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
    set_untrusted_client_session_id_from_request_or_raise_if_invalid,
)
from baserow.config.db_routers import set_db_alias
from baserow.core.chat_runs.exceptions import (
    ChatRunAlreadyActive,
    ChatRunDoesNotExist,
    ChatRunLimitReached,
)
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.service import ChatRunService, serialize_run
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow_enterprise.assistant.exceptions import (
    AssistantChatDoesNotExist,
    AssistantChatMessagePredictionDoesNotExist,
    AssistantConfiguredModelNotAvailableError,
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
from baserow_enterprise.assistant.runs import ASSISTANT_RUN_TYPE
from baserow_enterprise.assistant.stream import stream_run_messages
from baserow_enterprise.assistant.types import UIContext

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
    AssistantRateChatMessageSerializer,
    OnboardingPromptSuggestionsRequestSerializer,
    OnboardingPromptSuggestionsSerializer,
)


def _run_payload(run: ChatRun) -> dict[str, Any]:
    """
    :param run: A Kuma run.
    :return: The run's saved state, with the id of the message it answers.
    """

    return {**serialize_run(run), "human_message_id": run.context["human_message_id"]}


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
            "Send a message to the specified AI assistant chat, or follow the run "
            "answering one, and stream back the response.\n\n"
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
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_ASSISTANT_MODEL_DISABLED",
                    "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED",
                    "ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE",
                ]
            ),
            404: get_error_schema(
                ["ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST", "ERROR_CHAT_RUN_DOES_NOT_EXIST"]
            ),
            409: get_error_schema(["ERROR_CHAT_RUN_IN_PROGRESS"]),
            429: get_error_schema(["ERROR_CHAT_RUN_LIMIT"]),
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
            ChatRunAlreadyActive: ERROR_CHAT_RUN_IN_PROGRESS,
            ChatRunLimitReached: ERROR_CHAT_RUN_LIMIT,
            ChatRunDoesNotExist: ERROR_CHAT_RUN_DOES_NOT_EXIST,
        }
    )
    def post(
        self, request: Request, chat_uuid: UUID, data: dict[str, Any]
    ) -> StreamingHttpResponse:
        """
        Sends a message, or follows the run answering one, and streams its output.

        :param request: The authenticated API request.
        :param chat_uuid: The client-generated chat identifier.
        :param data: The validated request: a message with its UI context, or a
            run to follow.
        :return: A streaming response containing assistant events.
        :raises ChatRunDoesNotExist: When run_id names a run of another chat or type.
        """

        # A lagging replica could revive a disabled model or a revoked membership.
        set_db_alias(DEFAULT_DB_ALIAS)
        handler = AssistantHandler()
        human_message = None
        if "run_id" in data:
            run = ChatRunService().get_run(request.user, data["run_id"])
            chat = handler.get_chat(request.user, chat_uuid)
            if run.run_type != ASSISTANT_RUN_TYPE or run.chat_id != chat.id:
                raise ChatRunDoesNotExist()
        else:
            ui_context = UIContext.from_validate_request(request, data["ui_context"])
            workspace = CoreHandler().get_workspace(ui_context.workspace.id)
            CoreHandler().check_permissions(
                request.user,
                ChatAssistantChatOperationType.type,
                workspace=workspace,
                context=workspace,
            )
            # Reject a foreign chat uuid before resolving this workspace's model.
            handler.get_existing_chat(request.user, workspace, chat_uuid)
            check_lm_ready_or_raise(
                model_profile=resolve_assistant_model(workspace=workspace)
            )
            set_untrusted_client_session_id_from_request_or_raise_if_invalid(
                request.user, request
            )
            run, human_message = handler.send_message(
                request.user,
                workspace,
                chat_uuid,
                data["content"],
                ui_context,
                data["tab_id"],
            )
        response = StreamingHttpResponse(
            stream_run_messages(
                run,
                request.user,
                cursor=data.get("cursor"),
                tab_id=data["tab_id"],
                human_message=human_message,
            ),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @extend_schema(
        tags=["AI Assistant"],
        operation_id="list_assistant_chat_messages",
        description=(
            "List all messages in the specified AI assistant chat, with the run "
            "answering its latest message while Kuma works on it.\n\n"
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
    def get(self, request: Request, chat_uuid: UUID) -> Response:
        """
        Lists the chat's messages with its active and latest runs, read together.

        :param request: The authenticated API request.
        :param chat_uuid: The chat identifier.
        :return: The chat id and title, its messages, and its active and latest runs.
        """

        # A replica can lag behind a chat or run created a moment ago.
        set_db_alias(DEFAULT_DB_ALIAS)
        handler = AssistantHandler()
        chat = handler.get_chat(request.user, chat_uuid)

        workspace = chat.workspace
        CoreHandler().check_permissions(
            request.user,
            ChatAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        snapshot = handler.get_chat_snapshot(chat)
        serializer = AssistantChatMessagesSerializer(
            {
                "chat_id": chat.id,
                "chat_title": snapshot.chat_title,
                "messages": snapshot.messages,
                "active_run": _run_payload(snapshot.active_run)
                if snapshot.active_run
                else None,
                "latest_run": _run_payload(snapshot.latest_run)
                if snapshot.latest_run
                else None,
            }
        )
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
    def delete(self, request: Request, chat_uuid: UUID) -> Response:
        set_db_alias(DEFAULT_DB_ALIAS)
        handler = AssistantHandler()
        chat = handler.get_chat(request.user, chat_uuid)

        workspace = chat.workspace
        CoreHandler().check_permissions(
            request.user,
            ChatAssistantChatOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        active = ChatRunHandler().get_active_run(ASSISTANT_RUN_TYPE, chat.id)
        if active is not None:
            ChatRunService().request_cancel(request.user, active.id)

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
