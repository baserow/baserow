from datetime import timedelta

RUN_CREATED = "run.created"
RUN_STARTED = "run.started"
TEXT_DELTA = "text.delta"
PROGRESS = "progress"
RUN_CANCEL_REQUESTED = "run.cancel_requested"
RUN_FINISHED = "run.finished"

ERROR_FAILED = "failed"
ERROR_TIMEOUT = "timeout"
ERROR_INTERRUPTED = "interrupted"
ERROR_NOT_STARTED = "not_started"
ERROR_PERSIST_FAILED = "persist_failed"
ERROR_MODEL_UNAVAILABLE = "model_unavailable"

STOP_CANCELLED = "cancelled"
STOP_TIMEOUT = "timeout"
STOP_LOST = "lost"

FLUSH_INTERVAL_SECONDS = 0.25
PUSH_TIMEOUT_SECONDS = 2.0
LEASE_RENEW_INTERVAL_SECONDS = 2.0
LEASE_DURATION = timedelta(seconds=60)
RUN_DEADLINE_SECONDS = 900
RUN_TIME_LIMIT_SECONDS = 1020
SWEEP_INTERVAL = timedelta(seconds=30)
WAITING_WARNING_AFTER = timedelta(minutes=5)
NOT_STARTED_AFTER = timedelta(minutes=60)
PRUNE_INTERVAL = timedelta(hours=1)
RUN_RETENTION = timedelta(days=30)

MAX_ACTIVE_RUNS_PER_USER = 2
SWEEP_BATCH_SIZE = 100

# Keys pg_advisory_xact_lock(namespace, user_id); the two-key form has its own space.
USER_RUNS_LOCK_NAMESPACE = 6346

CHAT_RUN_QUEUE = "chat_run"
