from opentelemetry import metrics

meter = metrics.get_meter(__name__)

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
)


def record_button_field_dispatched(sender, outcome, duration_ms, **kwargs):
    attributes = {"outcome": str(outcome)}
    button_field_dispatch_counter.add(1, attributes)
    button_field_dispatch_duration.record(duration_ms, attributes)


def record_workflow_action_dispatched(
    sender, workflow_action, exception, duration_ms, **kwargs
):
    # The class only. An external action's message names its address.
    attributes = {
        "action_type": workflow_action.get_type().type,
        "result": "ok" if exception is None else type(exception).__name__,
    }
    workflow_action_dispatch_counter.add(1, attributes)
    workflow_action_dispatch_duration.record(duration_ms, attributes)
