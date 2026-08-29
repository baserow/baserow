from django.conf import settings
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.pagination import LimitOffsetPagination
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.api.user_files.errors import ERROR_INVALID_USER_FILE_NAME_ERROR
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import ApplicationDoesNotExist, UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.services.registries import service_type_registry
from baserow.core.user_files.exceptions import InvalidUserFileNameError
from baserow_enterprise.agent_application.actions import UpdateAgentDefinitionActionType
from baserow_enterprise.agent_application.channels.handler import (
    AgentChatChannelHandler,
)
from baserow_enterprise.agent_application.channels.registries import (
    agent_chat_channel_type_registry,
)
from baserow_enterprise.agent_application.exceptions import (
    AgentChatAlreadyRunning,
    AgentChatAwaitingApproval,
    AgentChatChannelDoesNotExist,
    AgentChatDoesNotExist,
    AgentChatNotRetryable,
    AgentDefinitionDoesNotExist,
    AgentModelNotConfigured,
    AgentToolApprovalDoesNotExist,
    AgentToolDoesNotExist,
    AgentTriggerDoesNotExist,
)
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import AgentChatMessage
from baserow_enterprise.agent_application.operations import (
    CancelAgentChatOperationType,
    CreateAgentToolOperationType,
    DecideAgentToolApprovalOperationType,
    DeleteAgentChatOperationType,
    DeleteAgentToolOperationType,
    ListAgentChatsOperationType,
    ListAgentToolsOperationType,
    ReadAgentChatChannelOperationType,
    ReadAgentChatOperationType,
    ReadAgentDefinitionOperationType,
    ReadAgentTriggerOperationType,
    ReadAgentUsageOperationType,
    RunAgentChatOperationType,
    UpdateAgentChatChannelOperationType,
    UpdateAgentToolOperationType,
    UpdateAgentTriggerOperationType,
)
from baserow_enterprise.agent_application.realtime import (
    broadcast_configuration_updated,
)
from baserow_enterprise.agent_application.tools.handler import AgentToolHandler
from baserow_enterprise.agent_application.triggers.handler import AgentTriggerHandler

from .errors import (
    ERROR_AGENT_CHAT_ALREADY_RUNNING,
    ERROR_AGENT_CHAT_AWAITING_APPROVAL,
    ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST,
    ERROR_AGENT_CHAT_DOES_NOT_EXIST,
    ERROR_AGENT_CHAT_NOT_RETRYABLE,
    ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
    ERROR_AGENT_MODEL_NOT_CONFIGURED,
    ERROR_AGENT_TOOL_APPROVAL_DOES_NOT_EXIST,
    ERROR_AGENT_TOOL_DOES_NOT_EXIST,
    ERROR_AGENT_TRIGGER_DOES_NOT_EXIST,
)
from .serializers import (
    AgentApplicationToolApprovalSerializer,
    AgentChatMessageSerializer,
    AgentChatSerializer,
    AgentChatToolApprovalSerializer,
    AgentDefinitionSerializer,
    CreateAgentChatChannelSerializer,
    CreateAgentToolSerializer,
    CreateAgentTriggerSerializer,
    DecideAgentToolApprovalsSerializer,
    SendAgentChatMessageSerializer,
    UpdateAgentChatChannelSerializer,
    UpdateAgentDefinitionSerializer,
    UpdateAgentToolSerializer,
    UpdateAgentTriggerSerializer,
)


def _serialize_trigger(trigger) -> dict:
    service = trigger.service.specific
    return {
        "id": trigger.id,
        "enabled": trigger.enabled,
        "service_type": service.get_type().type,
        "service": service_type_registry.get_serializer(service).data,
    }


def _get_application_and_check(request, application_id, operation_type):
    application = CoreHandler().get_application(application_id).specific
    CoreHandler().check_permissions(
        request.user,
        operation_type.type,
        workspace=application.workspace,
        context=application.application_ptr,
    )
    return application


def _get_chat_and_check(request, chat_uuid, operation_type):
    chat = AgentChatHandler().get_chat_by_uuid(chat_uuid)
    application = chat.agent.application
    CoreHandler().check_permissions(
        request.user,
        operation_type.type,
        workspace=application.workspace,
        context=application.application_ptr,
    )
    return chat


