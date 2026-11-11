from opentelemetry import metrics

from .models import ChatRun

meter = metrics.get_meter(__name__)

# Waits range from milliseconds to the one-hour not-started limit.
QUEUE_WAIT_BUCKETS_SECONDS = [0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 900, 3600]

queue_wait = meter.create_histogram(
    "baserow.chat_run.queue_wait",
    unit="s",
    description="How long a chat run waited for a worker.",
    explicit_bucket_boundaries_advisory=QUEUE_WAIT_BUCKETS_SECONDS,
)
runs_finished = meter.create_counter(
    "baserow.chat_run.finished",
    unit="1",
    description="Chat runs that ended, by run type, status and error code.",
)


def record_run_claimed(run: ChatRun) -> None:
    """
    :param run: A run that a worker just claimed.
    """

    waited = (run.started_on - run.created_on).total_seconds()
    queue_wait.record(waited, {"run_type": run.run_type})


def record_run_finished(run_type: str, status: str, error_code: str) -> None:
    """
    :param run_type: The run type of the run that ended.
    :param status: Its final status.
    :param error_code: Why it failed, if it did.
    """

    runs_finished.add(
        1, {"run_type": run_type, "status": status, "error_code": error_code}
    )
