from django.db import DEFAULT_DB_ALIAS, transaction

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_USER_INVALID_GROUP_PERMISSIONS,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.mixins import RealtimeRecoveryPrimaryReadMixin
from baserow.config.db_routers import set_db_alias
from baserow.core.ai_provider.exceptions import (
    AIProviderDoesNotExist,
    AIProviderFeatureModelNotAvailable,
    AIProviderFeatureModeNotAllowed,
    AIProviderIsReadOnly,
    AIProviderModelAlreadyConfigured,
    AIProviderModelDoesNotExist,
    AIProviderModelFeatureTypeDoesNotExist,
    AIProviderModelInUse,
    AIProviderTypeAlreadyConfigured,
    AIProviderTypeNotSupported,
    InvalidAIProviderSettings,
)
from baserow.core.ai_provider.service import AIProviderService
from baserow.core.exceptions import (
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled

from .errors import (
    ERROR_AI_PROVIDER_DOES_NOT_EXIST,
    ERROR_AI_PROVIDER_FEATURE_MODE_NOT_ALLOWED,
    ERROR_AI_PROVIDER_FEATURE_MODEL_NOT_AVAILABLE,
    ERROR_AI_PROVIDER_IS_READ_ONLY,
    ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED,
    ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST,
    ERROR_AI_PROVIDER_MODEL_FEATURE_TYPE_DOES_NOT_EXIST,
    ERROR_AI_PROVIDER_MODEL_IN_USE,
    ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED,
    ERROR_AI_PROVIDER_TYPE_NOT_SUPPORTED,
    ERROR_INVALID_AI_PROVIDER_SETTINGS,
)
from .serializers import (
    AIProviderConfigSerializer,
    AIProviderCreateSerializer,
    AIProviderFeatureSettingSerializer,
    AIProviderFeatureSettingUpdateSerializer,
    AIProviderModelDiscoveryRequestSerializer,
    AIProviderModelDiscoverySerializer,
    AIProviderModelSerializer,
    AIProviderModelsTestRequestSerializer,
    AIProviderModelsTestResponseSerializer,
    AIProviderModelUpdateSerializer,
    AIProviderModelWriteSerializer,
    AIProviderScopeRequestSerializer,
    AIProviderTypeSerializer,
    AIProviderUpdateSerializer,
    WorkspaceAIProviderConfigSerializer,
)


def _invalid_settings_error(
    exc: InvalidAIProviderSettings,
) -> tuple[str, int, str]:
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


def _model_in_use_error(exc: AIProviderModelInUse) -> tuple[str, int, str]:
    features = ", ".join(exc.feature_types)
    # apply_exception_mapping calls .format() on the detail, so braces must be escaped.
    detail = (
        (
            f"The model '{exc.model_identifier}' is selected by these AI features: "
            f"{features}. Choose another model for them first."
        )
        .replace("{", "{{")
        .replace("}", "}}")
    )
    return (
        ERROR_AI_PROVIDER_MODEL_IN_USE[0],
        ERROR_AI_PROVIDER_MODEL_IN_USE[1],
        detail,
    )


EXCEPTION_MAP = {
    AIProviderDoesNotExist: ERROR_AI_PROVIDER_DOES_NOT_EXIST,
    AIProviderModelDoesNotExist: ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST,
    AIProviderTypeNotSupported: ERROR_AI_PROVIDER_TYPE_NOT_SUPPORTED,
    AIProviderTypeAlreadyConfigured: ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED,
    AIProviderModelAlreadyConfigured: ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED,
    AIProviderIsReadOnly: ERROR_AI_PROVIDER_IS_READ_ONLY,
    AIProviderModelInUse: _model_in_use_error,
    AIProviderFeatureModelNotAvailable: ERROR_AI_PROVIDER_FEATURE_MODEL_NOT_AVAILABLE,
    AIProviderFeatureModeNotAllowed: ERROR_AI_PROVIDER_FEATURE_MODE_NOT_ALLOWED,
    AIProviderModelFeatureTypeDoesNotExist: ERROR_AI_PROVIDER_MODEL_FEATURE_TYPE_DOES_NOT_EXIST,
    InvalidAIProviderSettings: _invalid_settings_error,
    WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
    UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
    UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
}


def _provider_response(many: bool = False) -> PolymorphicProxySerializer:
    """
    The response shape depends on the ``workspace_id`` query parameter: a
    workspace scope additionally reports ``read_only`` and ``workspace_enabled``,
    and its ``is_active`` is the effective value for that workspace.
    """

    return PolymorphicProxySerializer(
        component_name="AIProviderConfigResponse",
        serializers=[AIProviderConfigSerializer, WorkspaceAIProviderConfigSerializer],
        resource_type_field_name=None,
        many=many,
    )


def _ensure_feature_enabled():
    feature_flag_is_enabled(FF_AI_PROVIDERS, raise_if_disabled=True)


def _get_workspace_id(request) -> int | None:
    serializer = AIProviderScopeRequestSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data.get("workspace_id")


def _serialize_provider(provider, workspace_id: int | None, many: bool = False):
    serializer_class = (
        WorkspaceAIProviderConfigSerializer
        if workspace_id is not None
        else AIProviderConfigSerializer
    )
    return serializer_class(provider, many=many).data


def _serialize_feature_settings(settings, workspace_id: int | None, many=False):
    return AIProviderFeatureSettingSerializer(
        settings,
        many=many,
        context={"workspace_id": workspace_id},
    ).data


class AIProviderFeaturesView(RealtimeRecoveryPrimaryReadMixin, APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="list_ai_provider_feature_settings",
        parameters=[AIProviderScopeRequestSerializer],
        responses={200: AIProviderFeatureSettingSerializer(many=True)},
    )
    @map_exceptions(EXCEPTION_MAP)
    def get(self, request):
        _ensure_feature_enabled()
        workspace_id = _get_workspace_id(request)
        settings = AIProviderService.list_feature_settings(
            request.user, workspace_id=workspace_id
        )
        return Response(_serialize_feature_settings(settings, workspace_id, many=True))


class AIProviderFeatureView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="update_ai_provider_feature_setting",
        parameters=[AIProviderScopeRequestSerializer],
        request=AIProviderFeatureSettingUpdateSerializer,
        responses={200: AIProviderFeatureSettingSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderFeatureSettingUpdateSerializer, return_validated=True)
    @transaction.atomic
    def put(self, request, feature_type, data):
        _ensure_feature_enabled()
        workspace_id = _get_workspace_id(request)
        setting = AIProviderService.update_feature_setting(
            request.user,
            feature_type,
            workspace_id=workspace_id,
            **data,
        )
        return Response(_serialize_feature_settings(setting, workspace_id))


class AIProvidersView(RealtimeRecoveryPrimaryReadMixin, APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="list_ai_providers",
        parameters=[AIProviderScopeRequestSerializer],
        responses={200: _provider_response(many=True)},
    )
    @map_exceptions(EXCEPTION_MAP)
    def get(self, request):
        _ensure_feature_enabled()
        workspace_id = _get_workspace_id(request)
        providers = AIProviderService.list_providers(
            request.user, workspace_id=workspace_id
        )
        return Response(_serialize_provider(providers, workspace_id, many=True))

    @extend_schema(
        tags=["AI providers"],
        operation_id="create_ai_provider",
        parameters=[AIProviderScopeRequestSerializer],
        request=AIProviderCreateSerializer,
        responses={201: _provider_response()},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderCreateSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, data):
        _ensure_feature_enabled()
        models_data = data.pop("models", [])
        workspace_id = _get_workspace_id(request)
        provider = AIProviderService.create_provider(
            request.user,
            workspace_id=workspace_id,
            models_data=models_data,
            **data,
        )
        return Response(
            _serialize_provider(provider, workspace_id), status=HTTP_201_CREATED
        )


class AIProviderView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="update_ai_provider",
        parameters=[AIProviderScopeRequestSerializer],
        request=AIProviderUpdateSerializer,
        responses={200: _provider_response()},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderUpdateSerializer, partial=True, return_validated=True)
    @transaction.atomic
    def patch(self, request, provider_id, data):
        _ensure_feature_enabled()
        workspace_id = _get_workspace_id(request)
        provider = AIProviderService.update_provider(
            request.user,
            provider_id,
            workspace_id=workspace_id,
            **data,
        )
        return Response(_serialize_provider(provider, workspace_id))

    @extend_schema(
        tags=["AI providers"],
        operation_id="delete_ai_provider",
        parameters=[AIProviderScopeRequestSerializer],
        responses={204: None},
    )
    @map_exceptions(EXCEPTION_MAP)
    @transaction.atomic
    def delete(self, request, provider_id):
        _ensure_feature_enabled()
        AIProviderService.delete_provider(
            request.user, provider_id, workspace_id=_get_workspace_id(request)
        )
        return Response(status=HTTP_204_NO_CONTENT)


class AIProviderModelsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="create_ai_provider_model",
        parameters=[AIProviderScopeRequestSerializer],
        request=AIProviderModelWriteSerializer,
        responses={201: AIProviderModelSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderModelWriteSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, provider_id, data):
        _ensure_feature_enabled()
        model = AIProviderService.create_model(
            request.user,
            provider_id,
            workspace_id=_get_workspace_id(request),
            **data,
        )
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
        parameters=[AIProviderScopeRequestSerializer],
        request=AIProviderModelUpdateSerializer,
        responses={200: AIProviderModelSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderModelUpdateSerializer, partial=True, return_validated=True)
    @transaction.atomic
    def patch(self, request, model_id, data):
        _ensure_feature_enabled()
        model = AIProviderService.update_model(
            request.user,
            model_id,
            workspace_id=_get_workspace_id(request),
            **data,
        )
        return Response(AIProviderModelSerializer(model).data)

    @extend_schema(
        tags=["AI providers"],
        operation_id="delete_ai_provider_model",
        parameters=[AIProviderScopeRequestSerializer],
        responses={204: None},
    )
    @map_exceptions(EXCEPTION_MAP)
    @transaction.atomic
    def delete(self, request, model_id):
        _ensure_feature_enabled()
        AIProviderService.delete_model(
            request.user, model_id, workspace_id=_get_workspace_id(request)
        )
        return Response(status=HTTP_204_NO_CONTENT)


class AIProviderModelsTestView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="test_ai_provider_models",
        parameters=[AIProviderScopeRequestSerializer],
        request=AIProviderModelsTestRequestSerializer,
        responses={200: AIProviderModelsTestResponseSerializer},
    )
    @map_exceptions(EXCEPTION_MAP)
    @validate_body(AIProviderModelsTestRequestSerializer, return_validated=True)
    def post(self, request, data):
        set_db_alias(DEFAULT_DB_ALIAS)
        _ensure_feature_enabled()
        results = AIProviderService.test_models(
            request.user, workspace_id=_get_workspace_id(request), **data
        )
        return Response(
            AIProviderModelsTestResponseSerializer({"results": results}).data
        )


class AIProviderTypesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="list_ai_provider_types",
        parameters=[AIProviderScopeRequestSerializer],
        responses={200: AIProviderTypeSerializer(many=True)},
    )
    @map_exceptions(EXCEPTION_MAP)
    def get(self, request):
        _ensure_feature_enabled()
        return Response(
            AIProviderTypeSerializer(
                AIProviderService.list_provider_types(
                    request.user, workspace_id=_get_workspace_id(request)
                ),
                many=True,
            ).data
        )
