from baserow_premium.generative_ai.managers import AIFileManager
from rest_framework import serializers

from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.contrib.database.rows.signals import rows_ai_values_generation_error
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.generative_ai.exceptions import ModelDoesNotBelongToType
from baserow.core.generative_ai.registries import (
    GenerativeAIWithFilesModelType,
    generative_ai_model_type_registry,
)
from baserow.core.handler import CoreHandler
from baserow.core.jobs.registries import JobType

from .models import AIField, GenerateAIValuesJob
from .operations import GenerateAIValuesOperationType
from .registries import ai_field_output_registry


class GenerateAIValuesJobType(JobType):
    type = "generate_ai_values"
    model_class = GenerateAIValuesJob
    max_count = 1

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
    }

    request_serializer_field_names = ["field_id"]
    request_serializer_field_overrides = {
        "field_id": serializers.IntegerField(
            help_text="The ID of the AI field to generate values for.",
        ),
        "row_ids": serializers.ListField(
            child=serializers.IntegerField(),
            required=False,
            help_text="The IDs of the rows to generate AI values for. If not "
            "provided, all rows in the view or table will be processed.",
        ),
        "view_id": serializers.IntegerField(
            required=False,
            help_text="The ID of the view to generate AI values for. If not provided, "
            "the entire table will be processed.",
        ),
        "only_empty": serializers.BooleanField(
            required=False,
            help_text="Whether to only generate AI values for rows where the "
            "field is empty.",
        ),
    }

    serializer_field_names = [
        "field_id",
        "row_ids",
        "view_id",
        "only_empty",
        "total_rows_count",
    ]
    serializer_field_overrides = {
        "field_id": serializers.IntegerField(
            help_text="The ID of the AI field to generate values for.",
        ),
        "row_ids": serializers.ListField(
            child=serializers.IntegerField(),
            required=False,
            help_text="The IDs of the rows to generate AI values for. If not "
            "provided, all rows in the view or table will be processed.",
        ),
        "view_id": serializers.IntegerField(
            required=False,
            help_text="The ID of the view to generate AI values for. If not provided, "
            "the entire table will be processed.",
        ),
        "only_empty": serializers.BooleanField(
            required=False,
            help_text="Whether to only generate AI values for rows where the "
            "field is empty.",
        ),
        "total_rows_count": serializers.IntegerField(
            required=False,
            help_text="The total number of rows to process. NOTE: this is calculated "
            "when the job is created and it might be inaccurate if the table is modified.",
        ),
    }

    def can_schedule_or_raise(self, job: GenerateAIValuesJob):
        # TODO: limit per table/view generationn jobs
        pass

    def prepare_values(self, values, user):
        ai_field = FieldHandler().get_field(values["field_id"], field_model=AIField)
        CoreHandler().check_permissions(
            user,
            GenerateAIValuesOperationType.type,
            workspace=ai_field.table.database.workspace,
            context=ai_field.table,
        )

        model = ai_field.table.get_model()
        req_row_ids = values["row_ids"]
        rows = RowHandler().get_rows(model, req_row_ids)
        if len(rows) != len(req_row_ids):
            found_rows_ids = [row.id for row in rows]
            raise RowDoesNotExist(sorted(list(set(req_row_ids) - set(found_rows_ids))))

        generative_ai_model_type = generative_ai_model_type_registry.get(
            ai_field.ai_generative_ai_type
        )
        ai_models = generative_ai_model_type.get_enabled_models(
            workspace=ai_field.table.database.workspace
        )

        if ai_field.ai_generative_ai_model not in ai_models:
            raise ModelDoesNotBelongToType(model_name=ai_field.ai_generative_ai_model)

        return values

    def run(self, job: GenerateAIValuesJob, progress):
        user = job.user
        ai_field = FieldHandler().get_field(job.field_id, field_model=AIField)
        table = ai_field.table
        workspace = table.database.workspace

        CoreHandler().check_permissions(
            user,
            GenerateAIValuesOperationType.type,
            workspace=workspace,
            context=table,
        )
        model = table.get_model()

        if job.mode == GenerateAIValuesJob.MODES.VIEW:
            view = ViewHandler().get_view_as_user(user, job.view_id, table_id=table.id)
            rows = (
                ViewHandler().get_queryset(view, model=model).iterator(chunk_size=200)
            )
        elif job.mode == GenerateAIValuesJob.MODES.TABLE:
            rows = model.objects.all().iterator(chunk_size=200)
        elif job.mode == GenerateAIValuesJob.MODES.ROWS:
            req_row_ids = job.row_ids
            rows = RowHandler().get_rows(model, req_row_ids)
        else:
            raise ValueError(f"Unknown mode {job.mode} for GenerateAIValuesJob")

        try:
            generative_ai_model_type = generative_ai_model_type_registry.get(
                ai_field.ai_generative_ai_type
            )
            ai_models = generative_ai_model_type.get_enabled_models(workspace=workspace)

            if ai_field.ai_generative_ai_model not in ai_models:
                raise ModelDoesNotBelongToType(
                    model_name=ai_field.ai_generative_ai_model
                )
        except ModelDoesNotBelongToType as exc:
            # If the workspace AI settings have been removed before the task starts,
            # or if the export worker doesn't have the right env vars yet, then it can
            # fail. We therefore want to handle the error gracefully.
            rows_ai_values_generation_error.send(
                self,
                user=user,
                rows=rows,
                field=ai_field,
                table=ai_field.table,
                error_message=str(exc),
            )
            raise exc

        ai_output_type = ai_field_output_registry.get(ai_field.ai_output_type)

        # TODO: batch rows processing to reduce number of requests to AI providers
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
                        generative_ai_model_type.delete_files(
                            file_ids, workspace=workspace
                        )
                else:
                    value = generative_ai_model_type.prompt(
                        ai_field.ai_generative_ai_model,
                        message,
                        workspace=workspace,
                        temperature=ai_field.ai_temperature,
                    )

                # Because the AI output type can change the prompt to try to force the
                # output a certain way, then it should give the opportunity to parse the
                # output when it's given. With the choice output type, it will try to
                # match it to a `SelectOption`, for example.
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

            # TODO: use actions to have undo/redo support

            # FIXME: manually set the websocket_id to None for now because the frontend
            # needs to receive the update to stop the loading state
            user.web_socket_id = None
            RowHandler().update_row_by_id(
                user,
                table,
                row.id,
                {ai_field.db_column: value},
                model=model,
                values_already_prepared=True,
            )
