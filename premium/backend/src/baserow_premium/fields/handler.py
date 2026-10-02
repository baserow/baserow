from __future__ import annotations

import json
import mimetypes
from copy import copy
from typing import TYPE_CHECKING, Any, Optional

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import Subquery

from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.contrib.database.table.models import Table
from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_FIELDS
from baserow.core.ai_provider.resolution import ScopedAIProviderState
from baserow.core.db import specific_iterator
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.generative_ai.exceptions import ModelDoesNotBelongToType
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.registries import ImportExportConfig
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
    def update_generated_value(
        cls,
        user: AbstractUser,
        ai_field: AIField,
        row_id: int,
        value: Any,
        model: type[GeneratedTableModel],
    ) -> bool:
        """
        Save a generated value using the field's current rich text setting.

        The row read also retrieves the setting, avoiding a separate field query
        for every result. A missing setting means the field was trashed, converted,
        or changed output type, so the prepared result must not be written.

        :param user: The user on whose behalf the value is saved.
        :param ai_field: The field configuration used to generate the value.
        :param row_id: The row receiving the value.
        :param value: The prepared AI output.
        :param model: The generated table model used by the job.
        :return: Whether the field still accepts this generation's output.
        :raises RowDoesNotExist: If the row was trashed during generation.
        """

        # Import here because field types also use this handler.
        from .models import AIField

        current_setting = AIField.objects.filter(
            pk=ai_field.pk, ai_output_type=ai_field.ai_output_type
        ).values("long_text_enable_rich_text")[:1]
        queryset = model.objects.annotate(
            _ai_generation_rich_text=Subquery(current_setting)
        ).enhance_by_fields()
        row_handler = RowHandler()
        with transaction.atomic():
            row = row_handler.get_row_for_update(
                user,
                ai_field.table,
                row_id,
                model=model,
                base_queryset=queryset.clear_multi_field_prefetch(),
            )
            if row._ai_generation_rich_text is None:
                return False

            # A converted choice column can hold text instead of option IDs.
            # Resolve relations only after checking that its output type matches,
            # retaining the usual combined prefetch for an unchanged field.
            for prefetch in queryset.get_multi_field_prefetches():
                prefetch(queryset, [row])

            # Generation threads keep their original prompt configuration.
            current_field = copy(ai_field)
            current_field.long_text_enable_rich_text = row._ai_generation_rich_text
            output_type = ai_field_output_registry.get(ai_field.ai_output_type)
            value = output_type.sanitize_value(current_field, value)
            row_handler.update_row(
                user,
                ai_field.table,
                row,
                {ai_field.db_column: value},
                model=model,
                values_already_prepared=True,
            )
        return True

    @classmethod
    def get_valid_model_type_or_raise(
        cls, ai_field: AIField, state: ScopedAIProviderState | None = None
    ) -> GenerativeAIModelType:
        """
        Return the generative AI model type for the given AI field, raising if
        the configured model is not enabled for the workspace.

        The field stores the provider type and model identifier as logical keys;
        the model type registry resolves the effective workspace or instance
        provider configuration.

        :param ai_field: The AI field to validate.
        :param state: Pre-loaded provider state, so a batch generating many
            rows resolves the workspace once instead of once per row.
        :raises ModelDoesNotBelongToType: If the model is not enabled.
        """

        generative_ai_model_type = generative_ai_model_type_registry.get(
            ai_field.ai_generative_ai_type
        )
        workspace = ai_field.table.database.workspace
        ai_models = generative_ai_model_type.get_enabled_models_for_feature(
            AI_PROVIDER_FEATURE_AI_FIELDS, workspace=workspace, state=state
        )

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
        ai_models = generative_ai_model_type.get_enabled_models_for_feature(
            AI_PROVIDER_FEATURE_AI_FIELDS,
            workspace=table.database.workspace,
        )

        if ai_model not in ai_models:
            raise ModelDoesNotBelongToType(model_name=ai_model)

        # The schema leaves this installation for a third party model, so it is
        # serialized the way an export is. A button field's actions can carry
        # an API key in their headers, and reading a formula field needs far
        # less permission than configuring a button does.
        prompt_config = ImportExportConfig(
            include_permission_data=False, exclude_sensitive_data=True
        )
        table_schema = []
        for field in specific_iterator(table.field_set.all()):
            field_type = field_type_registry.get_by_model(field)
            table_schema.append(
                field_type.export_serialized(field, import_export_config=prompt_config)
            )

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
        state: ScopedAIProviderState | None = None,
    ) -> Any:
        """
        Generate a single AI field value for the given row. Handles model
        validation, prompt resolution, file preparation, the AI call, file
        cleanup, and choice resolution.

        :param ai_field: The AI field configuration.
        :param row: The row to generate a value for.
        :param state: Pre-loaded provider state, so a batch generating many
            rows resolves the workspace once instead of once per row.
        :return: The generated value.
        :raises AIFieldEmptyPromptError: If the resolved prompt is empty.
        """

        generative_ai_model_type = cls.get_valid_model_type_or_raise(ai_field, state)
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

        instructions = ai_output_type.get_prompt_instructions(ai_field)
        if instructions:
            message += f"\n\n{instructions}"

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
        settings_override = generative_ai_model_type.get_model_settings_override(
            ai_field.ai_generative_ai_model, workspace, state=state
        )
        if settings_override is not None:
            prompt_kwargs["settings_override"] = settings_override
        try:
            if use_files:
                ai_files = cls._collect_ai_files(ai_field, row)
                prepared = generative_ai_model_type.prepare_files(
                    ai_files, workspace, settings_override
                )
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
                generative_ai_model_type.cleanup_files(
                    ai_files, workspace, settings_override
                )

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
