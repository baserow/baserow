import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, IntegrityError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from asgiref.sync import async_to_sync
from loguru import logger

from baserow.core.models import Workspace

from .constants import (
    ERROR_INTERRUPTED,
    ERROR_NOT_STARTED,
    LEASE_DURATION,
    MAX_ACTIVE_RUNS_PER_USER,
    NOT_STARTED_AFTER,
    RUN_CREATED,
    RUN_RETENTION,
    SWEEP_BATCH_SIZE,
    SWEEP_INTERVAL,
    USER_RUNS_LOCK_NAMESPACE,
    WAITING_WARNING_AFTER,
)
from .exceptions import ChatRunAlreadyActive, ChatRunDoesNotExist, ChatRunLimitReached
from .models import ACTIVE_CHAT_RUN_STATUSES, ChatRun, ChatRunStatus
from .push import notify_run_on_commit
from .registries import ChatRunType, chat_run_type_registry
from .telemetry import record_run_claimed, record_run_finished


@dataclass(frozen=True)
class LeaseRenewal:
    alive: bool
    cancel_requested: bool


@dataclass(frozen=True)
class PruneCursor:
    finished_on: datetime
    run_id: UUID


class ChatRunHandler:
    """Primary-backed lifecycle; output never participates in a DB transaction."""

    @property
    def runs(self):
        return ChatRun.objects.using(DEFAULT_DB_ALIAS)

    def create_run(
        self,
        run_type: str,
        chat_id: int,
        workspace: Workspace,
        created_by: AbstractUser | None,
        context: dict[str, Any],
    ) -> ChatRun:
        """Call inside the transaction saving the triggering product message."""

        with transaction.atomic():
            if created_by is not None:
                self._lock_user_runs(created_by.id)
            active_id = self._active_run_id(run_type, chat_id)
            if active_id:
                raise ChatRunAlreadyActive(active_id)
            if (
                created_by is not None
                and self.runs.filter(
                    created_by=created_by, status__in=ACTIVE_CHAT_RUN_STATUSES
                ).count()
                >= MAX_ACTIVE_RUNS_PER_USER
            ):
                raise ChatRunLimitReached()
            run = ChatRun(
                run_type=run_type,
                chat_id=chat_id,
                workspace=workspace,
                created_by=created_by,
                context=context,
            )
            try:
                with transaction.atomic():
                    run.save(force_insert=True, using=DEFAULT_DB_ALIAS)
            except IntegrityError:
                active_id = self._active_run_id(run_type, chat_id)
                if active_id:
                    raise ChatRunAlreadyActive(active_id) from None
                run.save(force_insert=True, using=DEFAULT_DB_ALIAS)
        return run

    def start_run(
        self,
        run_type: str,
        chat_id: int,
        workspace: Workspace,
        created_by: AbstractUser | None,
        context: dict[str, Any],
        created_event_data: dict[str, Any],
    ) -> ChatRun:
        run = self.create_run(run_type, chat_id, workspace, created_by, context)
        # Publication is best effort, and cannot prevent the enqueue callback.
        transaction.on_commit(
            lambda: self._publish(run, [(RUN_CREATED, created_event_data)]), robust=True
        )
        notify_run_on_commit(run)
        transaction.on_commit(lambda: self._enqueue(run.id), robust=True)
        return run

    def _publish(self, run: ChatRun, events: list[tuple[str, dict]]) -> None:
        from .buffer import ChatRunBuffer, close_buffer_redis

        async def publish():
            try:
                await ChatRunBuffer(run.id).append(events)
            finally:
                await close_buffer_redis()

        try:
            async_to_sync(publish)()
        except Exception as exc:
            logger.warning(
                "Chat run {} output unavailable ({})", run.id, type(exc).__name__
            )

    def _publish_terminal(self, run: ChatRun) -> None:
        from .buffer import ChatRunBuffer, close_buffer_redis
        from .constants import RUN_FINISHED
        from .service import serialize_run

        async def publish():
            try:
                buffer = ChatRunBuffer(run.id)
                await buffer.append([(RUN_FINISHED, snapshot)])
                await buffer.finish()
            finally:
                await close_buffer_redis()

        try:
            snapshot = serialize_run(run)
            async_to_sync(publish)()
        except Exception as exc:
            logger.warning(
                "Terminal output unavailable for {} ({})", run.id, type(exc).__name__
            )

    def _enqueue(self, run_id: UUID) -> None:
        from .tasks import execute_chat_run

        try:
            execute_chat_run.delay(str(run_id))
        except Exception as exc:
            logger.error(
                "Could not enqueue chat run {} ({})", run_id, type(exc).__name__
            )
            self.fail_not_started_run(run_id)

    def _lock_user_runs(self, user_id: int) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [USER_RUNS_LOCK_NAMESPACE, user_id],
            )

    def _active_run_id(self, run_type: str, chat_id: int) -> UUID | None:
        return (
            self.runs.filter(
                run_type=run_type, chat_id=chat_id, status__in=ACTIVE_CHAT_RUN_STATUSES
            )
            .values_list("id", flat=True)
            .first()
        )

    def get_active_run(self, run_type: str, chat_id: int) -> ChatRun | None:
        return self.runs.filter(
            run_type=run_type, chat_id=chat_id, status__in=ACTIVE_CHAT_RUN_STATUSES
        ).first()

    def get_run(self, run_id: UUID) -> ChatRun:
        run = self.runs.filter(id=run_id).first()
        if run is None:
            raise ChatRunDoesNotExist()
        return run

    def claim_run(self, run_id: UUID) -> ChatRun | None:
        now = timezone.now()
        if not self.runs.filter(id=run_id, status=ChatRunStatus.QUEUED).update(
            status=ChatRunStatus.RUNNING,
            started_on=now,
            lease_expires_at=now + LEASE_DURATION,
        ):
            return None
        run = self.get_run(run_id)
        record_run_claimed(run)
        notify_run_on_commit(run)
        return run

    def renew_lease(self, run_id: UUID) -> LeaseRenewal:
        renewed = self.runs.filter(id=run_id, status=ChatRunStatus.RUNNING).update(
            lease_expires_at=timezone.now() + LEASE_DURATION
        )
        requested = (
            self.runs.filter(id=run_id)
            .values_list("cancel_requested_at", flat=True)
            .first()
            if renewed
            else None
        )
        return LeaseRenewal(bool(renewed), requested is not None)

    def request_cancel(self, run_id: UUID) -> ChatRunStatus:
        with transaction.atomic():
            run = self.runs.select_for_update().filter(id=run_id).first()
            if run is None:
                raise ChatRunDoesNotExist()
            if run.status == ChatRunStatus.QUEUED:
                self._end_without_worker(
                    run,
                    ChatRunStatus.CANCELLED,
                    "",
                    lambda kind: kind.on_run_not_started(run),
                )
            elif run.status == ChatRunStatus.RUNNING and not run.cancel_requested_at:
                run.cancel_requested_at = timezone.now()
                run.save(update_fields=["cancel_requested_at"])
                notify_run_on_commit(run)
            return ChatRunStatus(run.status)

    def lock_running_run(self, run_id: UUID) -> bool:
        return (
            self.runs.select_for_update()
            .filter(id=run_id, status=ChatRunStatus.RUNNING)
            .exists()
        )

    def finish_run(
        self,
        run_id: UUID,
        status: ChatRunStatus,
        error_code: str = "",
        message: dict | None = None,
    ) -> bool:
        """Commit alongside product output; caller locks the run before product rows."""

        status = ChatRunStatus(status)
        if status in ACTIVE_CHAT_RUN_STATUSES:
            raise ValueError(f"{status} is not a final status.")
        json.dumps(message, allow_nan=False)
        with transaction.atomic():
            if not self.runs.filter(id=run_id, status=ChatRunStatus.RUNNING).update(
                status=status,
                error_code=error_code,
                outcome=message,
                finished_on=timezone.now(),
                lease_expires_at=None,
            ):
                return False
            run = self.get_run(run_id)
            notify_run_on_commit(run)
            transaction.on_commit(
                lambda: record_run_finished(run.run_type, str(status), error_code),
                robust=True,
            )
        return True

    def _end_without_worker(
        self,
        run: ChatRun,
        status: ChatRunStatus,
        error_code: str,
        hook: Callable[[ChatRunType], dict | None],
    ) -> None:
        """The caller owns the run lock. Hook failures cannot leave work active."""

        run.status = status
        run.error_code = error_code
        run.finished_on = timezone.now()
        run.lease_expires_at = None
        message = None
        try:
            with transaction.atomic():
                message = hook(chat_run_type_registry.get(run.run_type))
                json.dumps(message, allow_nan=False)
        except Exception as exc:
            message = None
            logger.error(
                "Could not save the answer of chat run {} ({})",
                run.id,
                type(exc).__name__,
            )
        run.outcome = message
        run.save(
            update_fields=[
                "status",
                "error_code",
                "finished_on",
                "lease_expires_at",
                "outcome",
            ]
        )
        notify_run_on_commit(run)
        transaction.on_commit(lambda: self._publish_terminal(run), robust=True)
        transaction.on_commit(
            lambda: record_run_finished(run.run_type, str(status), error_code),
            robust=True,
        )

    def finalize_lost_runs(self) -> int:
        now = timezone.now()
        ids = list(
            self.runs.filter(
                status=ChatRunStatus.RUNNING, lease_expires_at__lt=now
            ).values_list("id", flat=True)[:SWEEP_BATCH_SIZE]
        )
        ended = 0
        for run_id in ids:
            try:
                ended += self._finalize_lost_run(run_id, now)
            except Exception as exc:
                logger.error(
                    "Could not end lost chat run {} ({})", run_id, type(exc).__name__
                )
        return ended

    def _recover_output(self, run_id: UUID) -> list[dict] | None:
        from .buffer import ChatRunBuffer, close_buffer_redis

        async def recover():
            try:
                return await ChatRunBuffer(run_id).recover()
            finally:
                await close_buffer_redis()

        try:
            return async_to_sync(recover)()
        except Exception as exc:
            logger.warning(
                "Partial output unavailable for {} ({})", run_id, type(exc).__name__
            )
            return None

    def _finalize_lost_run(self, run_id: UUID, now: datetime) -> bool:
        # No DB transaction or row lock while Redis is read. Recheck expiry below:
        # a healthy worker may have renewed or committed during that bounded read.
        events = self._recover_output(run_id)
        with transaction.atomic():
            run = (
                self.runs.select_for_update()
                .filter(
                    id=run_id, status=ChatRunStatus.RUNNING, lease_expires_at__lt=now
                )
                .first()
            )
            if run is None:
                return False
            self._end_without_worker(
                run,
                ChatRunStatus.CANCELLED
                if run.cancel_requested_at
                else ChatRunStatus.FAILED,
                ERROR_INTERRUPTED,
                lambda kind: kind.on_run_lost(run, events),
            )
        return True

    def fail_not_started_run(self, run_id: UUID) -> bool:
        with transaction.atomic():
            run = (
                self.runs.select_for_update()
                .filter(id=run_id, status=ChatRunStatus.QUEUED)
                .first()
            )
            if run is None:
                return False
            self._end_without_worker(
                run,
                ChatRunStatus.FAILED,
                ERROR_NOT_STARTED,
                lambda kind: kind.on_run_not_started(run),
            )
        return True

    def fail_not_started_runs(self) -> int:
        ids = list(
            self.runs.filter(
                status=ChatRunStatus.QUEUED,
                created_on__lt=timezone.now() - NOT_STARTED_AFTER,
            ).values_list("id", flat=True)[:SWEEP_BATCH_SIZE]
        )
        failed = 0
        for run_id in ids:
            try:
                failed += self.fail_not_started_run(run_id)
            except Exception as exc:
                logger.error(
                    "Could not fail queued chat run {} ({})", run_id, type(exc).__name__
                )
        return failed

    def count_runs_newly_waiting_too_long(self) -> int:
        threshold = timezone.now() - WAITING_WARNING_AFTER
        return self.runs.filter(
            status=ChatRunStatus.QUEUED,
            created_on__lt=threshold,
            created_on__gte=threshold - SWEEP_INTERVAL,
        ).count()

    def prune(
        self, before: datetime | None = None, after: PruneCursor | None = None
    ) -> PruneCursor | None:
        """Prune one bounded page, moving past warnings that must be retained.

        :param before: Fixed retention cutoff for this sweep and its continuations.
        :param after: Last inspected row, including one that could not be deleted.
        :return: A cursor for the next page, or None when the sweep is finished.
        """

        candidates = self.runs.filter(
            finished_on__lt=before or timezone.now() - RUN_RETENTION
        )
        if after is not None:
            candidates = candidates.filter(
                Q(finished_on__gt=after.finished_on)
                | Q(finished_on=after.finished_on, id__gt=after.run_id)
            )
        rows = list(
            candidates.order_by("finished_on", "id").values_list("id", "finished_on")[
                : SWEEP_BATCH_SIZE + 1
            ]
        )
        for run_id, _ in rows[:SWEEP_BATCH_SIZE]:
            try:
                with transaction.atomic():
                    # Completed rows need no output/context blobs to be deleted.
                    # Another pruning task may already have deleted this row.
                    run = (
                        self.runs.select_for_update()
                        .defer("outcome", "context")
                        .filter(id=run_id)
                        .first()
                    )
                    if run is None:
                        continue
                    if run.started_on and run.status != ChatRunStatus.COMPLETED:
                        kind = chat_run_type_registry.get(run.run_type)
                        if not kind.ensure_interruption_warning(run):
                            continue
                    run.delete()
            except Exception as exc:
                logger.error(
                    "Could not safely prune chat run {} ({})",
                    run_id,
                    type(exc).__name__,
                )
        if len(rows) > SWEEP_BATCH_SIZE:
            run_id, finished_on = rows[SWEEP_BATCH_SIZE - 1]
            return PruneCursor(finished_on, run_id)
        return None
