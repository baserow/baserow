from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.core.models import Workspace
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.deps import AgentMode


@dataclass
class EvalScenario:
    user: AbstractUser
    workspace: Workspace
    ui_context: str | None  # UIContext.format() JSON, or None
    refs: dict[str, Any] = field(default_factory=dict)
    pre_state: dict[str, Any] = field(default_factory=dict)


ScenarioBuilder = Callable[[Fixtures], EvalScenario]


@dataclass
class EvalRunOutput:
    answer: str
    messages: list[dict]
    tool_calls: list[str]
    tool_error_count: int
    tool_error_hint: str
    sources: list[Any]
    request_count: int
    duration_s: float


@dataclass
class CheckResult:
    name: str
    passed: bool
    hint: str = ""


@dataclass(frozen=True)
class EvalCase:
    id: str
    dataset: str
    prompt: str
    scenario: str
    checks: "CheckSuite"
    mode: AgentMode = AgentMode.DATABASE
    max_iters: int = 15
    max_tool_errors: int = 0
    requires_knowledge_base: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
    reference_answer: str | None = None


CheckSuite = Callable[["EvalCase", EvalScenario, EvalRunOutput], list[CheckResult]]
