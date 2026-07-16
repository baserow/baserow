from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import override_settings

import pytest
from opentelemetry import baggage, context, propagate, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from baserow.core.telemetry.celery import (
    OTEL_CELERY_TASK_DURATION_ATTRIBUTE,
    OTEL_CELERY_TASK_QUEUE_ATTRIBUTE,
    OTEL_CELERY_TASK_ROOT_ATTRIBUTE,
    OTEL_SLOW_CELERY_TASK_ATTRIBUTE,
    BaserowCeleryInstrumentor,
    _inject_force_full_trace_baggage,
)
from baserow.core.telemetry.sampling import OTEL_FORCE_FULL_TRACE_ATTRIBUTE
from baserow.core.telemetry.telemetry import _create_tracer_provider


class FakeCeleryRequest(dict):
    def __getattr__(self, name):
        return self.get(name)


def _instrumentor_with_memory_exporter(provider=None):
    exporter = InMemorySpanExporter()
    provider = provider or TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    instrumentor = object.__new__(BaserowCeleryInstrumentor)
    instrumentor._tracer = provider.get_tracer(__name__)
    instrumentor._baserow_task_started_at = {}
    instrumentor.task_id_to_start_time = {}
    instrumentor.metrics = {"flower.task.runtime.seconds": MagicMock()}
    return instrumentor, provider, exporter


def _fake_task(carrier=None, queue="celery"):
    request = FakeCeleryRequest(
        carrier or {},
        delivery_info={"routing_key": queue},
        hostname="worker-1",
    )
    return SimpleNamespace(name="baserow.example.task", request=request)


@override_settings(
    BASEROW_OTEL_SLOW_CELERY_TASK_THRESHOLD_SECONDS=10,
    BASEROW_OTEL_SLOW_CELERY_TASK_EXCLUDED_QUEUES=frozenset({"export"}),
)
def test_celery_task_gets_independent_linked_trace_and_one_domain_operation():
    instrumentor, provider, exporter = _instrumentor_with_memory_exporter()
    tracer = provider.get_tracer(__name__)
    carrier = {}

    baggage_context = baggage.set_baggage("user.id", "42")
    baggage_token = context.attach(baggage_context)
    try:
        with tracer.start_as_current_span("request") as producer_span:
            propagate.inject(carrier)
            task = _fake_task(carrier)

            with (
                patch(
                    "baserow.core.telemetry.celery.default_timer",
                    side_effect=[100.0, 111.0],
                ),
                patch(
                    "baserow.core.telemetry.celery.task_duration_histogram"
                ) as histogram,
            ):
                instrumentor._trace_prerun(task=task, task_id="task-1")
                task_span = trace.get_current_span()
                assert task_span.get_span_context().trace_id != (
                    producer_span.get_span_context().trace_id
                )
                assert baggage.get_baggage("user.id") == "42"

                with tracer.start_as_current_span("ExportHandler.run_export_job"):
                    pass

                instrumentor._trace_postrun(
                    task=task,
                    task_id="task-1",
                    state="SUCCESS",
                )

            histogram.record.assert_called_once_with(
                11.0,
                {
                    "task_name": "baserow.example.task",
                    "queue": "celery",
                    "state": "SUCCESS",
                },
            )
    finally:
        context.detach(baggage_token)

    operation_span, task_span, producer_span = exporter.get_finished_spans()
    assert task_span.name == "run/baserow.example.task"
    assert task_span.parent is None
    assert task_span.links[0].context.trace_id == producer_span.context.trace_id
    assert operation_span.parent.span_id == task_span.context.span_id
    assert task_span.attributes[OTEL_CELERY_TASK_ROOT_ATTRIBUTE] is True
    assert task_span.attributes[OTEL_CELERY_TASK_QUEUE_ATTRIBUTE] == "celery"
    assert task_span.attributes[OTEL_CELERY_TASK_DURATION_ATTRIBUTE] == 11_000
    assert task_span.attributes[OTEL_SLOW_CELERY_TASK_ATTRIBUTE] is True
    provider.shutdown()


