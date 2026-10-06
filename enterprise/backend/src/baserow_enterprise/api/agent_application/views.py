from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.pagination import LimitOffsetPagination
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.api.skills.errors import ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST
from baserow.api.user_files.errors import ERROR_INVALID_USER_FILE_NAME_ERROR
from baserow.core.action.registries import action_type_registry
from baserow.core.db import specific_iterator
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.handler import CoreHandler
from baserow.core.operations import CreateApplicationsWorkspaceOperationType
from baserow.core.services.models import Service
from baserow.core.skills.exceptions import WorkspaceSkillDoesNotExist
from baserow.core.user_files.exceptions import InvalidUserFileNameError
from baserow_enterprise.agent_application.actions import (
    CancelAgentChatRunActionType,
    CreateAgentChatChannelActionType,
    CreateAgentToolActionType,
    CreateAgentTriggerActionType,
    DecideAgentToolApprovalActionType,
    DeleteAgentChatActionType,
    DeleteAgentChatChannelActionType,
    DeleteAgentToolActionType,
    DeleteAgentTriggerActionType,
    RetryAgentChatRunActionType,
    RotateAgentChatChannelLinkActionType,
    RunAgentOnceActionType,
    UpdateAgentChatActionType,
    UpdateAgentChatChannelActionType,
    UpdateAgentDefinitionActionType,
    UpdateAgentToolActionType,
    UpdateAgentTriggerActionType,
)
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
    AgentChatNotOwned,
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
from baserow_enterprise.agent_application.instructions import (
    draft_instructions,
    improve_instructions,
)
from baserow_enterprise.agent_application.models import AgentChatMessage
from baserow_enterprise.agent_application.operations import (
    CancelAgentChatOperationType,
    CreateAgentToolOperationType,
    DecideAgentToolApprovalOperationType,
    DeleteAgentChatChannelOperationType,
    DeleteAgentChatOperationType,
    DeleteAgentToolOperationType,
    DeleteAgentTriggerOperationType,
    ListAgentChatsOperationType,
    ListAgentToolsOperationType,
    ReadAgentChatChannelOperationType,
    ReadAgentChatOperationType,
    ReadAgentDefinitionOperationType,
    ReadAgentTriggerOperationType,
    ReadAgentUsageOperationType,
    RunAgentChatOperationType,
    UpdateAgentChatChannelOperationType,
    UpdateAgentChatOperationType,
    UpdateAgentDefinitionOperationType,
    UpdateAgentToolOperationType,
    UpdateAgentTriggerOperationType,
)
from baserow_enterprise.agent_application.tools.handler import AgentToolHandler
from baserow_enterprise.agent_application.triggers.handler import AgentTriggerHandler
from baserow_enterprise.api.assistant.errors import (
    ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE,
    ERROR_ASSISTANT_MODEL_DISABLED,
    ERROR_ASSISTANT_MODEL_NOT_SUPPORTED,
)
from baserow_enterprise.assistant.exceptions import (
    AssistantConfiguredModelNotAvailableError,
    AssistantModelDisabledError,
    AssistantModelNotSupportedError,
)

from .errors import (
    ERROR_AGENT_CHAT_ALREADY_RUNNING,
    ERROR_AGENT_CHAT_AWAITING_APPROVAL,
    ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST,
    ERROR_AGENT_CHAT_DOES_NOT_EXIST,
    ERROR_AGENT_CHAT_NOT_OWNED,
    ERROR_AGENT_CHAT_NOT_RETRYABLE,
    ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
    ERROR_AGENT_MODEL_NOT_CONFIGURED,
    ERROR_AGENT_TOOL_APPROVAL_DOES_NOT_EXIST,
    ERROR_AGENT_TOOL_DOES_NOT_EXIST,
    ERROR_AGENT_TRIGGER_DOES_NOT_EXIST,
)
from .serializers import (
    AgentApplicationToolApprovalSerializer,
    AgentChatChannelSerializer,
    AgentChatRunStartedSerializer,
    AgentChatSerializer,
    AgentChatToolApprovalSerializer,
    AgentChatTranscriptSerializer,
    AgentDefinitionSerializer,
    AgentInstructionsSerializer,
    AgentToolSerializer,
    AgentTriggerSerializer,
    AgentUsageSerializer,
    AgentWorkspaceToolSerializer,
    CreateAgentChatChannelSerializer,
    CreateAgentToolSerializer,
    CreateAgentTriggerSerializer,
    DecideAgentToolApprovalsSerializer,
    DraftAgentInstructionsSerializer,
    ImproveAgentInstructionsSerializer,
    SendAgentChatMessageSerializer,
    UpdateAgentChatChannelSerializer,
    UpdateAgentChatSerializer,
    UpdateAgentDefinitionSerializer,
    UpdateAgentToolSerializer,
    UpdateAgentTriggerSerializer,
)


