import asyncio
import threading
import time
from types import SimpleNamespace

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from baserow_enterprise.assistant.assistant import build_agent_run_context
from baserow_enterprise.assistant.deps import ToolHelpers
from baserow_enterprise.assistant.evals import harness, registry
from baserow_enterprise.assistant.evals.harness import (
    PROMPT_AGENT_TARGETS,
    PROMPT_ATTR_TARGETS,
    EvalCaseTimeout,
    get_case_timeout_s,
    override_assistant_model,
    override_assistant_prompts,
    run_case,
)
from baserow_enterprise.assistant.evals.prompt_sync import SYNCED_PROMPTS
from baserow_enterprise.assistant.evals.scenarios import make_fixtures
from baserow_enterprise.assistant.evals.types import CheckResult, EvalCase, EvalScenario


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setattr(registry, "_cases", {})
    monkeypatch.setattr(registry, "_scenarios", {})


@pytest.fixture(autouse=True)
def _set_test_model(settings):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/test-model"


def _noop_tool_helpers() -> ToolHelpers:
    return ToolHelpers(lambda x: None, lambda x: None)


@pytest.mark.django_db
class TestBuildAgentRunContext:
    def test_returns_deps_with_tool_catalog_and_toolset(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)

        ctx = build_agent_run_context(user, workspace, _noop_tool_helpers())

        assert ctx.deps.tool_catalog
        assert ctx.toolset is not None
        assert ctx.deps.user is user
        assert ctx.deps.workspace is workspace


class TestOverrideAssistantModel:
    def test_restores_previous_setting_on_exception(self, settings):
        settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/original-model"

        with pytest.raises(ValueError):
            with override_assistant_model("groq:override-model"):
                assert (
                    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL
                    == "groq/override-model"
                )
                raise ValueError("boom")

        assert settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL == "groq/original-model"

    def test_restores_previous_setting_on_success(self, settings):
        settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/original-model"

        with override_assistant_model("groq:override-model"):
            assert (
                settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL == "groq/override-model"
            )

        assert settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL == "groq/original-model"

    def test_noop_for_non_string_model(self, settings):
        settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/original-model"

        with override_assistant_model(TestModel()):
            assert (
                settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL == "groq/original-model"
            )

        assert settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL == "groq/original-model"


class TestAskUserTool:
    def test_records_the_question_and_tells_the_agent_to_stop(self):
        """Asking must be an action the agent can take, not the absence of
        one — otherwise it competes with the prompt's bias toward acting."""

        from baserow_enterprise.assistant.tools.core.tools import ask_user

        deps = SimpleNamespace(pending_question=None)
        result = ask_user(
            SimpleNamespace(deps=deps),
            question="Which table holds your customers?",
            thought="No Customers table found.",
        )

        assert deps.pending_question == "Which table holds your customers?"
        assert "restate this question verbatim" in result

    def test_is_reachable_from_every_mode(self):
        from baserow_enterprise.assistant.deps import AgentMode
        from baserow_enterprise.assistant.tools.routing import is_tool_active

        assert all(is_tool_active("ask_user", mode) for mode in AgentMode)


class TestCountToolErrors:
    def test_empty_response_retry_is_not_a_tool_error(self):
        """pydantic-ai nudges the model after an empty response with a
        tool_name-less RetryPromptPart; it recovers on its own, so it must not
        spend the case's tool-error budget."""

        from pydantic_ai.messages import ModelRequest, RetryPromptPart

        from baserow_enterprise.assistant.evals.harness import count_tool_errors

        result = SimpleNamespace(
            all_messages=lambda: [
                ModelRequest(
                    parts=[
                        RetryPromptPart(content="Please return text or call a tool.")
                    ]
                )
            ]
        )

        assert count_tool_errors(result) == (0, "")

    def test_real_tool_validation_error_still_counts(self):
        from pydantic_ai.messages import ModelRequest, RetryPromptPart

        from baserow_enterprise.assistant.evals.harness import count_tool_errors

        result = SimpleNamespace(
            all_messages=lambda: [
                ModelRequest(
                    parts=[
                        RetryPromptPart(
                            content="update_row requires row_id",
                            tool_name="create_workflows",
                        )
                    ]
                )
            ]
        )

        count, hint = count_tool_errors(result)
        assert count == 1
        assert "create_workflows" in hint


