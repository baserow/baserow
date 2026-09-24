import asyncio
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import async_to_sync
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_MODEL,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow_enterprise.assistant.agents import main_agent
from baserow_enterprise.assistant.assistant import build_agent_run_context
from baserow_enterprise.assistant.deps import ToolHelpers
from baserow_enterprise.assistant.evals import registry
from baserow_enterprise.assistant.evals.harness import (
    PROMPT_AGENT_TARGETS,
    PROMPT_ATTR_TARGETS,
    EvalCaseTimeout,
    get_case_timeout_s,
    override_assistant_prompts,
    run_case,
)
from baserow_enterprise.assistant.evals.prompt_sync import SYNCED_PROMPTS
from baserow_enterprise.assistant.evals.scenarios import make_fixtures
from baserow_enterprise.assistant.evals.types import CheckResult, EvalCase, EvalScenario
from baserow_enterprise.assistant.model_profiles import (
    ORCHESTRATOR,
    ResolvedAssistantModelProfile,
    get_model_settings,
    resolve_assistant_model,
)
from baserow_enterprise.assistant.retrying_model import RetryingModel
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry
from baserow_enterprise.assistant.tools.toolset import InlineRefsToolset


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setattr(registry, "_cases", {})
    monkeypatch.setattr(registry, "_scenarios", {})


@pytest.fixture(autouse=True)
def _set_test_model(settings):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/test-model"


@pytest.fixture
def configured_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    provider = AIProviderHandler.create_provider(
        "openai",
        api_key="database-secret",
        workspace=workspace,
        models_data=[
            {
                "model_identifier": "database-model",
                "feature_types": [AI_PROVIDER_FEATURE_KUMA],
            }
        ],
    )
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        workspace=workspace,
        model=provider.models.get(),
    )
    return user, workspace


def _noop_tool_helpers(workspace) -> ToolHelpers:
    return ToolHelpers(
        lambda x: None,
        lambda x: None,
        model_profile=resolve_assistant_model(
            workspace=workspace, model="groq:test-model"
        ),
    )


@pytest.mark.django_db
class TestBuildAgentRunContext:
    def test_returns_deps_with_manifests_and_toolset(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)

        ctx = build_agent_run_context(user, workspace, _noop_tool_helpers(workspace))

        assert ctx.deps.database_manifest
        assert ctx.deps.application_manifest
        assert ctx.deps.automation_manifest
        assert ctx.deps.explain_manifest
        assert ctx.toolset is not None
        assert ctx.deps.user is user
        assert ctx.deps.workspace is workspace

    def test_passes_concrete_model_and_explicit_profile(self, configured_workspace):
        user, workspace = configured_workspace
        helpers = _noop_tool_helpers(workspace)
        toolset = MagicMock()

        with patch.object(
            assistant_tool_registry,
            "build_toolset",
            return_value=(toolset, "database", "application", "automation", "explain"),
        ) as build_toolset:
            ctx = build_agent_run_context(user, workspace, helpers)

        assert ctx.toolset is toolset
        assert ctx.deps.tool_helpers.model_profile is helpers.model_profile
        assert (
            resolve_assistant_model(workspace=workspace).model_string
            == "openai:database-model"
        )
        build_toolset.assert_called_once_with(
            user=user,
            workspace=workspace,
            model=ctx.model,
            model_profile=helpers.model_profile,
            deps=ctx.deps,
        )
        assert isinstance(ctx.model, RetryingModel)

    def test_tool_arg_repair_owns_the_concrete_model_lifecycle(self, data_fixture):
        """Preserve the concrete-model regression from the retired eval utilities."""

        class ToolArgs(BaseModel):
            count: int

        user = data_fixture.create_user()
        workspace = data_fixture.create_workspace(user=user)
        model = MagicMock()
        model.__aenter__.return_value = model
        model.__aexit__.return_value = None

        def build_toolset(**kwargs):
            return (
                InlineRefsToolset(
                    MagicMock(),
                    model=kwargs["model"],
                    model_profile=kwargs["model_profile"],
                ),
                "database",
                "application",
                "automation",
                "explain",
            )

        with (
            patch.object(
                ResolvedAssistantModelProfile, "create_model", return_value=model
            ),
            patch.object(
                assistant_tool_registry, "build_toolset", side_effect=build_toolset
            ),
            patch(
                "pydantic_ai.Agent.run",
                new=AsyncMock(return_value=SimpleNamespace(output='{"count": 2}')),
            ),
        ):
            ctx = build_agent_run_context(
                user, workspace, _noop_tool_helpers(workspace)
            )
            validator = TypeAdapter(ToolArgs)
            ctx.toolset._schemas["example"] = ToolArgs.model_json_schema()
            ctx.toolset._original_validators["example"] = validator
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_python({"count": "invalid"})

            fixed = async_to_sync(ctx.toolset._fix_tool_args)(
                "example", {"count": "invalid"}, exc_info.value
            )

        assert fixed == ToolArgs(count=2)
        model.__aenter__.assert_awaited_once_with()
        model.__aexit__.assert_awaited_once()


