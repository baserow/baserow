import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.http import StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.chat_runs.errors import (
    ERROR_CHAT_RUN_DOES_NOT_EXIST,
    ERROR_CHAT_RUN_IN_PROGRESS,
)
from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.schemas import get_error_schema
from baserow.config.db_routers import set_db_alias
from baserow.contrib.agent.api.channels.errors import (
    ERROR_AGENT_CHANNEL_DOES_NOT_EXIST,
)
from baserow.contrib.agent.api.errors import (
    ERROR_AGENT_BUSY,
    ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST,
    ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL,
    ERROR_AGENT_MESSAGE_CONFLICT,
    ERROR_AGENT_NOT_READY,
)
from baserow.contrib.agent.api.serializers import AgentMessageCreateSerializer
from baserow.contrib.agent.channels.exceptions import AgentChannelDoesNotExist
from baserow.contrib.agent.channels.visitors import AgentVisitorService
from baserow.contrib.agent.exceptions import (
    AgentConversationDoesNotExist,
    AgentConversationWaitingForApproval,
    AgentMessageConflict,
    AgentNotReady,
)
from baserow.contrib.agent.types import AgentMessageCreated
from baserow.core.chat_runs.constants import ChatRunEventKind
from baserow.core.chat_runs.exceptions import (
    ChatRunAlreadyActive,
    ChatRunDoesNotExist,
    ChatRunLimitReached,
)
from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.service import serialize_run
from baserow.core.chat_runs.stream import follow_run
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow_enterprise.agent.constants import PUBLIC_CHAT_CONVERSATION_CLAIM
from baserow_enterprise.agent.models import PublicChatAgentChannel
from baserow_enterprise.agent.public_chat_tokens import (
    decode_token,
    encode_access_token,
    encode_conversation_token,
)

from .serializers import (
    PublicChatAuthRequestSerializer,
    PublicChatAuthResponseSerializer,
    PublicChatConversationSerializer,
    PublicChatConversationStartedSerializer,
    PublicChatConversationStartSerializer,
    PublicChatInfoSerializer,
    PublicChatMessageSerializer,
    PublicChatStopSerializer,
    PublicChatStreamQuerySerializer,
)

SLUG_PARAMETER = OpenApiParameter(
    name="slug",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.STR,
    required=True,
    description="The link of the public chat.",
)
PUBLIC_CHAT_EXCEPTIONS = {
    AgentChannelDoesNotExist: ERROR_AGENT_CHANNEL_DOES_NOT_EXIST,
    ApplicationDoesNotExist: ERROR_AGENT_CHANNEL_DOES_NOT_EXIST,
    AgentConversationDoesNotExist: ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST,
    AgentNotReady: ERROR_AGENT_NOT_READY,
    AgentConversationWaitingForApproval: ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL,
    AgentMessageConflict: ERROR_AGENT_MESSAGE_CONFLICT,
    ChatRunAlreadyActive: ERROR_CHAT_RUN_IN_PROGRESS,
    ChatRunLimitReached: ERROR_AGENT_BUSY,
    ChatRunDoesNotExist: ERROR_CHAT_RUN_DOES_NOT_EXIST,
}
VISITOR_RECORD_KEYS = {
    ChatRunEventKind.TEXT_DELTA: ("segment", "text"),
    "run.baseline": ("segment", "text"),
    ChatRunEventKind.RUN_HEARTBEAT: (),
    "run.replay_unavailable": ("reason",),
}
CHAT_ERRORS = {404: get_error_schema(["ERROR_AGENT_CHANNEL_DOES_NOT_EXIST"])}
CONVERSATION_ERRORS = {
    401: {"description": "The token is missing or doesn't open a conversation."},
    404: get_error_schema(
        [
            "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST",
            "ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST",
        ]
    ),
}
WRITE_ERRORS = {
    400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION", "ERROR_AGENT_NOT_READY"]),
    429: get_error_schema(["ERROR_AGENT_BUSY"]),
}


def get_public_chat(slug: str) -> PublicChatAgentChannel:
    """
    :param slug: The link of the public chat.
    :raises AgentChannelDoesNotExist: When no chat has this link, or it can't be
        used.
    :return: The chat, with its agent and the agent's workspace.
    """

    # A replica can still serve a chat that was just switched off or protected.
    set_db_alias(DEFAULT_DB_ALIAS)
    try:
        chat = PublicChatAgentChannel.objects.select_related("agent__workspace").get(
            slug=slug
        )
    except PublicChatAgentChannel.DoesNotExist as exc:
        raise AgentChannelDoesNotExist from exc
    AgentVisitorService().require_available(chat)
    return chat


def get_chat_token(request: Request) -> str | None:
    """
    :param request: The visitor's request.
    :return: The token of the request's authorization header, if any.
    """

    header = request.headers.get(settings.PUBLIC_AGENT_CHAT_AUTHORIZATION_HEADER)
    try:
        _, token = header.split(" ", 1)
    except (AttributeError, ValueError):
        return None
    return token


