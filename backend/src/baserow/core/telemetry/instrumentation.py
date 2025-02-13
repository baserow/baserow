from opentelemetry.instrumentation.celery import CeleryInstrumentor


class BaserowCeleryInstrumentor(CeleryInstrumentor):
    """
    Custom Celery instrumentor that disables tracing of task scheduling
    (apply_async/delay).

    By default, OpenTelemetry creates two spans for each Celery task:
    1. When task is scheduled (apply_async/delay)
    2. When task is executed (run)

    We disable the scheduling span to reduce noise in traces while keeping the
    execution span which provides the actual task runtime information.

    Note: In case there is a need to trace the scheduling of a task, in that
    case one solution is to create subclass of celery.Task and attach original
    CeleryInstrumentor._trace_before_publish method and use that class as base for
    @app.task(...)
    """

    def _trace_before_publish(self, *args, **kwargs):
        pass