@pytest.mark.django_db
class TestRunCase:
    def _register_scenario(self, user, workspace):
        @registry.register_scenario("harness-test-scenario")
        def _build(fixtures) -> EvalScenario:
            return EvalScenario(user=user, workspace=workspace, ui_context=None)

    def test_ask_user_is_exposed_to_the_agent_and_recorded_as_a_tool_call(self):
        """End-to-end guard for the intent eval checks.

        They assert ``tool_called(output, "ask_user")``, so the tool must be
        reachable through the real toolset AND land in ``output.tool_calls``
        under exactly that name. If either breaks, the ask cases would fail
        forever and the act cases would pass trivially — silently.
        """

        from baserow_enterprise.assistant.evals.harness import tool_called

        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)
        self._register_scenario(user, workspace)

        ctx = build_agent_run_context(user, workspace, _noop_tool_helpers())
        assert "ask_user" in ctx.deps.tool_catalog

        case = EvalCase(
            id="harness-test/ask-user",
            dataset="harness-test",
            prompt="build me a page for our Customers",
            scenario="harness-test-scenario",
            checks=lambda case, scenario, output: [],
        )

        output, _checks = run_case(case, TestModel(call_tools=["ask_user"]))

        assert "ask_user" in output.tool_calls
        assert tool_called(output, "ask_user") == 1

    def test_returns_output_and_prepends_budget_check(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)
        self._register_scenario(user, workspace)

        def _checks(case, scenario, output):
            return [
                CheckResult(name="has-no-tool-calls", passed=output.tool_calls == [])
            ]

        case = EvalCase(
            id="harness-test/basic",
            dataset="harness-test",
            prompt="say hi",
            scenario="harness-test-scenario",
            checks=_checks,
        )

        output, results = run_case(
            case,
            TestModel(custom_output_text="hello from test model", call_tools=[]),
        )

        assert output.answer == "hello from test model"
        assert output.tool_calls == []
        assert output.tool_error_count == 0
        assert len(results) == 2
        assert results[0] == CheckResult(
            name="tool_errors_within_budget", passed=True, hint=""
        )
        assert results[1].name == "has-no-tool-calls"
        assert results[1].passed is True

    def test_scenario_receives_case_mode_and_ui_context(self, monkeypatch):
        """The case's mode and the scenario's ui_context must reach the run's
        deps — otherwise every case silently runs in DATABASE mode with no
        UI context and the whole baseline measures the wrong agent."""

        from baserow_enterprise.assistant.deps import AgentMode

        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)

        @registry.register_scenario("harness-test-scenario-ui")
        def _build(fx) -> EvalScenario:
            return EvalScenario(
                user=user, workspace=workspace, ui_context='{"foo": "bar"}'
            )

        def _checks(case, scenario, output):
            return [CheckResult(name="noop", passed=True)]

        case = EvalCase(
            id="harness-test/ui-context",
            dataset="harness-test",
            prompt="say hi",
            scenario="harness-test-scenario-ui",
            checks=_checks,
            mode=AgentMode.APPLICATION,
        )

        captured = {}
        real_build_context = build_agent_run_context

        def build_context_spy(*args, **kwargs):
            ctx = real_build_context(*args, **kwargs)
            captured["ctx"] = ctx
            return ctx

        monkeypatch.setattr(harness, "build_agent_run_context", build_context_spy)

        output, results = run_case(
            case, TestModel(custom_output_text="hi", call_tools=[])
        )

        assert output.answer == "hi"
        deps = captured["ctx"].deps
        assert deps.mode is AgentMode.APPLICATION
        request_context = deps.tool_helpers.request_context
        assert request_context["ui_context"] == '{"foo": "bar"}'

    def test_string_model_uses_resolved_context_model_and_orchestrator_settings(
        self, monkeypatch
    ):
        from baserow_enterprise.assistant.model_profiles import (
            ORCHESTRATOR,
            get_model_settings,
        )

        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)
        self._register_scenario(user, workspace)
        case = EvalCase(
            id="harness-test/string-model",
            dataset="harness-test",
            prompt="say hi",
            scenario="harness-test-scenario",
            checks=lambda case, scenario, output: [],
        )
        model = "groq:openai/gpt-oss-120b"
        captured = {}
        real_build_context = build_agent_run_context

        def build_context_spy(*args, **kwargs):
            ctx = real_build_context(*args, **kwargs)
            captured["ctx"] = ctx
            return ctx

        async def run_spy(**kwargs):
            captured["run_kwargs"] = kwargs
            return SimpleNamespace(
                output="hello",
                usage=SimpleNamespace(requests=1),
                all_messages=lambda: [],
            )

        monkeypatch.setattr(harness, "build_agent_run_context", build_context_spy)
        monkeypatch.setattr(harness.main_agent, "run", run_spy)

        output, _checks = run_case(case, model)

        assert output.answer == "hello"
        assert captured["run_kwargs"]["model"] is captured["ctx"].model
        assert captured["run_kwargs"]["model_settings"] == get_model_settings(
            model, ORCHESTRATOR
        )

    def test_runs_the_agent_in_sequential_tool_execution_mode(self, monkeypatch):
        """Production serializes multi-tool-call responses (assistant.py);
        evals must measure the same execution mode, not pydantic-ai's
        parallel default."""

        from pydantic_ai.tool_manager import _parallel_execution_mode_ctx_var

        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)
        self._register_scenario(user, workspace)
        case = EvalCase(
            id="harness-test/sequential-mode",
            dataset="harness-test",
            prompt="say hi",
            scenario="harness-test-scenario",
            checks=lambda case, scenario, output: [],
        )
        seen = {}

        async def run_spy(**kwargs):
            seen["mode"] = _parallel_execution_mode_ctx_var.get()
            return SimpleNamespace(
                output="hello",
                usage=SimpleNamespace(requests=1),
                all_messages=lambda: [],
            )

        monkeypatch.setattr(harness.main_agent, "run", run_spy)

        run_case(case, TestModel(call_tools=[]))

        assert seen["mode"] == "sequential"


