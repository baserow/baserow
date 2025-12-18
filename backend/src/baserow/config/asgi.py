from django.conf import settings
from django.core.asgi import get_asgi_application
from django.urls import re_path

from channels.routing import ProtocolTypeRouter, URLRouter

from baserow.config.helpers import ConcurrencyLimiterASGI, check_lazy_loaded_libraries
from baserow.core.mcp import get_baserow_mcp_server
from baserow.core.telemetry.telemetry import setup_logging, setup_telemetry
from baserow.ws.routers import websocket_router

# The telemetry instrumentation library setup needs to run prior to django's setup.
setup_telemetry(add_django_instrumentation=True)

django_asgi_app = get_asgi_application()

# It is critical to setup our own logging after django has been setup and done its own
# logging setup. Otherwise Django will try to destroy and log handlers we added prior.
setup_logging()

# Check that libraries meant to be lazy-loaded haven't been imported at startup.
# This runs after Django is fully loaded, so it catches imports from all apps.
check_lazy_loaded_libraries()

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
