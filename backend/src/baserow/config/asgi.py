import django
from django.conf import settings
from django.urls import re_path

from channels.routing import ProtocolTypeRouter, URLRouter

from baserow.config.helpers import (
    BaserowASGIHandler,
    ConcurrencyLimiterASGI,
    check_lazy_loaded_libraries,
    log_env_warnings,
)
from baserow.core.mcp import get_baserow_mcp_server
from baserow.core.telemetry.telemetry import setup_telemetry
from baserow.ws.routers import websocket_router

# The telemetry instrumentation library setup needs to run prior to django's setup.
setup_telemetry(add_django_instrumentation=True)

# Same as django.core.asgi.get_asgi_application, but with Baserow's ASGI handler that
# doesn't keep per-request memory alive in reference cycles.
django.setup(set_prefix=False)
django_asgi_app = BaserowASGIHandler()

# Check that libraries meant to be lazy-loaded haven't been imported at startup.
# This runs after Django is fully loaded, so it catches imports from all apps.
check_lazy_loaded_libraries()

# Finally log any warnings about the environment variables that can help debug issues.
log_env_warnings()

application = ProtocolTypeRouter(
    {
        "http": ConcurrencyLimiterASGI(
            URLRouter(
                [
                    re_path(r"^mcp", get_baserow_mcp_server().sse_app()),
                    re_path(r"", django_asgi_app),
                ]
            ),
            max_concurrency=settings.ASGI_HTTP_MAX_CONCURRENCY,
        ),
        "websocket": websocket_router,
    }
)
