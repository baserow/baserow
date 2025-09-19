from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.core.services.registries import service_type_registry


class CoreHTTPWebhookView(APIView):
    """
    Handle incoming webhook requests.
    """

    permission_classes = (AllowAny,)

    def handle_request_data(self, request):
        headers = {key: value for key, value in request.headers.items()}
        query_params = dict(request.GET.items())
        body = request.data if hasattr(request, "data") else {}

        return {
            "method": request.method,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "remote_addr": request.META.get("REMOTE_ADDR", ""),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        }

    def post(self, request, webhook_uid):
        service_type = service_type_registry.get("http_webhook")
        service_type.process_webhook_request(
            webhook_uid, self.handle_request_data(request)
        )
        return Response(status=HTTP_204_NO_CONTENT)

    def get(self, request, webhook_uid):
        service_type = service_type_registry.get("http_webhook")
        service_type.process_webhook_request(
            webhook_uid, self.handle_request_data(request)
        )
        return Response(status=HTTP_204_NO_CONTENT)
