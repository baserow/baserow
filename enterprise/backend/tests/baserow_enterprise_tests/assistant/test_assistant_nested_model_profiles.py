from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from baserow_enterprise.assistant.model_profiles import UTILITY
from baserow_enterprise.assistant.tools.automation import agents as automation_agents
from baserow_enterprise.assistant.tools.builder import agents as builder_agents
from baserow_enterprise.assistant.tools.shared.agents import (
    FormulaGeneratorOutput,
    get_formula_generator,
)


def test_formula_generator_uses_request_model_profile():
    """The shared formula agent must not resolve a second model profile."""

    model_profile = MagicMock()
    nested_model = MagicMock()
    model_settings = {"temperature": 0.1}
    model_profile.create_model.return_value = nested_model
    model_profile.get_settings.return_value = model_settings
    context = MagicMock()
    context.get_formula_context.return_value = {}
    context.get_context_metadata.return_value = {}
    agent_result = SimpleNamespace(
        output=FormulaGeneratorOutput(generated_formulas={"title": "'Example'"})
    )

    with (
        patch(
            "baserow_enterprise.assistant.tools.shared.agents.resolve_formula"
        ) as resolve_formula,
        patch(
            "baserow_enterprise.assistant.tools.shared.agents."
            "run_agent_sync_with_model",
            return_value=agent_result,
        ) as run_agent,
    ):
        generate_formulas = get_formula_generator("prompt", model_profile)
        result = generate_formulas({"title": "A title"}, context)

    assert result == {"title": "'Example'"}
    assert run_agent.call_args.kwargs["model"] is nested_model
    assert run_agent.call_args.kwargs["model_settings"] is model_settings
    model_profile.get_settings.assert_called_once_with(UTILITY)
    resolve_formula.assert_called_once()


def test_builder_formula_orchestrator_forwards_request_model_profile():
    """Builder formula generation must reuse the enclosing request profile."""

    model_profile = MagicMock()
    tool_helpers = SimpleNamespace(model_profile=model_profile)
    context = MagicMock()

    with (
        patch.object(
            builder_agents,
            "BuilderFormulaContext",
            return_value=context,
        ),
        patch.object(builder_agents, "get_formula_generator") as factory,
    ):
        result = builder_agents.update_element_formulas(
            MagicMock(),
            MagicMock(),
            [],
            {},
            tool_helpers,
        )

    assert result == []
    factory.assert_called_once_with(
        builder_agents.BUILDER_FORMULA_PROMPT,
        model_profile,
    )


def test_automation_formula_orchestrator_forwards_request_model_profile():
    """Automation formula generation must reuse the enclosing request profile."""

    model_profile = MagicMock()
    tool_helpers = SimpleNamespace(model_profile=model_profile)
    workflow = MagicMock()
    workflow.automation_workflow_nodes.all.return_value.order_by.return_value = []
    orm_node = MagicMock(workflow=workflow)
    node_update = MagicMock()
    node_update.get_formulas_to_update.return_value = None

    with patch.object(
        automation_agents,
        "get_generate_formulas_tool",
    ) as factory:
        automation_agents.update_single_node_formulas(
            node_update,
            orm_node,
            tool_helpers,
        )

    factory.assert_called_once_with(model_profile)
