"""
Public endpoints of the agent "Web chat" channel, reachable without a Baserow
account. Everything they return goes through `public_serializers.py`; see the
exposure contract in `agent_application/channels/web.py` before adding data.
"""

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_202_ACCEPTED
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.core.utils import get_user_remote_ip_address_from_request
from baserow.throttling.exceptions import RateLimitExceededException
from baserow.throttling.handler import rate_limit
from baserow.throttling.types import RateLimit
from baserow_enterprise.agent_application.channels.registries import (
    agent_chat_channel_type_registry,
)
from baserow_enterprise.agent_application.channels.web import (
    WebAgentChatChannelType,
)
from baserow_enterprise.agent_application.channels.website import (
    WebsiteWidgetAgentChatChannelType,
)
from baserow_enterprise.agent_application.exceptions import (
    AgentChatAlreadyRunning,
    AgentChatAwaitingApproval,
    AgentChatChannelDoesNotExist,
    AgentChatDoesNotExist,
    PublicChatAuthorizationRequired,
    PublicChatMessageLimitReached,
)
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import AgentChatMessage

from .errors import (
    ERROR_AGENT_CHAT_ALREADY_RUNNING,
    ERROR_AGENT_CHAT_AWAITING_APPROVAL,
    ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST,
    ERROR_AGENT_CHAT_DOES_NOT_EXIST,
    ERROR_PUBLIC_CHAT_AUTHORIZATION_REQUIRED,
    ERROR_PUBLIC_CHAT_MESSAGE_LIMIT_REACHED,
    ERROR_PUBLIC_CHAT_RATE_LIMIT_EXCEEDED,
)
from .public_serializers import (
    PublicAgentChatAuthRequestSerializer,
    PublicAgentChatAuthResponseSerializer,
    PublicAgentChatInfoSerializer,
    PublicAgentChatSendMessageSerializer,
    serialize_public_conversation,
)

PUBLIC_CHAT_ERRORS = {
    AgentChatChannelDoesNotExist: ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST,
    PublicChatAuthorizationRequired: ERROR_PUBLIC_CHAT_AUTHORIZATION_REQUIRED,
    RateLimitExceededException: ERROR_PUBLIC_CHAT_RATE_LIMIT_EXCEEDED,
}
# Password attempts per IP, independent of the message limit.
AUTH_RATE_LIMIT = RateLimit.from_string("10/m")


def _get_token(request) -> str | None:
    value = request.headers.get(settings.PUBLIC_AGENT_CHAT_AUTHORIZATION_HEADER)
    if not value:
        return None
    parts = value.split(" ", 1)
    return parts[1] if len(parts) == 2 and parts[0] == "JWT" else None


def _get_channel(slug: str, request, require_token: bool = True):
    """
    The channel behind a public link. Disabled channels, inactive agents and
    unknown links are all reported as missing so nothing leaks.
    """

    channel = AgentChatHandler().get_public_web_channel(slug)
    if channel is None:
        raise AgentChatChannelDoesNotExist(f"No public chat for slug {slug}.")
    channel_type = agent_chat_channel_type_registry.get(channel.type)
    if (
        require_token
        and channel_type.has_password(channel)
        and not channel_type.is_token_valid(channel, _get_token(request))
    ):
        raise PublicChatAuthorizationRequired()
    return channel


def _get_chat(channel, chat_uuid):
    chat = AgentChatHandler().get_public_chat(channel, chat_uuid)
    if chat is None:
        raise AgentChatDoesNotExist(f"No conversation {chat_uuid}.")
    return chat


def _visitor_key(request) -> str:
    return get_user_remote_ip_address_from_request(request) or "unknown"


class PublicAgentChatView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Agent public chat"],
        operation_id="get_public_agent_chat",
        description=(
            "Returns the title and welcome text of an agent's public web chat. "
            "Requires the chat's access token when it is password protected."
        ),
        responses={200: PublicAgentChatInfoSerializer, 401: None, 404: None},
    )
    @map_exceptions(PUBLIC_CHAT_ERRORS)
    def get(self, request, slug):
        channel = _get_channel(slug, request)
        config = channel.config
        agent = AgentApplicationHandler().get_main_agent(channel.application)
        return Response(
            {
                "title": config.get("title") or agent.name,
                "welcome_text": config.get("welcome_text", ""),
                "agent_name": agent.name,
                "has_password": WebAgentChatChannelType().has_password(channel),
            }
        )


class PublicAgentChatAuthView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Agent public chat"],
        operation_id="authorize_public_agent_chat",
        description=(
            "Exchanges the password of a protected public web chat for an "
            "access token to send in the "
            "`Baserow-Agent-Chat-Authorization: JWT <token>` header."
        ),
        request=PublicAgentChatAuthRequestSerializer,
        responses={200: PublicAgentChatAuthResponseSerializer, 401: None},
    )
    @map_exceptions(PUBLIC_CHAT_ERRORS)
    @validate_body(PublicAgentChatAuthRequestSerializer, return_validated=True)
    def post(self, request, slug, data):
        channel = _get_channel(slug, request, require_token=False)
        channel_type = WebAgentChatChannelType()

        def check():
            if not channel_type.check_password(channel, data["password"]):
                raise PublicChatAuthorizationRequired()

        rate_limit(AUTH_RATE_LIMIT, key=f"public_chat_auth:{_visitor_key(request)}")(
            check
        )()
        return Response({"access_token": channel_type.encode_token(channel)})