class _InstructionSpyModel(TestModel):
    def __init__(self, captured: dict):
        super().__init__()
        self._captured = captured

    async def request(self, messages, model_settings, model_request_parameters):
        self._captured["instructions"] = messages[0].instructions
        return await super().request(messages, model_settings, model_request_parameters)


class TestOverrideAssistantPrompts:
    def test_targets_cover_every_synced_prompt_exactly(self):
        assert set(PROMPT_AGENT_TARGETS) | set(PROMPT_ATTR_TARGETS) == set(
            SYNCED_PROMPTS
        )
        assert not set(PROMPT_AGENT_TARGETS) & set(PROMPT_ATTR_TARGETS)

    def test_agent_target_swaps_static_text_and_keeps_dynamic_instructions(
        self, monkeypatch
    ):
        captured: dict = {}
        agent = Agent(model=_InstructionSpyModel(captured), instructions="STATIC")

        @agent.instructions
        def _dynamic(ctx) -> str:
            return "DYNAMIC"

        monkeypatch.setitem(PROMPT_AGENT_TARGETS, "kuma-system-prompt", agent)

        with override_assistant_prompts({"kuma-system-prompt": "OVERRIDDEN"}):
            asyncio.run(agent.run("hi"))
        assert captured["instructions"] == "OVERRIDDEN\n\nDYNAMIC"

        asyncio.run(agent.run("hi"))
        assert captured["instructions"] == "STATIC\n\nDYNAMIC"

    def test_attr_target_patches_module_constant_and_restores_it(self):
        module, attr = PROMPT_ATTR_TARGETS["kuma-database-sample-rows-agent"]
        original = getattr(module, attr)

        with override_assistant_prompts(
            {"kuma-database-sample-rows-agent": "OVERRIDDEN"}
        ):
            assert getattr(module, attr) == "OVERRIDDEN"

        assert getattr(module, attr) is original

    def test_restores_attr_even_when_body_raises(self):
        module, attr = PROMPT_ATTR_TARGETS["kuma-builder-formula-agent"]
        original = getattr(module, attr)

        with pytest.raises(RuntimeError):
            with override_assistant_prompts(
                {"kuma-builder-formula-agent": "OVERRIDDEN"}
            ):
                raise RuntimeError("boom")

        assert getattr(module, attr) is original

    def test_unknown_prompt_name_raises(self):
        with pytest.raises(ValueError, match="Unknown assistant prompt"):
            with override_assistant_prompts({"nope": "text"}):
                pass

    def test_empty_overrides_is_a_noop(self):
        with override_assistant_prompts({}):
            pass


