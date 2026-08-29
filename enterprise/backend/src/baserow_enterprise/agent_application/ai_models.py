from dataclasses import dataclass
from typing import Any

from baserow.core.generative_ai.exceptions import GenerativeAITypeDoesNotExist
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow_enterprise.assistant.retrying_model import RetryingModel

from .exceptions import AgentModelNotConfigured
from .models import AgentDefinition


@dataclass(frozen=True)
class AgentModelProfile:
    """
    Satisfies the assistant's model profile contract with the agent's own
    configured model, so the sub agents that reused assistant tools spin up
    (formula generation, sample rows, the tool argument fixer) run on the
    model and credentials the user picked for this agent instead of the
    workspace's Kuma model.
    """

    model: RetryingModel
    model_settings: dict[str, Any]

    def create_model(self) -> RetryingModel:
        return self.model

    def get_settings(self, role: str) -> dict[str, Any]:
        # The agent has one user-configured temperature for every role, and
        # callers merge extra keys into what they get back.
        return dict(self.model_settings)


def resolve_agent_model(agent: AgentDefinition) -> tuple[RetryingModel, dict[str, Any]]:
    """
    Resolves the agent's configured model through the reusable generative AI
    provider system, so agent runs use the same workspace/instance level API
    keys as the AI field and AI automation node.

    :param agent: The agent to resolve the model for.
    :raises AgentModelNotConfigured: When no usable model is configured.
    :return: A pydantic-ai model wrapped for transient-error retries, and the
        model settings dict for the run.
    """

    workspace = agent.application.workspace
    ai_type = agent.ai_generative_ai_type
    model_name = agent.ai_generative_ai_model

    if not ai_type or not model_name:
        raise AgentModelNotConfigured(
            f"The agent {agent.id} has no generative AI model configured."
        )

    try:
        model_type = generative_ai_model_type_registry.get(ai_type)
    except GenerativeAITypeDoesNotExist as exc:
        raise AgentModelNotConfigured(
            f"The generative AI type {ai_type} does not exist."
        ) from exc

    settings_override = model_type.get_model_settings_override(model_name, workspace)

    if model_name not in model_type.get_enabled_models(workspace, settings_override):
        raise AgentModelNotConfigured(
            f"The model {model_name} is not enabled for workspace {workspace.id}."
        )

    model = model_type.get_ai_model(model_name, workspace, settings_override)
    model_settings = model_type._prepare_model_settings(agent.ai_temperature)

    return RetryingModel(model), model_settings
