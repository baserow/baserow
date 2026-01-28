"""
Shared utilities for builder assistant evals.

These utilities are used by multiple eval test files and provide:
- LLM configuration
- UIContext building
- Callback tracking for assertions
- Assistant creation helpers
"""

import json
import os

import udspy

from baserow_enterprise.assistant.assistant import AssistantCallbacks, ToolHelpers
from baserow_enterprise.assistant.signatures import ChatSignature
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry
from baserow_enterprise.assistant.types import (
    ApplicationUIContext,
    PageUIContext,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)

# Default model for evals - can be overridden via EVAL_LLM_MODEL env var
DEFAULT_EVAL_MODEL = "groq/openai/gpt-oss-120b"


def build_builder_ui_context(user, workspace, builder, page) -> str:
    """
    Build a UIContext for a builder page, formatted as JSON string.

    This tells the agent what workspace/app/page the user is currently viewing.
    """
    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        application=ApplicationUIContext(id=str(builder.id), name=builder.name),
        page=PageUIContext(id=str(page.id), name=page.name),
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


def print_trajectory(result, max_obs_len=500):
    """Debug helper to print the agent's trajectory."""
    print("\n=== TRAJECTORY ===")
    for i, episode in enumerate(getattr(result, "trajectory", [])):
        print(f"\n--- Step {i + 1} ---")
        if "tool_name" in episode:
            print(f"Tool: {episode['tool_name']}")
        if "tool_args" in episode:
            print(f"Args: {episode['tool_args']}")
        if "observation" in episode:
            obs = episode["observation"]
            if len(obs) > max_obs_len:
                obs = obs[:max_obs_len] + "..."
            print(f"Observation: {obs}")
        if "next_thought" in episode:
            print(f"Thought: {episode['next_thought']}")
    print("\n=== END TRAJECTORY ===\n")


def get_eval_lm():
    """
    Get the LM client for evals.

    Configure via EVAL_LLM_MODEL environment variable.
    API keys should be set via standard env vars (OPENAI_API_KEY, GROQ_API_KEY).
    """
    model = os.environ.get("EVAL_LLM_MODEL", DEFAULT_EVAL_MODEL)
    return udspy.LM(model=model)


class EvalCallbacks(AssistantCallbacks):
    """
    Extended callbacks that track tool calls and errors for eval assertions.

    Logs tool calls to console for visibility when running tests individually.
    """

    def __init__(self, tool_helpers: ToolHelpers | None = None, verbose: bool = True):
        super().__init__(tool_helpers)
        self.tool_errors: list[tuple[str, Exception]] = []
        self.tool_call_counts: dict[str, int] = {}
        self.verbose = verbose

    def on_tool_start(self, call_id, instance, inputs):
        super().on_tool_start(call_id, instance, inputs)
        tool_name = instance.name
        self.tool_call_counts[tool_name] = self.tool_call_counts.get(tool_name, 0) + 1

        if self.verbose:
            print(f"\n→ {tool_name}")
            inputs_str = json.dumps(inputs, indent=2, default=str)
            if len(inputs_str) > 500:
                inputs_str = inputs_str[:500] + "..."
            print(f"  {inputs_str}")

    def on_tool_end(self, call_id, outputs, exception=None):
        instance, inputs = self.tool_calls[call_id]
        super().on_tool_end(call_id, outputs, exception)
        if exception is not None:
            self.tool_errors.append((instance.name, inputs, exception))
            if self.verbose:
                print(f"  ✗ Error: {exception}")
        elif self.verbose:
            outputs_str = str(outputs)
            if len(outputs_str) > 200:
                outputs_str = outputs_str[:200] + "..."
            print(f"  ✓ {outputs_str}")

    def get_tool_call_count(self, tool_name: str) -> int:
        """Get the number of times a tool was called."""
        return self.tool_call_counts.get(tool_name, 0)


def create_eval_assistant(user, workspace, max_iters=15):
    """
    Create a ReAct assistant configured like production for evals.

    Returns (react, callbacks, lm) so tests can use them with udspy.settings.context().
    """
    tool_helpers = ToolHelpers(lambda x: None, lambda x: None)

    tools = [
        udspy.Tool(t) if not isinstance(t, udspy.Tool) else t
        for t in assistant_tool_registry.list_all_usable_tools(
            user, workspace, tool_helpers
        )
    ]

    callbacks = EvalCallbacks(tool_helpers)
    lm = get_eval_lm()

    # Production uses temperature=0.3, response_format=json_object, max_iters=20
    # For evals we use lower max_iters but same other settings
    module_kwargs = {
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    react = udspy.ReAct(
        ChatSignature,
        tools=tools,
        max_iters=max_iters,
        **module_kwargs,
    )

    return react, callbacks, lm


def assert_no_tool_errors(callbacks: EvalCallbacks, result):
    """
    Assert no tool errors occurred during the agent run.

    Checks both:
    1. The callbacks.tool_errors list (exceptions caught by AssistantCallbacks)
    2. The trajectory observations (for errors that slipped through)
    """
    # Check callback-tracked errors
    assert not callbacks.tool_errors, (
        f"Tool errors occurred: {[(name, inputs, str(e)) for name, inputs, e in callbacks.tool_errors]}"
    )

    # Also check trajectory for any Traceback strings (belt and suspenders)
    for episode in getattr(result, "trajectory", []):
        observation = episode.get("observation", "")
        assert "Traceback" not in observation, (
            f"Tool error in trajectory: {observation[:500]}"
        )
