from datetime import timedelta
from enum import StrEnum


class ChatRunEventKind(StrEnum):
    """Kinds of the output events the engine emits. Run types may add their own."""

    RUN_CREATED = "run.created"
    RUN_STARTED = "run.started"
    TEXT_DELTA = "text.delta"
    PROGRESS = "progress"
    RUN_CANCEL_REQUESTED = "run.cancel_requested"
    RUN_FINISHED = "run.finished"
    RUN_HEARTBEAT = "run.heartbeat"


class ChatRunErrorCode(StrEnum):
    """Engine values of ``ChatRun.error_code``. Run types may add their own."""

    FAILED = "failed"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"
    NOT_STARTED = "not_started"
    PERSIST_FAILED = "persist_failed"


class ChatRunStopReason(StrEnum):
    """Why the journal asks a running ``execute`` to stop."""

    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    LOST = "lost"


# Worker loop: output flushing, lease renewal and the run deadline.
FLUSH_INTERVAL_SECONDS = 0.25
LEASE_RENEW_INTERVAL_SECONDS = 2.0
LEASE_DURATION = timedelta(seconds=60)
RUN_DEADLINE_SECONDS = 900
# Room to drain tools and save the outcome after the deadline stops the run.
RUN_TIME_LIMIT_SECONDS = RUN_DEADLINE_SECONDS + 120

# Bounds the channel layer send that tells followers a run changed.
PUSH_TIMEOUT_SECONDS = 2.0

# Periodic sweep and prune tasks.
SWEEP_INTERVAL = timedelta(seconds=30)
SWEEP_BATCH_SIZE = 100
WAITING_WARNING_AFTER = timedelta(minutes=5)
NOT_STARTED_AFTER = timedelta(minutes=60)
PRUNE_INTERVAL = timedelta(hours=1)
RUN_RETENTION = timedelta(days=7)

# Run creation.
MAX_ACTIVE_RUNS_PER_USER = 2
# Keys pg_advisory_xact_lock(namespace, id); the two-key form has its own space.
USER_RUNS_LOCK_NAMESPACE = 6346
WORKSPACE_RUNS_LOCK_NAMESPACE = 6347

# Consumed by the export worker: keep in sync with docker-entrypoint.sh.
CHAT_RUN_QUEUE = "chat_run"
