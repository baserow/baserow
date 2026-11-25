from uuid import UUID

from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.api.chat_runs.errors import ERROR_CHAT_RUN_IN_PROGRESS
from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.mixins import RealtimeRecoveryPrimaryReadMixin
from baserow.api.pagination import PageNumberPagination, encode_keyset_cursor
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
    DecideAgentToolApprovalsActionType,
    DeleteAgentConversationActionType,
    LeaveAgentConversationActionType,
    RequestAgentApprovalActionType,
    ShareAgentConversationActionType,
    UpdateAgentConfigurationActionType,
    UpdateAgentConversationActionType,
)
from baserow.contrib.agent.exceptions import (
    AgentConversationDoesNotExist,
    AgentConversationWaitingForApproval,
    AgentMessageConflict,
    AgentNotReady,
    AgentRunAsSubjectDoesNotExist,
    AgentToolApprovalNotPending,
    AgentToolRequirementsMissing,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication, AgentConversation
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.signals import agent_loaded
from baserow.contrib.agent.types import AgentMessageCreated
from baserow.core.action.registries import action_type_registry
from baserow.core.chat_runs.exceptions import ChatRunAlreadyActive, ChatRunLimitReached
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.pagination import KeysetCursor
from baserow.core.service import CoreService

from .errors import (
    ERROR_AGENT_BUSY,
    ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST,
    ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL,
    ERROR_AGENT_MESSAGE_CONFLICT,
    ERROR_AGENT_NOT_READY,
    ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST,
    ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING,
    ERROR_AGENT_TOOL_REQUIREMENTS_MISSING,
)
from .serializers import (
    AgentConfigurationSerializer,
    AgentConfigurationUpdateSerializer,
    AgentConversationCreateSerializer,
    AgentConversationSerializer,
    AgentConversationsQuerySerializer,
    AgentConversationsResponseSerializer,
    AgentConversationUpdateSerializer,
    AgentConversationUserSerializer,
    AgentMessageCreatedSerializer,
    AgentMessageCreateSerializer,
    AgentMessagePagination,
    AgentMessageSerializer,
    AgentOptionsQueryParamsSerializer,
    AgentPendingReplySerializer,
    AgentRunAsOptionSerializer,
    AgentToolDecisionsSerializer,
    AgentToolSerializer,
    LeaveAgentConversationSerializer,
    RequestAgentApprovalSerializer,
    get_listed_conversation_context,
)

AGENT_ID_PATH_PARAMETER = OpenApiParameter(
    name="agent_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the agent.",
)
AGENT_EXCEPTIONS = {
    ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
    AgentConversationDoesNotExist: ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST,
    AgentNotReady: ERROR_AGENT_NOT_READY,
    AgentMessageConflict: ERROR_AGENT_MESSAGE_CONFLICT,
    AgentRunAsSubjectDoesNotExist: ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST,
    AgentConversationWaitingForApproval: ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL,
    AgentToolApprovalNotPending: ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING,
    AgentToolRequirementsMissing: ERROR_AGENT_TOOL_REQUIREMENTS_MISSING,
    ChatRunAlreadyActive: ERROR_CHAT_RUN_IN_PROGRESS,
    ChatRunLimitReached: ERROR_AGENT_BUSY,
}
READ_ERRORS = {
    401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
    404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
}
CONVERSATION_READ_ERRORS = {
    **READ_ERRORS,
    404: get_error_schema(
        ["ERROR_APPLICATION_DOES_NOT_EXIST", "ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST"]
    ),
}
CONVERSATION_WRITE_ERRORS = {
    **CONVERSATION_READ_ERRORS,
    400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION", "ERROR_AGENT_NOT_READY"]),
    409: get_error_schema(["ERROR_AGENT_MESSAGE_CONFLICT"]),
    429: get_error_schema(["ERROR_AGENT_BUSY"]),
}
MESSAGE_WRITE_ERRORS = {
    **CONVERSATION_WRITE_ERRORS,
    409: get_error_schema(
        [
            "ERROR_AGENT_MESSAGE_CONFLICT",
            "ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL",
            "ERROR_CHAT_RUN_IN_PROGRESS",
        ]
    ),
}
APPROVAL_WRITE_ERRORS = {
    **CONVERSATION_WRITE_ERRORS,
    409: get_error_schema(["ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING"]),
}


def _serialize_conversation(conversation: AgentConversation) -> dict:
    """
    :param conversation: The conversation to serialize, as its list shows it.
    :return: The conversation with its running reply and pending approval count.
    """

    context = get_listed_conversation_context([conversation.id])
    return AgentConversationSerializer(conversation, context=context).data


def _accepted_context(result: AgentMessageCreated) -> dict[str, object]:
    """
    Build the serializer context for the reply and the conversation independently.
    New sends retain their run even if a fast reply ends before serialization.

    :param result: The accepted message with its reply and run.
    :return: The context showing the conversation as its list does, with the run
        id by reply id under ``active_runs``.
    """

    conversation_runs = (
        {result.conversation.id: result.conversation_run_id}
        if result.conversation_run_id is not None
        else {}
    )
    return {
        **get_listed_conversation_context([result.conversation.id], conversation_runs),
        "active_runs": (
            {result.reply.id: result.run_id}
            if result.reply is not None and result.run_id is not None
            else {}
        ),
    }


class AgentApplicationView(APIView):
    def _get_agent_and_record_visit(
        self, request: Request, agent_id: int
    ) -> AgentApplication:
        agent = CoreService().get_application(
            request.user, agent_id, base_queryset=AgentApplication.objects
        )
        agent_loaded.send(sender=self, agent_id=agent.id, user=request.user)
        return agent

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER],
        tags=["Agent applications"],
        operation_id="get_agent_application",
        description=(
            "Returns the agent, including its readiness, and records that the user "
            "opened it."
        ),
        responses={
            200: PolymorphicApplicationResponseSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            **READ_ERRORS,
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request: Request, agent_id: int) -> Response:
        """Responds with the agent if the user can read it."""

        agent = self._get_agent_and_record_visit(request, agent_id)
        return Response(
            PolymorphicApplicationResponseSerializer(
                agent, context={"request": request}
            ).data
        )

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER],
        tags=["Agent applications"],
        operation_id="load_agent_application",
        description="Records that the user opened the agent.",
        request=None,
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            **READ_ERRORS,
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def post(self, request: Request, agent_id: int) -> Response:
        """Record the visit without serializing an already-loaded application."""

        self._get_agent_and_record_visit(request, agent_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentConfigurationView(RealtimeRecoveryPrimaryReadMixin, APIView):
    def get_permissions(self):
        # A template preview reads the setup, also for a signed out visitor. The
        # permission check still only allows it on templates.
        if self.request.method == "GET":
            return [AllowAny()]
        return super().get_permissions()

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER],
        tags=["Agent applications"],
        operation_id="get_agent_configuration",
        description=(
            "Returns the instructions, provider, model, reasoning effort and run-as "
            "identity of the agent, with its readiness and the fields that are "
            "missing or no longer available."
        ),
        responses={200: AgentConfigurationSerializer, **READ_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        """Responds with the configuration if the user can read it."""

        configuration = AgentService().get_configuration(request.user, agent_id)
        return Response(AgentConfigurationSerializer(configuration).data)

    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER],
        tags=["Agent applications"],
        operation_id="update_agent_configuration",
        description=(
            "Updates the provided fields of the agent configuration and returns the "
            "result. An incomplete configuration can be saved and finished later."
        ),
        request=AgentConfigurationUpdateSerializer,
        responses={
            200: AgentConfigurationSerializer,
            **READ_ERRORS,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST",
                    "ERROR_AGENT_TOOL_REQUIREMENTS_MISSING",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(
        AgentConfigurationUpdateSerializer, partial=True, return_validated=True
    )
    def patch(self, request: Request, agent_id: int, data: dict) -> Response:
        """Updates the configuration if the user can both update and read it."""

        configuration = action_type_registry.get_by_type(
            UpdateAgentConfigurationActionType
        ).do(request.user, agent_id, **data)
        return Response(AgentConfigurationSerializer(configuration).data)


class AgentRunAsIdentitiesView(RealtimeRecoveryPrimaryReadMixin, APIView):
    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER, AgentOptionsQueryParamsSerializer],
        tags=["Agent applications"],
        operation_id="list_agent_run_as_identities",
        description="Lists active workspace identities selectable for this Agent. "
        "Requires permission to read and update its configuration.",
        responses={
            200: get_example_pagination_serializer_class(AgentRunAsOptionSerializer),
            **READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_query_parameters(AgentOptionsQueryParamsSerializer, return_validated=True)
    def get(self, request: Request, agent_id: int, query_params: dict) -> Response:
        """Return paginated choices authorized in this Agent's application scope."""

        options = AgentService().get_run_as_identities(
            request.user, agent_id, search=query_params["search"]
        )
        paginator = PageNumberPagination(limit_page_size=100)
        page = paginator.paginate_queryset(options, request, view=self)
        return paginator.get_paginated_response(
            AgentRunAsOptionSerializer(page, many=True).data
        )


class AgentToolsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workspace the agent is created in.",
            )
        ],
        tags=["Agent applications"],
        operation_id="list_workspace_agent_tools",
        description=(
            "Lists every tool an agent created in the workspace can be allowed to "
            "call. Requires permission to create an application in the workspace."
        ),
        responses={
            200: AgentToolSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request: Request, workspace_id: int) -> Response:
        """Responds with the tools if the user can create an agent."""

        tools = AgentService().get_available_tools(request.user, workspace_id)
        return Response(AgentToolSerializer(tools, many=True).data)


