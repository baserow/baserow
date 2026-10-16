from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.core.chat_runs.exceptions import ChatRunDoesNotExist
from baserow.core.chat_runs.service import ChatRunService

from .errors import ERROR_CHAT_RUN_DOES_NOT_EXIST
from .serializers import ChatRunCancelSerializer, ChatRunSerializer


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
