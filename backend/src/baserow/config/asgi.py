from django.conf import settings
from django.core.asgi import get_asgi_application
from django.urls import re_path

from channels.routing import ProtocolTypeRouter, URLRouter

from baserow.config.helpers import ConcurrencyLimiterASGI
from baserow.core.telemetry.telemetry import setup_logging, setup_telemetry
from baserow.core.mcp import baserow_mcp
from baserow.ws.routers import websocket_router

# The telemetry instrumentation library setup needs to run prior to django's setup.
setup_telemetry(add_django_instrumentation=True)

django_asgi_app = get_asgi_application()

# It is critical to setup our own logging after django has been setup and done its own
# logging setup. Otherwise Django will try to destroy and log handlers we added prior.
setup_logging()


application = ProtocolTypeRouter(
    {
        "http": ConcurrencyLimiterASGI(
            URLRouter(
                [
                    # Run
                    # `SERVER_PORT=3001 npx @modelcontextprotocol/inspector`
                    # URL: http://127.0.0.1:8000/mcp/sse
                    # re_path(r"^mcp", baserow_mcp.sse_app()),
                    re_path(r"^mcp", baserow_mcp.sse_app()),
                    # re_path(r"", django_asgi_app),
                ]
            ),
            max_concurrency=settings.ASGI_HTTP_MAX_CONCURRENCY,
        ),
        "websocket": websocket_router,
    }
)
