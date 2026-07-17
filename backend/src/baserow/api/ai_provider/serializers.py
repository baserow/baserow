from rest_framework import serializers

from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel


class AIProviderModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIProviderModel
        fields = (
            "id",
            "model_identifier",
            "is_enabled",
            "last_test_at",
            "last_test_status",
            "last_test_error",
        )
        read_only_fields = (
            "id",
            "last_test_at",
            "last_test_status",
            "last_test_error",
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


class AIProviderModelWriteSerializer(serializers.Serializer):
    model_identifier = serializers.CharField(max_length=255)
    is_enabled = serializers.BooleanField(required=False, default=True)


class AIProviderModelUpdateSerializer(serializers.Serializer):
    model_identifier = serializers.CharField(max_length=255, required=False)
    is_enabled = serializers.BooleanField(required=False)


class AIProviderModelDiscoverySerializer(serializers.Serializer):
    models = serializers.ListField(child=serializers.CharField())
    supported = serializers.BooleanField()


class AIProviderModelDiscoveryRequestSerializer(serializers.Serializer):
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
        required=False,
    )
    provider_type = serializers.CharField(max_length=32, required=False)
    model_identifiers = serializers.ListField(
        child=serializers.CharField(max_length=255),
        allow_empty=False,
        required=False,
    )
    api_key = serializers.CharField(
        max_length=512, required=False, allow_blank=True, write_only=True
    )
    extra_settings = serializers.DictField(required=False)

    def validate(self, attrs):
        saved_mode = "model_ids" in attrs
        transient_mode = any(
            key in attrs
            for key in (
                "provider_type",
                "model_identifiers",
                "api_key",
                "extra_settings",
            )
        )
        if saved_mode == transient_mode:
            raise serializers.ValidationError(
                "Provide either model_ids or transient provider settings."
            )
        if saved_mode:
            if len(attrs["model_ids"]) != len(set(attrs["model_ids"])):
                raise serializers.ValidationError(
                    {"model_ids": "Model IDs must be unique."}
                )
            return attrs
        if "provider_type" not in attrs:
            raise serializers.ValidationError(
                {"provider_type": "This field is required."}
            )
        if "model_identifiers" not in attrs:
            raise serializers.ValidationError(
                {"model_identifiers": "This field is required."}
            )
        normalized_identifiers = [
            identifier.strip() for identifier in attrs["model_identifiers"]
        ]
        if len(normalized_identifiers) != len(set(normalized_identifiers)):
            raise serializers.ValidationError(
                {"model_identifiers": "Model identifiers must be unique."}
            )
        attrs["model_identifiers"] = normalized_identifiers
        return attrs


class AIProviderModelTestResultSerializer(serializers.Serializer):
    model_id = serializers.IntegerField(allow_null=True)
    model_identifier = serializers.CharField()
    status = serializers.ChoiceField(choices=AIProviderModel.TestStatus.choices)
    error = serializers.CharField(allow_blank=True)
    tested_at = serializers.DateTimeField()


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
