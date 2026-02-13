import enum
from typing import Any, Dict, Generator, List, Optional

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.integrations.ai.integration_types import AIIntegrationType
from baserow.contrib.integrations.ai.models import AIAgentService, AIOutputType
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.validator import ensure_string
from baserow.core.generative_ai.exceptions import (
    GenerativeAIPromptError,
    GenerativeAITypeDoesNotExist,
)
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.output_parsers import get_strict_enum_output_parser
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict


class AIAgentServiceType(ServiceType):
    type = "ai_agent"
    model_class = AIAgentService
    integration_type = AIIntegrationType.type
    dispatch_types = [DispatchTypes.ACTION]
    returns_list = False

    allowed_fields = [
        "integration_id",
        "ai_generative_ai_type",
        "ai_generative_ai_model",
        "ai_output_type",
        "ai_temperature",
        "ai_prompt",
        "ai_choices",
    ]

    serializer_field_names = [
        "integration_id",
        "ai_generative_ai_type",
        "ai_generative_ai_model",
        "ai_output_type",
        "ai_temperature",
        "ai_prompt",
        "ai_choices",
    ]

    serializer_field_overrides = {
        "integration_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The ID of the AI integration to use for this service.",
        ),
        "ai_generative_ai_type": serializers.CharField(
            required=False,
            allow_null=True,
            allow_blank=True,
            help_text="The generative AI provider type (e.g., 'openai', 'anthropic').",
        ),
        "ai_generative_ai_model": serializers.CharField(
            required=False,
            allow_null=True,
            allow_blank=True,
            help_text="The specific AI model to use (e.g., 'gpt-4', 'claude-3-opus').",
        ),
        "ai_output_type": serializers.ChoiceField(
            required=False,
            choices=AIOutputType.choices,
            default=AIOutputType.TEXT,
            help_text="The output type: 'text' for raw text, 'choice' for constrained "
            "selection.",
        ),
        "ai_temperature": serializers.FloatField(
            required=False,
            allow_null=True,
            min_value=0,
            max_value=2,
            help_text="Temperature for response randomness (0-2). Lower is more "
            "focused.",
        ),
        "ai_prompt": FormulaSerializerField(
            help_text="The prompt to send to the AI model. Can be a formula.",
        ),
        "ai_choices": serializers.ListField(
            child=serializers.CharField(allow_blank=True),
            required=False,
            default=list,
            help_text="List of choice options for 'choice' output type.",
        ),
    }

    simple_formula_fields = ["ai_prompt"]

    class SerializedDict(ServiceDict):
        integration_id: int
        ai_generative_ai_type: str
        ai_generative_ai_model: str
        ai_output_type: str
        ai_temperature: Optional[float]
        ai_prompt: str
        ai_choices: List[str]

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[AIAgentService] = None,
    ) -> Dict[str, Any]:
        ai_type = values.get("ai_generative_ai_type") or (
            instance.ai_generative_ai_type if instance else None
        )
        ai_model = values.get("ai_generative_ai_model") or (
            instance.ai_generative_ai_model if instance else None
        )

        if ai_type:
            try:
                generative_ai_model_type_registry.get(ai_type)
            except GenerativeAITypeDoesNotExist as e:
                raise DRFValidationError(
                    {"ai_generative_ai_type": f"AI type '{ai_type}' does not exist."}
                ) from e

            # Get the integration to check available models
            integration_id = values.get("integration_id") or (
                instance.integration_id if instance else None
            )
            if integration_id and ai_model:
                integration = (
                    IntegrationHandler().get_integration(integration_id).specific
                )
                integration_type = AIIntegrationType()
                provider_settings = integration_type.get_provider_settings(
                    integration, ai_type
                )
                available_models = provider_settings.get("models", [])

                if available_models and ai_model not in available_models:
                    raise DRFValidationError(
                        {
                            "ai_generative_ai_model": f"Model '{ai_model}' is not available for provider '{ai_type}'."
                        }
                    )

        return super().prepare_values(values, user, instance)

    def formulas_to_resolve(
        self, service: AIAgentService
    ) -> Generator[FormulaToResolve, None, None]:
        yield FormulaToResolve(
            "ai_prompt",
            service.ai_prompt,
            ensure_string,
            'property "ai_prompt"',
        )

    def dispatch_data(
        self,
        service: AIAgentService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        from langchain_core.exceptions import OutputParserException
        from langchain_core.prompts import PromptTemplate

        if not service.ai_generative_ai_type:
            raise ServiceImproperlyConfiguredDispatchException(
                "The AI provider type is missing."
            )

        if not service.ai_generative_ai_model:
            raise ServiceImproperlyConfiguredDispatchException(
                "The AI model is missing."
            )

        # Check if prompt formula is set (FormulaField returns empty string when not
        # set)
        prompt = resolved_values.get("ai_prompt", "")

        if not prompt:
            raise ServiceImproperlyConfiguredDispatchException("The prompt is missing.")

        if service.ai_output_type == AIOutputType.CHOICE:
            if not service.ai_choices or len(service.ai_choices) == 0:
                raise ServiceImproperlyConfiguredDispatchException(
                    "At least one choice is required when output type is 'choice'."
                )
            # At least one option must be set, otherwise we can't force the LLM to give
            # one of the answers.
            if not any(choice and choice.strip() for choice in service.ai_choices):
                raise ServiceImproperlyConfiguredDispatchException(
                    "At least one non-empty choice is required when output type is 'choice'."
                )

        ai_model_type = generative_ai_model_type_registry.get(
            service.ai_generative_ai_type
        )
        workspace = service.integration.application.workspace
        integration = service.integration.specific
        integration_type = AIIntegrationType()

        # Always get provider settings (which handles fallback to workspace settings).
        # This ensures that published workflows can access settings correctly.
        provider_settings = integration_type.get_provider_settings(
            integration, service.ai_generative_ai_type
        )

        output_parser = None

        # If the choice output type has been set, then a different prompt and output
        # parser must be used to make sure the result matches the requirements of the
        # choice type.
        if service.ai_output_type == AIOutputType.CHOICE:
            choices = service.ai_choices or []

            if not choices:
                raise ServiceImproperlyConfiguredDispatchException(
                    "No valid choices provided for 'choice' output type."
                )

            choices_enum = enum.Enum(
                "Choices", {f"OPTION_{i}": choice for i, choice in enumerate(choices)}
            )
            output_parser = get_strict_enum_output_parser(enum=choices_enum)
            format_instructions = output_parser.get_format_instructions()
            prompt_template = PromptTemplate(
                template=prompt + "\n\nGiven this user query:\n\n{format_instructions}",
                input_variables=[],
                partial_variables={"format_instructions": format_instructions},
            )
            prompt = prompt_template.format()

        try:
            kwargs = {}
            if service.ai_temperature is not None:
                kwargs["temperature"] = service.ai_temperature

            # Always pass provider settings (which may be from integration or workspace)
            if provider_settings:
                kwargs["settings_override"] = provider_settings

            result = ai_model_type.prompt(
                model=service.ai_generative_ai_model,
                prompt=prompt,
                workspace=workspace,
                **kwargs,
            )
        except GenerativeAIPromptError as e:
            raise UnexpectedDispatchException(
                f"AI prompt execution failed: {str(e)}"
            ) from e

        # Parse the result for choice output type
        if service.ai_output_type == AIOutputType.CHOICE and output_parser:
            try:
                parsed_result = output_parser.parse(result)
                result = parsed_result.value
            except OutputParserException:
                # If parsing fails, return the raw result
                pass

        return {"result": result}

    def dispatch_transform(self, data: Dict[str, Any]) -> DispatchResult:
        return DispatchResult(data=data)

    def generate_schema(
        self, service: AIAgentService, allowed_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate JSON schema for the service output.
        """

        return {
            "type": "object",
            "title": self.get_schema_name(service),
            "properties": {
                "result": {
                    "type": "string",
                    "title": "AI Response",
                }
            },
        }
