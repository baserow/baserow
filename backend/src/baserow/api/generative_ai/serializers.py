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


class BedrockSettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.RegexField(
        r"\A\S+\Z",
        allow_blank=True,
        required=False,
        help_text="A Bedrock API key, or the secret access key of `access_key_id`.",
    )
    region = serializers.RegexField(
        r"\A[a-z]{2,4}(-[a-z]+)+-\d{1,2}\Z",
        max_length=32,
        allow_blank=True,
        required=False,
        help_text="The AWS region of the Bedrock runtime, for example eu-central-1.",
    )
    access_key_id = serializers.RegexField(
        r"\A\w{16,128}\Z",
        allow_blank=True,
        required=False,
        help_text="The IAM access key ID. Leave empty to use a Bedrock API key.",
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


class XaiSettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The xAI API key used to authenticate with the xAI API.",
    )


class ZaiSettingsSerializer(GenerativeAIModelsSerializer):
    api_key = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text="The Z.ai API key used to authenticate with the Z.ai API.",
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
        error_message = "Enter a valid URL starting with http:// or https://."
        try:
            parsed = urlsplit(value)
        except ValueError as exc:
            raise serializers.ValidationError(error_message) from exc
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.netloc
            or parsed.hostname is None
        ):
            raise serializers.ValidationError(error_message)
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
