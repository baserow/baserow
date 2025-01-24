import traceback
from typing import Any, Dict

from django.conf import settings

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from rest_framework.views import APIView

from baserow.api.decorators import validate_body
from baserow.api.health.serializers import (
    EmailTesterRequestSerializer,
    EmailTesterResponseSerializer,
    FullHealthCheckSerializer,
)
from baserow.api.schemas import get_error_schema
from baserow.core.health.handler import HealthCheckHandler
from baserow.core.health.utils import get_celery_queue_size


class FullHealthCheckView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Health"],
        request=None,
        operation_id="full_health_check",
        description="Runs a full health check testing as many services and systems "
        "as possible. These health checks can be expensive operations such as writing "
        "files to storage etc.",
        responses={
            200: FullHealthCheckSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        result = HealthCheckHandler.run_all_checks()
        celery_queue_size = get_celery_queue_size()
        celery_export_queue_size = get_celery_queue_size("export")
        return Response(
            FullHealthCheckSerializer(
                {
                    "checks": result.checks,
                    "passing": result.passing,
                    "celery_queue_size": celery_queue_size,
                    "celery_export_queue_size": celery_export_queue_size,
                }
            ).data
        )


class EmailTesterView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Health"],
        request=EmailTesterRequestSerializer,
        operation_id="email_tester",
        description="Sends a test email to the provided email address. Useful for "
        "testing Baserow's email configuration as errors are clearly "
        "returned.",
        responses={
            200: EmailTesterResponseSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
        },
    )
    @validate_body(EmailTesterRequestSerializer, return_validated=True)
    def post(self, request: Request, data: Dict[str, Any]) -> Response:
        target_email = data["target_email"]
        try:
            HealthCheckHandler.send_test_email(target_email)
            return Response(EmailTesterResponseSerializer({"succeeded": True}).data)
        except Exception as e:
            full = traceback.format_exc()
            return Response(
                EmailTesterResponseSerializer(
                    {
                        "succeeded": False,
                        "error_type": e.__class__.__name__,
                        "error_stack": full,
                        "error": str(e),
                    }
                ).data
            )


class CeleryQueueSizeExceededView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["Health"],
        parameters=[
            OpenApiParameter(
                name="queue",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "The name of the queues to check. Can be provided multiple times. "
                    "Accepts either `celery` or `export`."
                ),
            )
        ],
        operation_id="celery_queue_size_check",
        description=(
            f"Health check endpoint to check if the the celery and/or export celery "
            f"queue has  exceeded the maximum healthy size. Responds with `200` if "
            f"there there are less than "
            f"{settings.BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE} in all queues provided. "
            f"Otherwise responds with a `503`."
        ),
        responses={
            200: None,
            400: None,
            404: None,
            503: None,
        },
    )
    def get(self, request: Request) -> Response:
        queues = request.GET.getlist("queue")
        if len(queues) == 0:
            return Response("no queue provided", status=HTTP_400_BAD_REQUEST)

        allowed_queues = ["celery", "export"]

        for queue in queues:
            if queue not in allowed_queues:
                return Response(f"queue {queue} not found", status=HTTP_404_NOT_FOUND)
            queue_size = get_celery_queue_size(queue)
            if queue_size >= settings.BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE:
                return Response("not ok", status=HTTP_503_SERVICE_UNAVAILABLE)

        return Response("ok", status=200)