class AgentDefinitionView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The agent application to fetch the agent of.",
            ),
        ],
        tags=["Agent"],
        operation_id="get_agent_application_agent",
        description="Returns the agent of the given agent application.",
        responses={
            200: AgentDefinitionSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                [
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                    "ERROR_AGENT_DEFINITION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int):
        application = CoreHandler().get_application(application_id).specific

        CoreHandler().check_permissions(
            request.user,
            ReadAgentDefinitionOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        agent = AgentApplicationHandler().get_main_agent(application)

        return Response(AgentDefinitionSerializer(agent).data)


class UpdateAgentDefinitionView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="agent_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The agent to update.",
            ),
        ],
        tags=["Agent"],
        operation_id="update_agent_application_agent",
        description="Updates the given agent's configuration.",
        request=UpdateAgentDefinitionSerializer,
        responses={
            200: AgentDefinitionSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_DEFINITION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(UpdateAgentDefinitionSerializer, partial=True, return_validated=True)
    def patch(self, request, agent_id: int, data: dict):
        agent = action_type_registry.get_by_type(UpdateAgentDefinitionActionType).do(
            request.user, agent_id, data
        )

        return Response(AgentDefinitionSerializer(agent).data)


class AgentChatsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="list_agent_application_chats",
        description=(
            "Lists the conversations of the application's agent, paginated "
            "with limit/offset."
        ),
        responses={
            200: get_example_pagination_serializer_class(AgentChatSerializer),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int):
        application = _get_application_and_check(
            request, application_id, ListAgentChatsOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)
        chats = AgentChatHandler().list_chats(agent)

        paginator = LimitOffsetPagination()
        paginator.default_limit = 50
        paginator.max_limit = 100
        page = paginator.paginate_queryset(chats, request, self)
        return paginator.get_paginated_response(
            AgentChatSerializer(page, many=True).data
        )


class AgentChatMessagesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
        ],
        tags=["Agent"],
        operation_id="list_agent_application_chat_messages",
        description="Lists the messages of an agent conversation.",
        responses={
            200: AgentChatMessageSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_CHAT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int, chat_uuid):
        chat = _get_chat_and_check(request, chat_uuid, ReadAgentChatOperationType)
        messages = AgentChatHandler().list_messages(chat)
        approvals = AgentChatHandler().list_tool_approvals(chat)
        return Response(
            {
                "chat": AgentChatSerializer(chat).data,
                "messages": AgentChatMessageSerializer(messages, many=True).data,
                "tool_approvals": AgentChatToolApprovalSerializer(
                    approvals, many=True
                ).data,
            }
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
        ],
        tags=["Agent"],
        operation_id="send_agent_application_chat_message",
        description=(
            "Sends a message to the agent. Creates the conversation when the "
            "uuid is new and starts a background run; the response streams to "
            "the application's websocket page."
        ),
        request=SendAgentChatMessageSerializer,
        responses={
            202: AgentChatSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_AGENT_CHAT_ALREADY_RUNNING",
                    "ERROR_AGENT_MODEL_NOT_CONFIGURED",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                    "ERROR_AGENT_CHAT_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            AgentChatAlreadyRunning: ERROR_AGENT_CHAT_ALREADY_RUNNING,
            AgentChatAwaitingApproval: ERROR_AGENT_CHAT_AWAITING_APPROVAL,
            AgentModelNotConfigured: ERROR_AGENT_MODEL_NOT_CONFIGURED,
            InvalidUserFileNameError: ERROR_INVALID_USER_FILE_NAME_ERROR,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(SendAgentChatMessageSerializer, return_validated=True)
    def post(self, request, application_id: int, chat_uuid, data: dict):
        application = _get_application_and_check(
            request, application_id, RunAgentChatOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)

        if not agent.ai_generative_ai_type or not agent.ai_generative_ai_model:
            raise AgentModelNotConfigured(
                "The agent has no generative AI model configured."
            )

        handler = AgentChatHandler()
        chat = handler.get_or_create_manual_chat(agent, request.user, chat_uuid)

        if chat.is_running:
            raise AgentChatAlreadyRunning(f"The chat {chat.id} is already running.")

        attachments = [
            {**user_file.serialize(), "visible_name": user_file.original_name}
            for user_file in data.get("user_files", [])
        ]

        with transaction.atomic():
            message = handler.create_message(
                chat,
                AgentChatMessage.Role.HUMAN,
                data["content"],
                attachments=attachments,
            )
            handler.start_chat_run(chat, message)

        response_data = AgentChatSerializer(chat).data
        response_data["prompt_message_id"] = message.id
        return Response(response_data, status=HTTP_202_ACCEPTED)


class AgentChatRetryView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
        ],
        tags=["Agent"],
        operation_id="retry_agent_application_chat",
        description=(
            "Re-runs the turn of a conversation that ended in an error, "
            "using its last prompt message."
        ),
        responses={
            202: AgentChatSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_AGENT_CHAT_NOT_RETRYABLE",
                    "ERROR_AGENT_CHAT_ALREADY_RUNNING",
                ]
            ),
            404: get_error_schema(["ERROR_AGENT_CHAT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            AgentChatNotRetryable: ERROR_AGENT_CHAT_NOT_RETRYABLE,
            AgentChatAlreadyRunning: ERROR_AGENT_CHAT_ALREADY_RUNNING,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def post(self, request, chat_uuid):
        chat = _get_chat_and_check(request, chat_uuid, RunAgentChatOperationType)

        with transaction.atomic():
            message = AgentChatHandler().retry_chat_run(chat)

        response_data = AgentChatSerializer(chat).data
        response_data["prompt_message_id"] = message.id
        return Response(response_data, status=HTTP_202_ACCEPTED)


class AgentChatCancelView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
        ],
        tags=["Agent"],
        operation_id="cancel_agent_application_chat",
        description="Cancels the running turn of an agent conversation.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_CHAT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def post(self, request, chat_uuid):
        chat = _get_chat_and_check(request, chat_uuid, CancelAgentChatOperationType)
        with transaction.atomic():
            AgentChatHandler().cancel_chat_run(chat, request.user)
        return Response(status=HTTP_204_NO_CONTENT)


class AgentChatView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
        ],
        tags=["Agent"],
        operation_id="delete_agent_application_chat",
        description="Deletes an agent conversation.",
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_AGENT_CHAT_ALREADY_RUNNING"]
            ),
            404: get_error_schema(["ERROR_AGENT_CHAT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            AgentChatAlreadyRunning: ERROR_AGENT_CHAT_ALREADY_RUNNING,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, chat_uuid):
        chat = _get_chat_and_check(request, chat_uuid, DeleteAgentChatOperationType)

        if chat.is_running:
            raise AgentChatAlreadyRunning(
                f"The chat {chat.id} is running and cannot be deleted."
            )

        AgentChatHandler().delete_chat(chat)
        return Response(status=HTTP_204_NO_CONTENT)


class AgentUsageView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="get_agent_application_usage",
        description="Returns the aggregated token usage of the agent.",
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int):
        application = _get_application_and_check(
            request, application_id, ReadAgentUsageOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)
        return Response(AgentChatHandler().get_agent_usage(agent))


class AgentTriggersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="list_agent_application_triggers",
        description="Lists the triggers of the agent application.",
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int):
        application = _get_application_and_check(
            request, application_id, ReadAgentTriggerOperationType
        )
        triggers = AgentTriggerHandler().list_triggers(application)
        return Response([_serialize_trigger(trigger) for trigger in triggers])

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="create_agent_application_trigger",
        description="Adds a trigger to the agent application.",
        request=CreateAgentTriggerSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(CreateAgentTriggerSerializer, return_validated=True)
    def post(self, request, application_id: int, data: dict):
        application = _get_application_and_check(
            request, application_id, UpdateAgentTriggerOperationType
        )

        with transaction.atomic():
            trigger = AgentTriggerHandler().create_trigger(
                request.user,
                application,
                data["service_type"],
                service_values=data.get("service"),
                enabled=data.get("enabled", True),
            )

        broadcast_configuration_updated(application)
        return Response(_serialize_trigger(trigger))


