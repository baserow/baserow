from baserow_premium.generative_ai.managers import AIFileManager

from baserow.config.celery import app
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.contrib.database.rows.signals import rows_ai_values_generation_error
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.generative_ai.exceptions import ModelDoesNotBelongToType
from baserow.core.generative_ai.registries import (
    GenerativeAIWithFilesModelType,
    generative_ai_model_type_registry,
)
from baserow.core.handler import CoreHandler
from baserow.core.user.handler import User

from .models import AIField
from .registries import ai_field_output_registry


@app.task(bind=True, queue="export")
def generate_ai_values_for_rows(self, user_id: int, field_id: int, row_ids: list[int]):
    user = User.objects.get(pk=user_id)

    ai_field = FieldHandler().get_field(
        field_id,
        base_queryset=AIField.objects.all()
        .select_related("table__database__workspace")
        .prefetch_related("select_options"),
    )
    table = ai_field.table
    workspace = table.database.workspace

    CoreHandler().check_permissions(
        user,
        ListFieldsOperationType.type,
        workspace=workspace,
        context=table,
    )

    model = ai_field.table.get_model()
    req_row_ids = row_ids
    rows = RowHandler().get_rows(model, req_row_ids)
    if len(rows) != len(req_row_ids):
        found_rows_ids = [row.id for row in rows]
        raise RowDoesNotExist(sorted(list(set(req_row_ids) - set(found_rows_ids))))

    try:
        generative_ai_model_type = generative_ai_model_type_registry.get(
            ai_field.ai_generative_ai_type
        )
        ai_models = generative_ai_model_type.get_enabled_models(workspace=workspace)

        if ai_field.ai_generative_ai_model not in ai_models:
            raise ModelDoesNotBelongToType(model_name=ai_field.ai_generative_ai_model)
    except ModelDoesNotBelongToType as exc:
        # If the workspace AI settings have been removed before the task starts,
        # or if the export worker doesn't have the right env vars yet, then it can
        # fail. We therefore want to handle the error gracefully.
        rows_ai_values_generation_error.send(
            self,
            user=user,
            rows=rows,
            field=ai_field,
            table=table,
            error_message=str(exc),
        )
        raise exc

    ai_output_type = ai_field_output_registry.get(ai_field.ai_output_type)

    for i, row in enumerate(rows):
        context = HumanReadableRowContext(row, exclude_field_ids=[ai_field.id])
        message = str(
            resolve_formula(
                ai_field.ai_prompt, formula_runtime_function_registry, context
            )
        )

        # The AI output type should be able to format the prompt because it can add
        # additional instructions to it. The choice output type for example adds
        # additional prompt trying to force the out, for example.
        message = ai_output_type.format_prompt(message, ai_field)

        try:
            if ai_field.ai_file_field_id is not None and isinstance(
                generative_ai_model_type, GenerativeAIWithFilesModelType
            ):
                file_ids = AIFileManager.upload_files_from_file_field(
                    ai_field, row, generative_ai_model_type, workspace=workspace
                )
                try:
                    value = generative_ai_model_type.prompt_with_files(
                        ai_field.ai_generative_ai_model,
                        message,
                        file_ids=file_ids,
                        workspace=workspace,
                        temperature=ai_field.ai_temperature,
                    )
                except Exception as exc:
                    raise exc
                finally:
                    generative_ai_model_type.delete_files(file_ids, workspace=workspace)
            else:
                value = generative_ai_model_type.prompt(
                    ai_field.ai_generative_ai_model,
                    message,
                    workspace=workspace,
                    temperature=ai_field.ai_temperature,
                )

            # Because the AI output type can change the prompt to try to force the
            # output a certain way, then it should give the opportunity to parse the
            # output when it's given. With the choice output type, it will try to match
            # it to a `SelectOption`, for example.
            value = ai_output_type.parse_output(value, ai_field)
        except Exception as exc:
            # If the prompt fails once, we should not continue with the other rows.
            rows_ai_values_generation_error.send(
                self,
                user=user,
                rows=rows[i:],
                field=ai_field,
                table=table,
                error_message=str(exc),
            )
            raise exc

        RowHandler().update_row_by_id(
            user,
            table,
            row.id,
            {ai_field.db_column: value},
            model=model,
            values_already_prepared=True,
        )