class AgentConversationsView(RealtimeRecoveryPrimaryReadMixin, APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="list_agent_conversations",
        description=(
            "Lists the private conversations with the agent the authenticated user "
            "takes part in and the shared ones, pinned first, then most recently "
            "active within each group. Each includes its number of tool calls "
            "waiting for a decision."
        ),
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            OpenApiParameter(
                "pinned",
                OpenApiTypes.BOOL,
                description="Only pinned or unpinned conversations. Omit for both.",
            ),
            OpenApiParameter(
                "has_pending_approvals",
                OpenApiTypes.BOOL,
                description="Only conversations with or without calls waiting for approval.",
            ),
            OpenApiParameter(
                "shared",
                OpenApiTypes.BOOL,
                description="Only shared or private conversations. Omit for both.",
            ),
            OpenApiParameter(
                "started_by_trigger",
                OpenApiTypes.BOOL,
                description="Only conversations a trigger started or not. Omit for "
                "both.",
            ),
            OpenApiParameter(
                "last_reply_failed",
                OpenApiTypes.BOOL,
                description="Only conversations whose latest reply failed or not. "
                "Omit for both.",
            ),
            OpenApiParameter(
                "limit",
                OpenApiTypes.INT,
                default=20,
                description="Maximum number of conversations to return, up to 100.",
            ),
            OpenApiParameter(
                "cursor",
                OpenApiTypes.STR,
                description="The `next_cursor` of the previous page, omitted for "
                "the first page. The next page continues after the last conversation "
                "of the previous one, even when conversations changed in between.",
            ),
        ],
        responses={
            200: AgentConversationsResponseSerializer,
            400: get_error_schema(["ERROR_QUERY_PARAMETER_VALIDATION"]),
            **READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_query_parameters(AgentConversationsQuerySerializer, return_validated=True)
    def get(self, request: Request, agent_id: int, query_params: dict) -> Response:
        """List the user's own and the shared conversations, a page at a time."""

        limit = query_params["limit"]
        # One more than requested tells whether a next page exists without a count.
        conversations = list(
            AgentService().list_conversations(
                request.user,
                agent_id,
                query_params.get("cursor"),
                pinned=query_params.get("pinned"),
                has_pending_approvals=query_params.get("has_pending_approvals"),
                shared=query_params.get("shared"),
                started_by_trigger=query_params.get("started_by_trigger"),
                last_reply_failed=query_params.get("last_reply_failed"),
            )[: limit + 1]
        )
        page = conversations[:limit]
        next_cursor = (
            KeysetCursor(value=page[-1].updated_on, id=page[-1].id)
            if len(conversations) > limit
            else None
        )
        context = get_listed_conversation_context([item.id for item in page])
        return Response(
            {
                "results": AgentConversationSerializer(
                    page, many=True, context=context
                ).data,
                "next_cursor": (
                    f"{int(page[-1].pinned)}:{encode_keyset_cursor(next_cursor)}"
                    if next_cursor
                    else None
                ),
            }
        )

    @extend_schema(
        tags=["Agent applications"],
        operation_id="create_agent_conversation",
        description=(
            "Starts a private conversation with its first message. The conversation "
            "and message uuids identify the request, so a retry returns the already "
            "accepted message, and reusing a uuid with different content is "
            "rejected."
        ),
        request=AgentConversationCreateSerializer,
        responses={200: AgentMessageCreatedSerializer, **CONVERSATION_WRITE_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(AgentConversationCreateSerializer, return_validated=True)
    def post(self, request: Request, agent_id: int, data: dict) -> Response:
        """Starts a private conversation with its first message."""

        result = action_type_registry.get_by_type(CreateAgentConversationActionType).do(
            request.user, agent_id, **data
        )
        return Response(
            AgentMessageCreatedSerializer(
                result, context=_accepted_context(result)
            ).data
        )


class AgentConversationView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="update_agent_conversation",
        description=(
            "Updates the title or pinned state of one of the authenticated user's "
            "conversations, without changing its last activity time."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        request=AgentConversationUpdateSerializer,
        responses={
            200: AgentConversationSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            **CONVERSATION_READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(
        AgentConversationUpdateSerializer, partial=True, return_validated=True
    )
    def patch(
        self, request: Request, agent_id: int, conversation_uuid: UUID, data: dict
    ) -> Response:
        """Updates a conversation of the authenticated owner."""

        conversation = action_type_registry.get_by_type(
            UpdateAgentConversationActionType
        ).do(request.user, agent_id, conversation_uuid, **data)
        return Response(_serialize_conversation(conversation))

    @extend_schema(
        tags=["Agent applications"],
        operation_id="delete_agent_conversation",
        description=(
            "Moves one of the authenticated user's conversations to the trash and "
            "stops the reply being written in it. Only the owner sees and restores "
            "it there."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        responses={204: None, **CONVERSATION_READ_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def delete(
        self, request: Request, agent_id: int, conversation_uuid: UUID
    ) -> Response:
        """Trashes a conversation of the authenticated owner."""

        action_type_registry.get_by_type(DeleteAgentConversationActionType).do(
            request.user, agent_id, conversation_uuid
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShareAgentConversationView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="share_agent_conversation",
        description=(
            "Shares one of the authenticated user's private conversations with "
            "everyone who may read the agent's conversations. Sharing can't be undone."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        request=None,
        responses={200: AgentConversationSerializer, **CONVERSATION_READ_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def post(
        self, request: Request, agent_id: int, conversation_uuid: UUID
    ) -> Response:
        """Shares a private conversation of the authenticated owner."""

        conversation = action_type_registry.get_by_type(
            ShareAgentConversationActionType
        ).do(request.user, agent_id, conversation_uuid)
        return Response(_serialize_conversation(conversation))


class AgentApproversView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="list_agent_approver_candidates",
        description=(
            "Lists the workspace members the owner of a private conversation may ask "
            "to decide the held tool calls of its waiting reply: those who may "
            "approve tool calls and don't take part yet. Empty when no reply waits. "
            "The count only goes one past the members listed so far when more "
            "follow."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER, AgentOptionsQueryParamsSerializer],
        responses={
            200: get_example_pagination_serializer_class(
                AgentConversationUserSerializer
            ),
            400: get_error_schema(["ERROR_QUERY_PARAMETER_VALIDATION"]),
            **CONVERSATION_READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_query_parameters(AgentOptionsQueryParamsSerializer, return_validated=True)
    def get(
        self,
        request: Request,
        agent_id: int,
        conversation_uuid: UUID,
        query_params: dict,
    ) -> Response:
        """Lists the members who may be asked to approve, a page at a time."""

        paginator = PageNumberPagination(limit_page_size=100)
        # One more than the page shows whether another page follows.
        limit = query_params["page"] * paginator.get_page_size(request) + 1
        candidates = AgentService().list_approver_candidates(
            request.user, agent_id, conversation_uuid, query_params["search"], limit
        )
        page = paginator.paginate_queryset(candidates, request, view=self)
        return paginator.get_paginated_response(
            AgentConversationUserSerializer(page, many=True).data
        )

    @extend_schema(
        tags=["Agent applications"],
        operation_id="request_agent_approval",
        description=(
            "Adds members to a private conversation of the authenticated owner so "
            "they can decide the held tool calls of its waiting reply. They keep "
            "seeing its history and future messages."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        request=RequestAgentApprovalSerializer,
        responses={
            200: AgentConversationSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            409: get_error_schema(["ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING"]),
            **CONVERSATION_READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(RequestAgentApprovalSerializer, return_validated=True)
    def post(
        self, request: Request, agent_id: int, conversation_uuid: UUID, data: dict
    ) -> Response:
        """Adds members who may approve to a private conversation."""

        conversation = action_type_registry.get_by_type(
            RequestAgentApprovalActionType
        ).do(request.user, agent_id, conversation_uuid, **data)
        return Response(_serialize_conversation(conversation))


class LeaveAgentConversationView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="leave_agent_conversation",
        description=(
            "Removes the authenticated user from a private conversation they take "
            "part in, which the others keep. Its owner alone in it moves it to the "
            "trash instead, and the last one to leave after the owner deletes it."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER, CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        request=None,
        responses={200: LeaveAgentConversationSerializer, **CONVERSATION_READ_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def post(
        self, request: Request, agent_id: int, conversation_uuid: UUID
    ) -> Response:
        """Leaves a private conversation the authenticated user takes part in."""

        conversation = action_type_registry.get_by_type(
            LeaveAgentConversationActionType
        ).do(request.user, agent_id, conversation_uuid)
        return Response(LeaveAgentConversationSerializer(conversation).data)


class AgentMessagesView(RealtimeRecoveryPrimaryReadMixin, APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="list_agent_messages",
        description=(
            "Lists the messages of one of the authenticated user's conversations, "
            "newest page first, each page in chronological order."
        ),
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            OpenApiParameter("page", OpenApiTypes.INT, default=1),
            OpenApiParameter(
                "size",
                OpenApiTypes.INT,
                default=50,
                description="Number of messages per page, up to 100.",
            ),
        ],
        responses={
            200: get_example_pagination_serializer_class(AgentMessageSerializer),
            **CONVERSATION_READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request: Request, agent_id: int, conversation_uuid: UUID) -> Response:
        """Lists messages in pages from the newest, each in chronological order."""

        conversation, messages = AgentService().list_messages(
            request.user, agent_id, conversation_uuid
        )
        paginator = AgentMessagePagination(limit_page_size=100)
        page = paginator.paginate_queryset(messages, request, self)
        handler = AgentHandler()
        newest_page = paginator.page.number == 1
        # After the page, so each reply it lists has its run or is read again as ended.
        active_runs = handler.get_active_reply_runs(conversation) if newest_page else {}
        page = handler.refresh_unfinished_replies(page, active_runs)
        return paginator.get_paginated_response(
            AgentMessageSerializer(
                list(reversed(page)), many=True, context={"active_runs": active_runs}
            ).data
        )

    @extend_schema(
        tags=["Agent applications"],
        operation_id="create_agent_message",
        description=(
            "Adds a message to one of the authenticated user's conversations. The "
            "message uuid identifies the request, so a retry returns the already "
            "accepted message, and reusing it with different content is rejected."
        ),
        request=AgentMessageCreateSerializer,
        responses={200: AgentMessageCreatedSerializer, **MESSAGE_WRITE_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(AgentMessageCreateSerializer, return_validated=True)
    def post(
        self, request: Request, agent_id: int, conversation_uuid: UUID, data: dict
    ) -> Response:
        """Accept an authorized owner's message or recover its identical retry."""

        result = action_type_registry.get_by_type(CreateAgentMessageActionType).do(
            request.user, agent_id, conversation_uuid, **data
        )
        return Response(
            AgentMessageCreatedSerializer(
                result, context=_accepted_context(result)
            ).data
        )


class AgentPendingApprovalsView(RealtimeRecoveryPrimaryReadMixin, APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="list_agent_pending_approvals",
        description="List pending tool approvals grouped by reply in conversations visible to the current user.",
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            OpenApiParameter("page", OpenApiTypes.INT, default=1),
            OpenApiParameter(
                "size",
                OpenApiTypes.INT,
                default=100,
                description="Number of replies per page, up to 100.",
            ),
        ],
        responses={
            200: get_example_pagination_serializer_class(AgentPendingReplySerializer),
            **READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        paginator = PageNumberPagination(limit_page_size=100)
        page = paginator.paginate_queryset(
            AgentService().list_pending_replies(request.user, agent_id), request, self
        )
        context = {
            "conversation_pending_approvals": {
                reply.conversation_id: len(reply.pending_approvals) for reply in page
            }
        }
        return paginator.get_paginated_response(
            AgentPendingReplySerializer(page, many=True, context=context).data
        )


class AgentToolApprovalsView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="decide_agent_tool_approvals",
        description=(
            "Approves or rejects tool calls that the waiting reply of one of the "
            "authenticated user's conversations, or of a shared conversation a "
            "trigger started, holds for approval. Once none are "
            "left to decide, a run continues the reply and the response names it. "
            "With always_allow, the tools of the approved calls stop asking first."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER],
        request=AgentToolDecisionsSerializer,
        responses={200: AgentMessageSerializer, **APPROVAL_WRITE_ERRORS},
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(AgentToolDecisionsSerializer, return_validated=True)
    def post(
        self, request: Request, agent_id: int, conversation_uuid: UUID, data: dict
    ) -> Response:
        """Saves the user's decisions and names the run continuing the reply."""

        result = action_type_registry.get_by_type(
            DecideAgentToolApprovalsActionType
        ).do(request.user, agent_id, conversation_uuid, **data)
        reply = result.reply
        active_runs = {reply.id: result.run_id} if result.run_id else {}
        return Response(
            AgentMessageSerializer(reply, context={"active_runs": active_runs}).data
        )
