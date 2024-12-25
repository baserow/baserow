from rest_framework import serializers


class GenerativeAIModelsSerializer(serializers.Serializer):
    models = serializers.ListField(
        required=False,
        child=serializers.CharField(),
        help_text="The models that are enabled for this AI type.",
    )


class OpenAISettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The OpenAI API key that is used to authenticate with the OpenAI API.",
    )
    organization = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The organization that the OpenAI API key belongs to.",
    )


class AnthropicSettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The Anthropic API key that is used to authenticate with the "
        "Anthropic API.",
    )


class MistralSettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The Mistral API key that is used to authenticate with the Mistral "
        "API.",
    )


class OllamaSettingsSerializer(GenerativeAIModelsSerializer):
    host = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The host that is used to authenticate with the Ollama API.",
    )


class OpenRouterSettingsSerializer(OpenAISettingsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The OpenRouter API key that is used to authenticate with the OpenAI "
        "API.",
    )
    organization = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The organization that the OpenRouter API key belongs to.",
    )
