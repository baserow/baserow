from collections.abc import Iterator
from concurrent.futures import Executor, ThreadPoolExecutor
from queue import Empty, Queue
from typing import Any, Type

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow_premium.generative_ai.managers import AIFileManager
from loguru import logger
from rest_framework import serializers

from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.contrib.database.api.fields.errors import ERROR_FIELD_DOES_NOT_EXIST
from baserow.contrib.database.api.views.errors import ERROR_VIEW_DOES_NOT_EXIST
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.contrib.database.rows.signals import rows_ai_values_generation_error
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.generative_ai.exceptions import (
    GenerativeAIPromptError,
    ModelDoesNotBelongToType,
)
from baserow.core.generative_ai.registries import (
    GenerativeAIWithFilesModelType,
    generative_ai_model_type_registry,
)
from baserow.core.handler import CoreHandler
from baserow.core.job_types import _empty_transaction_context
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.registries import JobType
from baserow.core.utils import ChildProgressBuilder, Progress

from .models import AIField, GenerateAIValuesJob
from .registries import ai_field_output_registry


class GenerateAIValuesJobFiltersSerializer(serializers.Serializer):
    """
    Adds the ability to filter GenerateAIValuesJob by AI field ID.
    """

    generate_ai_values_field_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Filter by the AI field ID.",
    )


def get_valid_generative_ai_model_type_or_raise(ai_field: AIField):
    """
    Returns the generative AI model type for the given AI field if the model belongs
    to the type. Otherwise, raises a ModelDoesNotBelongToType exception.

    :param ai_field: The AI field to check.
    :return: The generative AI model type.
    :raises ModelDoesNotBelongToType: If the model does not belong to the type.
    """

    generative_ai_model_type = generative_ai_model_type_registry.get(
        ai_field.ai_generative_ai_type
    )
    workspace = ai_field.table.database.workspace
    ai_models = generative_ai_model_type.get_enabled_models(workspace=workspace)

    if ai_field.ai_generative_ai_model not in ai_models:
        raise ModelDoesNotBelongToType(model_name=ai_field.ai_generative_ai_model)
    return generative_ai_model_type


