from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS

from baserow.config.db_routers import set_db_alias

from .exceptions import ChatRunDoesNotExist
from .handler import ChatRunHandler
from .models import ChatRun, ChatRunStatus
from .registries import chat_run_type_registry


def serialize_run(run: ChatRun) -> dict:
    """Serialize saved state for HTTP snapshots and worker completion events.

    Calls the adapter's synchronous ``serialize_outcome`` hook in the caller's
    context; it neither executes work nor reads the temporary Redis output.
    """

    try:
        message = chat_run_type_registry.get(run.run_type).serialize_outcome(run)
    except chat_run_type_registry.does_not_exist_exception_class:
        message = run.outcome
    return {
        "id": str(run.id),
        "run_type": run.run_type,
        "chat_id": run.chat_id,
        "status": str(run.status),
        "error_code": run.error_code,
        "cancel_requested_at": (
            run.cancel_requested_at.isoformat() if run.cancel_requested_at else None
        ),
        "message": message,
    }


class ChatRunService:
    """Permission-checked HTTP access to the synchronous lifecycle handler.

    Status, cancel and stream views call this service directly. The stream view
    passes the run it read to ``follow_run``, which calls ``snapshot`` through its
    synchronous database bridge only when a stream opens without it. Later status
    reads bypass this service. Reading and cancelling use independent adapter
    permission hooks; none of these calls executes the run's AI work.
    """

    def get_run(self, user: AbstractUser, run_id: UUID, *, cancel=False) -> ChatRun:
        # Adapters and permission managers must use the same primary as the run:
        # a just-created chat or a revoked membership may not exist on a replica yet.
        set_db_alias(DEFAULT_DB_ALIAS)
        run = ChatRunHandler().get_run(run_id)
        try:
            kind = chat_run_type_registry.get(run.run_type)
        except chat_run_type_registry.does_not_exist_exception_class:
            raise ChatRunDoesNotExist() from None
        if not (kind.can_cancel(user, run) if cancel else kind.can_read(user, run)):
            raise ChatRunDoesNotExist()
        return run

    def snapshot(self, user: AbstractUser, run_id: UUID) -> dict:
        return serialize_run(self.get_run(user, run_id))

    def request_cancel(self, user: AbstractUser, run_id: UUID) -> ChatRunStatus:
        self.get_run(user, run_id, cancel=True)
        return ChatRunHandler().request_cancel(run_id)