def has_access(chat: PublicChatAgentChannel, request: Request) -> bool:
    """
    :param chat: The public chat.
    :param request: The visitor's request.
    :return: Whether the chat has no password, or the request carries a token that
        proves it.
    """

    return (
        not chat.has_password or decode_token(chat, get_chat_token(request)) is not None
    )


def get_conversation_uuid(chat: PublicChatAgentChannel, request: Request) -> UUID:
    """
    :param chat: The public chat.
    :param request: The visitor's request.
    :raises AuthenticationFailed: When the request carries no token of a
        conversation of this chat's current link and password.
    :return: The uuid of the conversation the token opens.
    """

    payload = decode_token(chat, get_chat_token(request)) or {}
    try:
        return UUID(payload[PUBLIC_CHAT_CONVERSATION_CLAIM])
    except (KeyError, TypeError, ValueError):
        raise AuthenticationFailed() from None


def serialize_accepted(result: AgentMessageCreated) -> dict[str, Any]:
    """
    :param result: The accepted visitor message.
    :return: The message and its reply, and the run writing the reply.
    """

    return {"messages": [result.message, result.reply], "run_id": result.run_id}


def to_visitor_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """
    :param record: A record of the stream members follow.
    :return: What a visitor may see of the record: the answer's text and how the
        run ended, or None to drop it.
    """

    kind, data = record["kind"], record["data"]
    if kind == ChatRunEventKind.RUN_FINISHED:
        message = data["message"]
        data = {
            "status": data["status"],
            "message": (
                None if message is None else PublicChatMessageSerializer(message).data
            ),
        }
    elif kind in VISITOR_RECORD_KEYS and data.get("variant") is None:
        data = {key: data[key] for key in VISITOR_RECORD_KEYS[kind] if key in data}
    else:
        return None
    return {
        "kind": kind,
        "data": data,
        "cursor": record["cursor"],
        "replayed": record["replayed"],
    }


async def encode_visitor_records(
    run: ChatRun, cursor: str | None, initial_state: dict[str, Any]
) -> AsyncIterator[str]:
    """
    :param run: The run writing a reply of the visitor's conversation.
    :param cursor: The cursor to resume after, or None to read from the start.
    :param initial_state: The run's saved state.
    :return: What a visitor may see of the run's records, as JSON separated by
        blank lines.
    """

    async with aclosing(
        follow_run(run, None, cursor, initial_state=initial_state)
    ) as records:
        async for record in records:
            if (shown := to_visitor_record(record)) is not None:
                yield json.dumps(shown) + "\n\n"


@method_decorator(never_cache, name="dispatch")
class PublicChatView(APIView):
    """Anonymous, and never cached: the answer depends on the visitor's token."""

    permission_classes = (AllowAny,)


class PublicChatInfoView(PublicChatView):
    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Agent public chat"],
        operation_id="get_agent_public_chat_info",
        description="Returns what the page of a public chat shows before a message.",
        responses={200: PublicChatInfoSerializer, **CHAT_ERRORS},
    )
    @map_exceptions(PUBLIC_CHAT_EXCEPTIONS)
    def get(self, request: Request, slug: str) -> Response:
        chat = get_public_chat(slug)
        allowed = has_access(chat, request)
        return Response(
            PublicChatInfoSerializer(
                {
                    "title": (chat.title or chat.agent.name) if allowed else "",
                    "welcome_text": chat.welcome_text if allowed else "",
                    "password_protected": chat.has_password,
                    "has_access": allowed,
                }
            ).data
        )


class PublicChatAuthView(PublicChatView):
    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Agent public chat"],
        operation_id="agent_public_chat_token_auth",
        description=(
            "Exchanges the password of a public chat for a token that lets the "
            "visitor start a conversation."
        ),
        request=PublicChatAuthRequestSerializer,
        responses={
            200: PublicChatAuthResponseSerializer,
            401: {"description": "The password is incorrect."},
            **CHAT_ERRORS,
        },
    )
    @map_exceptions(PUBLIC_CHAT_EXCEPTIONS)
    @validate_body(PublicChatAuthRequestSerializer, return_validated=True)
    def post(self, request: Request, slug: str, data: dict[str, str]) -> Response:
        chat = get_public_chat(slug)
        if not chat.check_password(data["password"]):
            raise AuthenticationFailed()
        return Response(
            PublicChatAuthResponseSerializer(
                {"access_token": encode_access_token(chat)}
            ).data
        )