class GenerateAIValuesJobType(JobType):
    type = "generate_ai_values"
    model_class = GenerateAIValuesJob
    max_count = 3

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
        FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
    }
    serializer_field_names = [
        "field_id",
        "row_ids",
        "view_id",
        "only_empty",
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
    }

    def can_schedule_or_raise(self, job: GenerateAIValuesJob):
        """
        Checks whether a new job of this type can be scheduled for the given user. It
        doesn't limit the number of jobs if specific row IDs are provided. It limits to
        1 job per table and to max_count jobs in total.

        :param job: The job instance that is going to be scheduled.
        :raises MaxJobCountExceeded: If the user cannot schedule a new job of this type
        """

        # No limits when specific row IDs are provided
        if job.row_ids:
            return

        running_jobs = (
            GenerateAIValuesJob.objects.filter(
                user_id=job.user.id,
                row_ids__isnull=True,
            )
            .is_pending_or_running()
            .select_related("field")
        )

        # No more than max_count jobs in total
        if len(running_jobs) >= self.max_count:
            raise MaxJobCountExceeded(
                f"You can only launch {self.max_count} {self.type} job(s) at "
                "the same time."
            )

        # No more than 1 job per field
        for running_job in running_jobs:
            if running_job.field_id == job.field_id:
                raise MaxJobCountExceeded(
                    f"You can only launch 1 {self.type} job(s) at "
                    "the same time for the same field."
                )

    def transaction_atomic_context(self, job: GenerateAIValuesJob):
        # We want to commit a row at a time to provide faster feedback to the user.
        return _empty_transaction_context()

    def _get_view_queryset(self, user, view_id: int, table_id: int):
        """
        Returns the queryset for the given view as the given user.

        :param user: The user for whom the view queryset should be fetched.
        :param view_id: The id of the view.
        :param table_id: The id of the table the view belongs to.
        :return: The queryset for the view.
        :raises ViewDoesNotExist: If the view does not exist or the user has no access
            to it.
        """

        handler = ViewHandler()
        view = handler.get_view_as_user(user, view_id, table_id=table_id)
        return handler.get_queryset(user, view)

    def _filter_empty_values(
        self, queryset: QuerySet[GeneratedTableModel], ai_field: AIField
    ) -> QuerySet[GeneratedTableModel]:
        """
        Filters the given queryset to only include rows where the given AI field is
        empty.

        :param queryset: The queryset to filter.
        :param ai_field: The AI field to check for emptiness.
        :return: The filtered queryset.
        """

        return queryset.filter(
            **{f"{ai_field.db_column}__isnull": True}
        ) | queryset.filter(**{ai_field.db_column: ""})

    def _get_field(self, field_id: int) -> AIField:
        """
        Returns the AI field with the given ID.

        :param field_id: The ID of the AI field to retrieve.
        :return: The AI field instance.
        :raises FieldDoesNotExist: If the field does not exist.
        """

        return FieldHandler().get_field(
            field_id,
            base_queryset=AIField.objects.all()
            .select_related("table__database__workspace")
            .prefetch_related("select_options"),
        )

    def prepare_values(self, values, user):
        ai_field = self._get_field(values["field_id"])

        model = ai_field.table.get_model()
        req_row_ids = values.get("row_ids")
        view_id = values.get("view_id")

        # Create the job instance without saving it yet, so we can use its mode property
        unsaved_job = GenerateAIValuesJob(**values)

        get_valid_generative_ai_model_type_or_raise(ai_field)

        if unsaved_job.mode == GenerateAIValuesJob.MODES.ROWS:
            found_rows_ids = (
                RowHandler().get_rows(model, req_row_ids).values_list("id", flat=True)
            )
            if len(found_rows_ids) != len(req_row_ids):
                raise RowDoesNotExist(
                    sorted(list(set(req_row_ids) - set(found_rows_ids)))
                )
        elif unsaved_job.mode == GenerateAIValuesJob.MODES.VIEW:
            # Ensure the view exists in the table
            ViewHandler().get_view_as_user(user, view_id, table_id=ai_field.table.id)

        return values

    def get_filters_serializer(self) -> Type[serializers.Serializer] | None:
        """
        Adds the ability to filter GenerateAIValuesJob by AI field ID.

        :return: A serializer class extending JobTypeFiltersSerializer.
        """

        return GenerateAIValuesJobFiltersSerializer

    def run(self, job: GenerateAIValuesJob, progress):
        user = job.user
        ai_field = self._get_field(job.field_id)
        table = ai_field.table
        workspace = table.database.workspace
        model = table.get_model()

        CoreHandler().check_permissions(
            job.user,
            ListFieldsOperationType.type,
            workspace=workspace,
            context=ai_field.table,
        )

        if job.mode == GenerateAIValuesJob.MODES.VIEW:
            rows = self._get_view_queryset(user, job.view_id, table.id)
        elif job.mode == GenerateAIValuesJob.MODES.TABLE:
            rows = model.objects.all()
        elif job.mode == GenerateAIValuesJob.MODES.ROWS:
            req_row_ids = job.row_ids
            rows = RowHandler().get_rows(model, req_row_ids)
        else:
            raise ValueError(f"Unknown mode {job.mode} for GenerateAIValuesJob")

        if job.only_empty:
            rows = self._filter_empty_values(rows, ai_field)

        progress_builder = progress.create_child_builder(
            represents_progress=progress.total
        )

        rows_progress = ChildProgressBuilder.build(progress_builder, rows.count())
        generator = AIValueGenerator(user, ai_field, self, rows_progress)
        generator.process(rows.order_by("id"))


