from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from baserow.core.generative_ai.registries import GenerativeAIModelType


class _StructuredOutputGenerativeAIModelType(GenerativeAIModelType):
    type = "test_structured_output_generative_ai"

    def is_enabled(self, workspace=None):
        return True

    def get_enabled_models(self, workspace=None):
        return ["test_1"]

    def get_settings_serializer(self):
        return None


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
