from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.utils import extract_allowed

from .models import AgentApplication
from .types import AgentConfiguration, AgentConfigurationUpdated
from .validators import validate_configuration_values


class AgentHandler:
    configuration_fields = [
        "name",
        "instructions",
        "provider_type",
        "model_identifier",
    ]

    def get_agent(self, agent_id: int, for_update: bool = False) -> AgentApplication:
        """Fetch a live Agent subtype, optionally locking its configuration rows."""

        queryset = AgentApplication.objects.filter(workspace__isnull=False)
        if for_update:
            # The parent row holds the name, which configuration updates also write.
            queryset = queryset.select_for_update(of=("self", "application_ptr"))
        return CoreHandler().get_application(agent_id, base_queryset=queryset)

    def get_configuration(self, agent: AgentApplication) -> AgentConfiguration:
        """Resolve draft completeness and current eligible models without execution."""

        errors = {}
        for field in self.configuration_fields:
            if not (getattr(agent, field) or "").strip():
                errors[field] = "required"

        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            agent.workspace, feature_type=AI_PROVIDER_FEATURE_AI_AGENT
        )
        if agent.provider_type:
            if agent.provider_type not in models:
                errors["provider_type"] = "unavailable"
            if agent.model_identifier and agent.model_identifier not in models.get(
                agent.provider_type, []
            ):
                errors["model_identifier"] = "unavailable"

        if "required" in errors.values():
            state = "incomplete"
        elif errors:
            state = "unavailable"
        else:
            state = "ready"
        return {
            **{field: getattr(agent, field) for field in self.configuration_fields},
            "state": state,
            "errors": errors,
        }

    def update_configuration(
        self, agent: AgentApplication, **values
    ) -> AgentConfigurationUpdated:
        """Persist a partial static draft and identify its changed field names."""

        values = extract_allowed(values, self.configuration_fields)
        validate_configuration_values(values)
        changed_fields = []
        for field, value in values.items():
            if field in ("provider_type", "model_identifier"):
                value = (value or "").strip() or None
            if getattr(agent, field) != value:
                setattr(agent, field, value)
                changed_fields.append(field)
        if changed_fields:
            agent.save(update_fields=[*changed_fields, "updated_on"])
        return AgentConfigurationUpdated(agent, changed_fields)