class AIValueGenerator:
    """
    AIValueGenerator encapsulates AI field value generation process. It needs user and
    field context to work, but also utilizes Job object as a sender for generation
    error signal, and Progress object to mark the progress of processing.

    Internally, this schedules processing of each row to a separate thread using a
    thread pool controlled by a `concurrent.futures.ThreadPoolExecutor`. Because we
    use threads, a general rule is to run all code that needs a database connection in
    the same, one (main) thread. The code that issues http requests to the model,
    should be run in a separate thread.

    After a completion of processing, the result will be send back to the main thread
    with a queue, and processed.
    """

    def __init__(
        self,
        user: AbstractUser,
        ai_field: AIField,
        signal_sender: GenerateAIValuesJob | Any | None = None,
        progress: Progress | None = None,
    ):
        self.user = user

        self.ai_field = ai_field
        self.table = table = ai_field.table
        self.model = table.get_model()
        self.signal_sender = signal_sender
        self.workspace = table.database.workspace
        self.max_concurrency = self.ai_field.ai_max_concurrent_generations

        # A counter of processed rows. This doesn't include rows being still processed.
        self.finished = 0

        # Keeps track of currently processing row ids.
        self.in_process = set()

        # A marker to know if we should schedule more rows. This can be set to `False`
        # in two cases: when rows iterator finishes, and when there's an error and
        # we don't want to continue.
        self.generate_more_rows = True

        # A queue of results
        self.results_queue = Queue(self.max_concurrency)

        # Marker to keep track if any errors ocurred during the process.
        self.has_errors = False

        self.row_handler = RowHandler()
        self.progress = progress

        self.prepare()

    def prepare(self):
        """
        Prepares runtime values from AI field attached.

        This method prepares common values to be used during processing and should be
        called once, before processing is started.
        """

        try:
            self.generative_ai_model_type = get_valid_generative_ai_model_type_or_raise(
                self.ai_field
            )
        except ModelDoesNotBelongToType as exc:
            # If the workspace AI settings have been removed before the task starts,
            # or if the export worker doesn't have the right env vars yet, then it can
            # fail. We therefore want to handle the error gracefully.
            # Note: rows might be a generator, so we can't pass it directly
            rows_ai_values_generation_error.send(
                self.signal_sender,
                user=self.user,
                rows=[],
                field=self.ai_field,
                table=self.ai_field.table,
                error_message=str(exc),
            )
            raise exc

        self.ai_output_type = ai_field_output_registry.get(self.ai_field.ai_output_type)

        self.use_file_fields = (
            self.ai_field.ai_file_field_id is not None
            and isinstance(
                self.generative_ai_model_type, GenerativeAIWithFilesModelType
            )
        )

        # FIXME: manually set the websocket_id to None for now because the frontend
        # needs to receive the update to stop the loading state
        self.user.web_socket_id = None

    def generate_value_for(self, row: GeneratedTableModel):
        """
        Runs value generation for a single row using AI model.

        The contents of the method should prepare and run a prompt on a model for the
        row. This method doesn't return any value. Instead, the result, or any error
        that will happen during the processing, will be put on a results queue.

        :param row: A row to generate value for.
        """

        try:
            result = self._generate_value_for(row)

            self.results_queue.put(
                (
                    row,
                    result,
                ),
                block=True,
            )
        except Exception as e:
            logger.opt(exception=e).error(f"Value generation for row {row} failed: {e}")

            self.results_queue.put(
                (
                    row,
                    e,
                ),
                block=True,
            )

    def _generate_value_for(self, row: GeneratedTableModel) -> Any:
        """
        Prepares the message (and optionally files), sends it to the AI model and
        returns the result.

        :param row: A row to generate value for.
        :return: A result from the AI model.
        """

        ai_field = self.ai_field
        ai_output_type = self.ai_output_type
        generative_ai_model_type = self.generative_ai_model_type
        workspace = self.workspace

        context = HumanReadableRowContext(row, exclude_field_ids=[ai_field.id])
        message = str(
            resolve_formula(
                ai_field.ai_prompt, formula_runtime_function_registry, context
            )
        )

        # The AI output type should be able to format the prompt because it can add
        # additional instructions to it. The choice output type for example adds
        # additional prompt trying to force the output, for example.
        message = ai_output_type.format_prompt(message, ai_field)

        if self.use_file_fields:
            try:
                file_ids = AIFileManager.upload_files_from_file_field(
                    ai_field, row, generative_ai_model_type
                )
                value = generative_ai_model_type.prompt_with_files(
                    ai_field.ai_generative_ai_model,
                    message,
                    file_ids=file_ids,
                    workspace=workspace,
                    temperature=ai_field.ai_temperature,
                )
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
        # output when it's given. With the choice output type, it will try to
        # match it to a `SelectOption`, for example.
        value = ai_output_type.parse_output(value, ai_field)
        return value

    def handle_error(self, row: GeneratedTableModel, exc: Exception):
        """
        Error handling routine, if an error occurred during getting AI model response
        for a row.

        If an error occurs, this will stop processing any pending rows and will notify
        the frontend on a first occurrence of an error.

        :param row: A row on which the error occurred.
        :param exc: The exception that occurred.
        :return:
        """

        self.stop_scheduling_rows()

        if not self.has_errors:
            rows_ai_values_generation_error.send(
                self,
                user=self.user,
                rows=[row],
                field=self.ai_field,
                table=self.table,
                error_message=str(exc),
            )

        self.has_errors = True

    def update_value(self, row: GeneratedTableModel, value: Any):
        """
        Updates AI field value for the row with the value returned from the AI model.
        """

        self.row_handler.update_row_by_id(
            self.user,
            self.table,
            row.id,
            {self.ai_field.db_column: value},
            model=self.model,
            values_already_prepared=True,
        )

    def raise_if_error(self):
        """
        Checks if there was any error during the processing of rows with the AI model,
        and raises GenerativeAIPromptError exception..

        This should be called at the end of processing, to inform the caller that
        there was an error.
        """

        if self.has_errors:
            raise GenerativeAIPromptError(f"AI model responded with errors.")

    def process(self, rows: QuerySet[GeneratedTableModel]):
        """
        Generate AI model value for selected rows in parallel.

        This will call the AI model generator for several rows at once. Each row is
        processed in a separate thread, and the number of worker threads is fixed,
        controlled by AIField.ai_max_concurrent_generations value.

        When there an error occurs during the processing in a worker thread, it won't
        be propagated immediately. Instead, it's pushed to the queue and handled as a
        result for a specific row, but also an internal flag, that informs about the
        error, is set. No new rows should be scheduled after an error is received, but
        the loop will wait for already scheduled threads to finish. Because the flag
        is set, we can raise an appropriate exception at the end to inform the caller
        about the error.

        :param rows: An iterable of rows to generate values for.
        :return:
        :raise GenerativeAIPromptError: Raised at the end of processing, when at least
        one row failed.
        """

        rows_iter = iter(rows.iterator(chunk_size=200))

        with ThreadPoolExecutor(self.max_concurrency) as executor:
            while True:
                try:
                    # Allow to schedule only a limited number of futures, so we don't
                    # populate executor's backlog with an excessive amount of rows
                    # to process. We add new rows to process only if there's a
                    # 'free slot' in the executor.
                    while self.can_schedule_next():
                        self.schedule_next_row(rows_iter, executor)

                except StopIteration:
                    self.stop_scheduling_rows()

                try:
                    processed = self.results_queue.get(block=True, timeout=0.1)
                    row, result = processed
                    self.handle_result(row, result)

                # Queue is empty, no processed results available yet; continue polling.
                except Empty:
                    pass
                except Exception as e:
                    logger.opt(exception=e).error(f"Error when handing result: {e}")
                    self.stop_scheduling_rows()

                if self.is_finished():
                    break

        self.raise_if_error()

    def stop_scheduling_rows(self):
        """
        Sets internal flag to stop producing and scheduling new rows to process.
        """

        self.generate_more_rows = False

    def can_schedule_next(self) -> bool:
        """
        Returns True, if there's a free slot to process.
        """

        return self.generate_more_rows and len(self.in_process) < self.max_concurrency

    def is_finished(self) -> bool:
        """
        Returns true, if there's no rows left to process.
        """

        return not len(self.in_process) and not self.generate_more_rows

    def handle_result(self, row: GeneratedTableModel, result: Exception | Any):
        """
        An entry point to handle the result value for a row. The result may be an
        error or a correct result, so, depending on its type, it will be handled
        differently.

        A correct value will be stored for the row.

        The error will be stored and a signal may be emitted, so the frontend will
        know about the error. This will also stop processing new rows.

        In any case, we want to update internal progress state.

        :param row: The row for which result arrived.
        :param result: The result from the AI model.
        :return:
        """

        try:
            if isinstance(result, Exception):
                self.handle_error(row, result)
            else:
                self.update_value(row, result)
        finally:
            self.update_progress(row)

    def update_progress(self, row: GeneratedTableModel):
        """
        Update internal progress state.
        """

        self.finished += 1
        self.in_process.remove(row.id)
        if self.progress:
            self.progress.increment()

    def schedule_next_row(self, rows_iter: Iterator, executor: Executor):
        """
        Prepares and adds the next row to the work queue.
        """

        row = next(rows_iter)

        executor.submit(self.generate_value_for, row)
        self.in_process.add(row.id)
