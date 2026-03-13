"""
Shared formula generation agent factory.

Contains:
- ``FormulaGeneratorOutput``: Output model for the formula generator agent.
- ``get_formula_generator()``: Factory to create a formula generator with a custom prompt.
"""

from typing import Callable

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field
from pydantic_ai import Agent

from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
)

from .formula_utils import BaseFormulaContext


class FormulaGeneratorOutput(PydanticBaseModel):
    """Output model for the formula generator agent."""

    generated_formulas: dict[str, str] = Field(
        description=(
            "A mapping of field identifiers to their generated formulas. "
            "Each key is a field id/name from `fields_to_resolve` and the value "
            "is the generated formula string."
        )
    )


def get_formula_generator(
    prompt: str,
) -> Callable[[dict, BaseFormulaContext, int], dict[str, str]]:
    """
    Factory to create a formula generator with a custom prompt.

    :param prompt: The system prompt for the LLM describing available functions.
    :return: A function that generates formulas from field descriptions.
    """

    formula_agent = Agent(
        output_type=FormulaGeneratorOutput,
        instructions=prompt,
        name="formula_agent",
    )

    def check_formula(generated_formula: str, context: BaseFormulaContext) -> str:
        """Validate a generated formula against the context."""
        try:
            resolve_formula(
                BaserowFormulaObject.create(
                    formula=generated_formula, mode=BASEROW_FORMULA_MODE_ADVANCED
                ),
                formula_runtime_function_registry,
                context,
            )
        except Exception as exc:
            raise ValueError(f"Generated formula is invalid: {str(exc)}")
        return "ok, the formula is valid"

    def generate_formulas(
        fields_to_resolve: dict,
        context: BaseFormulaContext,
        max_retries: int = 3,
    ) -> dict[str, str]:
        """
        Generate formulas for the given field descriptions.

        :param fields_to_resolve: Dict mapping field names to descriptions.
        :param context: Formula context with available data.
        :param max_retries: Number of retry attempts on validation failure.
        :return: Dict mapping field names to generated formulas.
        :raises ValueError: If no valid formulas could be generated.
        """
        feedback = ""
        valid_formulas = {}
        remaining = dict(fields_to_resolve)

        for __ in range(max_retries):
            if not remaining:
                break

            user_prompt = (
                f"Fields to resolve: {remaining}\n"
                f"(If prefixed with [optional], the field is not mandatory.)\n\n"
                f"Context: {context.get_formula_context()}\n\n"
                f"Context metadata: {context.get_context_metadata()}\n"
                f"(Metadata about the context fields, with refs and names "
                f"to assist in formula generation.)\n\n"
                f"Feedback: {feedback or 'None (first attempt)'}"
            )
            from baserow_enterprise.assistant.model_profiles import (
                UTILITY,
                get_model_settings,
                get_model_string,
            )

            model = get_model_string()
            try:
                result = formula_agent.run_sync(
                    user_prompt,
                    model=model,
                    model_settings=get_model_settings(model, UTILITY),
                )
            except Exception as exc:
                feedback += f"Formula agent error: {str(exc)}\n"
                continue

            generated_formulas = result.output.generated_formulas
            for field_id, formula in generated_formulas.items():
                if field_id not in remaining:
                    continue
                try:
                    check_formula(formula, context)
                    valid_formulas[field_id] = formula
                    remaining.pop(field_id, None)
                except ValueError as exc:
                    feedback += (
                        f"Error for {field_id}, formula {formula} not valid: "
                        f"{str(exc)}\n"
                    )

            if not remaining:
                return valid_formulas

        # Return any valid formulas we have, or raise if none
        if valid_formulas:
            return valid_formulas
        else:
            raise ValueError(
                f"Failed to generate any valid formulas after "
                f"{max_retries} attempts. Feedback:\n{feedback}"
            )

    return generate_formulas
