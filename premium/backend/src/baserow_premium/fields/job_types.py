from collections.abc import Callable, Iterator
from concurrent.futures import Executor, ThreadPoolExecutor
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any, NamedTuple, Type

from django.contrib.auth.models import AbstractUser
from django.db.models import Exists, OuterRef, QuerySet

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
from baserow.contrib.database.rows.signals import rows_ai_values_generation_error
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.generative_ai.exceptions import (
    GenerativeAIPromptError,
    ModelDoesNotBelongToType,
    get_user_friendly_error_message,
)
from baserow.core.handler import CoreHandler
from baserow.core.job_types import _empty_transaction_context
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.registries import JobType
from baserow.core.utils import ChildProgressBuilder

from .exceptions import AIFieldEmptyPromptError
from .handler import AIFieldHandler
from .models import AIField, AIFieldScheduledUpdate, GenerateAIValuesJob


class AIValueUpdate(NamedTuple):
    row: Type[GeneratedTableModel]
    result: Any | Exception
    start_at: datetime
    end_at: datetime


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
        "is_auto_update",
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
        "is_auto_update": serializers.BooleanField(
            required=False,
            read_only=True,
            help_text="Indicates if the job has been created because values in a "
            "dependent field changed.",
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
        if job.row_ids or job.is_auto_update:
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

        baserow_field_type = ai_field.get_type().get_baserow_field_type(ai_field)
        model_field = baserow_field_type.get_model_field(ai_field)
        q = ai_field.get_type().empty_query(
            ai_field.db_column,
            model_field,
            ai_field,
        )
        return queryset.filter(q)

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
        prepared_values = {
            "field_id": ai_field.id,
        }

        AIFieldHandler.get_valid_model_type_or_raise(ai_field)

        if unsaved_job.mode == GenerateAIValuesJob.MODES.AUTO_UPDATE:
            if not AIFieldScheduledUpdate.objects.filter(field_id=ai_field.id).exists():
                raise ValueError("No rows scheduled for AI field auto update.")
            prepared_values["is_auto_update"] = True
        elif unsaved_job.mode == GenerateAIValuesJob.MODES.ROWS:
            found_rows_ids = (
                RowHandler().get_rows(model, req_row_ids).values_list("id", flat=True)
            )
            if len(found_rows_ids) != len(req_row_ids):
                raise RowDoesNotExist(
                    sorted(list(set(req_row_ids) - set(found_rows_ids)))
                )
            prepared_values["row_ids"] = req_row_ids
        elif unsaved_job.mode == GenerateAIValuesJob.MODES.VIEW:
            # Ensure the view exists in the table
            ViewHandler().get_view_as_user(user, view_id, table_id=ai_field.table.id)
            prepared_values["view_id"] = view_id

        prepared_values["only_empty"] = values.get("only_empty", False)

        return prepared_values

    def get_filters_serializer(self) -> Type[serializers.Serializer] | None:
        """
        Adds the ability to filter GenerateAIValuesJob by AI field ID.

        :return: A serializer class extending JobTypeFiltersSerializer.
        """

        from baserow_premium.api.fields.serializers import (
            GenerateAIValuesJobFiltersSerializer,
        )

        return GenerateAIValuesJobFiltersSerializer

    def run(self, job: GenerateAIValuesJob, progress):
        user = job.user

        ai_field = self._get_field(job.field_id)
        table = ai_field.table
        workspace = table.database.workspace
        model = table.get_model()
        row_handler = RowHandler()
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
        elif job.mode == GenerateAIValuesJob.MODES.AUTO_UPDATE:
            rows = model.objects.filter(
                Exists(
                    AIFieldScheduledUpdate.objects.filter(
                        field_id=ai_field.id, row_id=OuterRef("id")
                    )
                )
            )
        elif job.mode in {GenerateAIValuesJob.MODES.ROWS}:
            req_row_ids = job.row_ids
            rows = row_handler.get_rows(model, req_row_ids)
        else:
            raise ValueError(f"Unknown mode {job.mode} for GenerateAIValuesJob")

        if job.only_empty:
            rows = self._filter_empty_values(rows, ai_field)

        progress_builder = progress.create_child_builder(
            represents_progress=progress.total
        )

        rows_progress = ChildProgressBuilder.build(progress_builder, rows.count())

        def on_progress(value_update: AIValueUpdate):
            """
            Called when a row has been processed, and a result from AI model has been
            retrieved.

            This is called from AIValueGenerator, to inform that a row has been
            processed, and there's a specific result of that processing. If the value
            is an exception, that means the processing ended with an error.

            :param result: AIValueResult object with the row, result and timing
            information.
            """

            from baserow_premium.fields.tasks import (
                _schedule_generate_ai_value_generation,
            )

            rows_progress.increment()
            row = value_update.row
            start_at = value_update.start_at

            if isinstance(value_update.result, Exception):
                rows_ai_values_generation_error.send(
                    self,
                    user=user,
                    rows=[row],
                    field=ai_field,
                    table=table,
                    error_message=get_user_friendly_error_message(value_update.result),
                )
                return

            if job.is_auto_update:
                deleted_count, _ = AIFieldScheduledUpdate.objects.filter(
                    field_id=ai_field.id, row_id=row.id, updated_on__lte=start_at
                ).delete()
                # The scheduled update was removed or updated after the job
                # started, so we skip updating this row with an already outdated
                # value, and we renschedule generation for it.
                if deleted_count == 0:
                    _schedule_generate_ai_value_generation(field_id=ai_field.id)
                    return

            try:
                row_handler.update_row_by_id(
                    user,
                    table,
                    row.id,
                    {ai_field.db_column: value_update.result},
                    model=model,
                    values_already_prepared=True,
                )
            except RowDoesNotExist:
                # The row was trahsed during the generation and we cannot update
                # it, so we skip it.
                return

        generator = AIValueGenerator(user, ai_field, self, on_progress)
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
        on_progress: Callable[[AIValueUpdate], None] | None = None,
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
        self.error_msg = None

        self.row_handler = RowHandler()
        self.on_progress = on_progress

        self.prepare()

    def prepare(self):
        """
        Validates that the AI field's model configuration is still valid
        before processing begins. Sends an error signal and re-raises if the
        model is no longer available.
        """

        try:
            AIFieldHandler.get_valid_model_type_or_raise(self.ai_field)
        except ModelDoesNotBelongToType as exc:
            rows_ai_values_generation_error.send(
                self.signal_sender,
                user=self.user,
                rows=[],
                field=self.ai_field,
                table=self.ai_field.table,
                error_message=get_user_friendly_error_message(exc),
            )
            raise exc

    def generate_value_for(self, row: GeneratedTableModel):
        """
        Runs value generation for a single row using AI model.

        The contents of the method should prepare and run a prompt on a model for the
        row. This method doesn't return any value. Instead, the result, or any error
        that will happen during the processing, will be put on a results queue.

        :param row: A row to generate value for.
        """

        start = datetime.now(tz=timezone.utc)
        try:
            result = AIFieldHandler.generate_value_with_ai(self.ai_field, row)
        except AIFieldEmptyPromptError:
            # Empty prompt — preserve existing value.
            result = getattr(row, self.ai_field.db_column, None)
        except Exception as exc:
            logger.exception(f"Value generation for row {row} failed: {exc}")
            result = exc

        end = datetime.now(tz=timezone.utc)
        self.results_queue.put(
            AIValueUpdate(row, result, start, end),
            block=True,
        )

    def handle_error(self, error_message: str):
        """
        Error handling routine, if an error occurred during getting AI model response
        for a row.

        If an error occurs, this will stop processing any pending rows and will notify
        the frontend on a first occurrence of an error.

        :param error_message: The exception message to log and send with the signal.
        """

        self.stop_scheduling_rows()
        self.error_msg = error_message

    def raise_if_error(self):
        """
        Checks if there was any error during the processing of rows with the AI model,
        and raises GenerativeAIPromptError exception..

        This should be called at the end of processing, to inform the caller that
        there was an error.
        """

        if self.error_msg:
            raise GenerativeAIPromptError(self.error_msg)

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
                    processed = self.results_queue.get(block=True, timeout=0.01)
                    self.handle_result(processed)

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

    def handle_result(self, result: AIValueUpdate):
        """
        An entry point to handle the result value for a row. The result may be an
        error or a correct result, so, depending on its type, it will be handled
        differently.

        This will update a local state and pass the result to a callback, so the caller
        can decide how to handle the result.

        :param result: An AIValueResult object with the result.
        """

        if isinstance(result.result, Exception):
            exc = result.result
            self.handle_error(str(exc))

        self.finished += 1
        self.in_process.remove(result.row.id)
        if self.on_progress:
            try:
                self.on_progress(result)
            except Exception as exc:
                self.handle_error(str(exc))

    def schedule_next_row(self, rows_iter: Iterator, executor: Executor):
        """
        Prepares and adds the next row to the work queue.
        """

        row = next(rows_iter)
        executor.submit(self.generate_value_for, row)
        self.in_process.add(row.id)
