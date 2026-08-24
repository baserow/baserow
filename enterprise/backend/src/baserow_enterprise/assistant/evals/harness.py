"""Eval run engine: build a scenario, run ``main_agent``, execute checks.

``format_message_history``, ``get_tool_call_sequence`` and
``count_tool_errors`` are ported verbatim from the legacy pytest-only
``eval_utils.py`` so they can run outside pytest too. The legacy file keeps
its own copies for now; a later task deletes them.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from django.conf import settings

from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from baserow_enterprise.assistant.agents import main_agent
from baserow_enterprise.assistant.assistant import build_agent_run_context
from baserow_enterprise.assistant.deps import ToolHelpers
from baserow_enterprise.assistant.evals.registry import get_scenario, load_all
from baserow_enterprise.assistant.evals.scenarios import make_fixtures
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
)


@contextmanager
def override_assistant_model(model: str | Model) -> Iterator[None]:
    """Scoped replacement for the old global settings mutation (single-worker only).

    A no-op for non-string models (e.g. ``TestModel``/``FunctionModel``
    instances used in tests): there is no setting value to derive from them.
    """

    if not isinstance(model, str):
        yield
        return

    previous = settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = model.replace(":", "/", 1)
    try:
        yield
    finally:
        settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = previous


def format_message_history(result: Any) -> list[dict]:
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


def get_tool_call_sequence(result: Any) -> list[str]:
    """
    Return the ordered list of tool names called during an agent run.

    Extracts assistant-side tool call entries from the message history,
    preserving chronological order.
    """

    history = format_message_history(result)
    return [
        e["tool_name"]
        for e in history
        if e["role"] == "assistant" and "tool_name" in e and "args" in e
    ]


def count_tool_errors(result: Any) -> tuple[int, str]:
    """
    Count tool validation errors in the agent result.

    Inspects the pydantic-ai message history for ``RetryPromptPart`` entries,
    which indicate the LLM sent invalid arguments that failed pydantic
    validation.  "Unknown tool name" retries are excluded — the LLM explored a
    non-existent tool and recovered on its own, which is acceptable.

    Returns ``(error_count, hint)`` suitable for a ``CheckResult`` hint.
    """
    if result is None:
        return 0, ""

    messages = getattr(result, "all_messages", lambda: [])() or []
    retry_errors = []
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, RetryPromptPart):
                    content = str(part.content)
                    if "Unknown tool name" in content:
                        continue
                    retry_errors.append(
                        {
                            "tool_name": getattr(part, "tool_name", None),
                            "content": content,
                        }
                    )
    hint = "\n".join(f"  - {e['tool_name']}: {e['content']}" for e in retry_errors)
    return len(retry_errors), hint


def tool_called(output: EvalRunOutput, name: str) -> int:
    """Return how many times *name* was called during the run."""

    return output.tool_calls.count(name)


def tool_call_order_ok(output: EvalRunOutput, names: list[str]) -> bool:
    """Check that tools were called in the given relative order.

    For each consecutive pair (A, B) in *names*, the **last** call to A must
    come before the **first** call to B, so all A work finishes before any B
    work begins.
    """

    sequence = output.tool_calls
    for name_a, name_b in zip(names, names[1:]):
        indices_a = [i for i, n in enumerate(sequence) if n == name_a]
        indices_b = [i for i, n in enumerate(sequence) if n == name_b]
        if not indices_a or not indices_b or indices_a[-1] >= indices_b[0]:
            return False
    return True


def run_case(
    case: EvalCase, model: str | Model
) -> tuple[EvalRunOutput, list[CheckResult]]:
    """Build the scenario, run ``main_agent``, and execute the case's checks.

    Performs no teardown and no chat persistence — the eval DB is disposable.
    """

    load_all()
    scenario = get_scenario(case.scenario)(make_fixtures())
    tool_helpers = ToolHelpers(lambda x: None, lambda x: None)

    with override_assistant_model(model):
        ctx = build_agent_run_context(scenario.user, scenario.workspace, tool_helpers)
        ctx.deps.mode = case.mode
        ctx.deps.tool_helpers.request_context["ui_context"] = scenario.ui_context

        start = time.monotonic()
        result = main_agent.run_sync(
            user_prompt=case.prompt,
            deps=ctx.deps,
            model=model,
            usage_limits=UsageLimits(request_limit=case.max_iters),
            toolsets=[ctx.toolset],
        )
        duration_s = time.monotonic() - start

    tool_error_count, tool_error_hint = count_tool_errors(result)
    output = EvalRunOutput(
        answer=result.output,
        messages=format_message_history(result),
        tool_calls=get_tool_call_sequence(result),
        tool_error_count=tool_error_count,
        tool_error_hint=tool_error_hint,
        sources=list(ctx.deps.sources),
        request_count=result.usage.requests,
        duration_s=duration_s,
    )

    budget_check = CheckResult(
        name="tool_errors_within_budget",
        passed=tool_error_count <= case.max_tool_errors,
        hint=tool_error_hint,
    )
    checks = [budget_check, *case.checks(case, scenario, output)]
    return output, checks
