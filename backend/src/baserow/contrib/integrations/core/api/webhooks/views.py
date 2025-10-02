from typing import Optional
from uuid import uuid4

from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.contrib.integrations.core.api.webhooks.errors import (
    ERROR_CORE_HTTP_WEBHOOK_SERVICE_DOES_NOT_EXIST,
    ERROR_CORE_HTTP_WEBHOOK_SERVICE_METHOD_NOT_ALLOWED,
)
from baserow.contrib.integrations.core.exceptions import (
    CoreHTTPWebhookServiceDoesNotExist,
    CoreHTTPWebhookServiceMethodNotAllowed,
)
from baserow.core.cache import global_cache
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


def get_error_cache_key(uid: uuid4, simulate: bool = False) -> str:
    return f"http_webhook_error_simulate_{simulate}_{uid}"


class CoreHTTPWebhookView(APIView):
    """
    Handle incoming webhook requests.
    """

    permission_classes = (AllowAny,)
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def handle_request_data(self, request):
        headers = {key: value for key, value in request.headers.items()}
        query_params = dict(request.GET.items())
        body = request.data if hasattr(request, "data") else {}
        raw_body = request.body.decode("utf-8") if request.body else ""

        return {
            "method": request.method,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "raw_body": raw_body,
            "remote_addr": request.META.get("REMOTE_ADDR", ""),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        }

    def handle_error(self, cache_key: str, webhook_uid: uuid4) -> None:
        """
        Checks the cache to see if the error exists. If so, raises the appropriate
        exception.
        """

        if error := global_cache.get(cache_key, default=None, timeout=0):
            if error == "CoreHTTPWebhookServiceDoesNotExist":
                raise CoreHTTPWebhookServiceDoesNotExist(uid=webhook_uid)
            elif error == "CoreHTTPWebhookServiceMethodNotAllowed":
                raise CoreHTTPWebhookServiceMethodNotAllowed()

    @webhook_schema("GET")
    @webhook_schema("POST")
    @webhook_schema("PUT")
    @webhook_schema("PATCH")
    @webhook_schema("DELETE")
    @transaction.atomic
    @map_exceptions(
        {
            CoreHTTPWebhookServiceDoesNotExist: ERROR_CORE_HTTP_WEBHOOK_SERVICE_DOES_NOT_EXIST,
            CoreHTTPWebhookServiceMethodNotAllowed: ERROR_CORE_HTTP_WEBHOOK_SERVICE_METHOD_NOT_ALLOWED,
        }
    )
    def handle_request(self, request, webhook_uid, *args, **kwargs):
        request_data = self.handle_request_data(request)
        simulate = request.GET.get("test", "").lower() == "true"

        cache_key = get_error_cache_key(webhook_uid, simulate)
        self.handle_error(cache_key, webhook_uid)

        service_type = service_type_registry.get("http_webhook")
        try:
            service_type.process_webhook_request(webhook_uid, request_data, simulate)
        except (
            CoreHTTPWebhookServiceDoesNotExist,
            CoreHTTPWebhookServiceMethodNotAllowed,
        ) as e:
            global_cache.get(cache_key, e.__class__.__name__, timeout=300)
            raise

        return Response(status=HTTP_204_NO_CONTENT)

    get = post = put = patch = delete = handle_request
