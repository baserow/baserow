from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_MODE_MODEL,
    AI_PROVIDER_FEATURE_MODES,
)
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.ai_provider.registries import ai_provider_model_feature_type_registry


class AIProviderFeatureTestResultSerializer(serializers.Serializer):
    feature_type = serializers.CharField()
    status = serializers.ChoiceField(choices=AIProviderModel.TestStatus.choices)
    error = serializers.CharField(allow_blank=True)


class AIProviderModelSerializer(serializers.ModelSerializer):
    last_test_feature_results = serializers.SerializerMethodField()

    @extend_schema_field(AIProviderFeatureTestResultSerializer(many=True))
    def get_last_test_feature_results(self, instance) -> list[dict]:
        """
        Derive feature-level results from the stored capability probes.

        :param instance: The model whose latest test results are serialized.
        :return: Feature test results, or an empty list before the first test.
        """

        if instance.last_test_at is None:
            return []

        return ai_provider_model_feature_type_registry.get_feature_test_results(
            instance.feature_types, instance.last_test_capabilities
        )

    class Meta:
        model = AIProviderModel
        fields = (
            "id",
            "model_identifier",
            "is_enabled",
            "feature_types",
            "last_test_at",
            "last_test_status",
            "last_test_error",
            "last_test_feature_results",
        )
        read_only_fields = (
            "id",
            "last_test_at",
            "last_test_status",
            "last_test_error",
            "last_test_feature_results",
        )


class AIProviderConfigSerializer(serializers.ModelSerializer):
    models = AIProviderModelSerializer(many=True, read_only=True)

    class Meta:
        model = AIProviderConfig
        fields = (
            "id",
            "provider_type",
            "extra_settings",
            "is_active",
            "models",
        )
        read_only_fields = fields


class WorkspaceAIProviderConfigSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    provider_type = serializers.CharField(read_only=True)
    extra_settings = serializers.DictField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    models = AIProviderModelSerializer(many=True, read_only=True)
    workspace_enabled = serializers.BooleanField(read_only=True)
    read_only = serializers.BooleanField(read_only=True)


class AIProviderScopeRequestSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(min_value=1, required=False)


class AIProviderModelWriteSerializer(serializers.Serializer):
    model_identifier = serializers.CharField(max_length=255)
    is_enabled = serializers.BooleanField(required=False, default=True)
    feature_types = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False
    )


class AIProviderModelUpdateSerializer(serializers.Serializer):
    model_identifier = serializers.CharField(max_length=255, required=False)
    is_enabled = serializers.BooleanField(required=False)
    feature_types = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False
    )


class AIProviderFeatureModelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    model_identifier = serializers.CharField()
    provider_type = serializers.CharField(source="provider_config.provider_type")
    inherited = serializers.SerializerMethodField()

    def get_inherited(self, instance) -> bool:
        """
        Report whether the model comes from the instance scope.

        :param instance: The selected provider model.
        :return: Whether a workspace inherits this instance model.
        """

        workspace_id = self.context.get("workspace_id")
        return (
            workspace_id is not None and instance.provider_config.workspace_id is None
        )


class AIProviderFeatureSettingSerializer(serializers.Serializer):
    feature_type = serializers.CharField()
    mode = serializers.ChoiceField(choices=AI_PROVIDER_FEATURE_MODES)
    state = serializers.ChoiceField(
        choices=(
            "configured",
            "inherited",
            "overridden",
            "disabled",
            "unconfigured",
            "invalid",
        )
    )
    model = AIProviderFeatureModelSerializer(allow_null=True)
    inherited_model = AIProviderFeatureModelSerializer(allow_null=True)
    inherited_state = serializers.ChoiceField(
        choices=("configured", "disabled", "unconfigured", "invalid"),
        allow_null=True,
        help_text=(
            "How the instance selection resolves in this workspace, or null at "
            "instance scope."
        ),
    )


class AIProviderFeatureSettingUpdateSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=AI_PROVIDER_FEATURE_MODES)
    model_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate(self, attrs):
        """
        Enforce that only model mode accepts exactly one model identifier.

        :param attrs: The parsed feature-setting request values.
        :return: The validated request values.
        :raises serializers.ValidationError: If the mode and model selection are
            incompatible.
        """

        model_mode = attrs["mode"] == AI_PROVIDER_FEATURE_MODE_MODEL
        if model_mode and not attrs.get("model_id"):
            raise serializers.ValidationError(
                {"model_id": "A model is required when selecting model mode."}
            )
        if not model_mode and "model_id" in attrs:
            raise serializers.ValidationError(
                {"model_id": "A model can only be provided in model mode."}
            )
        return attrs


class AIProviderModelDiscoverySerializer(serializers.Serializer):
    models = serializers.ListField(child=serializers.CharField())
    supported = serializers.BooleanField()


class AIProviderModelDiscoveryRequestSerializer(AIProviderScopeRequestSerializer):
    provider_type = serializers.CharField(max_length=32)


class AIProviderCreateSerializer(serializers.Serializer):
    provider_type = serializers.CharField(max_length=32)
    api_key = serializers.CharField(
        max_length=512, required=False, allow_blank=True, write_only=True, default=""
    )
    extra_settings = serializers.DictField(required=False, default=dict)
    models = AIProviderModelWriteSerializer(many=True, required=False, default=list)


class AIProviderUpdateSerializer(serializers.Serializer):
    api_key = serializers.CharField(
        max_length=512, required=False, allow_blank=True, write_only=True
    )
    extra_settings = serializers.DictField(required=False)
    is_active = serializers.BooleanField(required=False)


class AIProviderModelsTestRequestSerializer(serializers.Serializer):
    model_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        required=True,
    )

    def validate(self, attrs):
        if len(attrs["model_ids"]) != len(set(attrs["model_ids"])):
            raise serializers.ValidationError(
                {"model_ids": "Model IDs must be unique."}
            )
        return attrs


class AIProviderModelTestResultSerializer(serializers.Serializer):
    model_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=AIProviderModel.TestStatus.choices)
    error = serializers.CharField(allow_blank=True)
    tested_at = serializers.DateTimeField()
    feature_results = AIProviderFeatureTestResultSerializer(many=True)


class AIProviderModelsTestResponseSerializer(serializers.Serializer):
    results = AIProviderModelTestResultSerializer(many=True)


class AIProviderTypeExtraFieldSerializer(serializers.Serializer):
    name = serializers.CharField()
    required = serializers.BooleanField()
    allow_blank = serializers.BooleanField()


class AIProviderTypeSerializer(serializers.Serializer):
    type = serializers.CharField()
    name = serializers.CharField()
    uses_api_key = serializers.BooleanField()
    extra_fields = AIProviderTypeExtraFieldSerializer(many=True)
