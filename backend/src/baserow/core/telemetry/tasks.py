from celery import Task
from celery.signals import worker_process_init

from baserow.core.telemetry.telemetry import setup_logging, setup_telemetry
from baserow.core.telemetry.utils import otel_is_enabled

TASK_NAME_KEY = "celery.task_name"


@worker_process_init.connect
def initialize_otel(**kwargs):
    setup_telemetry(add_django_instrumentation=False)
    setup_logging()


class BaserowTelemetryTask(Task):
    def __call__(self, *args, **kwargs):
        from opentelemetry import baggage, context

        if otel_is_enabled():
            # Safely attach and detach baggage context within the same task call
            curr_ctx = context.get_current()
            new_ctx = baggage.set_baggage(TASK_NAME_KEY, self.name, context=curr_ctx)
            token = context.attach(new_ctx)
            try:
                return super().__call__(*args, **kwargs)
            finally:
                context.detach(token)
        else:
            return super().__call__(*args, **kwargs)
