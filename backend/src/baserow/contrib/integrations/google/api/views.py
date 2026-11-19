from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.integrations.errors import ERROR_INTEGRATION_DOES_NOT_EXIST
from baserow.api.integrations.serializers import IntegrationSerializer
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.services.exceptions import DispatchException

from .. import service

EXCEPTIONS = {
    IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
    DispatchException: (
        "ERROR_GOOGLE_REQUEST_FAILED",
        400,
        "Google could not complete the request. Try again or reconnect.",
    ),
}


class StartSerializer(serializers.Serializer):
    service_type = serializers.CharField(required=False)


class StartResponseSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()


class CompleteSerializer(serializers.Serializer):
    state = serializers.CharField(max_length=256)
    code = serializers.CharField(max_length=4096, allow_blank=True)


def respond(integration):
    return Response(
        integration_type_registry.get_serializer(
            integration, IntegrationSerializer
        ).data
    )


class GoogleOAuthStartView(APIView):
    @extend_schema(
        tags=["Integrations"],
        operation_id="start_google_oauth",
        request=StartSerializer,
        responses={200: StartResponseSerializer},
    )
    @map_exceptions(EXCEPTIONS)
    @validate_body(StartSerializer)
    def post(self, request, integration_id, data):
        return Response(
            {
                "authorization_url": service.start(
                    request.user, integration_id, data.get("service_type")
                )
            }
        )


class GoogleOAuthCompleteView(APIView):
    @extend_schema(
        tags=["Integrations"],
        operation_id="complete_google_oauth",
        request=CompleteSerializer,
        responses={200: IntegrationSerializer},
    )
    @map_exceptions(EXCEPTIONS)
    @validate_body(CompleteSerializer)
    def post(self, request, data):
        return respond(service.complete(request.user, data["state"], data["code"]))


class GoogleOAuthDisconnectView(APIView):
    @extend_schema(
        tags=["Integrations"],
        operation_id="disconnect_google_oauth",
        request=None,
        responses={200: IntegrationSerializer},
    )
    @map_exceptions(EXCEPTIONS)
    def post(self, request, integration_id):
        return respond(service.disconnect(request.user, integration_id))


class ConfigSerializer(serializers.Serializer):
    redirect_uri = serializers.URLField()
    default_client_available = serializers.BooleanField()


class GoogleOAuthConfigView(APIView):
    @extend_schema(
        tags=["Integrations"],
        operation_id="google_oauth_config",
        responses={200: ConfigSerializer},
    )
    def get(self, request):
        return Response(integration_type_registry.get("google").get_context_data(None))