@pytest.mark.django_db
class TestRunCase:
    def _register_scenario(self, user, workspace):
        @registry.register_scenario("harness-test-scenario")
        def _build(fixtures) -> EvalScenario:
            return EvalScenario(user=user, workspace=workspace, ui_context=None)

    def test_uses_explicit_model_with_production_settings_and_lifecycle(
        self, configured_workspace, settings
    ):
        user, workspace = configured_workspace
        self._register_scenario(user, workspace)
        case = EvalCase(
            id="harness-test/settings",
            dataset="harness-test",
            prompt="say hi",
            scenario="harness-test-scenario",
            checks=lambda case, scenario, output: [],
        )
        model = "groq:openai/gpt-oss-120b"
        test_model = _LifecycleModel(custom_output_text="hello", call_tools=[])
        with (
            patch(
                "baserow_enterprise.assistant.retrying_model._resolve_model",
                return_value=test_model,
            ),
            patch(
                "baserow_enterprise.assistant.evals.harness.main_agent.run",
                wraps=main_agent.run,
            ) as run,
        ):
            output, _ = run_case(case, model)

        assert output.answer == "hello"
        assert isinstance(run.call_args.kwargs["model"], RetryingModel)
        assert run.call_args.kwargs["model_settings"] == get_model_settings(
            model, ORCHESTRATOR
        )
        profile = run.call_args.kwargs["deps"].tool_helpers.model_profile
        assert profile.model_string == model
        assert profile.source == "explicit"
        assert (
            resolve_assistant_model(workspace=workspace).model_string
            == "openai:database-model"
        )
        assert settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL == "groq/test-model"
        assert test_model.entered
        assert test_model.closed

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

    def test_scenario_receives_case_mode_and_ui_context(self):
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

        output, results = run_case(
            case, TestModel(custom_output_text="hi", call_tools=[])
        )

        assert output.answer == "hi"


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


class _LifecycleModel(TestModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.entered = False
        self.closed = False

    async def __aenter__(self):
        self.entered = True
        return await super().__aenter__()

    async def __aexit__(self, *args):
        self.closed = True
        return await super().__aexit__(*args)


class _HangingModel(_LifecycleModel):
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
        model = _HangingModel(cancelled)

        began = time.monotonic()
        with pytest.raises(EvalCaseTimeout, match="db/hangs exceeded 0.3s"):
            run_case(self._case("db/hangs"), model)
        elapsed = time.monotonic() - began

        # The reason for wait_for over a worker thread: the provider call
        # really stops, instead of running on and burning quota.
        assert cancelled.is_set(), "the model request was abandoned, not cancelled"
        assert model.entered
        assert model.closed
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
