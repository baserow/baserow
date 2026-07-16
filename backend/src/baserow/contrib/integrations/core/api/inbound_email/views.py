import hmac

from django.conf import settings
from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_401_UNAUTHORIZED
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.contrib.integrations.core.api.inbound_email.errors import (
    ERROR_INVALID_INBOUND_EMAIL_PAYLOAD,
)
from baserow.contrib.integrations.core.exceptions import InvalidInboundEmailPayload
from baserow.contrib.integrations.core.inbound_email import InboundEmailHandler

INBOUND_EMAIL_TAG = "Inbound email"


class CoreInboundEmailWebhookView(APIView):
    """
    Receives incoming email delivery webhooks from the inbound mail server and
    dispatches the matching email trigger services. The request is
    authenticated with the shared secret configured in
    `BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET`, which the mail server must send in
    the Authorization header.
    """

    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    @extend_schema(
        operation_id="handle_inbound_email_webhook",
        tags=[INBOUND_EMAIL_TAG],
        description="Receives and handles an inbound email webhook request "
        "from the inbound mail server.",
        responses={
            200: None,
            400: get_error_schema(["ERROR_INVALID_INBOUND_EMAIL_PAYLOAD"]),
            401: None,
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            InvalidInboundEmailPayload: ERROR_INVALID_INBOUND_EMAIL_PAYLOAD,
        }
    )
    def post(self, request, *args, **kwargs):
        secret = settings.INBOUND_EMAIL_WEBHOOK_SECRET
        provided = request.headers.get("Authorization", "")

        # When no secret is configured the endpoint is disabled; never fall
        # through to comparing against an empty string.
        if not secret or not hmac.compare_digest(provided.encode(), secret.encode()):
            return Response(
                {"error": "ERROR_INVALID_INBOUND_EMAIL_SECRET"},
                status=HTTP_401_UNAUTHORIZED,
            )

        status = InboundEmailHandler().handle_webhook_payload(request.data)

        return Response({"status": status})
