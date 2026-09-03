from typing import Any, Dict, Generator, List, Optional

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.integrations.ai.integration_types import AIIntegrationType
from baserow.contrib.integrations.ai.models import AIAgentService, AIOutputType
from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.validator import ensure_string
from baserow.core.generative_ai.exceptions import (
    GenerativeAIPromptError,
    GenerativeAITypeDoesNotExist,
)
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.integrations.handler import IntegrationHandler
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

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        *args,
        **kwargs,
    ) -> AIAgentService:
        # The app might have been exported from another instance (e.g. Baserow
        # SaaS), where a generative AI model type can exist that isn't registered
        # here. In that case there's nothing valid to use, so clear the provider
        # and model rather than importing a dangling reference.
        ai_type = serialized_values.get("ai_generative_ai_type")
        if ai_type:
            try:
                generative_ai_model_type_registry.get(ai_type)
            except GenerativeAITypeDoesNotExist:
                serialized_values["ai_generative_ai_type"] = None
                serialized_values["ai_generative_ai_model"] = None

        return super().import_serialized(
            parent, serialized_values, id_mapping, *args, **kwargs
        )

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
                ai_model_type = generative_ai_model_type_registry.get(ai_type)
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
                available_models = ai_model_type.call_get_enabled_models(
                    workspace=integration.application.workspace,
                    settings_override=provider_settings or None,
                )

                if ai_model not in available_models:
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
        integration = service.integration.specific
        integration_type = AIIntegrationType()
        workspace = integration.application.workspace

        # Published applications have no direct workspace. Their dispatch contexts
        # retain a path to the original Builder or Automation workspace.
        if workspace is None:
            page = getattr(dispatch_context, "page", None)
            if page is not None:
                workspace = page.builder.get_workspace()
            else:
                workflow = getattr(dispatch_context, "workflow", None)
                if workflow is not None:
                    workspace = workflow.get_original().automation.workspace

        # This returns explicit integration settings, or the legacy workspace fallback
        # while database-backed providers are disabled.
        provider_settings = integration_type.get_provider_settings(
            integration, service.ai_generative_ai_type
        )
        settings_override = provider_settings or None

        providers_enabled = feature_flag_is_enabled(FF_AI_PROVIDERS)
        if providers_enabled:
            if settings_override is None and workspace is None:
                raise ServiceImproperlyConfiguredDispatchException(
                    "The workspace context for the AI integration is missing."
                )
            available_models = ai_model_type.call_get_enabled_models(
                workspace=workspace,
                settings_override=settings_override,
            )
            if service.ai_generative_ai_model not in available_models:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The AI model '{service.ai_generative_ai_model}' is not "
                    f"available for provider '{service.ai_generative_ai_type}'."
                )

        kwargs = {}
        if service.ai_temperature is not None:
            kwargs["temperature"] = service.ai_temperature

        if settings_override is not None:
            kwargs["settings_override"] = settings_override

        try:
            if service.ai_output_type == AIOutputType.CHOICE:
                choices = service.ai_choices or []

                if not choices:
                    raise ServiceImproperlyConfiguredDispatchException(
                        "No valid choices provided for 'choice' output type."
                    )

                kwargs["output_type"] = choices

            result = ai_model_type.prompt(
                model=service.ai_generative_ai_model,
                prompt=prompt,
                workspace=workspace,
                **kwargs,
            )
            return {"result": result}
        except GenerativeAIPromptError as e:
            raise UnexpectedDispatchException(
                f"AI prompt execution failed: {str(e)}"
            ) from e

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
