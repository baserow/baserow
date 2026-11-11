from uuid import UUID

from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
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
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.mixins import RealtimeRecoveryPrimaryReadMixin
from baserow.api.pagination import PageNumberPagination, encode_keyset_cursor
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.api.subjects.serializers import SubjectOptionSerializer
from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
    DecideAgentToolApprovalsActionType,
    DeleteAgentConversationActionType,
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
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.signals import agent_loaded
from baserow.contrib.agent.types import AgentMessageCreated
from baserow.core.action.registries import action_type_registry
from baserow.core.chat_runs.exceptions import ChatRunAlreadyActive, ChatRunLimitReached
from baserow.core.exceptions import ApplicationDoesNotExist, UserNotInWorkspace
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
)
from .serializers import (
    AgentConfigurationSerializer,
    AgentConfigurationUpdateSerializer,
    AgentConversationCreateSerializer,
    AgentConversationSerializer,
    AgentConversationsQuerySerializer,
    AgentConversationsResponseSerializer,
    AgentConversationUpdateSerializer,
    AgentMessageCreatedSerializer,
    AgentMessageCreateSerializer,
    AgentMessagePagination,
    AgentMessageSerializer,
    AgentRunAsSubjectsQueryParamsSerializer,
    AgentToolDecisionsSerializer,
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


def _accepted_context(result: AgentMessageCreated) -> dict[str, dict[int, UUID]]:
    """
    Build the serializer context for the reply and the conversation independently.
    New sends retain their run even if a fast reply ends before serialization.

    :param result: The accepted message with its reply and run.
    :return: The context, with the run id by reply id under ``active_runs`` and by
        conversation id under ``conversation_runs``.
    """

    return {
        "active_runs": (
            {result.reply.id: result.run_id}
            if result.reply is not None and result.run_id is not None
            else {}
        ),
        "conversation_runs": (
            {result.conversation.id: result.conversation_run_id}
            if result.conversation_run_id is not None
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


class AgentRunAsSubjectsView(RealtimeRecoveryPrimaryReadMixin, APIView):
    @extend_schema(
        parameters=[AGENT_ID_PATH_PARAMETER, AgentRunAsSubjectsQueryParamsSerializer],
        tags=["Agent applications"],
        operation_id="list_agent_run_as_subjects",
        description="Lists active workspace identities selectable for this Agent. "
        "Requires permission to read and update its configuration.",
        responses={
            200: get_example_pagination_serializer_class(SubjectOptionSerializer),
            **READ_ERRORS,
        },
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_query_parameters(
        AgentRunAsSubjectsQueryParamsSerializer, return_validated=True
    )
    def get(self, request: Request, agent_id: int, query_params: dict) -> Response:
        """Return paginated choices authorized in this Agent's application scope."""

        options = AgentService().get_run_as_subject_options(
            request.user, agent_id, search=query_params["search"]
        )
        paginator = PageNumberPagination(limit_page_size=100)
        page = paginator.paginate_queryset(options, request, view=self)
        return paginator.get_paginated_response(
            SubjectOptionSerializer(page, many=True).data
        )


class AgentConversationsView(RealtimeRecoveryPrimaryReadMixin, APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="list_agent_conversations",
        description=(
            "Lists the authenticated user's own conversations with the agent, pinned "
            "first, then most recently active within each group. Each includes its "
            "number of tool calls waiting for the user's approval."
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
        """List only the authenticated owner's conversations, a page at a time."""

        limit = query_params["limit"]
        # One more than requested tells whether a next page exists without a count.
        conversations = list(
            AgentService().list_conversations(
                request.user,
                agent_id,
                query_params.get("cursor"),
                pinned=query_params.get("pinned"),
                has_pending_approvals=query_params.get("has_pending_approvals"),
            )[: limit + 1]
        )
        page = conversations[:limit]
        next_cursor = (
            KeysetCursor(value=page[-1].updated_on, id=page[-1].id)
            if len(conversations) > limit
            else None
        )
        page_ids = [item.id for item in page]
        context = {
            "conversation_runs": AgentHandler().get_conversation_runs(page_ids),
            "conversation_pending_approvals": (
                AgentHandler().get_conversation_pending_approval_counts(page_ids)
            ),
        }
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
            "Updates one of the authenticated user's conversations, for now only its "
            "title. It keeps its place in the list, which is ordered by activity."
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
    @validate_body(AgentConversationUpdateSerializer, return_validated=True)
    def patch(
        self, request: Request, agent_id: int, conversation_uuid: UUID, data: dict
    ) -> Response:
        """Updates a conversation of the authenticated owner."""

        conversation = action_type_registry.get_by_type(
            UpdateAgentConversationActionType
        ).do(request.user, agent_id, conversation_uuid, **data)
        context = {
            "conversation_runs": AgentHandler().get_conversation_runs(
                [conversation.id]
            ),
            "conversation_pending_approvals": (
                AgentHandler().get_conversation_pending_approval_counts(
                    [conversation.id]
                )
            ),
        }
        return Response(AgentConversationSerializer(conversation, context=context).data)

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


class AgentToolApprovalsView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="decide_agent_tool_approvals",
        description=(
            "Approves or rejects tool calls that the waiting reply of one of the "
            "authenticated user's conversations holds for approval. Once none are "
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
        """Saves the owner's decisions and names the run continuing the reply."""

        result = action_type_registry.get_by_type(
            DecideAgentToolApprovalsActionType
        ).do(request.user, agent_id, conversation_uuid, **data)
        reply = result.reply
        active_runs = {reply.id: result.run_id} if result.run_id else {}
        return Response(
            AgentMessageSerializer(reply, context={"active_runs": active_runs}).data
        )
