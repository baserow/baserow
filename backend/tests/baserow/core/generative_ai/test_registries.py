import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from baserow.core.ai_provider.resolution import ScopedAIProviderState
from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    GenerativeAIModelTypeRegistry,
)


class _StructuredOutputGenerativeAIModelType(GenerativeAIModelType):
    type = "test_structured_output_generative_ai"

    def is_enabled(self, workspace=None):
        return True

    def get_enabled_models(self, workspace=None):
        return ["test_1"]

    def get_settings_serializer(self):
        return None


class _EmptyGenerativeAIModelType(_StructuredOutputGenerativeAIModelType):
    type = "test_empty_generative_ai"

    def get_enabled_models(self, workspace=None):
        return []

    def get_enabled_models_for_feature(self, feature_type, workspace=None):
        return [f"{feature_type}-only"]


class _LegacyPluginGenerativeAIModelType(GenerativeAIModelType):
    """An out-of-tree provider implementing the pre-ai-providers contract."""

    type = "legacy_plugin_generative_ai"

    def get_api_key(self, workspace=None):
        return self.get_workspace_setting(workspace, "api_key")

    def get_enabled_models(self, workspace=None):
        return self.get_workspace_setting(workspace, "models") or []

    def get_ai_model(self, model_name, workspace=None, settings_override=None):
        assert settings_override is None

        def func(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            return ModelResponse(parts=[TextPart(content=f"used {model_name}")])

        return FunctionModel(func)


class _DemoOutput(BaseModel):
    value: str


def _flaky_model(fail_times: int) -> FunctionModel:
    """A FunctionModel that returns invalid output `fail_times` times before succeeding."""

    calls = {"n": 0}

    def func(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] <= fail_times:
            return ModelResponse(parts=[TextPart(content="not valid json")])
        return ModelResponse(parts=[TextPart(content='{"value": "ok"}')])

    return FunctionModel(func)


def test_build_agent_with_pydantic_output_type_constructs_a_real_agent():
    """Regression test: Agent(output_retries=...) was removed in pydantic-ai V2."""

    ai_model_type = _StructuredOutputGenerativeAIModelType()

    agent = ai_model_type._build_agent(output_type=_DemoOutput)

    assert isinstance(agent, Agent)


def test_build_agent_output_retries_survives_two_failures():
    """The V1 output_retries=3 budget must still allow two output-validation
    retries before succeeding, not silently downgrade to V2's default of 1."""

    ai_model_type = _StructuredOutputGenerativeAIModelType()
    agent = ai_model_type._build_agent(output_type=_DemoOutput)

    result = agent.run_sync("hi", model=_flaky_model(fail_times=2))

    assert result.output == _DemoOutput(value="ok")


def test_generic_model_map_preserves_enabled_providers_with_no_models():
    registry = GenerativeAIModelTypeRegistry()
    registry.register(_EmptyGenerativeAIModelType())
    state = ScopedAIProviderState()

    assert registry.get_enabled_models_per_type(state=state) == {
        "test_empty_generative_ai": []
    }
    assert registry.get_enabled_models_per_type(
        feature_type="ai_fields", state=state
    ) == {"test_empty_generative_ai": ["ai_fields-only"]}


@pytest.mark.django_db
def test_legacy_plugin_provider_survives_database_provider_feature_flag(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    model_type = _LegacyPluginGenerativeAIModelType()
    registry = GenerativeAIModelTypeRegistry()
    registry.register(model_type)
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={
            model_type.type: {
                "api_key": "plugin-key",
                "models": ["plugin-model"],
            }
        }
    )

    assert registry.get_enabled_models_per_type(workspace) == {
        model_type.type: ["plugin-model"]
    }
    assert model_type.prompt("plugin-model", "hello", workspace) == (
        "used plugin-model"
    )
