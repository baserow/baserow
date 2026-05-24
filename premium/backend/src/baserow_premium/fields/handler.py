from __future__ import annotations

import json
import mimetypes
from typing import TYPE_CHECKING, Any, Optional

from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.contrib.database.table.models import Table
from baserow.core.db import specific_iterator
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.generative_ai.exceptions import ModelDoesNotBelongToType
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow_premium.prompts import get_generate_formula_prompt

from .ai_file import AIFile
from .exceptions import AIFieldEmptyPromptError
from .pydantic_models import BaserowFormulaModel
from .registries import ai_field_output_registry

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel
    from baserow.core.generative_ai.registries import GenerativeAIModelType
    from baserow_premium.fields.models import AIField


class AIFieldHandler:
    @classmethod
    def get_valid_model_type_or_raise(cls, ai_field: AIField) -> GenerativeAIModelType:
        """
        Return the generative AI model type for the given AI field, raising if
        the configured model is not enabled for the workspace.

        :param ai_field: The AI field to validate.
        :raises ModelDoesNotBelongToType: If the model is not enabled.
        """

        generative_ai_model_type = generative_ai_model_type_registry.get(
            ai_field.ai_generative_ai_type
        )
        workspace = ai_field.table.database.workspace
        ai_models = generative_ai_model_type.get_enabled_models(workspace=workspace)

        if ai_field.ai_generative_ai_model not in ai_models:
            raise ModelDoesNotBelongToType(model_name=ai_field.ai_generative_ai_model)
        return generative_ai_model_type

    @classmethod
    def generate_formula_with_ai(
        cls,
        table: Table,
        ai_type: str,
        ai_model: str,
        ai_prompt: str,
        ai_temperature: Optional[float] = None,
    ) -> str:
        """
        Generate a formula using the provided AI type, model and prompt.

        :param table: The table where to generate the formula for.
        :param ai_type: The generate AI type that must be used.
        :param ai_model: The model related to the AI type that must be used.
        :param ai_prompt: The prompt that must be executed.
        :param ai_temperature: The temperature that's passed into the prompt.
        :raises ModelDoesNotBelongToType: if the provided model doesn't belong to the
            type
        :return: The generated formula string.
        """

        generative_ai_model_type = generative_ai_model_type_registry.get(ai_type)
        ai_models = generative_ai_model_type.get_enabled_models(
            table.database.workspace
        )

        if ai_model not in ai_models:
            raise ModelDoesNotBelongToType(model_name=ai_model)

        table_schema = []
        for field in specific_iterator(table.field_set.all()):
            field_type = field_type_registry.get_by_model(field)
            table_schema.append(field_type.export_serialized(field))

        table_schema_json = json.dumps(table_schema, indent=4)
        message = get_generate_formula_prompt().format(
            table_schema_json=table_schema_json, user_prompt=ai_prompt
        )

        result = generative_ai_model_type.prompt(
            ai_model,
            message,
            output_type=BaserowFormulaModel,
            workspace=table.database.workspace,
            temperature=ai_temperature,
        )
        return result.formula

    @classmethod
    def generate_value_with_ai(
        cls,
        ai_field: AIField,
        row: GeneratedTableModel,
    ) -> Any:
        """
        Generate a single AI field value for the given row. Handles model
        validation, prompt resolution, file preparation, the AI call, file
        cleanup, and choice resolution.

        :param ai_field: The AI field configuration.
        :param row: The row to generate a value for.
        :return: The generated value.
        :raises AIFieldEmptyPromptError: If the resolved prompt is empty.
        """

        generative_ai_model_type = cls.get_valid_model_type_or_raise(ai_field)
        ai_output_type = ai_field_output_registry.get(ai_field.ai_output_type)
        workspace = ai_field.table.database.workspace

        # 1. Resolve prompt from formula
        context = HumanReadableRowContext(row, exclude_field_ids=[ai_field.id])
        message = str(
            resolve_formula(
                ai_field.ai_prompt, formula_runtime_function_registry, context
            )
        )

        if not message or not message.strip():
            raise AIFieldEmptyPromptError(
                "The resolved prompt is empty; nothing to send to the model."
            )

        # 2. Build prompt kwargs
        choices = ai_output_type.get_choices(ai_field)
        prompt_kwargs: dict[str, Any] = {
            "workspace": workspace,
            "temperature": ai_field.ai_temperature,
        }
        if choices is not None:
            prompt_kwargs["output_type"] = choices

        # 3. Prepare files, call AI, cleanup
        ai_files: list[AIFile] = []
        use_files = (
            generative_ai_model_type.supports_files
            and ai_field.ai_file_field_id is not None
        )
        try:
            if use_files:
                ai_files = cls._collect_ai_files(ai_field, row)
                prepared = generative_ai_model_type.prepare_files(ai_files, workspace)
                if prepared:
                    prompt_kwargs["content"] = [f.content for f in prepared]
                skipped = [f for f in ai_files if f.content is None]
                if skipped:
                    names = ", ".join(f.original_name for f in skipped)
                    message += (
                        f"\n\nNote: the following files were provided but could "
                        f"not be included due to format, size, or processing "
                        f"limitations: "
                        f"{names}"
                    )

            value = generative_ai_model_type.prompt(
                ai_field.ai_generative_ai_model,
                message,
                **prompt_kwargs,
            )
        finally:
            # cleanup uses ai_files (not prepared) so that files uploaded
            # before a mid-prepare failure are still cleaned up.
            if ai_files:
                generative_ai_model_type.cleanup_files(ai_files, workspace)

        # 4. Resolve choice if needed
        if choices is not None:
            value = ai_output_type.resolve_choice(value, ai_field)

        return value

    @classmethod
    def _collect_ai_files(
        cls, ai_field: AIField, row: GeneratedTableModel
    ) -> list[AIFile]:
        """
        Build a list of AIFile instances from the row's file field cell data.
        """

        cell_files = getattr(row, f"field_{ai_field.ai_file_field_id}")
        if not isinstance(cell_files, list):
            cell_files = [cell_files] if cell_files else []

        return [
            AIFile(
                name=f["name"],
                original_name=f.get("visible_name", f["name"]),
                size=f.get("size", 0),
                mime_type=(
                    f.get("mime_type")
                    or mimetypes.guess_type(f["name"])[0]
                    or "application/octet-stream"
                ),
            )
            for f in cell_files
        ]
