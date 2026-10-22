import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.http import StreamingHttpResponse

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_query_parameters
from baserow.api.schemas import get_error_schema
from baserow.core.chat_runs.constants import ChatRunEventKind
from baserow.core.chat_runs.exceptions import ChatRunDoesNotExist
from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.service import ChatRunService
from baserow.core.chat_runs.stream import follow_run

from .errors import ERROR_CHAT_RUN_DOES_NOT_EXIST
from .serializers import (
    ChatRunCancelSerializer,
    ChatRunSerializer,
    ChatRunStreamQuerySerializer,
)


class ChatRunView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Chat runs"],
        operation_id="get_chat_run",
        description="Read durable run status and its saved outcome, including after replay expires.",
        responses={
            200: ChatRunSerializer,
            404: get_error_schema(["ERROR_CHAT_RUN_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({ChatRunDoesNotExist: ERROR_CHAT_RUN_DOES_NOT_EXIST})
    def get(self, request: Request, run_id: UUID) -> Response:
        return Response(ChatRunService().snapshot(request.user, run_id))


class ChatRunCancelView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Chat runs"],
        operation_id="cancel_chat_run",
        description="Request Stop for this run. Active tools drain before it ends.",
        request=None,
        responses={
            200: ChatRunCancelSerializer,
            404: get_error_schema(["ERROR_CHAT_RUN_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({ChatRunDoesNotExist: ERROR_CHAT_RUN_DOES_NOT_EXIST})
    def post(self, request: Request, run_id: UUID) -> Response:
        return Response(
            {"status": ChatRunService().request_cancel(request.user, run_id)}
        )


async def encode_records(
    run: ChatRun, user: AbstractUser, cursor: str | None
) -> AsyncIterator[str]:
    """Encode the run's records as JSON separated by blank lines.

    :param run: The run to follow.
    :param user: The user reading it.
    :param cursor: The cursor to resume after, or None to read from the start.
    :return: The encoded records; a heartbeat is a bare separator.
    """

    async with aclosing(follow_run(run, user, cursor)) as records:
        async for record in records:
            if record["kind"] == ChatRunEventKind.RUN_HEARTBEAT:
                yield "\n\n"
            else:
                yield json.dumps(record) + "\n\n"


class ChatRunStreamView(APIView):
    permission_classes = (IsAuthenticated,)
    # Django serves HEAD with get, which the stream router wouldn't cap.
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["Chat runs"],
        operation_id="stream_chat_run",
        description=(
            "Follow a run's output as JSON records separated by blank lines, ending "
            "with `run.finished`. Pass the last received `cursor` to resume."
        ),
        parameters=[ChatRunStreamQuerySerializer],
        responses={
            (200, "text/event-stream"): OpenApiTypes.STR,
            400: get_error_schema(["ERROR_QUERY_PARAMETER_VALIDATION"]),
            404: get_error_schema(["ERROR_CHAT_RUN_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({ChatRunDoesNotExist: ERROR_CHAT_RUN_DOES_NOT_EXIST})
    @validate_query_parameters(ChatRunStreamQuerySerializer, return_validated=True)
    def get(
        self, request: Request, run_id: UUID, query_params: dict
    ) -> StreamingHttpResponse:
        run = ChatRunService().get_run(request.user, run_id)
        response = StreamingHttpResponse(
            encode_records(run, request.user, query_params.get("cursor")),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
