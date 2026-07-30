import logging
import os
import sys
from time import monotonic_ns

from django.http import HttpRequest, HttpResponse

from celery import signals
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Span, Status, StatusCode

from baserow.core.psycopg import is_psycopg3
from baserow.core.telemetry.sampling import (
    OTEL_FORCE_FULL_TRACE_ATTRIBUTE,
    OTEL_FORCE_FULL_TRACE_QUERY_PARAMETER,
    DropOrphanImplementationSpansSampler,
    ForceFullTraceSampler,
)
from baserow.core.telemetry.utils import (
    BatchBaggageSpanProcessor,
    baserow_trace_entrypoint,
    baserow_trace_phase,
    otel_is_enabled,
)
from baserow.core.utils import get_user_remote_ip_address_from_request

OTEL_CLIENT_IP_ATTRIBUTE_NAMES = ("client.address", "net.peer.ip")
OTEL_REQUEST_STARTED_AT_ATTRIBUTE = "_baserow_otel_request_started_at"
OTEL_REQUEST_DURATION_ATTRIBUTE = "baserow.http.request.duration_ms"
OTEL_SLOW_REQUEST_ATTRIBUTE = "baserow.http.request.slow"
_django_lifecycle_instrumented = False
_baserow_signal_instrumented = False


class LogGuruCompatibleLoggerHandler(LoggingHandler):
    def emit(self, record: logging.LogRecord) -> None:
        # The Otel exporter does not handle nested dictionaries. Loguru stores all of
        # the extra log context developers can add on the extra dict. Here unnest
        # them as attributes on the record itself so otel can export them properly.
        for k, v in record.extra.items():
            setattr(record, f"baserow.{k}", v)
        del record.extra

        # by default otel doesn't send funcName, rename it so it does.
        record.python_function = record.funcName
        super().emit(record)


def setup_logging():
    """
    This function configures loguru and optionally sets up open telemetry log exporting
    using a loguru sink.

    It is not run as part of setup_logging_and_telemetry as we want this to run
    after Django has set up its own logging. If we run prior to Django, it will teardown
    any log handlers we set up in here causing errors due to the exporters being flushed
    immediately with no contents.
    """

    from django.conf import settings

    from loguru import logger

    # A slightly customized default loguru format which includes the process id.
    loguru_format = (
        "<magenta>{process}|</magenta>"
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>|"
        "<level>{level}</level>|"
        "<cyan>{name}</cyan>:"
        "<cyan>{function}</cyan>:"
        "<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Remove the default loguru stderr sink
    logger.remove()
    # Replace it with our format, loguru recommends sending application logs to stderr.
    logger.add(
        sys.stderr, format=loguru_format, level=settings.BASEROW_BACKEND_LOG_LEVEL
    )
    logger.info("Logger setup.")
    if otel_is_enabled():
        _setup_log_exporting(logger)


def setup_telemetry(add_django_instrumentation: bool):
    """
    Sets up logging and when the env var BASEROW_ENABLE_OTEL is set to any non-blank
    string and this function is called metrics will be setup and sent according to
    the OTEL env vars you can find described at:
    - https://opentelemetry.io/docs/reference/specification/protocol/exporter/
    - https://opentelemetry.io/docs/reference/specification/sdk-environment-variables/

    :param add_django_instrumentation: Enables specific instrumentation for a django
        process that is processing requests. Don't enable this for a celery process etc.
    """

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics._internal.export import PeriodicExportingMetricReader
    from opentelemetry.trace import ProxyTracerProvider

    if otel_is_enabled():
        existing_provider = trace.get_tracer_provider()
        if not isinstance(existing_provider, ProxyTracerProvider):
            print("Provider already configured not reconfiguring...")
        else:
            provider = _create_tracer_provider()
            processor = BatchBaggageSpanProcessor(OTLPSpanExporter())
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)

            reader = PeriodicExportingMetricReader(OTLPMetricExporter())
            provider = MeterProvider(
                metric_readers=[reader],
            )
            metrics.set_meter_provider(provider)

            _setup_celery_metrics()
            _setup_standard_backend_instrumentation()

            print("Configured default backend instrumentation")
            if add_django_instrumentation:
                print("Adding Django request instrumentation also.")
                _setup_django_process_instrumentation()

            print("Telemetry enabled!")
    else:
        print("Not configuring telemetry due to BASEROW_ENABLE_OTEL not being set.")


