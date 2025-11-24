import logging
import os
import sys

from celery import signals
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler

from baserow.core.psycopg import is_psycopg3
from baserow.core.telemetry.provider import DifferentSamplerPerLibraryTracerProvider
from baserow.core.telemetry.utils import BatchBaggageSpanProcessor, otel_is_enabled


class LogGuruCompatibleLoggerHandler(LoggingHandler):
    def emit(self, record: logging.LogRecord) -> None:
        # The Otel exporter does not handle nested dictionaries. Loguru stores all of
        # the extra log context developers can add on the extra dict. Here unnest
        # them as attributes on the record itself so otel can export them properly.
        for k, v in record.extra.items():
            setattr(record, f"baserow.{k}", v)
        del record.extra

        # by default otel doesn't send funcName, rename it so it does.
        setattr(record, "python_function", record.funcName)
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
        f"<magenta>{os.getpid()}|</magenta>"
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
            provider = DifferentSamplerPerLibraryTracerProvider()
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
        level=settings.BASEROW_BACKEND_LOG_LEVEL,
        logger_provider=logger_provider,
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    logger.add(handler, format="{message}", level=settings.BASEROW_BACKEND_LOG_LEVEL)
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
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    if is_psycopg3:
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    else:
        from opentelemetry.instrumentation.psycopg2 import (
            Psycopg2Instrumentor as PsycopgInstrumentor,
        )

    BotocoreInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    CeleryInstrumentor().instrument()


def _setup_django_process_instrumentation():
    from opentelemetry.instrumentation.django import DjangoInstrumentor

    DjangoInstrumentor().instrument()
