from timeit import default_timer

from django.conf import settings

from opentelemetry import baggage, metrics, trace
from opentelemetry import context as context_api
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.instrumentation.celery import (
    CeleryInstrumentor,
    celery_getter,
    utils,
)
from opentelemetry.propagate import extract
from opentelemetry.trace import Link, SpanKind

from baserow.core.telemetry.sampling import OTEL_FORCE_FULL_TRACE_ATTRIBUTE

OTEL_CELERY_TASK_ROOT_ATTRIBUTE = "baserow.celery.task.root"
OTEL_CELERY_TASK_QUEUE_ATTRIBUTE = "baserow.celery.task.queue"
OTEL_CELERY_TASK_DURATION_ATTRIBUTE = "baserow.celery.task.duration_ms"
OTEL_SLOW_CELERY_TASK_ATTRIBUTE = "baserow.celery.task.slow"

_TASK_RUN = "run"

meter = metrics.get_meter("baserow.celery")
task_duration_histogram = meter.create_histogram(
    name="baserow.celery.task.duration",
    description="The duration of completed Baserow Celery tasks",
    unit="s",
)


def _get_task_queue(task) -> str:
    request = task.request
    delivery_info = getattr(request, "delivery_info", None) or {}
    return (
        delivery_info.get("routing_key") or getattr(request, "queue", None) or "unknown"
    )


def _is_force_full_trace(context) -> bool:
    value = baggage.get_baggage(OTEL_FORCE_FULL_TRACE_ATTRIBUTE, context=context)
    return value is True or value == "true"


def _inject_force_full_trace_baggage(headers) -> None:
    if headers is None:
        return

    current_span = trace.get_current_span()
    attributes = getattr(current_span, "attributes", None) or {}
    if attributes.get(OTEL_FORCE_FULL_TRACE_ATTRIBUTE) is not True:
        return

    force_context = baggage.set_baggage(OTEL_FORCE_FULL_TRACE_ATTRIBUTE, "true")
    W3CBaggagePropagator().inject(headers, context=force_context)


class BaserowCeleryInstrumentor(CeleryInstrumentor):
    """
    Give every task execution an independently sampled trace linked to its producer.

    The upstream Celery instrumentation makes the consumer a child of the publishing
    request. Long-running tasks then arrive after the Collector may already have made
    the request trace's tail-sampling decision. A link preserves navigation without
    coupling the task's sampling lifecycle to the producer trace.
    """

    _instance = None
    _is_instrumented_by_opentelemetry = False

    def __init__(self):
        self._baserow_task_started_at = {}

    def _trace_before_publish(self, *args, **kwargs):
        super()._trace_before_publish(*args, **kwargs)
        _inject_force_full_trace_baggage(kwargs.get("headers"))

    def _trace_prerun(self, *args, **kwargs):
        task = utils.retrieve_task(kwargs)
        task_id = utils.retrieve_task_id(kwargs)

        if task is None or task_id is None:
            return

        self.update_task_duration_time(task_id)
        self._baserow_task_started_at[task_id] = default_timer()

        extracted_context = extract(task.request, getter=celery_getter)
        producer_span_context = trace.get_current_span(
            extracted_context
        ).get_span_context()
        links = (
            [Link(producer_span_context)] if producer_span_context.is_valid else None
        )

        # Keep propagated baggage, but remove the remote producer as the parent so the
        # task receives a new trace ID and an independent tail-sampling decision.
        task_context = trace.set_span_in_context(trace.INVALID_SPAN, extracted_context)
        token = context_api.attach(task_context)
        queue = _get_task_queue(task)
        attributes = {
            OTEL_CELERY_TASK_ROOT_ATTRIBUTE: True,
            OTEL_CELERY_TASK_QUEUE_ATTRIBUTE: queue,
        }
        if _is_force_full_trace(task_context):
            attributes[OTEL_FORCE_FULL_TRACE_ATTRIBUTE] = True

        try:
            span = self._tracer.start_span(
                f"{_TASK_RUN}/{task.name}",
                context=task_context,
                kind=SpanKind.CONSUMER,
                attributes=attributes,
                links=links,
            )
            activation = trace.use_span(span, end_on_exit=True)
            activation.__enter__()
        except Exception:
            context_api.detach(token)
            raise

        utils.attach_context(task, task_id, span, activation, token)

    def _trace_postrun(self, *args, **kwargs):
        task = utils.retrieve_task(kwargs)
        task_id = utils.retrieve_task_id(kwargs)
        started_at = self._baserow_task_started_at.pop(task_id, None)

        if task is not None and task_id is not None and started_at is not None:
            duration_seconds = default_timer() - started_at
            queue = _get_task_queue(task)
            state = kwargs.get("state") or "UNKNOWN"
            task_duration_histogram.record(
                duration_seconds,
                {
                    "task_name": task.name,
                    "queue": queue,
                    "state": state,
                },
            )

            task_context = utils.retrieve_context(task, task_id)
            if task_context is not None:
                span, _, _ = task_context
                if span.is_recording():
                    span.set_attribute(
                        OTEL_CELERY_TASK_DURATION_ATTRIBUTE,
                        duration_seconds * 1000,
                    )
                    if (
                        settings.BASEROW_OTEL_SLOW_CELERY_TASK_THRESHOLD_SECONDS > 0
                        and duration_seconds
                        >= settings.BASEROW_OTEL_SLOW_CELERY_TASK_THRESHOLD_SECONDS
                    ):
                        span.set_attribute(OTEL_SLOW_CELERY_TASK_ATTRIBUTE, True)

        super()._trace_postrun(*args, **kwargs)
