from typing import Any, Dict, Generator, List, Optional

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.integrations.ai.integration_types import AIIntegrationType
from baserow.contrib.integrations.ai.models import AIAgentService, AIOutputType
from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_AI_AGENT,
    AI_PROVIDER_TYPES,
)
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.validator import ensure_string
from baserow.core.generative_ai.exceptions import (
    GenerativeAIPromptError,
    GenerativeAITypeDoesNotExist,
)
from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    generative_ai_model_type_registry,
)
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.models import Workspace
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

    @staticmethod
    def _resolve_available_models_and_settings_override(
        ai_model_type: GenerativeAIModelType,
        workspace: Workspace | None,
        integration_settings: dict[str, Any] | None,
    ) -> tuple[list[str], dict[str, Any] | None]:
        """Resolve one integration override without mixing configuration scopes.

        A self-contained override owns its connection and any explicit model
        list. Built-in overrides without a model list inherit the active
        allowlist. An incomplete connection can only narrow inherited models;
        its other fields are ignored so it never borrows credentials.

        :param ai_model_type: The registered provider resolving the model list.
        :param workspace: The owning workspace, or None if unavailable.
        :param integration_settings: The explicit provider override, or None when
            the integration inherits all settings.
        :returns: The selectable model identifiers and the complete connection
            override to pass to the provider, or None to inherit its connection.
        """

        atomic_settings = (
            ai_model_type.get_atomic_settings_override(integration_settings)
            if integration_settings is not None
            else None
        )
        if atomic_settings is not None and (
            ai_model_type.type not in AI_PROVIDER_TYPES
            or "models" in integration_settings
        ):
            available_models = ai_model_type.get_enabled_models_for_feature(
                AI_PROVIDER_FEATURE_AI_AGENT,
                workspace=workspace,
                settings_override=atomic_settings,
            )
            return available_models, atomic_settings

        available_models = ai_model_type.get_enabled_models_for_feature(
            AI_PROVIDER_FEATURE_AI_AGENT,
            workspace=workspace,
        )

        if atomic_settings is not None:
            # Legacy callers may override only their connection. Preserve the
            # omitted model list's inheritance without inheriting credentials or
            # optional connection settings. An explicit empty list stays empty.
            return available_models, {**atomic_settings, "models": available_models}

        if integration_settings is not None and "models" in integration_settings:
            model_limit = integration_settings["models"]
            if not isinstance(model_limit, list):
                return [], None
            inherited_models = set(available_models)
            available_models = [
                model for model in model_limit if model in inherited_models
            ]

        return available_models, None

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[AIAgentService] = None,
    ) -> Dict[str, Any]:
        """
        Validate the effective provider selection before creating or updating.

        An unchanged selection is retained even when its model becomes unavailable.
        Dispatch still checks availability. An unavailable integration skips the
        model check. The base type preserves trashed references for undo/redo but
        rejects missing IDs; dispatch blocks trashed integrations until restored.

        :param values: The service values supplied for creation or a partial update.
        :param user: The user creating or updating the service.
        :param instance: The current service when updating, or None when creating.
        :returns: The prepared values, with any integration ID resolved by the
            base service type.
        :raises DRFValidationError: If the selection being validated names an
            unknown provider, an unavailable model, or an invalid integration.
        """

        ai_type = values.get("ai_generative_ai_type") or (
            instance.ai_generative_ai_type if instance else None
        )
        ai_model = values.get("ai_generative_ai_model") or (
            instance.ai_generative_ai_model if instance else None
        )
        integration_id = values.get("integration_id") or (
            instance.integration_id if instance else None
        )
        selection_changed = instance is None or (
            ai_type != instance.ai_generative_ai_type
            or ai_model != instance.ai_generative_ai_model
            or integration_id != instance.integration_id
        )

        if ai_type and selection_changed:
            try:
                ai_model_type = generative_ai_model_type_registry.get(ai_type)
            except GenerativeAITypeDoesNotExist as e:
                raise DRFValidationError(
                    {"ai_generative_ai_type": f"AI type '{ai_type}' does not exist."}
                ) from e

            if integration_id and ai_model:
                try:
                    integration = (
                        IntegrationHandler().get_integration(integration_id).specific
                    )
                except IntegrationDoesNotExist:
                    # Preserve trashed references for undo/redo. The base type
                    # rejects missing IDs; dispatch blocks trashed integrations.
                    return super().prepare_values(values, user, instance)

                integration_type = AIIntegrationType()
                integration_settings = (
                    integration_type.get_integration_provider_settings(
                        integration, ai_type
                    )
                )
                available_models, _ = (
                    self._resolve_available_models_and_settings_override(
                        ai_model_type,
                        integration.application.workspace,
                        integration_settings,
                    )
                )
                if ai_model not in available_models:
                    raise DRFValidationError(
                        {
                            "ai_generative_ai_model": f"Model '{ai_model}' is not "
                            f"available for provider '{ai_type}'."
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
        """
        Resolve the current provider configuration and execute the AI prompt.

        Published applications recover their owning workspace from the dispatch
        context. Model eligibility is rechecked so changes made after saving the
        service take effect before a provider receives the prompt.

        :param service: The AI Agent service to execute.
        :param resolved_values: Formula results, including the resolved AI prompt.
        :param dispatch_context: The current Builder or Automation execution context.
        :returns: The provider response under the result key.
        :raises ServiceImproperlyConfiguredDispatchException: If required input,
            workspace context, provider registration, or model availability is
            missing, or choice output has no non-empty options.
        :raises UnexpectedDispatchException: If the provider raises a prompt error.
        """

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

        try:
            ai_model_type = generative_ai_model_type_registry.get(
                service.ai_generative_ai_type
            )
        except GenerativeAITypeDoesNotExist as exc:
            raise ServiceImproperlyConfiguredDispatchException(
                f"AI provider type '{service.ai_generative_ai_type}' is unavailable."
            ) from exc
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

        integration_settings = integration_type.get_integration_provider_settings(
            integration, service.ai_generative_ai_type
        )
        available_models, settings_override = (
            self._resolve_available_models_and_settings_override(
                ai_model_type,
                workspace,
                integration_settings,
            )
        )
        if settings_override is None and workspace is None:
            raise ServiceImproperlyConfiguredDispatchException(
                "The workspace context for the AI integration is missing."
            )
        if service.ai_generative_ai_model not in available_models:
            raise ServiceImproperlyConfiguredDispatchException(
                f"Model '{service.ai_generative_ai_model}' is not available "
                f"for provider '{service.ai_generative_ai_type}'."
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
