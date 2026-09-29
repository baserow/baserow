from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.instrumentation.asgi import asgi_getter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.django.middleware.otel_middleware import (
    _DjangoMiddleware,
)
from opentelemetry.instrumentation.wsgi import wsgi_getter
from opentelemetry.propagate import extract, get_global_textmap


def _trace_header_names() -> set[str]:
    """Return the configured propagation headers, excluding W3C baggage."""

    return {
        field.lower()
        for field in get_global_textmap().fields
        if field.lower() != "baggage"
    }


@contextmanager
def _without_remote_parent(request):
    """
    Extract an inbound parent for linking, then hide it during span creation.

    Baggage stays visible to the upstream middleware. Trace propagation headers are
    restored before Django handles the request, so application behavior is unchanged.
    """

    trace_headers = _trace_header_names()
    scope = getattr(request, "scope", None)
    if scope is not None:
        carrier = scope
        getter = asgi_getter
        original_headers = scope.get("headers", [])
        if not any(
            name.decode("latin1").lower() in trace_headers
            for name, _ in original_headers
        ):
            yield None
            return
    else:
        carrier = request.META
        getter = wsgi_getter
        meta_keys = {
            "HTTP_" + header.upper().replace("-", "_") for header in trace_headers
        }
        if meta_keys.isdisjoint(request.META):
            yield None
            return

    extracted_context = extract(carrier, getter=getter)
    remote_parent = trace.get_current_span(extracted_context).get_span_context()
    if not remote_parent.is_valid or not remote_parent.is_remote:
        yield None
        return

    if scope is not None:
        scope["headers"] = [
            (name, value)
            for name, value in original_headers
            if name.decode("latin1").lower() not in trace_headers
        ]
        try:
            yield remote_parent
        finally:
            scope["headers"] = original_headers
    else:
        removed_headers = {
            key: request.META.pop(key) for key in meta_keys if key in request.META
        }
        try:
            yield remote_parent
        finally:
            request.META.update(removed_headers)


class BaserowDjangoMiddleware(_DjangoMiddleware):
    """Make every inbound HTTP request an independently sampled trace root."""

    def process_request(self, request):
        with _without_remote_parent(request) as remote_parent:
            result = super().process_request(request)

        if remote_parent is not None:
            request_span = trace.get_current_span()
            if request_span.is_recording():
                request_span.add_link(remote_parent)

        return result


class BaserowDjangoInstrumentor(DjangoInstrumentor):
    _instance = None
    _is_instrumented_by_opentelemetry = False
    _opentelemetry_middleware = "baserow.core.telemetry.django.BaserowDjangoMiddleware"