def _setup_log_exporting(logger):
    from django.conf import settings

    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs._internal.export import BatchLogRecordProcessor

    logger_provider = LoggerProvider()
    set_logger_provider(logger_provider)
    exporter = OTLPLogExporter()
    handler = LogGuruCompatibleLoggerHandler(
        level=settings.BASEROW_OTEL_LOG_LEVEL,
        logger_provider=logger_provider,
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    logger.add(handler, format="{message}", level=settings.BASEROW_OTEL_LOG_LEVEL)
    logger.info("Logger open telemetry exporting setup.")


meter = metrics.get_meter("celery_tasks")
task_counter = meter.create_counter(
    name="baserow.celery_task_scheduled",
    description="Number of times each Celery task has been scheduled",
    unit="1",
)


def _setup_celery_metrics():
    def count_task(sender, **kwargs):
        task_counter.add(1, {"task_name": sender})

    signals.after_task_publish.connect(count_task, weak=False)


def _setup_standard_backend_instrumentation():
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    if is_psycopg3:
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    else:
        from opentelemetry.instrumentation.psycopg2 import (
            Psycopg2Instrumentor as PsycopgInstrumentor,
        )

    from baserow.core.telemetry.celery import BaserowCeleryInstrumentor

    BotocoreInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    BaserowCeleryInstrumentor().instrument()
    RedisInstrumentor().instrument()
    setup_baserow_signal_instrumentation()


def _setup_django_process_instrumentation():
    from baserow.core.telemetry.django import BaserowDjangoInstrumentor

    BaserowDjangoInstrumentor().instrument(
        request_hook=_prepare_request_span,
        response_hook=_finish_request_span,
        excluded_urls=_django_excluded_urls(),
    )


def _create_drf_view_dispatch_wrapper(tracer):
    def trace_drf_view_dispatch(wrapped, instance, args, kwargs):
        request = args[0] if args else kwargs["request"]
        method_name = str(getattr(request, "method", "unknown")).lower()
        view_class = type(instance)
        view_name = view_class.__name__

        with baserow_trace_entrypoint(tracer, f"{view_name}.{method_name}") as span:
            if span is not None and span.is_recording():
                span.set_attribute("baserow.api.view", view_name)
                span.set_attribute("baserow.api.view_module", view_class.__module__)
                span.set_attribute("baserow.api.method", method_name)

            response = wrapped(*args, **kwargs)
            if (
                span is not None
                and span.is_recording()
                and getattr(response, "status_code", 0) >= 500
            ):
                span.set_status(Status(StatusCode.ERROR))
            return response

    return trace_drf_view_dispatch


def _create_drf_initial_wrapper(tracer):
    def trace_drf_initial(wrapped, instance, args, kwargs):
        with tracer.start_as_current_span("DRF.initial") as span:
            if span.is_recording():
                view_class = type(instance)
                span.set_attribute("baserow.api.view", view_class.__name__)
                span.set_attribute("baserow.api.view_module", view_class.__module__)
            return wrapped(*args, **kwargs)

    return trace_drf_initial


def _create_drf_response_render_wrapper(tracer):
    def trace_drf_response_render(wrapped, instance, args, kwargs):
        with tracer.start_as_current_span("DRFResponse.render") as span:
            renderer = getattr(instance, "accepted_renderer", None)
            if span.is_recording() and renderer is not None:
                span.set_attribute("baserow.response.renderer", type(renderer).__name__)
            return wrapped(*args, **kwargs)

    return trace_drf_response_render


def _create_silk_response_processing_wrapper(tracer):
    def trace_silk_response_processing(wrapped, instance, args, kwargs):
        with tracer.start_as_current_span("Silk.persist_profile"):
            # The profiler's own database writes are implementation details. Retain
            # one timing span without producing dependency spans for every write.
            with suppress_instrumentation():
                return wrapped(*args, **kwargs)

    return trace_silk_response_processing


def _callable_name(value) -> str:
    module = getattr(value, "__module__", None)
    qualname = getattr(value, "__qualname__", None)
    if module and qualname:
        return f"{module}.{qualname}"

    value_type = value if isinstance(value, type) else type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _create_baserow_signal_send_wrapper(tracer):
    baserow_module_prefixes = ("baserow.", "baserow_premium.", "baserow_enterprise.")

    def trace_baserow_signal_send(wrapped, instance, args, kwargs):
        from django.dispatch import Signal

        current_span = trace.get_current_span()
        if type(instance) is not Signal or not current_span.is_recording():
            return wrapped(*args, **kwargs)

        sender = args[0] if args else kwargs.get("sender")
        sync_receivers, async_receivers = instance._live_receivers(sender)
        receiver_names = [
            _callable_name(receiver) for receiver in [*sync_receivers, *async_receivers]
        ]
        baserow_receivers = [
            name for name in receiver_names if name.startswith(baserow_module_prefixes)
        ]
        if not baserow_receivers:
            return wrapped(*args, **kwargs)

        first_receiver = baserow_receivers[0].rsplit(".", 1)[-1]
        remaining_receivers = len(receiver_names) - 1
        span_name = f"Signal.send {first_receiver}"
        if remaining_receivers:
            span_name += f" +{remaining_receivers}"

        with baserow_trace_phase(tracer, span_name) as span:
            if span is not None and span.is_recording():
                span.set_attribute("baserow.signal.sender", _callable_name(sender))
                span.set_attribute("baserow.signal.receiver_count", len(receiver_names))
                span.set_attribute("baserow.signal.receivers", receiver_names)
            return wrapped(*args, **kwargs)

    return trace_baserow_signal_send


def setup_baserow_signal_instrumentation():
    """Trace aggregate execution time for Baserow-owned Django signal receivers."""

    global _baserow_signal_instrumented
    if _baserow_signal_instrumented:
        return

    from wrapt import wrap_function_wrapper

    wrap_function_wrapper(
        "django.dispatch.dispatcher",
        "Signal.send",
        _create_baserow_signal_send_wrapper(trace.get_tracer("baserow.signals")),
    )
    _baserow_signal_instrumented = True


def setup_django_lifecycle_instrumentation():
    """Trace selected high-value phases after Django has initialized."""

    global _django_lifecycle_instrumented
    if _django_lifecycle_instrumented or not otel_is_enabled():
        return

    from django.conf import settings

    from wrapt import wrap_function_wrapper

    tracer = trace.get_tracer("baserow.api.views")
    wrap_function_wrapper(
        "rest_framework.views",
        "APIView.dispatch",
        _create_drf_view_dispatch_wrapper(tracer),
    )
    wrap_function_wrapper(
        "rest_framework.views",
        "APIView.initial",
        _create_drf_initial_wrapper(tracer),
    )
    wrap_function_wrapper(
        "rest_framework.response",
        "Response.render",
        _create_drf_response_render_wrapper(tracer),
    )

    if "silk.middleware.SilkyMiddleware" in settings.MIDDLEWARE:
        wrap_function_wrapper(
            "silk.middleware",
            "SilkyMiddleware.process_response",
            _create_silk_response_processing_wrapper(tracer),
        )

    _django_lifecycle_instrumented = True


def _django_excluded_urls() -> str:
    """
    Health checks produce no diagnostic value as traces, so they are always
    excluded on top of any operator-provided exclusions.
    """

    operator_excluded = os.environ.get(
        "OTEL_PYTHON_DJANGO_EXCLUDED_URLS"
    ) or os.environ.get("OTEL_PYTHON_EXCLUDED_URLS", "")
    return f"{operator_excluded},_health" if operator_excluded else "_health"


def _create_tracer_provider() -> TracerProvider:
    """
    Create one trace-wide sampler for every instrumentation scope.

    OpenTelemetry sampling decisions must be consistent across a trace. Using a
    different sampler for Django, database, Redis, or application spans produces
    root-only or otherwise fragmented traces.
    """

    provider = TracerProvider()
    provider.sampler = DropOrphanImplementationSpansSampler(
        ForceFullTraceSampler(provider.sampler)
    )
    return provider


def _prepare_request_span(span: Span, request: HttpRequest):
    if span and span.is_recording():
        setattr(request, OTEL_REQUEST_STARTED_AT_ATTRIBUTE, monotonic_ns())
        if request.GET.get(OTEL_FORCE_FULL_TRACE_QUERY_PARAMETER) == "true":
            span.set_attribute(OTEL_FORCE_FULL_TRACE_ATTRIBUTE, True)
        ip_address = get_user_remote_ip_address_from_request(request)
        if ip_address:
            for attribute_name in OTEL_CLIENT_IP_ATTRIBUTE_NAMES:
                span.set_attribute(attribute_name, ip_address)


def _finish_request_span(span: Span, request: HttpRequest, response: HttpResponse):
    from django.conf import settings

    if not span or not span.is_recording():
        return

    started_at = getattr(request, OTEL_REQUEST_STARTED_AT_ATTRIBUTE, None)
    if started_at is None:
        return

    duration_ms = (monotonic_ns() - started_at) / 1_000_000
    span.set_attribute(OTEL_REQUEST_DURATION_ATTRIBUTE, duration_ms)
    if (
        settings.BASEROW_OTEL_SLOW_REQUEST_THRESHOLD_SECONDS > 0
        and duration_ms >= settings.BASEROW_OTEL_SLOW_REQUEST_THRESHOLD_SECONDS * 1000
    ):
        span.set_attribute(OTEL_SLOW_REQUEST_ATTRIBUTE, True)
