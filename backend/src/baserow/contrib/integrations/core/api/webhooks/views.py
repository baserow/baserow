from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse
from django.utils.datastructures import MultiValueDict

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
    HTTP_504_GATEWAY_TIMEOUT,
)
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.integrations.core.api.webhooks.errors import (
    ERROR_CORE_HTTP_TRIGGER_REQUEST_BODY_TOO_LARGE,
    ERROR_CORE_HTTP_TRIGGER_SERVICE_DOES_NOT_EXIST,
    ERROR_CORE_HTTP_TRIGGER_SERVICE_METHOD_NOT_ALLOWED,
)
from baserow.contrib.integrations.core.api.webhooks.throttling import (
    CoreHTTPTriggerRateThrottle,
)
from baserow.contrib.integrations.core.constants import (
    DISALLOWED_WORKFLOW_RESPONSE_HEADERS,
    HTTP_TRIGGER_DROPPED_REQUEST_HEADERS,
    RESPONSE_BODY_TYPE,
)
from baserow.contrib.integrations.core.exceptions import (
    CoreHTTPTriggerRequestBodyTooLarge,
    CoreHTTPTriggerServiceDoesNotExist,
    CoreHTTPTriggerServiceMethodNotAllowed,
)
from baserow.core.services.registries import service_type_registry

CORE_WEBHOOKS_TAG = "Core webhooks"
WORKFLOW_RESPONSE_CONTENT_SECURITY_POLICY = "sandbox"


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
            413: get_error_schema(["ERROR_CORE_HTTP_TRIGGER_REQUEST_BODY_TOO_LARGE"]),
        },
    )


class CoreHTTPTriggerView(APIView):
    """
    Handle incoming HTTP trigger requests.
    """

    permission_classes = (AllowAny,)
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_throttles(self):
        self.trigger_throttle = CoreHTTPTriggerRateThrottle()
        return [*super().get_throttles(), self.trigger_throttle]

    def finalize_response(self, request, response, *args, **kwargs):
        # The throttle reserves a slot before this view runs. A uid that
        # doesn't belong to any trigger has no budget to count against, so its
        # slot is given back and nothing is kept for it.
        if response.status_code == HTTP_404_NOT_FOUND and hasattr(
            self, "trigger_throttle"
        ):
            self.trigger_throttle.release()

        return super().finalize_response(request, response, *args, **kwargs)

    def check_body_size(self, request):
        """
        Refuses a body larger than the configured cap, so it never reaches the
        workflow's history or sample data. The declared `Content-Length` is
        checked before the body is read, and the body itself afterwards.
        """

        max_size = settings.AUTOMATION_HTTP_TRIGGER_MAX_BODY_SIZE_BYTES

        try:
            content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            content_length = 0

        if content_length > max_size or len(request.body) > max_size:
            raise CoreHTTPTriggerRequestBodyTooLarge()

    def handle_request_data(self, request):
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in HTTP_TRIGGER_DROPPED_REQUEST_HEADERS
        }
        query_params = dict(request.GET.items())

        # The sender is an arbitrary third-party system, so the body can
        # arrive in any encoding; it must never cause a 500. `request.body`
        # must be accessed before `request.data`, because multipart parsing
        # consumes the request stream.
        raw_body = ""
        if request.body:
            charset = (request.content_params or {}).get("charset")
            try:
                raw_body = request.body.decode(charset or "utf-8")
            except (UnicodeDecodeError, LookupError):
                raw_body = request.body.decode("utf-8", errors="replace")

        try:
            body = request.data
        except (UnsupportedMediaType, ParseError):
            body = {}

        if isinstance(body, MultiValueDict):
            # Form and multipart bodies can contain `UploadedFile` values,
            # which wouldn't survive the JSON serialization towards the
            # workflow's Celery task; keep only the plain form fields.
            fields = {}
            for key, values in body.lists():
                values = [v for v in values if not isinstance(v, UploadedFile)]
                if values:
                    fields[key] = values[0] if len(values) == 1 else values
            body = fields

        return {
            "method": request.method,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "raw_body": raw_body,
            "remote_addr": request.META.get("REMOTE_ADDR", ""),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        }

    def response_to_http_response(self, workflow_response):
        """Builds a browser-sandboxed HTTP response from a workflow response."""

        headers = {
            key: value
            for key, value in (workflow_response.headers or {}).items()
            if key.lower() not in DISALLOWED_WORKFLOW_RESPONSE_HEADERS
        }
        headers["Content-Security-Policy"] = WORKFLOW_RESPONSE_CONTENT_SECURITY_POLICY
        status = workflow_response.status_code

        if workflow_response.body_type == RESPONSE_BODY_TYPE.TEXT:
            content_type = next(
                (
                    value
                    for key, value in headers.items()
                    if key.lower() == "content-type"
                ),
                "text/plain",
            )
            headers = {
                key: value
                for key, value in headers.items()
                if key.lower() != "content-type"
            }
            return HttpResponse(
                workflow_response.body or "",
                status=status,
                headers=headers,
                content_type=content_type,
            )

        if workflow_response.body_type == RESPONSE_BODY_TYPE.EMPTY:
            return Response(status=status, headers=headers)

        return Response(
            data=workflow_response.body,
            status=status,
            headers=headers,
        )

    @webhook_schema("GET")
    @webhook_schema("POST")
    @webhook_schema("PUT")
    @webhook_schema("PATCH")
    @webhook_schema("DELETE")
    @map_exceptions(
        {
            CoreHTTPTriggerServiceDoesNotExist: ERROR_CORE_HTTP_TRIGGER_SERVICE_DOES_NOT_EXIST,
            CoreHTTPTriggerServiceMethodNotAllowed: ERROR_CORE_HTTP_TRIGGER_SERVICE_METHOD_NOT_ALLOWED,
            CoreHTTPTriggerRequestBodyTooLarge: ERROR_CORE_HTTP_TRIGGER_REQUEST_BODY_TOO_LARGE,
        }
    )
    def handle_request(self, request, webhook_uid, *args, **kwargs):
        self.check_body_size(request)
        request_data = self.handle_request_data(request)
        simulate = request.GET.get("test", "").lower() == "true"

        service_type = service_type_registry.get("http_trigger")
        service, history = service_type.process_webhook_request(
            webhook_uid, request_data, simulate
        )

        if (
            service.wait_for_response
            and history is not None
            and history.simulate_until_node_id is None
        ):
            history_handler = AutomationHistoryHandler()
            workflow_response = history_handler.wait_for_workflow_response(
                history,
                service.response_timeout_seconds,
            )
            if workflow_response is None:
                return Response(status=HTTP_504_GATEWAY_TIMEOUT)
            return self.response_to_http_response(workflow_response)

        return Response(status=HTTP_204_NO_CONTENT)

    get = post = put = patch = delete = handle_request
