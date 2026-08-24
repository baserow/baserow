import pytest
from pydantic_ai.models.test import TestModel

from baserow_enterprise.assistant.assistant import build_agent_run_context
from baserow_enterprise.assistant.deps import ToolHelpers
from baserow_enterprise.assistant.evals import registry
from baserow_enterprise.assistant.evals.harness import (
    override_assistant_model,
    run_case,
)
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
    def test_returns_deps_with_manifests_and_toolset(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)

        ctx = build_agent_run_context(user, workspace, _noop_tool_helpers())

        assert ctx.deps.database_manifest
        assert ctx.deps.application_manifest
        assert ctx.deps.automation_manifest
        assert ctx.deps.explain_manifest
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


@pytest.mark.django_db
class TestRunCase:
    def _register_scenario(self, user, workspace):
        @registry.register_scenario("harness-test-scenario")
        def _build(fixtures) -> EvalScenario:
            return EvalScenario(user=user, workspace=workspace, ui_context=None)

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