class _HangingModel(TestModel):
    """Never answers, and records whether its request was actually cancelled."""

    def __init__(self, cancelled: threading.Event):
        super().__init__()
        self._cancelled = cancelled

    async def request(self, *args, **kwargs):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self._cancelled.set()
            raise
        return await super().request(*args, **kwargs)


@pytest.mark.django_db
class TestCaseTimeout:
    def _register_scenario(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)

        @registry.register_scenario("timeout-test-scenario")
        def _build(_fixtures) -> EvalScenario:
            return EvalScenario(user=user, workspace=workspace, ui_context=None)

    def _case(self, case_id: str) -> EvalCase:
        return EvalCase(
            id=case_id,
            dataset="harness-test",
            prompt="say hi",
            scenario="timeout-test-scenario",
            checks=lambda case, scenario, output: [],
        )

    def test_default_budget_is_two_minutes(self, monkeypatch):
        monkeypatch.delenv("BASEROW_EVAL_CASE_TIMEOUT", raising=False)

        assert get_case_timeout_s() == 120

    def test_budget_is_overridable_by_env(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_CASE_TIMEOUT", "0.25")

        assert get_case_timeout_s() == 0.25

    def test_a_hung_case_is_cancelled_not_abandoned(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_CASE_TIMEOUT", "0.3")
        self._register_scenario()
        cancelled = threading.Event()

        began = time.monotonic()
        with pytest.raises(EvalCaseTimeout, match="db/hangs exceeded 0.3s"):
            run_case(self._case("db/hangs"), _HangingModel(cancelled))
        elapsed = time.monotonic() - began

        # The reason for wait_for over a worker thread: the provider call
        # really stops, instead of running on and burning quota.
        assert cancelled.is_set(), "the model request was abandoned, not cancelled"
        assert elapsed < 5, f"took {elapsed:.1f}s — it waited for the model"

    def test_a_normal_case_is_untouched_by_the_budget(self):
        self._register_scenario()

        output, checks = run_case(
            self._case("db/fast"),
            TestModel(custom_output_text="hello", call_tools=[]),
        )

        assert output.answer == "hello"
        assert [c.name for c in checks] == ["tool_errors_within_budget"]

    def test_the_loop_still_works_after_a_timeout(self, monkeypatch):
        """A cancelled run must not poison the shared event loop for the
        cases that follow it — the worker runs every case on the same loop."""

        self._register_scenario()
        monkeypatch.setenv("BASEROW_EVAL_CASE_TIMEOUT", "0.3")
        with pytest.raises(EvalCaseTimeout):
            run_case(self._case("db/hangs"), _HangingModel(threading.Event()))

        monkeypatch.setenv("BASEROW_EVAL_CASE_TIMEOUT", "30")
        output, _checks = run_case(
            self._case("db/after"),
            TestModel(custom_output_text="still working", call_tools=[]),
        )

        assert output.answer == "still working"


@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_timeout_env_var_falls_back_to_the_default(monkeypatch, value):
    """docker-compose writes ${VAR:-} as an empty string, not an absent key,
    so float("") would crash the runner at startup."""

    monkeypatch.setenv("BASEROW_EVAL_CASE_TIMEOUT", value)

    assert get_case_timeout_s() == 120
