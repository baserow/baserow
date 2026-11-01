import time
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional, Type

from django.db import router, transaction
from django.db.models import Q

from celery_singleton import DuplicateTaskError
from django_cte import With
from loguru import logger

from baserow.celery_singleton_backend import SingletonAutoRescheduleFlag
from baserow.core.registry import Instance, Registry

from .models import AbstractPendingSearchDataUpdate

if TYPE_CHECKING:
    from celery import Task

    from baserow.contrib.database.table.models import Table


class SearchDataUpdaterType(Instance):
    """
    Keeps search data of cell values up to date, like the full-text search data.
    Changed cells are queued in `queue_model`, and processed in the background by
    `get_update_task`. Every type has its own queue and task, so that a slow type
    never delays another.
    """

    queue_model: Type[AbstractPendingSearchDataUpdate]
    # Must be unique per type, because it's also used by tasks of the running
    # version during a deploy.
    reschedule_flag_key_prefix: str
    # Balances the cost of one update query against the work redone after a failure.
    full_field_batch_size = 1
    row_batch_size = 1000
    # Whether processing the updates of all rows of a field also covers the pending
    # updates of single cells of that field. Not the case if the rows are processed
    # over multiple runs, because a cell can change after its row was processed.
    full_field_updates_cover_row_updates = True
    # Processes a batch and deletes its pending updates in one transaction. Not
    # possible for types that call external services, because a transaction must
    # not stay open during their requests.
    atomic_batches = False

    def get_update_task(self) -> "Task":
        """
        :return: The singleton task per table that calls `update`.
        """

        raise NotImplementedError

    def get_throttle_seconds(self) -> int:
        """
        :return: How many seconds changes are collected before they're processed.
        """

        return 0

    def get_time_budget_seconds(self) -> int:
        """
        :return: How many seconds the update task processes updates before it
            continues in a new task, which must be shorter than its time limit.
        """

        raise NotImplementedError

    def should_queue(self) -> bool:
        """
        :return: Whether changes must be queued, for example False if the type is
            disabled on this instance.
        """

        return True

    def get_queued_field_ids(
        self, table: "Table", field_ids: list[int] | None
    ) -> list[int]:
        """
        :param table: The table of the changed fields.
        :param field_ids: The changed fields, or None if all fields changed.
        :return: The changed fields of which this type keeps the search data.
        """

        raise NotImplementedError

    def prepare(self, table: "Table") -> bool:
        """
        Called before the pending updates of the table are processed.

        :param table: The table of which the pending updates are processed.
        :return: Whether they can be processed. If not, they're kept.
        """

        return True

    def process_full_field_updates(
        self,
        table: "Table",
        updates: list[AbstractPendingSearchDataUpdate],
        check_timestamp: datetime,
        deadline: Optional[float],
    ) -> bool:
        """
        Updates the search data of all rows of the fields of the updates.

        :param table: The table of the fields.
        :param updates: The pending updates of all rows of a field.
        :param check_timestamp: Updates queued after this moment are kept.
        :param deadline: The `time.monotonic()` after which no new batch is started.
        :return: Whether all rows were updated. If not, the updates are kept so that
            they continue in a next run.
        """

        raise NotImplementedError

    def process_row_updates(
        self,
        table: "Table",
        updates: list[AbstractPendingSearchDataUpdate],
        deadline: Optional[float],
    ) -> int:
        """
        Updates the search data of the cells of the updates, in order.

        :param table: The table of the cells.
        :param updates: The pending updates of single cells, sorted by field and row.
        :param deadline: The `time.monotonic()` after which no new batch is started.
        :return: The number of processed updates. The remaining ones are kept.
        """

        raise NotImplementedError

    def get_retry_countdown(self, table: "Table", exception: Exception) -> int | None:
        """
        :param table: The table of which the updates failed.
        :param exception: The exception that was raised while processing them.
        :return: The seconds after which the updates are retried if the exception
            is temporary, for example if an external service is unavailable. None
            raises the exception.
        """

        return None

    def queue(
        self,
        table: "Table",
        field_ids: list[int] | None = None,
        row_ids: list[int] | None = None,
    ) -> bool:
        """
        :param table: The table of the changed cells.
        :param field_ids: The changed fields, or None if all fields changed.
        :param row_ids: The changed rows, or None if all rows changed.
        :return: Whether anything was queued.
        """

        field_ids = self.get_queued_field_ids(table, field_ids)
        if not field_ids:
            return False
        self.queue_pending_updates(field_ids, row_ids)
        return True

    def queue_pending_updates(
        self, field_ids: list[int], row_ids: list[int] | None = None, **values: Any
    ):
        """
        :param field_ids: The fields of which the search data must be updated.
        :param row_ids: The rows of which the search data must be updated, or None
            to update all rows.
        :param values: Extra values of the pending updates, which also replace the
            values of updates that were already queued.
        """

        # Ordered to avoid deadlocks when updating the same cells.
        self.queue_model.objects.bulk_create(
            [
                self.queue_model(field_id=field_id, row_id=row_id, **values)
                for field_id in sorted(set(field_ids))
                for row_id in sorted(set(row_ids or [None]))
            ],
            update_conflicts=True,
            unique_fields=["field_id", "row_id"],
            update_fields=["updated_on", *values],
            batch_size=1000,
        )

    def _get_reschedule_flag(self, table_id: int) -> SingletonAutoRescheduleFlag:
        return SingletonAutoRescheduleFlag(
            f"{self.reschedule_flag_key_prefix}_{table_id}"
        )

    def has_pending_updates(self, table_id: int) -> bool:
        """
        :param table_id: The table that's checked.
        :return: Whether the update task must run for the table.
        """

        from baserow.contrib.database.fields.models import Field

        return self.queue_model.objects.filter(
            field_id__in=Field.objects_and_trash.filter(table_id=table_id).values("id")
        ).exists()

    def schedule(self, table_id: int, new_pending_updates: bool = True):
        """
        Starts the update task of the table after the throttle.

        :param table_id: The table of which the pending updates are processed.
        :param new_pending_updates: Whether updates were queued that a running task
            may not have seen, so that it runs again when it's finished.
        """

        try:
            self.get_update_task().apply_async(
                (table_id,), countdown=self.get_throttle_seconds()
            )
        except DuplicateTaskError:
            # The running task processes the new updates when it finishes.
            if new_pending_updates:
                self._get_reschedule_flag(table_id).set()

    def _reschedule(self, table_id: int, countdown: int = 0):
        from .tasks import schedule_search_data_updater_task

        # Through another task, because the update task can't be scheduled while it
        # still runs.
        schedule_search_data_updater_task.apply_async(
            (self.type, table_id), countdown=countdown
        )

    def update(self, table_id: int):
        """
        The body of the update task.

        :param table_id: The table of which the pending updates are processed.
        :raises Exception: Any exception of processing for which
            `get_retry_countdown` returns None.
        """

        from baserow.contrib.database.table.exceptions import TableDoesNotExist
        from baserow.contrib.database.table.handler import TableHandler

        try:
            table = TableHandler().get_table(table_id)
        except TableDoesNotExist:
            logger.warning(f"Table with id {table_id} doesn't exist.")
            return
        if not self.prepare(table):
            return

        # Updates queued from now on reschedule this task when it's finished.
        flag = self._get_reschedule_flag(table_id)
        flag.clear()
        try:
            completed = self.process_pending_updates(
                table, time.monotonic() + self.get_time_budget_seconds()
            )
        except Exception as exception:
            countdown = self.get_retry_countdown(table, exception)
            if countdown is None:
                raise
            self._reschedule(table_id, countdown)
            return

        if not completed or flag.is_set():
            self._reschedule(table_id)

    def process_pending_updates(
        self, table: "Table", deadline: Optional[float] = None
    ) -> bool:
        """
        Processes the updates of all rows of a field first, because they can also
        cover the updates of single cells of that field.

        :param table: The table of which the pending updates are processed.
        :param deadline: The `time.monotonic()` after which no new batch is started.
        :return: Whether all pending updates were processed.
        """

        from baserow.contrib.database.fields.models import Field

        def deadline_passed() -> bool:
            return deadline is not None and time.monotonic() > deadline

        table_field_ids = list(
            Field.objects_and_trash.filter(table=table)
            .order_by()
            .values_list("id", flat=True)
        )
        pending_updates = self.queue_model.objects.filter(
            field_id__in=table_field_ids
        ).order_by()

        last = False
        while not last:
            if deadline_passed():
                logger.info(
                    "Time budget exhausted for table {} during full-field updates.",
                    table.id,
                )
                return False
            with self._batch_transaction():
                updates = list(
                    pending_updates.filter(row_id=None)[: self.full_field_batch_size]
                )
                # Only delete updates older than this timestamp to avoid loosing
                # newer updates made while processing.
                check_timestamp = datetime.now(tz=timezone.utc)
                last = len(updates) < self.full_field_batch_size
                if not updates:
                    break
                if not self.process_full_field_updates(
                    table, updates, check_timestamp, deadline
                ):
                    return False
                covered_updates = (
                    Q(field_id__in=[update.field_id for update in updates])
                    if self.full_field_updates_cover_row_updates
                    else Q(id__in=[update.id for update in updates])
                )
                self._delete_pending_updates(
                    covered_updates & Q(updated_on__lte=check_timestamp)
                )

        last = False
        while not last:
            if deadline_passed():
                logger.info(
                    "Time budget exhausted for table {} during row updates.",
                    table.id,
                )
                return False
            with self._batch_transaction():
                # Sorted here instead of by the query, which then doesn't have to
                # sort a possibly large queue.
                updates = sorted(
                    pending_updates.filter(row_id__isnull=False)[: self.row_batch_size],
                    key=lambda update: (update.field_id, update.row_id),
                )
                check_timestamp = datetime.now(tz=timezone.utc)
                last = len(updates) < self.row_batch_size
                if not updates:
                    break
                processed = self.process_row_updates(table, updates, deadline)
                self._delete_pending_updates(
                    Q(
                        id__in=[update.id for update in updates[:processed]],
                        updated_on__lte=check_timestamp,
                    )
                )
            if processed < len(updates):
                return False

        return True

    def _batch_transaction(self):
        return transaction.atomic() if self.atomic_batches else nullcontext()

    def _delete_pending_updates(self, q: Q):
        self.queue_model.objects.filter(q)._raw_delete(
            using=router.db_for_write(self.queue_model)
        )

    def get_table_ids_with_pending_updates(self) -> list[int]:
        """
        :return: The tables of which the update task must run, used to restart
            lost tasks.
        """

        from baserow.contrib.database.fields.models import Field

        cte = With(self.queue_model.objects.values("field_id").distinct())
        return list(
            cte.join(
                Field.objects_and_trash.filter(
                    table__database__workspace_id__isnull=False
                ),
                id=cte.col.field_id,
            )
            .with_cte(cte)
            .values_list("table_id", flat=True)
            .distinct()
        )


class SearchDataUpdaterTypeRegistry(Registry[SearchDataUpdaterType]):
    name = "search_data_updater"


search_data_updater_registry = SearchDataUpdaterTypeRegistry()
