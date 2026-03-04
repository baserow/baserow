"""
Shared utilities for assistant evals (single-agent architecture).

These utilities are used by multiple eval test files and provide:
- LLM configuration
- UIContext building
- Callback tracking for assertions
- Assistant creation helpers
- Message history formatting for inspection
"""

import json
import os

from pydantic_ai.usage import UsageLimits

from baserow_enterprise.assistant.agents import main_agent
from baserow_enterprise.assistant.deps import AssistantDeps, ToolHelpers
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry
from baserow_enterprise.assistant.types import (
    ApplicationUIContext,
    TableUIContext,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)

# Default model for evals - can be overridden via EVAL_LLM_MODEL env var
DEFAULT_EVAL_MODEL = "groq:openai/gpt-oss-120b"


def build_database_ui_context(user, workspace, database=None, table=None) -> str:
    """
    Build a UIContext for a database, formatted as JSON string.

    This tells the agent which workspace/database/table the user is viewing.
    """
    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        database=ApplicationUIContext(id=str(database.id), name=database.name)
        if database
        else None,
        table=TableUIContext(id=table.id, name=table.name) if table else None,
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


def format_message_history(result) -> list[dict]:
    """
    Format the full message history from an agent run for inspection.

    Returns a list of dicts with structured info about each message:
    - role: system/user/assistant/tool
    - type: the pydantic-ai message class name
    - content: text content (if any)
    - tool_calls: list of tool call info (if any)
    - tool_name: name of tool that returned this result (for tool results)
    - timestamp: message timestamp (if available)
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
    )

    messages = getattr(result, "all_messages", lambda: [])() or []
    formatted = []

    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                part_type = type(part).__name__
                entry = {"role": "user", "type": part_type}

                if hasattr(part, "content"):
                    entry["content"] = part.content
                if hasattr(part, "tool_name"):
                    entry["tool_name"] = part.tool_name
                if hasattr(part, "tool_call_id"):
                    entry["tool_call_id"] = part.tool_call_id
                if hasattr(part, "timestamp"):
                    entry["timestamp"] = str(part.timestamp)

                formatted.append(entry)

        elif isinstance(msg, ModelResponse):
            for part in msg.parts:
                part_type = type(part).__name__
                entry = {"role": "assistant", "type": part_type}

                if hasattr(part, "content"):
                    entry["content"] = part.content
                if hasattr(part, "tool_name"):
                    entry["tool_name"] = part.tool_name
                if hasattr(part, "tool_call_id"):
                    entry["tool_call_id"] = part.tool_call_id
                if hasattr(part, "args"):
                    # Tool call arguments
                    args = part.args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    entry["args"] = args

                formatted.append(entry)

    return formatted


def print_message_history(result, max_content_len=1000):
    """
    Print a human-readable summary of the full message history.

    Shows all LLM requests, responses, tool calls, and tool results
    in chronological order.
    """
    history = format_message_history(result)

    print("\n" + "=" * 80)
    print("MESSAGE HISTORY")
    print("=" * 80)

    for i, entry in enumerate(history):
        role = entry["role"].upper()
        msg_type = entry.get("type", "unknown")
        print(f"\n--- [{i + 1}] {role} ({msg_type}) ---")

        if "content" in entry:
            content = str(entry["content"])
            if len(content) > max_content_len:
                content = content[:max_content_len] + "..."
            print(f"  Content: {content}")

        if "tool_name" in entry:
            print(f"  Tool: {entry['tool_name']}")

        if "args" in entry:
            args_str = json.dumps(entry["args"], indent=2, default=str)
            if len(args_str) > max_content_len:
                args_str = args_str[:max_content_len] + "..."
            print(f"  Args: {args_str}")

        if "tool_call_id" in entry:
            print(f"  Call ID: {entry['tool_call_id']}")

    print("\n" + "=" * 80)
    print(f"Total entries: {len(history)}")
    print("=" * 80 + "\n")


def print_trajectory(result, max_obs_len=500):
    """Debug helper to print the agent's trajectory."""
    print("\n=== TRAJECTORY ===")
    # pydantic-ai stores messages differently
    for i, msg in enumerate(getattr(result, "all_messages", lambda: [])() or []):
        print(f"\n--- Message {i + 1} ---")
        print(f"  {type(msg).__name__}: {str(msg)[:max_obs_len]}")
    print("\n=== END TRAJECTORY ===\n")


def get_eval_model() -> str:
    """
    Get the model string for evals.

    Configure via EVAL_LLM_MODEL environment variable.
    API keys should be set via standard env vars (OPENAI_API_KEY, GROQ_API_KEY).
    """
    return os.environ.get("EVAL_LLM_MODEL", DEFAULT_EVAL_MODEL)


class EvalToolTracker:
    """
    Placeholder for future tool-call instrumentation.

    Currently eval assertions rely on inspecting the pydantic-ai message
    history (``RetryPromptPart`` entries) rather than wrapping individual
    tools, so this class is intentionally minimal.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose


def create_eval_assistant(user, workspace, max_iters=15, model=None):
    """
    Create an assistant configured like production for evals.

    Returns (agent, deps, tracker, model, usage_limits, toolset) so tests
    can run the agent. Uses the single-agent architecture with the full
    monolithic toolset from build_assistant_toolset().

    :param model: Override the LLM model string. Falls back to
        ``get_eval_model()`` (i.e. the ``EVAL_LLM_MODEL`` env var).
    """
    from django.conf import settings

    tool_helpers = ToolHelpers(lambda x: None, lambda x: None)
    tracker = EvalToolTracker()
    model = model or get_eval_model()

    # Ensure sub-agents (e.g. formula_agent) also use the eval model.
    # get_model_string() does .replace("/", ":", 1) on the setting value,
    # so store in "/" format (e.g. "groq/openai/gpt-oss-120b").
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = model.replace(":", "/", 1)

    # Build the single-agent toolset (navigation + core + database + automation)
    toolset, tool_manifest = assistant_tool_registry.build_toolset(
        user, workspace, model
    )

    deps = AssistantDeps(
        user=user,
        workspace=workspace,
        tool_helpers=tool_helpers,
        tool_manifest=tool_manifest,
    )
    usage_limits = UsageLimits(request_limit=max_iters)

    return main_agent, deps, tracker, model, usage_limits, toolset


def assert_no_tool_errors(tracker: EvalToolTracker, result=None):
    """
    Assert no tool errors occurred during the agent run.

    Inspects the pydantic-ai message history for ``RetryPromptPart``
    entries, which indicate the LLM sent invalid arguments that failed
    pydantic validation.
    """
    from pydantic_ai.messages import ModelRequest, RetryPromptPart

    if result is not None:
        messages = getattr(result, "all_messages", lambda: [])() or []
        retry_errors = []
        for msg in messages:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, RetryPromptPart):
                        content = str(part.content)
                        # Skip "Unknown tool name" retries -- the LLM explored
                        # a tool that doesn't exist but recovered on its own.
                        if "Unknown tool name" in content:
                            continue
                        retry_errors.append(
                            {
                                "tool_name": getattr(part, "tool_name", None),
                                "content": content,
                            }
                        )
        assert not retry_errors, (
            f"Validation errors (RetryPromptPart) occurred -- the LLM sent "
            f"invalid tool arguments:\n"
            + "\n".join(f"  - {e['tool_name']}: {e['content']}" for e in retry_errors)
        )
