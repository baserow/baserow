from channels.routing import URLRouter

from .auth import JWTTokenAuthMiddleware
from .routing import websocket_urlpatterns
from .telemetry import WebsocketTelemetryMiddleware

websocket_router = WebsocketTelemetryMiddleware(
    JWTTokenAuthMiddleware(URLRouter(websocket_urlpatterns))
)