@pytest.mark.parametrize(
    ("threshold", "queue", "expected_slow"),
    [
        (10, "celery", True),
        (10, "export", False),
        (0, "celery", False),
    ],
)
def test_celery_slow_task_classification_is_queue_aware(
    settings, threshold, queue, expected_slow
):
    settings.BASEROW_OTEL_SLOW_CELERY_TASK_THRESHOLD_SECONDS = threshold
    settings.BASEROW_OTEL_SLOW_CELERY_TASK_EXCLUDED_QUEUES = frozenset({"export"})
    instrumentor, provider, exporter = _instrumentor_with_memory_exporter()
    task = _fake_task(queue=queue)

    with (
        patch(
            "baserow.core.telemetry.celery.default_timer",
            side_effect=[100.0, 200.0],
        ),
        patch("baserow.core.telemetry.celery.task_duration_histogram"),
    ):
        instrumentor._trace_prerun(task=task, task_id="task-1")
        instrumentor._trace_postrun(
            task=task,
            task_id="task-1",
            state="SUCCESS",
        )

    task_span = exporter.get_finished_spans()[0]
    assert (OTEL_SLOW_CELERY_TASK_ATTRIBUTE in task_span.attributes) is expected_slow
    provider.shutdown()


def test_force_full_trace_baggage_forces_independent_task_root(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
    provider = _create_tracer_provider()
    instrumentor, provider, exporter = _instrumentor_with_memory_exporter(provider)
    carrier = {}
    force_context = baggage.set_baggage(OTEL_FORCE_FULL_TRACE_ATTRIBUTE, "true")
    propagate.inject(carrier, context=force_context)
    task = _fake_task(carrier)

    with (
        patch(
            "baserow.core.telemetry.celery.default_timer",
            side_effect=[100.0, 101.0],
        ),
        patch("baserow.core.telemetry.celery.task_duration_histogram"),
    ):
        instrumentor._trace_prerun(task=task, task_id="task-1")
        task_span = trace.get_current_span()
        assert task_span.is_recording()
        instrumentor._trace_postrun(
            task=task,
            task_id="task-1",
            state="SUCCESS",
        )

    finished_task_span = exporter.get_finished_spans()[0]
    assert finished_task_span.attributes[OTEL_FORCE_FULL_TRACE_ATTRIBUTE] is True
    provider.shutdown()


def test_celery_failure_marks_independent_task_root_as_error():
    instrumentor, provider, exporter = _instrumentor_with_memory_exporter()
    task = _fake_task()

    with (
        patch(
            "baserow.core.telemetry.celery.default_timer",
            side_effect=[100.0, 101.0],
        ),
        patch("baserow.core.telemetry.celery.task_duration_histogram"),
    ):
        instrumentor._trace_prerun(task=task, task_id="task-1")
        instrumentor._trace_failure(
            sender=task,
            task_id="task-1",
            einfo=RuntimeError("task failed"),
        )
        instrumentor._trace_postrun(
            task=task,
            task_id="task-1",
            state="FAILURE",
        )

    task_span = exporter.get_finished_spans()[0]
    assert task_span.status.status_code is trace.StatusCode.ERROR
    provider.shutdown()


def test_force_full_trace_is_added_to_published_task_baggage():
    provider = TracerProvider()
    tracer = provider.get_tracer(__name__)
    headers = {}
    user_context = baggage.set_baggage("user.id", "42")
    token = context.attach(user_context)
    try:
        with tracer.start_as_current_span(
            "apply_async/task",
            attributes={OTEL_FORCE_FULL_TRACE_ATTRIBUTE: True},
        ):
            _inject_force_full_trace_baggage(headers)
    finally:
        context.detach(token)

    extracted_context = propagate.extract(headers)
    assert (
        baggage.get_baggage(OTEL_FORCE_FULL_TRACE_ATTRIBUTE, context=extracted_context)
        == "true"
    )
    assert baggage.get_baggage("user.id", context=extracted_context) == "42"
    provider.shutdown()
