from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.usage import UsageLimits

from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterOperation,
    FilterState,
    FilterValidationContext,
    ServiceFilterValidationError,
    apply_operations,
)
from baserow.core.generative_ai.lifecycle import run_agent_sync_with_model
from baserow_enterprise.assistant.types import BaseModel

from .prompts import SERVICE_FILTER_AGENT_INSTRUCTIONS

if TYPE_CHECKING:
    from baserow_enterprise.assistant.model_profiles import (
        ResolvedAssistantModelProfile,
    )

# Each rejected answer costs a retry, so allow a few rounds of feedback.
SERVICE_FILTER_AGENT_RETRIES = 3
SERVICE_FILTER_AGENT_REQUEST_LIMIT = 8
SERVICE_FILTER_AGENT_TIMEOUT_SECONDS = 90


class ServiceFilterChanges(BaseModel):
    """The agent's answer to a filter request."""

    operations: list[FilterOperation] = Field(
        description=(
            "The changes to apply, in order. Empty when the request can't be done, "
            "or when the filters already match it."
        )
    )
    summary: str = Field(
        description=(
            "One short sentence for the user describing what changed, or why "
            "nothing changed. Written in the language of the request."
        )
    )


@dataclass
class ServiceFilterAgentDeps:
    state: FilterState
    validation: FilterValidationContext


service_filter_agent: Agent[ServiceFilterAgentDeps, ServiceFilterChanges] = Agent(
    deps_type=ServiceFilterAgentDeps,
    output_type=ServiceFilterChanges,
    instructions=SERVICE_FILTER_AGENT_INSTRUCTIONS,
    name="service_filter_agent",
    retries=SERVICE_FILTER_AGENT_RETRIES,
)


@service_filter_agent.output_validator
def _changes_must_apply(
    ctx: RunContext[ServiceFilterAgentDeps], output: ServiceFilterChanges
) -> ServiceFilterChanges:
    """
    Sends the answer back when its operations don't apply cleanly, with every
    problem found so the agent can fix them in one go.

    :param ctx: The agent run context.
    :param output: The candidate changes.
    :raises ModelRetry: When the changes are invalid.
    :return: The changes unchanged when they are valid.
    """

    try:
        apply_operations(ctx.deps.state, output.operations, ctx.deps.validation)
    except ServiceFilterValidationError as exc:
        problems = "\n".join(f"- {error}" for error in exc.errors)
        raise ModelRetry(
            f"These changes can't be applied. Fix them and answer again:\n{problems}"
        ) from exc
    return output


def run_service_filter_agent(
    prompt: str,
    deps: ServiceFilterAgentDeps,
    model_profile: "ResolvedAssistantModelProfile",
) -> ServiceFilterChanges:
    """
    Asks the model for the filter changes matching the request in the prompt.

    :param prompt: The formatted prompt.
    :param deps: The current state and the validation context.
    :param model_profile: The Kuma model profile to run on.
    :return: The validated changes.
    """

    from baserow_enterprise.assistant.model_profiles import UTILITY

    result = run_agent_sync_with_model(
        service_filter_agent,
        prompt,
        model=model_profile.create_model(),
        model_settings=model_profile.get_settings(UTILITY),
        deps=deps,
        usage_limits=UsageLimits(request_limit=SERVICE_FILTER_AGENT_REQUEST_LIMIT),
        timeout_seconds=SERVICE_FILTER_AGENT_TIMEOUT_SECONDS,
    )
    return result.output
