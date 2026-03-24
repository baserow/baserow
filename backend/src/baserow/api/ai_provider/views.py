from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.ai_provider.errors import (
    ERROR_AI_PROVIDER_DOES_NOT_EXIST,
    ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST,
)
from baserow.api.ai_provider.serializers import (
    AIFeatureDefaultModelSerializer,
    AIProviderConfigSerializer,
    AIProviderModelSerializer,
    AIProviderOverrideSerializer,
    AvailableModelSerializer,
    CreateAIProviderSerializer,
    ScopeQueryParamsSerializer,
    UpdateAIProviderSerializer,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.core.ai_provider.actions import (
    CreateAIProviderActionType,
    DeleteAIProviderActionType,
    SetAIFeatureDefaultModelActionType,
    ToggleAIProviderOverrideActionType,
    UpdateAIProviderActionType,
)
from baserow.core.ai_provider.constants import (
    SCOPE_APPLICATION,
    SCOPE_INSTANCE,
    SCOPE_WORKSPACE,
)
from baserow.core.ai_provider.exceptions import (
    AIProviderDoesNotExist,
    AIProviderModelDoesNotExist,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.operations import (
    ManageApplicationAIProvidersOperationType,
    ManageWorkspaceAIProvidersOperationType,
)
from baserow.core.handler import CoreHandler


def _check_scope_permissions(user, scope_type, scope_id):
    """
    Check that the user has permission to manage AI providers at the given
    scope. Follows the audit log pattern for multi-scope views.
    """

    if scope_type == SCOPE_APPLICATION:
        application = CoreHandler().get_application(scope_id)
        if not user.is_staff:
            CoreHandler().check_permissions(
                user,
                ManageApplicationAIProvidersOperationType.type,
                workspace=application.workspace,
                context=application,
            )
        return application.workspace
    elif scope_type == SCOPE_WORKSPACE:
        workspace = CoreHandler().get_workspace(scope_id)
        if not user.is_staff:
            CoreHandler().check_permissions(
                user,
                ManageWorkspaceAIProvidersOperationType.type,
                workspace=workspace,
                context=workspace,
            )
        return workspace
    else:  # instance
        if not user.is_staff:
            raise PermissionDenied()
        return None


def _get_scope_from_request(request):
    """Extract and validate scope query params from the request."""

    serializer = ScopeQueryParamsSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["scope"], serializer.validated_data.get("scope_id")


class AIProvidersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="list_ai_providers",
        description=(
            "Lists AI providers at the given scope. For workspace and application "
            "scopes, this returns the effective list including inherited providers "
            "from parent scopes."
        ),
        parameters=[ScopeQueryParamsSerializer],
        responses={
            200: AIProviderConfigSerializer(many=True),
        },
    )
    @map_exceptions(
        {
            AIProviderDoesNotExist: ERROR_AI_PROVIDER_DOES_NOT_EXIST,
        }
    )
    def get(self, request):
        scope_type, scope_id = _get_scope_from_request(request)
        _check_scope_permissions(request.user, scope_type, scope_id)

        if scope_type == SCOPE_INSTANCE:
            # Instance scope: return only instance-level providers
            providers = AIProviderHandler.list_providers(scope_type, scope_id)
            serializer = AIProviderConfigSerializer(providers, many=True)
        else:
            # Workspace/Application scope: return effective (merged) list
            effective = AIProviderHandler.list_effective_providers(scope_type, scope_id)
            serializer = AIProviderConfigSerializer(effective, many=True)

        return Response(serializer.data)

    @extend_schema(
        tags=["AI providers"],
        operation_id="create_ai_provider",
        description="Creates a new AI provider at the given scope.",
        parameters=[ScopeQueryParamsSerializer],
        request=CreateAIProviderSerializer,
        responses={
            200: AIProviderConfigSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
        },
    )
    @transaction.atomic
    @validate_body(CreateAIProviderSerializer)
    @map_exceptions(
        {
            AIProviderDoesNotExist: ERROR_AI_PROVIDER_DOES_NOT_EXIST,
        }
    )
    def post(self, request, data):
        scope_type, scope_id = _get_scope_from_request(request)
        _check_scope_permissions(request.user, scope_type, scope_id)

        provider = AIProviderHandler.create_provider(
            user=request.user,
            provider_type=data["provider_type"],
            name=data["name"],
            scope_type=scope_type,
            scope_id=scope_id,
            api_key=data.get("api_key", ""),
            extra_settings=data.get("extra_settings", {}),
            is_active=data.get("is_active", True),
            models_data=data.get("models_data", []),
        )

        CreateAIProviderActionType.do(request.user, provider, scope_type, scope_id)

        serializer = AIProviderConfigSerializer(provider)
        return Response(serializer.data)


class AIProviderView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="get_ai_provider",
        description="Returns a single AI provider.",
        responses={
            200: AIProviderConfigSerializer,
            404: get_error_schema(["ERROR_AI_PROVIDER_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AIProviderDoesNotExist: ERROR_AI_PROVIDER_DOES_NOT_EXIST,
        }
    )
    def get(self, request, provider_id):
        provider = AIProviderHandler.get_provider(provider_id)
        _check_provider_scope_permissions(request.user, provider)
        serializer = AIProviderConfigSerializer(provider)
        return Response(serializer.data)

    @extend_schema(
        tags=["AI providers"],
        operation_id="update_ai_provider",
        description="Updates an AI provider.",
        request=UpdateAIProviderSerializer,
        responses={
            200: AIProviderConfigSerializer,
            404: get_error_schema(["ERROR_AI_PROVIDER_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateAIProviderSerializer)
    @map_exceptions(
        {
            AIProviderDoesNotExist: ERROR_AI_PROVIDER_DOES_NOT_EXIST,
        }
    )
    def patch(self, request, data, provider_id):
        provider = AIProviderHandler.get_provider(provider_id)
        _check_provider_scope_permissions(request.user, provider)

        provider = AIProviderHandler.update_provider(
            user=request.user,
            provider=provider,
            **data,
        )

        UpdateAIProviderActionType.do(request.user, provider)

        serializer = AIProviderConfigSerializer(provider)
        return Response(serializer.data)

    @extend_schema(
        tags=["AI providers"],
        operation_id="delete_ai_provider",
        description="Deletes an AI provider.",
        responses={
            204: None,
            404: get_error_schema(["ERROR_AI_PROVIDER_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AIProviderDoesNotExist: ERROR_AI_PROVIDER_DOES_NOT_EXIST,
        }
    )
    def delete(self, request, provider_id):
        provider = AIProviderHandler.get_provider(provider_id)
        workspace = _check_provider_scope_permissions(request.user, provider)

        provider_id_val = provider.id
        provider_name = provider.name

        AIProviderHandler.delete_provider(request.user, provider)

        DeleteAIProviderActionType.do(
            request.user, provider_id_val, provider_name, workspace
        )

        return Response(status=204)


class AIProviderOverrideView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="toggle_ai_provider_override",
        description=(
            "Toggle an inherited provider on/off at the given scope. "
            "The scope is specified via query parameters."
        ),
        parameters=[ScopeQueryParamsSerializer],
        request=AIProviderOverrideSerializer,
        responses={
            200: AIProviderOverrideSerializer,
            404: get_error_schema(["ERROR_AI_PROVIDER_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(AIProviderOverrideSerializer)
    @map_exceptions(
        {
            AIProviderDoesNotExist: ERROR_AI_PROVIDER_DOES_NOT_EXIST,
        }
    )
    def patch(self, request, data, provider_id):
        scope_type, scope_id = _get_scope_from_request(request)
        workspace = _check_scope_permissions(request.user, scope_type, scope_id)

        provider = AIProviderHandler.get_provider(provider_id)
        override = AIProviderHandler.toggle_provider_override(
            user=request.user,
            provider=provider,
            scope_type=scope_type,
            scope_id=scope_id,
            is_enabled=data["is_enabled"],
        )

        ToggleAIProviderOverrideActionType.do(
            request.user,
            provider,
            scope_type,
            data["is_enabled"],
            workspace,
        )

        return Response(AIProviderOverrideSerializer(override).data)


class AIProviderModelTestView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="test_ai_provider_model",
        description=(
            "Tests a specific AI provider model by sending a minimal prompt. "
            "Updates the test status on the model."
        ),
        responses={
            200: AIProviderModelSerializer,
            404: get_error_schema(["ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AIProviderModelDoesNotExist: ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST,
        }
    )
    def post(self, request, model_id):
        provider_model = AIProviderHandler.get_provider_model(model_id)
        _check_provider_scope_permissions(request.user, provider_model.provider_config)

        provider_model = AIProviderHandler.test_model(request.user, provider_model)

        serializer = AIProviderModelSerializer(provider_model)
        return Response(serializer.data)


class AvailableModelsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="list_available_ai_models",
        description=(
            "Returns all enabled models available for a given feature "
            "at a given scope. Used by model selectors in the UI."
        ),
        responses={
            200: AvailableModelSerializer(many=True),
        },
    )
    def get(self, request):
        scope_type, scope_id = _get_scope_from_request(request)
        feature_type = request.query_params.get("feature", None)

        # Validate scope exists and user has access to the workspace.
        if scope_type == SCOPE_WORKSPACE:
            workspace = CoreHandler().get_workspace(scope_id)
            CoreHandler().check_permissions(
                request.user,
                ManageWorkspaceAIProvidersOperationType.type,
                workspace=workspace,
                context=workspace,
            )
        elif scope_type == SCOPE_APPLICATION:
            application = CoreHandler().get_application(scope_id)
            CoreHandler().check_permissions(
                request.user,
                ManageApplicationAIProvidersOperationType.type,
                workspace=application.workspace,
                context=application,
            )
        elif not request.user.is_staff:
            raise PermissionDenied()

        models = AIProviderHandler.get_available_models_for_feature(
            feature_type=feature_type,
            scope_type=scope_type,
            scope_id=scope_id,
        )

        serializer = AvailableModelSerializer(models, many=True)
        return Response(serializer.data)


class FeatureDefaultsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["AI providers"],
        operation_id="get_feature_defaults",
        description=(
            "Returns the current default model for each feature at the given scope."
        ),
        responses={200: AIFeatureDefaultModelSerializer(many=True)},
    )
    def get(self, request):
        scope_type, scope_id = _get_scope_from_request(request)
        _check_scope_permissions(request.user, scope_type, scope_id)

        from baserow.core.ai_provider.registries import ai_feature_type_registry

        results = []
        for feature in ai_feature_type_registry.get_all():
            if not feature.requires_default_model:
                continue
            model = AIProviderHandler.get_feature_default_model(
                feature.type, scope_type, scope_id
            )
            if model:
                results.append(
                    {
                        "feature_type": feature.type,
                        "provider_model_id": model.id,
                    }
                )
        return Response(results)

    @extend_schema(
        tags=["AI providers"],
        operation_id="set_feature_default",
        description="Sets the default model for a feature at the given scope.",
        request=AIFeatureDefaultModelSerializer,
        responses={200: AIFeatureDefaultModelSerializer},
    )
    @transaction.atomic
    @validate_body(AIFeatureDefaultModelSerializer)
    @map_exceptions(
        {
            AIProviderModelDoesNotExist: ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST,
        }
    )
    def patch(self, request, data):
        scope_type, scope_id = _get_scope_from_request(request)
        workspace = _check_scope_permissions(request.user, scope_type, scope_id)

        provider_model = AIProviderHandler.get_provider_model(data["provider_model_id"])

        AIProviderHandler.set_feature_default_model(
            user=request.user,
            feature_type=data["feature_type"],
            provider_model=provider_model,
            scope_type=scope_type,
            scope_id=scope_id,
        )

        SetAIFeatureDefaultModelActionType.do(
            request.user,
            data["feature_type"],
            provider_model,
            scope_type,
            workspace,
        )

        return Response(data)


def _check_provider_scope_permissions(user, provider):
    """
    Check permissions based on a provider's actual scope.
    Returns the workspace (if any) for the provider's scope.
    """

    from baserow.core.models import Application, Workspace

    if provider.is_instance_level:
        if not user.is_staff:
            raise PermissionDenied()
        return None

    model_class = provider.scope_content_type.model_class()
    if model_class == Workspace:
        workspace = CoreHandler().get_workspace(provider.scope_object_id)
        if not user.is_staff:
            CoreHandler().check_permissions(
                user,
                ManageWorkspaceAIProvidersOperationType.type,
                workspace=workspace,
                context=workspace,
            )
        return workspace
    elif model_class == Application:
        application = CoreHandler().get_application(provider.scope_object_id)
        if not user.is_staff:
            CoreHandler().check_permissions(
                user,
                ManageApplicationAIProvidersOperationType.type,
                workspace=application.workspace,
                context=application,
            )
        return application.workspace

    raise PermissionDenied()