def _with_specific_services(items: list) -> list:
    """
    Serializing a trigger or tool needs its specific service. Loading them in
    bulk costs one query per service type instead of one per item, and
    `.specific` on the assigned instance is then a no-op.
    """

    services = [item.service for item in items if item.service_id is not None]
    specific_by_id = {
        service.id: service
        for service in specific_iterator(services, base_model=Service)
    }
    for item in items:
        if item.service_id is not None:
            item.service = specific_by_id[item.service_id]
    return items


def _get_application_and_check(request, application_id, operation_type):
    application = CoreHandler().get_application(application_id).specific
    CoreHandler().check_permissions(
        request.user,
        operation_type.type,
        workspace=application.workspace,
        context=application.application_ptr,
    )
    return application


def _get_agent_and_check(request, agent_id, operation_type):
    agent = AgentApplicationHandler().get_agent(agent_id)
    application = agent.application
    CoreHandler().check_permissions(
        request.user,
        operation_type.type,
        workspace=application.workspace,
        context=application.application_ptr,
    )
    return agent


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
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="update_agent_application_agent",
        description="Updates the given agent's configuration.",
        request=UpdateAgentDefinitionSerializer,
        responses={
            200: AgentDefinitionSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(
                [
                    "ERROR_AGENT_DEFINITION_DOES_NOT_EXIST",
                    "ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceSkillDoesNotExist: ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST,
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
            401: get_error_schema(["PERMISSION_DENIED"]),
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
        description=(
            "Returns the transcript of an agent conversation: the chat with its "
            "trigger payload, its messages and its tool approvals."
        ),
        responses={
            200: AgentChatTranscriptSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            AgentChatTranscriptSerializer(
                {"chat": chat, "messages": messages, "tool_approvals": approvals}
            ).data
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
            202: AgentChatRunStartedSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_AGENT_CHAT_ALREADY_RUNNING",
                    "ERROR_AGENT_CHAT_AWAITING_APPROVAL",
                    "ERROR_AGENT_MODEL_NOT_CONFIGURED",
                    "ERROR_INVALID_USER_FILE_NAME_ERROR",
                ]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            403: get_error_schema(["ERROR_AGENT_CHAT_NOT_OWNED"]),
            404: get_error_schema(
                [
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                    "ERROR_AGENT_DEFINITION_DOES_NOT_EXIST",
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
            AgentChatNotOwned: ERROR_AGENT_CHAT_NOT_OWNED,
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

        return Response(
            AgentChatRunStartedSerializer(
                chat, context={"prompt_message": message}
            ).data,
            status=HTTP_202_ACCEPTED,
        )


class AgentChatRetryView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="retry_agent_application_chat",
        description=(
            "Re-runs the turn of a conversation that ended in an error, "
            "using its last prompt message."
        ),
        request=None,
        responses={
            202: AgentChatRunStartedSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_AGENT_CHAT_NOT_RETRYABLE",
                    "ERROR_AGENT_CHAT_ALREADY_RUNNING",
                ]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            403: get_error_schema(["ERROR_AGENT_CHAT_NOT_OWNED"]),
            404: get_error_schema(["ERROR_AGENT_CHAT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatNotOwned: ERROR_AGENT_CHAT_NOT_OWNED,
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            AgentChatNotRetryable: ERROR_AGENT_CHAT_NOT_RETRYABLE,
            AgentChatAlreadyRunning: ERROR_AGENT_CHAT_ALREADY_RUNNING,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def post(self, request, chat_uuid):
        chat = _get_chat_and_check(request, chat_uuid, RunAgentChatOperationType)
        AgentChatHandler().check_chat_can_be_continued_by(chat, request.user)

        with transaction.atomic():
            message = action_type_registry.get_by_type(RetryAgentChatRunActionType).do(
                request.user, chat
            )

        return Response(
            AgentChatRunStartedSerializer(
                chat, context={"prompt_message": message}
            ).data,
            status=HTTP_202_ACCEPTED,
        )


class AgentChatCancelView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="cancel_agent_application_chat",
        description="Cancels the running turn of an agent conversation.",
        request=None,
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
        if chat.is_awaiting_approval:
            # Cancelling a paused run rejects its pending steps, which is a
            # decision reserved to those who may decide approvals.
            application = chat.agent.application
            CoreHandler().check_permissions(
                request.user,
                DecideAgentToolApprovalOperationType.type,
                workspace=application.workspace,
                context=application.application_ptr,
            )
        with transaction.atomic():
            action_type_registry.get_by_type(CancelAgentChatRunActionType).do(
                request.user, chat
            )
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
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="delete_agent_application_chat",
        description="Deletes an agent conversation.",
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_AGENT_CHAT_ALREADY_RUNNING"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
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

        action_type_registry.get_by_type(DeleteAgentChatActionType).do(
            request.user, chat
        )
        return Response(status=HTTP_204_NO_CONTENT)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="chat_uuid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="update_agent_application_chat",
        description="Renames or pins an agent conversation.",
        request=UpdateAgentChatSerializer,
        responses={
            200: AgentChatSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_AGENT_CHAT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatDoesNotExist: ERROR_AGENT_CHAT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(UpdateAgentChatSerializer, return_validated=True)
    def patch(self, request, chat_uuid, data: dict):
        chat = _get_chat_and_check(request, chat_uuid, UpdateAgentChatOperationType)
        chat = action_type_registry.get_by_type(UpdateAgentChatActionType).do(
            request.user, chat, **data
        )
        return Response(AgentChatSerializer(chat).data)


_INSTRUCTIONS_MODEL_ERRORS = {
    AssistantModelDisabledError: ERROR_ASSISTANT_MODEL_DISABLED,
    AssistantConfiguredModelNotAvailableError: (
        ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE
    ),
    AssistantModelNotSupportedError: ERROR_ASSISTANT_MODEL_NOT_SUPPORTED,
}


class AgentInstructionsDraftView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="draft_agent_application_instructions",
        description=(
            "Drafts the instructions of a new agent from the name and the "
            "description the user typed, using the workspace's Kuma model."
        ),
        request=DraftAgentInstructionsSerializer,
        responses={
            200: AgentInstructionsSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED",
                    "ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE",
                    "ERROR_ASSISTANT_MODEL_DISABLED",
                ]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            **_INSTRUCTIONS_MODEL_ERRORS,
        }
    )
    @validate_body(DraftAgentInstructionsSerializer, return_validated=True)
    def post(self, request, workspace_id: int, data: dict):
        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            request.user,
            CreateApplicationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        instructions = draft_instructions(workspace, data["name"], data["description"])
        return Response(
            AgentInstructionsSerializer({"instructions": instructions}).data
        )


class AgentInstructionsImproveView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="agent_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
        ],
        tags=["Agent"],
        operation_id="improve_agent_application_instructions",
        description=(
            "Returns an improved version of the given agent instructions, "
            "written by the workspace's Kuma model. Nothing is saved."
        ),
        request=ImproveAgentInstructionsSerializer,
        responses={
            200: AgentInstructionsSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED",
                    "ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE",
                    "ERROR_ASSISTANT_MODEL_DISABLED",
                ]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_AGENT_DEFINITION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            **_INSTRUCTIONS_MODEL_ERRORS,
        }
    )
    @validate_body(ImproveAgentInstructionsSerializer, return_validated=True)
    def post(self, request, agent_id: int, data: dict):
        agent = _get_agent_and_check(
            request, agent_id, UpdateAgentDefinitionOperationType
        )
        workspace = agent.application.workspace
        instructions = improve_instructions(workspace, agent, data["instructions"])
        return Response(
            AgentInstructionsSerializer({"instructions": instructions}).data
        )


class AgentRunOnceView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="run_agent_application_once",
        description=(
            "Starts a conversation for the application's first enabled trigger "
            "as if it had fired now, without event data."
        ),
        request=None,
        responses={
            202: AgentChatSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_AGENT_MODEL_NOT_CONFIGURED"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(
                [
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                    "ERROR_AGENT_DEFINITION_DOES_NOT_EXIST",
                    "ERROR_AGENT_TRIGGER_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            AgentDefinitionDoesNotExist: ERROR_AGENT_DEFINITION_DOES_NOT_EXIST,
            AgentTriggerDoesNotExist: ERROR_AGENT_TRIGGER_DOES_NOT_EXIST,
            AgentModelNotConfigured: ERROR_AGENT_MODEL_NOT_CONFIGURED,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @transaction.atomic
    def post(self, request, application_id: int):
        application = _get_application_and_check(
            request, application_id, RunAgentChatOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)
        if not agent.ai_generative_ai_type or not agent.ai_generative_ai_model:
            raise AgentModelNotConfigured(
                "The agent has no generative AI model configured."
            )
        chat = action_type_registry.get_by_type(RunAgentOnceActionType).do(
            request.user, application
        )
        return Response(AgentChatSerializer(chat).data, status=HTTP_202_ACCEPTED)


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
            200: AgentUsageSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
        application = _get_application_and_check(
            request, application_id, ReadAgentUsageOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)
        return Response(
            AgentUsageSerializer(AgentChatHandler().get_agent_usage(agent)).data
        )


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
            200: AgentTriggerSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
        triggers = _with_specific_services(
            list(AgentTriggerHandler().list_triggers(application))
        )
        return Response(AgentTriggerSerializer(triggers, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="create_agent_application_trigger",
        description="Adds a trigger to the agent application.",
        request=CreateAgentTriggerSerializer,
        responses={
            200: AgentTriggerSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(
                [
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                    "ERROR_AGENT_TRIGGER_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            # Raised for a trigger service type no agent trigger type handles.
            AgentTriggerDoesNotExist: ERROR_AGENT_TRIGGER_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(CreateAgentTriggerSerializer, return_validated=True)
    def post(self, request, application_id: int, data: dict):
        application = _get_application_and_check(
            request, application_id, UpdateAgentTriggerOperationType
        )

        with transaction.atomic():
            trigger = action_type_registry.get_by_type(CreateAgentTriggerActionType).do(
                request.user,
                application,
                data["service_type"],
                service_values=data.get("service"),
                enabled=data.get("enabled", True),
            )

        return Response(AgentTriggerSerializer(trigger).data)


class AgentTriggerView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="trigger_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="update_agent_application_trigger",
        description="Updates a trigger of the agent application.",
        request=UpdateAgentTriggerSerializer,
        responses={
            200: AgentTriggerSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            trigger = action_type_registry.get_by_type(UpdateAgentTriggerActionType).do(
                request.user,
                trigger,
                service_values=data.get("service"),
                enabled=data.get("enabled"),
            )

        return Response(AgentTriggerSerializer(trigger).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="trigger_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="delete_agent_application_trigger",
        description="Removes a trigger from the agent application.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            DeleteAgentTriggerOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        with transaction.atomic():
            action_type_registry.get_by_type(DeleteAgentTriggerActionType).do(
                request.user, trigger
            )

        return Response(status=HTTP_204_NO_CONTENT)


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
            200: AgentToolSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
        application = _get_application_and_check(
            request, application_id, ListAgentToolsOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)
        tools = _with_specific_services(list(AgentToolHandler().list_tools(agent)))
        return Response(AgentToolSerializer(tools, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="create_agent_application_tool",
        description="Enables a tool for the application's agent.",
        request=CreateAgentToolSerializer,
        responses={
            200: AgentToolSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
    @validate_body(CreateAgentToolSerializer, return_validated=True)
    def post(self, request, application_id: int, data: dict):
        application = _get_application_and_check(
            request, application_id, CreateAgentToolOperationType
        )
        agent = AgentApplicationHandler().get_main_agent(application)

        with transaction.atomic():
            tool = action_type_registry.get_by_type(CreateAgentToolActionType).do(
                request.user,
                agent,
                data["type"],
                name=data.get("name", ""),
                config=data.get("config"),
                service_type_str=data.get("service_type"),
                service_values=data.get("service"),
            )

        return Response(AgentToolSerializer(tool).data)


class AgentToolView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="tool_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="update_agent_application_tool",
        description="Updates a tool of the application's agent.",
        request=UpdateAgentToolSerializer,
        responses={
            200: AgentToolSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            tool = action_type_registry.get_by_type(UpdateAgentToolActionType).do(
                request.user,
                tool,
                name=data.get("name"),
                config=data.get("config"),
                service_values=data.get("service"),
                **(
                    {"identity_id": data["identity_id"]}
                    if "identity_id" in data
                    else {}
                ),
            )

        return Response(AgentToolSerializer(tool).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="tool_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="delete_agent_application_tool",
        description="Removes a tool from the application's agent.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            action_type_registry.get_by_type(DeleteAgentToolActionType).do(
                request.user, tool
            )

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
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            200: AgentWorkspaceToolSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
        from baserow_enterprise.agent_application.tools.catalog import (
            list_workspace_tools,
        )

        _get_application_and_check(
            request, application_id, ReadAgentDefinitionOperationType
        )
        return Response(
            AgentWorkspaceToolSerializer(list_workspace_tools(), many=True).data
        )


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
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
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
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
        if any(decision.get("dont_ask_again") for decision in data["decisions"]):
            # "Don't ask again" rewrites the tool configuration, which is a
            # builder-level change and not part of deciding an approval.
            application = chat.agent.application
            CoreHandler().check_permissions(
                request.user,
                UpdateAgentToolOperationType.type,
                workspace=application.workspace,
                context=application.application_ptr,
            )

        with transaction.atomic():
            decided = action_type_registry.get_by_type(
                DecideAgentToolApprovalActionType
            ).do(request.user, chat, data["decisions"])

        return Response(AgentChatToolApprovalSerializer(decided, many=True).data)


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
            200: AgentChatChannelSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
        return Response(AgentChatChannelSerializer(channels, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="create_agent_application_chat_channel",
        description="Connects an external chat channel to the agent application.",
        request=CreateAgentChatChannelSerializer,
        responses={
            200: AgentChatChannelSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            channel = action_type_registry.get_by_type(
                CreateAgentChatChannelActionType
            ).do(
                request.user,
                application,
                data["type"],
                name=data.get("name", ""),
                config=data.get("config"),
                enabled=data.get("enabled", True),
            )

        return Response(AgentChatChannelSerializer(channel).data)


class AgentChatChannelView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="channel_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="update_agent_application_chat_channel",
        description="Updates an external chat channel of the agent application.",
        request=UpdateAgentChatChannelSerializer,
        responses={
            200: AgentChatChannelSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            channel = action_type_registry.get_by_type(
                UpdateAgentChatChannelActionType
            ).do(
                request.user,
                channel,
                name=data.get("name"),
                config=data.get("config"),
                enabled=data.get("enabled"),
            )

        return Response(AgentChatChannelSerializer(channel).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="channel_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="delete_agent_application_chat_channel",
        description="Removes an external chat channel from the agent application.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
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
            DeleteAgentChatChannelOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        with transaction.atomic():
            action_type_registry.get_by_type(DeleteAgentChatChannelActionType).do(
                request.user, channel
            )

        return Response(status=HTTP_204_NO_CONTENT)


class AgentChatChannelEventsView(APIView):
    """
    Public inbound webhook for external chat services. The channel is
    identified by its unguessable uid; the channel type verifies the request
    (e.g. the Slack signature) before anything is processed.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="channel_uid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
                description="The unguessable uid of the channel.",
            ),
        ],
        tags=["Agent"],
        operation_id="receive_agent_application_chat_channel_event",
        description=(
            "Inbound webhook for the external service of a chat channel, for "
            "example Slack's Events API. The request and the response body "
            "follow the external service's protocol, which the channel type "
            "verifies and answers. Unknown channels are acknowledged without "
            "content so the URL reveals nothing."
        ),
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="The protocol answer of the channel type, such as "
                "Slack's URL verification challenge.",
            ),
            204: OpenApiResponse(
                description="The event was accepted, or no such channel exists."
            ),
            400: OpenApiResponse(description="The payload is malformed."),
            401: OpenApiResponse(description="The request signature is invalid."),
        },
    )
    def post(self, request, channel_uid):
        try:
            channel = AgentChatChannelHandler().get_channel_by_uid(channel_uid)
        except AgentChatChannelDoesNotExist:
            return Response(status=HTTP_204_NO_CONTENT)

        channel_type = agent_chat_channel_type_registry.get(channel.type)
        return channel_type.handle_inbound(channel, request)


class AgentChatChannelRotateSlugView(APIView):
    """Gives a web chat channel a new public link, invalidating the old one."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="channel_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Agent"],
        operation_id="rotate_agent_chat_channel_slug",
        description=(
            "Replaces the public link of a web chat channel; the old link stops "
            "working at once."
        ),
        request=None,
        responses={
            200: AgentChatChannelSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AgentChatChannelDoesNotExist: ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @transaction.atomic
    def post(self, request, channel_id: int):
        from baserow_enterprise.agent_application.channels.web import (
            WebAgentChatChannelType,
        )

        channel = AgentChatChannelHandler().get_channel(channel_id)
        application = channel.application
        CoreHandler().check_permissions(
            request.user,
            UpdateAgentChatChannelOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )
        if channel.type != WebAgentChatChannelType.type:
            raise AgentChatChannelDoesNotExist("Only web chat channels have a link.")
        channel = action_type_registry.get_by_type(
            RotateAgentChatChannelLinkActionType
        ).do(request.user, channel)
        return Response(AgentChatChannelSerializer(channel).data)