class AgentTriggerView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="trigger_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="update_agent_application_trigger",
        description="Updates a trigger of the agent application.",
        request=UpdateAgentTriggerSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_TRIGGER_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentTriggerDoesNotExist: ERROR_AGENT_TRIGGER_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(UpdateAgentTriggerSerializer, return_validated=True)
    def patch(self, request, trigger_id: int, data: dict):
        trigger = AgentTriggerHandler().get_trigger(trigger_id)
        application = trigger.application
        CoreHandler().check_permissions(
            request.user,
            UpdateAgentTriggerOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        with transaction.atomic():
            trigger = AgentTriggerHandler().update_trigger(
                request.user,
                trigger,
                service_values=data.get("service"),
                enabled=data.get("enabled"),
            )

        broadcast_configuration_updated(application)
        return Response(_serialize_trigger(trigger))

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="trigger_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="delete_agent_application_trigger",
        description="Removes a trigger from the agent application.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_TRIGGER_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentTriggerDoesNotExist: ERROR_AGENT_TRIGGER_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, trigger_id: int):
        trigger = AgentTriggerHandler().get_trigger(trigger_id)
        application = trigger.application
        CoreHandler().check_permissions(
            request.user,
            UpdateAgentTriggerOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        with transaction.atomic():
            AgentTriggerHandler().delete_trigger(trigger)

        broadcast_configuration_updated(application)
        return Response(status=HTTP_204_NO_CONTENT)


def _serialize_tool(tool) -> dict:
    service_data = None
    service_type = None
    if tool.service_id is not None:
        service = tool.service.specific
        service_type = service.get_type().type
        service_data = service_type_registry.get_serializer(service).data
    return {
        "id": tool.id,
        "type": tool.type,
        "name": tool.name,
        "config": tool.config,
        "order": tool.order,
        "service_type": service_type,
        "service": service_data,
    }


class AgentToolsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="list_agent_application_tools",
        description="Lists the tools enabled for the application's agent.",
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int):
        application = _get_application_and_check(
            request, application_id, ListAgentToolsOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)
        tools = AgentToolHandler().list_tools(agent)
        return Response([_serialize_tool(tool) for tool in tools])

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="create_agent_application_tool",
        description="Enables a tool for the application's agent.",
        request=CreateAgentToolSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(CreateAgentToolSerializer, return_validated=True)
    def post(self, request, application_id: int, data: dict):
        application = _get_application_and_check(
            request, application_id, CreateAgentToolOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)

        with transaction.atomic():
            tool = AgentToolHandler().create_tool(
                request.user,
                agent,
                data["type"],
                name=data.get("name", ""),
                config=data.get("config"),
                service_type_str=data.get("service_type"),
                service_values=data.get("service"),
            )

        broadcast_configuration_updated(application)
        return Response(_serialize_tool(tool))


class AgentToolView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="tool_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="update_agent_application_tool",
        description="Updates a tool of the application's agent.",
        request=UpdateAgentToolSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_TOOL_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentToolDoesNotExist: ERROR_AGENT_TOOL_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(UpdateAgentToolSerializer, return_validated=True)
    def patch(self, request, tool_id: int, data: dict):
        tool = AgentToolHandler().get_tool(tool_id)
        application = tool.agent.application
        CoreHandler().check_permissions(
            request.user,
            UpdateAgentToolOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        with transaction.atomic():
            tool = AgentToolHandler().update_tool(
                request.user,
                tool,
                name=data.get("name"),
                config=data.get("config"),
                service_values=data.get("service"),
            )

        broadcast_configuration_updated(application.specific)
        return Response(_serialize_tool(tool))

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="tool_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="delete_agent_application_tool",
        description="Removes a tool from the application's agent.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_TOOL_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentToolDoesNotExist: ERROR_AGENT_TOOL_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, tool_id: int):
        tool = AgentToolHandler().get_tool(tool_id)
        application = tool.agent.application
        CoreHandler().check_permissions(
            request.user,
            DeleteAgentToolOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        with transaction.atomic():
            AgentToolHandler().delete_tool(tool)

        broadcast_configuration_updated(application.specific)
        return Response(status=HTTP_204_NO_CONTENT)


class AgentApplicationApprovalsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="list_agent_application_pending_approvals",
        description=(
            "Lists the pending tool approvals of the agent application "
            "across all of its conversations."
        ),
        responses={
            200: AgentApplicationToolApprovalSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int):
        application = _get_application_and_check(
            request, application_id, ReadAgentChatOperationType
        )
        approvals = AgentChatHandler().list_pending_approvals(application)
        return Response(
            AgentApplicationToolApprovalSerializer(approvals, many=True).data
        )


class AgentWorkspaceToolsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="list_agent_application_workspace_tools",
        description=(
            "Lists every Baserow workspace tool the agent can be given "
            "access to, with its group and whether it changes data."
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int):
        from baserow_enterprise.agent_application.tools.workspace import (
            list_workspace_tools,
        )

        _get_application_and_check(
            request, application_id, ReadAgentDefinitionOperationType
        )
        return Response(list_workspace_tools())


class AgentChatApprovalsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
        ],
        tags=["Agent"],
        operation_id="list_agent_application_chat_approvals",
        description="Lists the tool approvals of an agent conversation.",
        responses={
            200: AgentChatToolApprovalSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_CHAT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, chat_uuid):
        chat = _get_chat_and_check(request, chat_uuid, ReadAgentChatOperationType)
        approvals = AgentChatHandler().list_tool_approvals(chat)
        return Response(AgentChatToolApprovalSerializer(approvals, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
        ],
        tags=["Agent"],
        operation_id="decide_agent_application_chat_approvals",
        description=(
            "Approves or rejects pending tool approvals of a paused agent "
            "conversation. Once every pending approval is decided, the run "
            "resumes automatically."
        ),
        request=DecideAgentToolApprovalsSerializer,
        responses={
            200: AgentChatToolApprovalSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                [
                    "ERROR_AGENT_CHAT_DOES_NOT_EXIST",
                    "ERROR_AGENT_TOOL_APPROVAL_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            AgentToolApprovalDoesNotExist: ERROR_AGENT_TOOL_APPROVAL_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(DecideAgentToolApprovalsSerializer, return_validated=True)
    def post(self, request, chat_uuid, data: dict):
        chat = _get_chat_and_check(
            request, chat_uuid, DecideAgentToolApprovalOperationType
        )

        with transaction.atomic():
            decided = AgentChatHandler().decide_tool_approvals(
                chat, request.user, data["decisions"]
            )

        return Response(AgentChatToolApprovalSerializer(decided, many=True).data)


def _serialize_channel(channel) -> dict:
    channel_type = agent_chat_channel_type_registry.get(channel.type)
    events_url = (
        f"{settings.PUBLIC_BACKEND_URL}/api/agent_application/channels/"
        f"{channel.uid}/events/"
    )
    return {
        "id": channel.id,
        "type": channel.type,
        "name": channel.name,
        "enabled": channel.enabled,
        "config": channel_type.get_public_config(channel),
        "events_url": events_url,
    }


class AgentChatChannelsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="list_agent_application_chat_channels",
        description="Lists the external chat channels of the agent application.",
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id: int):
        application = _get_application_and_check(
            request, application_id, ReadAgentChatChannelOperationType
        )
        channels = AgentChatChannelHandler().list_channels(application)
        return Response([_serialize_channel(channel) for channel in channels])

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="create_agent_application_chat_channel",
        description="Connects an external chat channel to the agent application.",
        request=CreateAgentChatChannelSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(CreateAgentChatChannelSerializer, return_validated=True)
    def post(self, request, application_id: int, data: dict):
        application = _get_application_and_check(
            request, application_id, UpdateAgentChatChannelOperationType
        )

        with transaction.atomic():
            channel = AgentChatChannelHandler().create_channel(
                application,
                data["type"],
                name=data.get("name", ""),
                config=data.get("config"),
                enabled=data.get("enabled", True),
            )

        broadcast_configuration_updated(application)
        return Response(_serialize_channel(channel))


class AgentChatChannelView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="channel_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="update_agent_application_chat_channel",
        description="Updates an external chat channel of the agent application.",
        request=UpdateAgentChatChannelSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatChannelDoesNotExist: ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(UpdateAgentChatChannelSerializer, return_validated=True)
    def patch(self, request, channel_id: int, data: dict):
        channel = AgentChatChannelHandler().get_channel(channel_id)
        application = channel.application
        CoreHandler().check_permissions(
            request.user,
            UpdateAgentChatChannelOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        with transaction.atomic():
            channel = AgentChatChannelHandler().update_channel(
                channel,
                name=data.get("name"),
                config=data.get("config"),
                enabled=data.get("enabled"),
            )

        broadcast_configuration_updated(application)
        return Response(_serialize_channel(channel))

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="channel_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="delete_agent_application_chat_channel",
        description="Removes an external chat channel from the agent application.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatChannelDoesNotExist: ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, channel_id: int):
        channel = AgentChatChannelHandler().get_channel(channel_id)
        application = channel.application
        CoreHandler().check_permissions(
            request.user,
            UpdateAgentChatChannelOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        with transaction.atomic():
            AgentChatChannelHandler().delete_channel(channel)

        broadcast_configuration_updated(application)
        return Response(status=HTTP_204_NO_CONTENT)


class AgentChatChannelEventsView(APIView):
    """
    Public inbound webhook for external chat services. The channel is
    identified by its unguessable uid; the channel type verifies the request
    (e.g. the Slack signature) before anything is processed.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(exclude=True)
    def post(self, request, channel_uid):
        try:
            channel = AgentChatChannelHandler().get_channel_by_uid(channel_uid)
        except AgentChatChannelDoesNotExist:
            return Response(status=HTTP_204_NO_CONTENT)

        channel_type = agent_chat_channel_type_registry.get(channel.type)
        return channel_type.handle_inbound(channel, request)
