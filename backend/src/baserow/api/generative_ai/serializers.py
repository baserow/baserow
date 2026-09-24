from urllib.parse import urlsplit

from rest_framework import serializers


class GenerativeAIModelsSerializer(serializers.Serializer):
    models = serializers.ListField(
        required=False,
        child=serializers.CharField(),
        help_text="The models that are enabled for this AI type.",
    )


class BaseOpenAISettingsSerializer(GenerativeAIModelsSerializer):
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


class OpenAISettingsSerializer(BaseOpenAISettingsSerializer):
    base_url = serializers.URLField(
        allow_blank=True,
        required=False,
        help_text="https://api.openai.com/v1 by default, but can be changed to "
        "https://eu.api.openai.com/v1, https://<your-resource-name>.openai.azure.com,"
        "or any other OpenAI compatible API.",
    )


class AnthropicSettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The Anthropic API key that is used to authenticate with the "
        "Anthropic API.",
    )


class GoogleSettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The Google AI Studio API key used to authenticate with Gemini.",
    )


class GroqSettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The Groq API key used to authenticate with the Groq API.",
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

    def validate_host(self, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.netloc
            or parsed.hostname is None
        ):
            raise serializers.ValidationError(
                "Enter a valid URL starting with http:// or https://."
            )
        return value.rstrip("/")


class OpenRouterSettingsSerializer(BaseOpenAISettingsSerializer):
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
