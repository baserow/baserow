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
    LEASE_DURATION,
    NOT_STARTED_AFTER,
    RUN_RETENTION,
    SWEEP_BATCH_SIZE,
    SWEEP_INTERVAL,
    USER_RUNS_LOCK_NAMESPACE,
    WAITING_WARNING_AFTER,
    WORKSPACE_RUNS_LOCK_NAMESPACE,
    ChatRunErrorCode,
    ChatRunEventKind,
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


class ChatRunHandler:
    """Synchronous lifecycle operations shared by HTTP requests and Celery tasks.

    Product code calls ``start_run`` while saving the user's message. Its commit
    callbacks publish the initial event and enqueue work in that caller's process.
    ``execute_chat_run`` then calls ``claim_run`` in a Celery worker; its runner
    uses ``renew_lease`` and ``finish_run`` through synchronous database bridges.
    HTTP reads/cancellation arrive through ``ChatRunService``. The separate sweep
    and prune Celery tasks call the recovery and retention methods below.

    Run state uses the primary database. Redis output is read/published outside
    database transactions; this handler never executes the product's AI work.
    """

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
        """Call inside the transaction saving the triggering product message.

        :param run_type: The registered type of the run.
        :param chat_id: The product chat the run answers.
        :param workspace: The workspace the run belongs to.
        :param created_by: The user who sent the message, or None for a system run:
            no per-user limit applies, the workspace limit still does.
        :param context: The product data the run needs.
        :raises ChatRunAlreadyActive: When the chat already has an active run.
        :raises ChatRunLimitReached: When the user or the workspace already has the
            maximum number of active runs of this type.
        :return: The new queued run.
        """

        kind = chat_run_type_registry.get(run_type)
        user_limit = kind.get_max_active_runs_per_user() if created_by else None
        workspace_limit = kind.get_max_active_runs_per_workspace()
        with transaction.atomic():
            # A fixed lock order keeps concurrent sends from deadlocking.
            if workspace_limit is not None:
                self._lock_runs(WORKSPACE_RUNS_LOCK_NAMESPACE, workspace.id)
            if user_limit is not None:
                self._lock_runs(USER_RUNS_LOCK_NAMESPACE, created_by.id)
            active_id = self._active_run_id(run_type, chat_id)
            if active_id:
                raise ChatRunAlreadyActive(active_id)
            active_runs = self.runs.filter(
                run_type=run_type, status__in=ACTIVE_CHAT_RUN_STATUSES
            )
            limits = [
                (user_limit, active_runs.filter(created_by=created_by)),
                (workspace_limit, active_runs.filter(workspace=workspace)),
            ]
            if any(
                limit is not None and runs.count() >= limit for limit, runs in limits
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
        """Create a run in the product request's message-saving transaction.

        After that transaction commits, callbacks in the request process publish
        ``run.created`` and call ``execute_chat_run.delay``. The Celery worker
        executes the run independently of this request's streaming response.
        """

        run = self.create_run(run_type, chat_id, workspace, created_by, context)
        # Publication is best effort, and cannot prevent the enqueue callback.
        transaction.on_commit(
            lambda: self._publish(
                run, [(ChatRunEventKind.RUN_CREATED, created_event_data)]
            ),
            robust=True,
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
            # A request thread would otherwise reuse the HTTP loop and cleanup
            # would close pools still serving other followers. Own this loop.
            async_to_sync(publish, force_new_loop=True)()
        except Exception as exc:
            logger.warning(
                "Chat run {} output unavailable ({})", run.id, type(exc).__name__
            )

    def _publish_terminal(self, run: ChatRun) -> None:
        from .service import serialize_run

        try:
            snapshot = serialize_run(run)
        except Exception as exc:
            logger.warning(
                "Terminal output unavailable for {} ({})", run.id, type(exc).__name__
            )
            return
        self._publish(run, [(ChatRunEventKind.RUN_FINISHED, snapshot)])

    def _enqueue(self, run_id: UUID) -> None:
        """Send the task from ``start_run``'s commit callback; do not execute it."""

        from .tasks import execute_chat_run

        try:
            execute_chat_run.delay(str(run_id))
        except Exception as exc:
            logger.error(
                "Could not enqueue chat run {} ({})", run_id, type(exc).__name__
            )
            self.fail_not_started_run(run_id)

    def _lock_runs(self, namespace: int, key: int) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [namespace, key])

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
        """Called by ``execute_chat_run`` before starting its async runner.

        Overdue runs are left to the not-started sweep, so a worker returning
        after an outage never answers a prompt the user gave up on.
        """

        now = timezone.now()
        if not self.runs.filter(
            id=run_id,
            status=ChatRunStatus.QUEUED,
            created_on__gte=now - NOT_STARTED_AFTER,
        ).update(
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
        """Called through a sync bridge by the worker's journal keep-alive loop."""

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
        """Called by the HTTP service; running workers observe Stop on renewal."""

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
        """End a claimed run from the worker's synchronous finalization section.

        Commit alongside product output; caller locks the run before product rows.
        ``execute_chat_run`` also uses this when the adapter type is unavailable.
        """

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
        """Called by ``sweep_chat_runs`` to end runs with expired worker leases."""

        now = timezone.now()
        run_ids = self.runs.filter(
            status=ChatRunStatus.RUNNING, lease_expires_at__lt=now
        ).values_list("id", flat=True)[:SWEEP_BATCH_SIZE]
        ended = 0
        for run_id in run_ids:
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
            # As in _publish, cleanup must only close this call's own pools.
            return async_to_sync(recover, force_new_loop=True)()
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
                ChatRunErrorCode.INTERRUPTED,
                lambda kind: kind.on_run_lost(run, events),
            )
        return True

    def fail_not_started_run(self, run_id: UUID) -> bool:
        """End queued work after enqueue failure or from the Celery sweeper."""

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
                ChatRunErrorCode.NOT_STARTED,
                lambda kind: kind.on_run_not_started(run),
            )
        return True

    def fail_not_started_runs(self) -> int:
        """Called by ``sweep_chat_runs`` for work left queued beyond its timeout."""

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

    def prune(self) -> bool:
        """Delete one page of expired runs, warning once for incomplete ones.

        Called by the ``prune_chat_runs`` Celery task. Product warning hooks run
        synchronously in that task, and the run is deleted even if its hook fails.

        :return: Whether the page was full, so more expired runs may remain.
        """

        page_ids = list(
            self.runs.filter(finished_on__lt=timezone.now() - RUN_RETENTION)
            .order_by("finished_on")
            .values_list("id", flat=True)[:SWEEP_BATCH_SIZE]
        )
        page = self.runs.filter(id__in=page_ids)
        started = Q(started_on__isnull=False)
        for run in page.filter(started & ~Q(status=ChatRunStatus.COMPLETED)):
            try:
                with transaction.atomic():
                    kind = chat_run_type_registry.get(run.run_type)
                    kind.ensure_interruption_warning(run)
            except Exception as exc:
                logger.error(
                    "Could not preserve the warning of chat run {} ({})",
                    run.id,
                    type(exc).__name__,
                )
        page.delete()
        return len(page_ids) == SWEEP_BATCH_SIZE
