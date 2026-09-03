"""Eval run engine: build a scenario, run ``main_agent``, execute checks."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from types import ModuleType
from typing import Any

from django.conf import settings

from pydantic_ai import Agent
from pydantic_ai._utils import run_until_complete  # noqa: PLC2701
from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart
from pydantic_ai.models import Model
from pydantic_ai.tool_manager import ToolManager
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
from baserow_enterprise.assistant.model_profiles import (
    ORCHESTRATOR,
    get_model_settings,
)
from baserow_enterprise.assistant.onboarding import onboarding_suggestions_agent
from baserow_enterprise.assistant.tools.automation import agents as automation_agents
from baserow_enterprise.assistant.tools.builder import agents as builder_agents
from baserow_enterprise.assistant.tools.database import agents as database_agents
from baserow_enterprise.assistant.tools.database.agents import formula_generation_agent
from baserow_enterprise.assistant.tools.search_user_docs.tools import search_docs_agent

# Prompts bound into Agent singletons at import time: swapped via Agent.override.
PROMPT_AGENT_TARGETS: dict[str, Agent] = {
    "kuma-system-prompt": main_agent,
    "kuma-database-formula-agent": formula_generation_agent,
    "kuma-search-docs-agent": search_docs_agent,
    "kuma-onboarding-suggestions-agent": onboarding_suggestions_agent,
}

# Prompts read from their consumer module at call time: swapped by attribute patch.
PROMPT_ATTR_TARGETS: dict[str, tuple[ModuleType, str]] = {
    "kuma-database-sample-rows-agent": (
        database_agents,
        "SAMPLE_ROW_AGENT_INSTRUCTIONS",
    ),
    "kuma-builder-formula-agent": (builder_agents, "BUILDER_FORMULA_PROMPT"),
    "kuma-automation-formula-agent": (automation_agents, "GENERATE_FORMULA_PROMPT"),
}


@contextmanager
def _patched_module_attr(module: ModuleType, attr: str, value: str) -> Iterator[None]:
    previous = getattr(module, attr)
    setattr(module, attr, value)
    try:
        yield
    finally:
        setattr(module, attr, previous)


@contextmanager
def override_assistant_prompts(prompt_texts: dict[str, str]) -> Iterator[None]:
    """Scoped prompt swaps for an eval run (single-worker only).

    Agent-singleton prompts keep their dynamic ``@instructions`` functions:
    only the static string entries are replaced.
    """

    with ExitStack() as stack:
        for name, text in prompt_texts.items():
            agent = PROMPT_AGENT_TARGETS.get(name)
            if agent is not None:
                instructions = [
                    text if isinstance(entry, str) else entry
                    for entry in agent._instructions
                ]
                stack.enter_context(agent.override(instructions=instructions))
            elif name in PROMPT_ATTR_TARGETS:
                module, attr = PROMPT_ATTR_TARGETS[name]
                stack.enter_context(_patched_module_attr(module, attr, text))
            else:
                raise ValueError(f"Unknown assistant prompt '{name}'")
        yield


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
                    # The mode router's re-call redirect is protocol, not a failure.
                    if "was not executed yet" in content and "Switched to" in content:
                        continue
                    # pydantic-ai's nudge after an empty model response, which it
                    # recovers from on its own — not a tool failure.
                    if part.tool_name is None and content.startswith("Please "):
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


DEFAULT_CASE_TIMEOUT_S = 120


def get_case_timeout_s() -> float:
    """Wall-clock budget for one case; the slowest baseline case takes 17s."""

    # Blank, not just missing: compose always defines the key.
    raw = os.environ.get("BASEROW_EVAL_CASE_TIMEOUT", "").strip()
    return float(raw) if raw else float(DEFAULT_CASE_TIMEOUT_S)


class EvalCaseTimeout(Exception):
    """A case outran its budget and its in-flight request was cancelled."""


def run_case(
    case: EvalCase, model: str | Model
) -> tuple[EvalRunOutput, list[CheckResult]]:
    """Build the scenario, run ``main_agent``, and execute the case's checks.

    Performs no teardown and no chat persistence — the eval DB is disposable.
    Raises ``EvalCaseTimeout`` when the agent outruns its wall-clock budget:
    a hung case would otherwise block the single worker indefinitely.
    """

    load_all()
    scenario = get_scenario(case.scenario)(make_fixtures())
    tool_helpers = ToolHelpers(lambda x: None, lambda x: None)

    with override_assistant_model(model):
        string_model = model if isinstance(model, str) else None
        ctx = build_agent_run_context(
            scenario.user,
            scenario.workspace,
            tool_helpers,
            model=string_model,
        )
        ctx.deps.mode = case.mode
        ctx.deps.tool_helpers.request_context["ui_context"] = scenario.ui_context
        run_model = ctx.model if string_model is not None else model
        model_settings = (
            get_model_settings(string_model, ORCHESTRATOR)
            if string_model is not None
            else None
        )

        timeout_s = get_case_timeout_s()
        start = time.monotonic()
        # wait_for on pydantic-ai's own loop: cancels the in-flight request
        # instead of stranding a thread that keeps calling the provider.
        try:
            # Sequential tool execution mirrors production (assistant.py).
            with ToolManager.parallel_execution_mode("sequential"):
                result = run_until_complete(
                    asyncio.wait_for(
                        main_agent.run(
                            user_prompt=case.prompt,
                            deps=ctx.deps,
                            model=run_model,
                            usage_limits=UsageLimits(request_limit=case.max_iters),
                            toolsets=[ctx.toolset],
                            model_settings=model_settings,
                        ),
                        timeout_s,
                    )
                )
        except (TimeoutError, asyncio.CancelledError) as exc:
            raise EvalCaseTimeout(
                f"{case.id} exceeded {timeout_s:g}s and was cancelled"
            ) from exc
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