class PublicAgentChatConversationsView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Agent public chat"],
        operation_id="create_public_agent_chat_conversation",
        description="Starts a new conversation with the agent behind a public link.",
        responses={201: None, 401: None, 404: None},
    )
    @map_exceptions(PUBLIC_CHAT_ERRORS)
    def post(self, request, slug):
        channel = _get_channel(slug, request)

        def create():
            return AgentChatHandler().create_public_chat(channel)

        chat = rate_limit(
            RateLimit(60, settings.AGENT_PUBLIC_CHAT_RATE_LIMIT_PER_MINUTE),
            key=f"public_chat_create:{_visitor_key(request)}",
        )(create)()
        return Response(
            serialize_public_conversation(chat, []), status=HTTP_201_CREATED
        )


class PublicAgentChatConversationView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Agent public chat"],
        operation_id="get_public_agent_chat_conversation",
        description=(
            "Returns the visitor's messages, the agent's answers and the "
            "conversation status. Used to load the page and as the polling "
            "fallback when realtime is unavailable."
        ),
        responses={200: None, 401: None, 404: None},
    )
    @map_exceptions(
        {**PUBLIC_CHAT_ERRORS, AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST}
    )
    def get(self, request, slug, chat_uuid):
        channel = _get_channel(slug, request)
        chat = _get_chat(channel, chat_uuid)
        messages = chat.messages.order_by("id")
        return Response(serialize_public_conversation(chat, messages))


class PublicAgentChatMessagesView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Agent public chat"],
        operation_id="send_public_agent_chat_message",
        description="Sends a visitor message and starts the agent's answer.",
        request=PublicAgentChatSendMessageSerializer,
        responses={202: None, 401: None, 404: None, 409: None, 429: None},
    )
    @map_exceptions(
        {
            **PUBLIC_CHAT_ERRORS,
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            AgentChatAlreadyRunning: ERROR_AGENT_CHAT_ALREADY_RUNNING,
            AgentChatAwaitingApproval: ERROR_AGENT_CHAT_AWAITING_APPROVAL,
            PublicChatMessageLimitReached: ERROR_PUBLIC_CHAT_MESSAGE_LIMIT_REACHED,
        }
    )
    @validate_body(PublicAgentChatSendMessageSerializer, return_validated=True)
    def post(self, request, slug, chat_uuid, data):
        channel = _get_channel(slug, request)
        chat = _get_chat(channel, chat_uuid)
        handler = AgentChatHandler()

        if chat.is_running:
            raise AgentChatAlreadyRunning(f"The chat {chat.id} is already running.")
        if chat.is_awaiting_approval:
            raise AgentChatAwaitingApproval(f"The chat {chat.id} awaits approval.")
        human_messages = chat.messages.filter(role=AgentChatMessage.Role.HUMAN).count()
        if human_messages >= settings.AGENT_PUBLIC_CHAT_MAX_MESSAGES:
            raise PublicChatMessageLimitReached()
        # The channel-wide limit protects the agent from a flood across all
        # visitors; it counts like a visitor's own limit.
        if WebAgentChatChannelType().is_rate_limited(channel):
            raise RateLimitExceededException("Channel limit exceeded")

        def send():
            with transaction.atomic():
                message = handler.create_message(
                    chat, AgentChatMessage.Role.HUMAN, data["content"]
                )
                handler.start_chat_run(chat, message)
            return message

        message = rate_limit(
            RateLimit(60, settings.AGENT_PUBLIC_CHAT_RATE_LIMIT_PER_MINUTE),
            key=f"public_chat_message:{_visitor_key(request)}",
        )(send)()
        return Response(
            {"message_id": message.id, "status": "working"}, status=HTTP_202_ACCEPTED
        )


class PublicAgentWidgetScriptView(APIView):
    """
    The embed script of a website widget channel. It is plain JavaScript, so
    a `<script src>` on any site can load it without CORS, and it is served
    uncached so widget settings apply as soon as they change.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Agent application"],
        operation_id="get_agent_widget_script",
        description=(
            "Returns the JavaScript that embeds the agent chat widget of a "
            "website channel. Only channels of that type serve a script."
        ),
        responses={200: None, 404: None},
    )
    def get(self, request, slug):
        channel = AgentChatHandler().get_public_web_channel(slug)
        channel_type = WebsiteWidgetAgentChatChannelType()
        if channel is None or channel.type != channel_type.type:
            return HttpResponse(status=404)
        response = HttpResponse(
            channel_type.build_script(channel),
            content_type="application/javascript; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache"
        return response
