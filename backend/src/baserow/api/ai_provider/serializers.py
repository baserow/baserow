from rest_framework import serializers

from baserow.core.ai_provider.constants import SCOPE_CHOICES
from baserow.core.ai_provider.models import (
    AIProviderConfig,
    AIProviderModel,
)


class AIProviderModelSerializer(serializers.ModelSerializer):
    features = serializers.SerializerMethodField()

    class Meta:
        model = AIProviderModel
        fields = (
            "id",
            "model_identifier",
            "display_name",
            "is_enabled",
            "features",
            "last_test_at",
            "last_test_status",
            "last_test_error",
        )

    def get_features(self, obj):
        return list(obj.features.values_list("feature_type", flat=True))


class AIProviderConfigSerializer(serializers.ModelSerializer):
    models = AIProviderModelSerializer(many=True, read_only=True)
    is_own_scope = serializers.BooleanField(read_only=True, default=True)
    is_enabled = serializers.BooleanField(read_only=True, default=True)

    class Meta:
        model = AIProviderConfig
        fields = (
            "id",
            "provider_type",
            "name",
            "api_key",
            "extra_settings",
            "is_active",
            "created_on",
            "updated_on",
            "models",
            "is_own_scope",
            "is_enabled",
        )
        read_only_fields = ("id", "created_on", "updated_on")

    def to_representation(self, instance):
        """
        If the instance is a dict (from list_effective_providers), unwrap it.
        API keys are never returned — only a boolean indicating whether one is set.
        """

        if isinstance(instance, dict):
            provider = instance["provider"]
            data = super().to_representation(provider)
            data["is_own_scope"] = instance["is_own_scope"]
            data["is_enabled"] = instance["is_enabled"]
        else:
            provider = instance
            data = super().to_representation(instance)

        # Never expose the actual API key. Return a flag instead.
        data["has_api_key"] = bool(provider.api_key)
        data["api_key"] = ""
        return data


class ModelDataSerializer(serializers.Serializer):
    """Nested serializer for model data in create/update requests."""

    model_identifier = serializers.CharField(max_length=255)
    display_name = serializers.CharField(max_length=255, required=False, default="")
    is_enabled = serializers.BooleanField(required=False, default=True)
    features = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
    )


class CreateAIProviderSerializer(serializers.Serializer):
    provider_type = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=255)
    api_key = serializers.CharField(max_length=512, required=False, default="")
    extra_settings = serializers.JSONField(required=False, default=dict)
    is_active = serializers.BooleanField(required=False, default=True)
    models_data = ModelDataSerializer(many=True, required=False, default=list)

    PROVIDERS_REQUIRING_API_KEY = {"openai", "anthropic", "mistral", "openrouter"}

    def validate(self, data):
        provider_type = data.get("provider_type", "")
        api_key = data.get("api_key", "")
        if provider_type in self.PROVIDERS_REQUIRING_API_KEY and not api_key:
            raise serializers.ValidationError(
                {"api_key": "API key is required for this provider type."}
            )
        return data


class UpdateAIProviderSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    api_key = serializers.CharField(max_length=512, required=False)
    extra_settings = serializers.JSONField(required=False)
    is_active = serializers.BooleanField(required=False)
    models_data = ModelDataSerializer(many=True, required=False)


class AIProviderOverrideSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()


class ScopeQueryParamsSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=SCOPE_CHOICES)
    scope_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        scope = data.get("scope")
        scope_id = data.get("scope_id")
        if scope != "instance" and not scope_id:
            raise serializers.ValidationError(
                "scope_id is required for non-instance scopes."
            )
        return data


class AvailableModelSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    model_identifier = serializers.CharField()
    display_name = serializers.CharField()
    provider_name = serializers.SerializerMethodField()
    provider_type = serializers.SerializerMethodField()
    last_test_status = serializers.CharField()

    def get_provider_name(self, obj):
        return obj.provider_config.name

    def get_provider_type(self, obj):
        return obj.provider_config.provider_type


class AIFeatureDefaultModelSerializer(serializers.Serializer):
    feature_type = serializers.CharField(max_length=64)
    provider_model_id = serializers.IntegerField()
