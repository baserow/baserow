from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.contrib.integrations.core.api.webhooks.errors import (
    ERROR_CORE_HTTP_TRIGGER_SERVICE_DOES_NOT_EXIST,
    ERROR_CORE_HTTP_TRIGGER_SERVICE_METHOD_NOT_ALLOWED,
)
from baserow.contrib.integrations.core.exceptions import (
    CoreHTTPTriggerServiceDoesNotExist,
    CoreHTTPTriggerServiceMethodNotAllowed,
)
from baserow.core.services.registries import service_type_registry

CORE_WEBHOOKS_TAG = "Core webhooks"


def webhook_schema(method):
    """
    Dynamically generate the schema and specifically the operation_id.

    Without a unique operation_id, the API schema will contain a numbered
    postfix for each method.
    """

    return extend_schema(
        methods=[method],
        operation_id=f"handle_core_webhook_request_{method.lower()}",
        tags=[CORE_WEBHOOKS_TAG],
        description="Receives and handles a webhook request.",
        responses={
            204: None,
            404: get_error_schema(["ERROR_CORE_HTTP_WEBHOOK_SERVICE_DOES_NOT_EXIST"]),
        },
    )


class CoreHTTPTriggerView(APIView):
    """
    Handle incoming HTTP trigger requests.
    """

    permission_classes = (AllowAny,)
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def handle_request_data(self, request):
        headers = {key: value for key, value in request.headers.items()}
        query_params = dict(request.GET.items())
        raw_body = request.body.decode("utf-8") if request.body else ""
        body = request.data if hasattr(request, "data") else {}

        return {
            "method": request.method,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "raw_body": raw_body,
            "remote_addr": request.META.get("REMOTE_ADDR", ""),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        }

    @webhook_schema("GET")
    @webhook_schema("POST")
    @webhook_schema("PUT")
    @webhook_schema("PATCH")
    @webhook_schema("DELETE")
    @transaction.atomic
    @map_exceptions(
        {
            CoreHTTPTriggerServiceDoesNotExist: ERROR_CORE_HTTP_TRIGGER_SERVICE_DOES_NOT_EXIST,
            CoreHTTPTriggerServiceMethodNotAllowed: ERROR_CORE_HTTP_TRIGGER_SERVICE_METHOD_NOT_ALLOWED,
        }
    )
    def handle_request(self, request, webhook_uid, *args, **kwargs):
        request_data = self.handle_request_data(request)
        simulate = request.GET.get("test", "").lower() == "true"

        service_type = service_type_registry.get("http_trigger")
        service_type.process_webhook_request(webhook_uid, request_data, simulate)

        return Response(status=HTTP_204_NO_CONTENT)

    get = post = put = patch = delete = handle_request