class PublicChatConversationsView(PublicChatView):
    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Agent public chat"],
        operation_id="start_agent_public_chat_conversation",
        description=(
            "Starts a conversation with the visitor's first message and returns the "
            "token that opens it, also when the same key and content are sent "
            "again. A password protected chat needs the token from its auth "
            "endpoint."
        ),
        request=PublicChatConversationStartSerializer,
        responses={
            200: PublicChatConversationStartedSerializer,
            401: {
                "description": "The chat is password protected and no valid "
                "token was sent."
            },
            404: CONVERSATION_ERRORS[404],
            409: get_error_schema(["ERROR_AGENT_MESSAGE_CONFLICT"]),
            **WRITE_ERRORS,
        },
    )
    @map_exceptions(PUBLIC_CHAT_EXCEPTIONS)
    @validate_body(PublicChatConversationStartSerializer, return_validated=True)
    def post(self, request: Request, slug: str, data: dict[str, Any]) -> Response:
        chat = get_public_chat(slug)
        if not has_access(chat, request):
            raise AuthenticationFailed()
        result = AgentVisitorService().start_conversation(
            chat, data["key"], data["content"]
        )
        return Response(
            PublicChatConversationStartedSerializer(
                {
                    "token": encode_conversation_token(chat, result.conversation),
                    **serialize_accepted(result),
                }
            ).data
        )


class PublicChatConversationView(PublicChatView):
    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Agent public chat"],
        operation_id="get_agent_public_chat_conversation",
        description=(
            "Returns the latest messages of the visitor's conversation, oldest "
            "first, and the run writing a reply now."
        ),
        responses={200: PublicChatConversationSerializer, **CONVERSATION_ERRORS},
    )
    @map_exceptions(PUBLIC_CHAT_EXCEPTIONS)
    def get(self, request: Request, slug: str) -> Response:
        chat = get_public_chat(slug)
        conversation = AgentVisitorService().get_conversation(
            chat, get_conversation_uuid(chat, request)
        )
        return Response(PublicChatConversationSerializer(conversation).data)


class PublicChatMessagesView(PublicChatView):
    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Agent public chat"],
        operation_id="create_agent_public_chat_message",
        description=(
            "Adds the visitor's next message to their conversation, or returns it "
            "when the same uuid is sent again."
        ),
        request=AgentMessageCreateSerializer,
        responses={
            200: PublicChatConversationSerializer,
            **CONVERSATION_ERRORS,
            **WRITE_ERRORS,
            409: get_error_schema(
                [
                    "ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL",
                    "ERROR_AGENT_MESSAGE_CONFLICT",
                    "ERROR_CHAT_RUN_IN_PROGRESS",
                ]
            ),
        },
    )
    @map_exceptions(PUBLIC_CHAT_EXCEPTIONS)
    @validate_body(AgentMessageCreateSerializer, return_validated=True)
    def post(self, request: Request, slug: str, data: dict[str, Any]) -> Response:
        chat = get_public_chat(slug)
        result = AgentVisitorService().send_message(
            chat, get_conversation_uuid(chat, request), data["uuid"], data["content"]
        )
        return Response(
            PublicChatConversationSerializer(serialize_accepted(result)).data
        )


class PublicChatStopView(PublicChatView):
    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Agent public chat"],
        operation_id="stop_agent_public_chat_reply",
        description="Stops the reply the agent is writing in the conversation.",
        request=None,
        responses={200: PublicChatStopSerializer, **CONVERSATION_ERRORS},
    )
    @map_exceptions(PUBLIC_CHAT_EXCEPTIONS)
    def post(self, request: Request, slug: str) -> Response:
        chat = get_public_chat(slug)
        status = AgentVisitorService().stop_reply(
            chat, get_conversation_uuid(chat, request)
        )
        return Response(PublicChatStopSerializer({"status": status}).data)


class PublicChatStreamView(PublicChatView):
    # Django serves HEAD with get, which the stream router wouldn't cap.
    http_method_names = ["get", "options"]

    @extend_schema(
        parameters=[SLUG_PARAMETER, PublicChatStreamQuerySerializer],
        tags=["Agent public chat"],
        operation_id="stream_agent_public_chat_reply",
        description=(
            "Follows the text of a reply of the visitor's conversation as JSON "
            "records separated by blank lines, ending with `run.finished`. While no "
            "text arrives, a `run.heartbeat` record is sent every few seconds. Pass "
            "the last received `cursor` to resume."
        ),
        responses={
            (200, "text/event-stream"): OpenApiTypes.STR,
            400: get_error_schema(["ERROR_QUERY_PARAMETER_VALIDATION"]),
            401: CONVERSATION_ERRORS[401],
            404: get_error_schema(
                [
                    "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST",
                    "ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST",
                    "ERROR_CHAT_RUN_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(PUBLIC_CHAT_EXCEPTIONS)
    @validate_query_parameters(PublicChatStreamQuerySerializer, return_validated=True)
    def get(
        self, request: Request, slug: str, query_params: dict[str, Any]
    ) -> StreamingHttpResponse:
        chat = get_public_chat(slug)
        run = AgentVisitorService().get_run(
            chat, get_conversation_uuid(chat, request), query_params["run_id"]
        )
        response = StreamingHttpResponse(
            encode_visitor_records(run, query_params.get("cursor"), serialize_run(run)),
            content_type="text/event-stream",
        )
        response["X-Accel-Buffering"] = "no"
        return response
