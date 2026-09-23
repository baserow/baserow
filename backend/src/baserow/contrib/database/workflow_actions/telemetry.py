from opentelemetry import metrics

meter = metrics.get_meter(__name__)

# The SDK's default boundaries stop at 10s, while an HTTP action's timeout goes
# up to 120s and its watchdog allows twice that, so every slow endpoint would
# land in the same bucket as a timeout.
DURATION_BUCKETS_MS = [
    5,
    10,
    25,
    50,
    100,
    250,
    500,
    1000,
    2500,
    5000,
    10000,
    30000,
    60000,
    120000,
    240000,
]

# No ids in any attribute: a workspace or field id per series would give the
# backend one series per button.
button_field_dispatch_counter = meter.create_counter(
    "baserow.button_field.dispatch",
    unit="1",
    description="Button field clicks, by outcome.",
)
button_field_dispatch_duration = meter.create_histogram(
    "baserow.button_field.dispatch.duration",
    unit="ms",
    description="How long a button field click took, by outcome.",
    explicit_bucket_boundaries_advisory=DURATION_BUCKETS_MS,
)
workflow_action_dispatch_counter = meter.create_counter(
    "baserow.workflow_action.dispatch",
    unit="1",
    description="Server-side button field actions run, by type and result.",
)
workflow_action_dispatch_duration = meter.create_histogram(
    "baserow.workflow_action.dispatch.duration",
    unit="ms",
    description="How long a server-side button field action took.",
    explicit_bucket_boundaries_advisory=DURATION_BUCKETS_MS,
)


def record_button_field_dispatched(sender, outcome, duration_ms, **kwargs):
    attributes = {"outcome": str(outcome)}
    button_field_dispatch_counter.add(1, attributes)
    button_field_dispatch_duration.record(duration_ms, attributes)


def result_label(succeeded, result) -> str:
    """
    What became of one action, as the per-action metric labels it.

    :param succeeded: Whether the action ran without raising.
    :param result: What it returned, or None when it failed.
    :return: `failed`, `error_status` or `ok`.
    """

    if not succeeded:
        return "failed"
    # An HTTP action answers a timeout or a remote error with a result of its
    # own rather than raising. Only the status code is read: the rest of the
    # data is what the endpoint sent back.
    status_code = (
        result.data.get("status_code") if isinstance(result.data, dict) else None
    )
    if result.status >= 400 or (isinstance(status_code, int) and status_code >= 400):
        return "error_status"
    return "ok"


def record_workflow_action_dispatched(
    sender, workflow_action, succeeded, result, duration_ms, **kwargs
):
    attributes = {
        "action_type": workflow_action.get_type().type,
        "result": result_label(succeeded, result),
    }
    workflow_action_dispatch_counter.add(1, attributes)
    workflow_action_dispatch_duration.record(duration_ms, attributes)
