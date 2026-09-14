"""
One-shot Kuma calls that write or improve an agent's instructions: drafting
them from the description the user typed in the create wizard, and the
"Improve with Kuma" button next to the instructions field.
"""

from pydantic_ai import Agent

from baserow.core.generative_ai.lifecycle import run_agent_sync_with_model
from baserow.core.models import Workspace
from baserow_enterprise.assistant.model_profiles import (
    UTILITY,
    check_lm_ready_or_raise,
    resolve_assistant_model,
)

from .models import AgentDefinition
from .prompts import (
    AGENT_INSTRUCTIONS_DRAFT_PROMPT,
    AGENT_INSTRUCTIONS_IMPROVE_PROMPT,
)

# Instructions are a few paragraphs; this keeps a runaway model from tying up
# a web worker.
INSTRUCTIONS_TIMEOUT_SECONDS = 60
INSTRUCTIONS_MAX_TOKENS = 2048

draft_instructions_agent: Agent[None, str] = Agent(
    output_type=str,
    instructions=AGENT_INSTRUCTIONS_DRAFT_PROMPT,
    name="agent_instructions_draft",
)

improve_instructions_agent: Agent[None, str] = Agent(
    output_type=str,
    instructions=AGENT_INSTRUCTIONS_IMPROVE_PROMPT,
    name="agent_instructions_improve",
)


def _run(agent: Agent, prompt: str, workspace: Workspace) -> str:
    model_profile = resolve_assistant_model(workspace=workspace)
    check_lm_ready_or_raise(model_profile=model_profile)
    settings = {
        **model_profile.get_settings(UTILITY),
        "timeout": INSTRUCTIONS_TIMEOUT_SECONDS,
        "max_tokens": INSTRUCTIONS_MAX_TOKENS,
    }
    result = run_agent_sync_with_model(
        agent, prompt, model=model_profile.create_model(), model_settings=settings
    )
    return result.output.strip()


def draft_instructions(workspace: Workspace, name: str, description: str) -> str:
    prompt = (
        f'Workspace: "{workspace.name}"\n'
        f'Agent name: "{name}"\n\n'
        f"What the agent should do, in the user's words:\n{description}"
    )
    return _run(draft_instructions_agent, prompt, workspace)


def improve_instructions(
    workspace: Workspace, agent: AgentDefinition, instructions: str
) -> str:
    prompt = (
        f'Workspace: "{workspace.name}"\n'
        f'Agent name: "{agent.name}"\n\n'
        f"Current instructions:\n{instructions}"
    )
    return _run(improve_instructions_agent, prompt, workspace)
