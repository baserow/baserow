from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.core.ai_provider.exceptions import (
    AIProviderDoesNotExist,
    AIProviderModelAlreadyConfigured,
    AIProviderModelDoesNotExist,
    AIProviderTypeAlreadyConfigured,
    AIProviderTypeNotSupported,
    InvalidAIProviderSettings,
)
from baserow.core.ai_provider.provider_types import get_provider_type_metadata
from baserow.core.ai_provider.service import AIProviderService
from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled

from .errors import (
    ERROR_AI_PROVIDER_DOES_NOT_EXIST,
    ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED,
    ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST,
    ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED,
    ERROR_AI_PROVIDER_TYPE_NOT_SUPPORTED,
    ERROR_INVALID_AI_PROVIDER_SETTINGS,
)
from .serializers import (
    AIProviderConfigSerializer,
    AIProviderCreateSerializer,
    AIProviderModelDiscoveryRequestSerializer,
    AIProviderModelDiscoverySerializer,
    AIProviderModelSerializer,
    AIProviderModelsTestRequestSerializer,
    AIProviderModelsTestResponseSerializer,
    AIProviderModelUpdateSerializer,
    AIProviderModelWriteSerializer,
    AIProviderTypeSerializer,
    AIProviderUpdateSerializer,
)


def _invalid_settings_error(exc):
    fields = []
    for field, errors in exc.errors.items():
        if isinstance(errors, (list, tuple)):
            errors = " ".join(str(error) for error in errors)
        fields.append(f"{field}: {errors}")
    # apply_exception_mapping calls .format() on the detail, so braces must be escaped.
    detail = "; ".join(fields).replace("{", "{{").replace("}", "}}")
    return (
        ERROR_INVALID_AI_PROVIDER_SETTINGS[0],
        ERROR_INVALID_AI_PROVIDER_SETTINGS[1],
        detail,
    )


EXCEPTION_MAP = {
    AIProviderDoesNotExist: ERROR_AI_PROVIDER_DOES_NOT_EXIST,
    AIProviderModelDoesNotExist: ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST,
    AIProviderTypeNotSupported: ERROR_AI_PROVIDER_TYPE_NOT_SUPPORTED,
    AIProviderTypeAlreadyConfigured: ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED,
    AIProviderModelAlreadyConfigured: ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED,
    InvalidAIProviderSettings: _invalid_settings_error,
}


def _ensure_feature_enabled():
    feature_flag_is_enabled(FF_AI_PROVIDERS, raise_if_disabled=True)


class AIProvidersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="list_ai_providers",
        responses={200: AIProviderConfigSerializer(many=True)},
    )
    @map_exceptions(EXCEPTION_MAP)
    def get(self, request):
        _ensure_feature_enabled()
        providers = AIProviderService.list_providers(request.user)
        return Response(AIProviderConfigSerializer(providers, many=True).data)

    @extend_schema(
        tags=["AI providers"],
        operation_id="create_ai_provider",
        request=AIProviderCreateSerializer,
        responses={201: AIProviderConfigSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderCreateSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, data):
        _ensure_feature_enabled()
        models_data = data.pop("models", [])
        provider = AIProviderService.create_provider(
            request.user, models_data=models_data, **data
        )
        return Response(
            AIProviderConfigSerializer(provider).data, status=HTTP_201_CREATED
        )


class AIProviderView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="update_ai_provider",
        request=AIProviderUpdateSerializer,
        responses={200: AIProviderConfigSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderUpdateSerializer, partial=True, return_validated=True)
    @transaction.atomic
    def patch(self, request, provider_id, data):
        _ensure_feature_enabled()
        provider = AIProviderService.update_provider(request.user, provider_id, **data)
        return Response(AIProviderConfigSerializer(provider).data)

    @extend_schema(
        tags=["AI providers"],
        operation_id="delete_ai_provider",
        responses={204: None},
    )
    @map_exceptions(EXCEPTION_MAP)
    @transaction.atomic
    def delete(self, request, provider_id):
        _ensure_feature_enabled()
        AIProviderService.delete_provider(request.user, provider_id)
        return Response(status=HTTP_204_NO_CONTENT)


class AIProviderModelsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="create_ai_provider_model",
        request=AIProviderModelWriteSerializer,
        responses={201: AIProviderModelSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderModelWriteSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, provider_id, data):
        _ensure_feature_enabled()
        model = AIProviderService.create_model(request.user, provider_id, **data)
        return Response(AIProviderModelSerializer(model).data, status=HTTP_201_CREATED)


class AIProviderModelDiscoveryView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="discover_ai_provider_models",
        parameters=[AIProviderModelDiscoveryRequestSerializer],
        responses={200: AIProviderModelDiscoverySerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_query_parameters(
        AIProviderModelDiscoveryRequestSerializer, return_validated=True
    )
    def get(self, request, query_params):
        _ensure_feature_enabled()
        models = AIProviderService.discover_models(request.user, **query_params)
        return Response(
            AIProviderModelDiscoverySerializer(
                {"models": models or [], "supported": models is not None}
            ).data
        )


class AIProviderModelView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="update_ai_provider_model",
        request=AIProviderModelUpdateSerializer,
        responses={200: AIProviderModelSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderModelUpdateSerializer, partial=True, return_validated=True)
    @transaction.atomic
    def patch(self, request, model_id, data):
        _ensure_feature_enabled()
        model = AIProviderService.update_model(request.user, model_id, **data)
        return Response(AIProviderModelSerializer(model).data)

    @extend_schema(
        tags=["AI providers"],
        operation_id="delete_ai_provider_model",
        responses={204: None},
    )
    @map_exceptions(EXCEPTION_MAP)
    @transaction.atomic
    def delete(self, request, model_id):
        _ensure_feature_enabled()
        AIProviderService.delete_model(request.user, model_id)
        return Response(status=HTTP_204_NO_CONTENT)


class AIProviderModelsTestView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="test_ai_provider_models",
        request=AIProviderModelsTestRequestSerializer,
        responses={200: AIProviderModelsTestResponseSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderModelsTestRequestSerializer, return_validated=True)
    def post(self, request, data):
        _ensure_feature_enabled()
        results = AIProviderService.test_models(request.user, **data)
        return Response(
            AIProviderModelsTestResponseSerializer({"results": results}).data
        )


class AIProviderTypesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="list_ai_provider_types",
        responses={200: AIProviderTypeSerializer(many=True)},
    )
    @map_exceptions(EXCEPTION_MAP)
    def get(self, request):
        _ensure_feature_enabled()
        AIProviderService.check_permissions(request.user)
        return Response(
            AIProviderTypeSerializer(get_provider_type_metadata(), many=True).data
        )
