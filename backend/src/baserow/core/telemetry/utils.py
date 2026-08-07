import asyncio
import functools
import inspect
import os
import typing
from abc import ABCMeta
from contextlib import contextmanager
from contextvars import ContextVar
from operator import attrgetter

from opentelemetry import baggage, context
from opentelemetry.context import Context, attach, detach, set_value
from opentelemetry.sdk.trace import Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode, Tracer, get_current_span, get_tracer

from baserow.core.telemetry.sampling import OTEL_FORCE_FULL_TRACE_ATTRIBUTE


def disable_instrumentation(wrapped_function):
    if asyncio.iscoroutinefunction(wrapped_function):

        @functools.wraps(wrapped_function)
        async def _async_wrapper(*args, **kwargs):
            token = attach(set_value("suppress_instrumentation", True))
            try:
                return await wrapped_function(*args, **kwargs)
            finally:
                detach(token)

        return _async_wrapper
    else:

        @functools.wraps(wrapped_function)
        def _sync_wrapper(*args, **kwargs):
            token = attach(set_value("suppress_instrumentation", True))
            try:
                return wrapped_function(*args, **kwargs)
            finally:
                detach(token)

        return _sync_wrapper


# attrs don't include the module name to keep them short and easier to see so we add
# baserow manually.
BASEROW_OTEL_TRACE_ATTR_PREFIX = "baserow."

# A Baserow handler often calls other decorated handlers. One domain-level operation
# span around the outer call is useful; spans for every nested Python call are not.
# API entry points sit above that operation, while selected phases (for example
# permission checks and model generation) can opt into one level below it. ContextVar
# keeps this async- and thread-safe while automatic dependency spans remain attached to
# the nearest semantic span.
_baserow_span_scope = ContextVar("baserow_span_scope", default=None)
_BASEROW_TRACE_CONFIG_ATTR = "__baserow_trace_config__"
_BASEROW_SPAN_LEVEL_ENTRYPOINT = "entrypoint"
_BASEROW_SPAN_LEVEL_OPERATION = "operation"
_BASEROW_SPAN_LEVEL_PHASE = "phase"
_BASEROW_SPAN_LEVEL_RANK = {
    _BASEROW_SPAN_LEVEL_ENTRYPOINT: 0,
    _BASEROW_SPAN_LEVEL_OPERATION: 1,
    _BASEROW_SPAN_LEVEL_PHASE: 2,
}


class BatchBaggageSpanProcessor(BatchSpanProcessor):
    def on_start(
        self, span: Span, parent_context: typing.Optional[Context] = None
    ) -> None:
        super().on_start(span, parent_context)
        get_all = baggage.get_all(context=parent_context)
        for name, value in get_all.items():
            if name == OTEL_FORCE_FULL_TRACE_ATTRIBUTE:
                value = value is True or value == "true"
            span.set_attribute(name, value)


def _django_server_span(request) -> typing.Optional[Span]:
    """
    Return the Django server span the OpenTelemetry middleware stored on this request.

    Authentication runs inside the `DRF.initial` span, so the current span during
    authentication is an internal child, not the server span. Attributes set only on
    that child are invisible to anything selecting on `SpanKind.SERVER`, such as the
    Collector's per-user request metric connector.
    """

    # Imported lazily: this module is loaded by setup_telemetry() before django.setup(),
    # and otel_middleware imports django.http at module scope.
    from opentelemetry.instrumentation.django.middleware.otel_middleware import (
        _DjangoMiddleware,
    )

    key = getattr(_DjangoMiddleware, "_environ_span_key", None)
    meta = getattr(request, "META", None)
    if not key or not meta:
        return None
    return meta.get(key)


@contextmanager
def setup_user_in_baggage_and_spans(user, request=None):
    """
    Context manager that sets user-related attributes on the request's server span,
    falling back to the current span, and adds selected attributes as OpenTelemetry
    baggage. Automatically handles context attach/detach safely for ASGI.
    """

    if not otel_is_enabled():
        yield
        return

    span = get_current_span()
    if request is not None:
        server_span = _django_server_span(request)
        if server_span is not None:
            span = server_span
    ctx = context.get_current()

    def _set(name, attr, source, set_baggage=False):
        nonlocal ctx
        try:
            value = attrgetter(attr)(source)
        except AttributeError:
            value = None
        if value:
            span.set_attribute(name, value)
            if set_baggage:
                ctx = baggage.set_baggage(name, str(value), context=ctx)

    _set("user.id", "id", user, set_baggage=True)
    _set("user.untrusted_client_session_id", "untrusted_client_session_id", user)
    if request is not None:
        _set("user.token_id", "user_token.id", request)

    token = context.attach(ctx)
    try:
        yield
    finally:
        context.detach(token)


def _should_skip_baserow_span(span_level: str) -> bool:
    current_level = _baserow_span_scope.get()
    return current_level is not None and (
        _BASEROW_SPAN_LEVEL_RANK[span_level] <= _BASEROW_SPAN_LEVEL_RANK[current_level]
    )


@contextmanager
def _baserow_trace_span(tracer: Tracer, span_name: str, span_level: str):
    if _should_skip_baserow_span(span_level):
        yield None
        return

    token = _baserow_span_scope.set(span_level)
    try:
        with tracer.start_as_current_span(span_name) as span:
            try:
                yield span
            except Exception as ex:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(ex)
                raise
    finally:
        _baserow_span_scope.reset(token)


@contextmanager
def baserow_trace_entrypoint(tracer: Tracer, span_name: str):
    """
    Create the first Baserow-owned span below an automatically instrumented root.

    A domain operation and one important phase may be retained below this span. This
    is intended for framework-level entry points such as concrete DRF view methods,
    not for ordinary application functions.
    """

    with _baserow_trace_span(tracer, span_name, _BASEROW_SPAN_LEVEL_ENTRYPOINT) as span:
        yield span


@contextmanager
def baserow_trace_phase(tracer: Tracer, span_name: str):
    """Create one important phase below an entry point or domain operation."""

    with _baserow_trace_span(tracer, span_name, _BASEROW_SPAN_LEVEL_PHASE) as span:
        yield span


def _baserow_trace_func(wrapped_func, tracer: Tracer, allow_nested: bool = False):
    span_level = (
        _BASEROW_SPAN_LEVEL_PHASE if allow_nested else _BASEROW_SPAN_LEVEL_OPERATION
    )

    if asyncio.iscoroutinefunction(wrapped_func):

        @functools.wraps(wrapped_func)
        async def _async_wrapper(*args, **kwargs):
            with _baserow_trace_span(tracer, wrapped_func.__qualname__, span_level):
                return await wrapped_func(*args, **kwargs)

        wrapper = _async_wrapper
    else:

        @functools.wraps(wrapped_func)
        def _sync_wrapper(*args, **kwargs):
            with _baserow_trace_span(tracer, wrapped_func.__qualname__, span_level):
                return wrapped_func(*args, **kwargs)

        wrapper = _sync_wrapper

    setattr(wrapper, _BASEROW_TRACE_CONFIG_ATTR, (tracer, allow_nested))
    return wrapper


def _get_baserow_trace_config(value):
    if isinstance(value, (classmethod, staticmethod)):
        value = value.__func__
    return getattr(value, _BASEROW_TRACE_CONFIG_ATTR, None)


def _trace_method_descriptor(value, tracer: Tracer, allow_nested: bool):
    if isinstance(value, classmethod):
        return classmethod(
            _baserow_trace_func(value.__func__, tracer, allow_nested=allow_nested)
        )
    if isinstance(value, staticmethod):
        return staticmethod(
            _baserow_trace_func(value.__func__, tracer, allow_nested=allow_nested)
        )
    if inspect.isfunction(value):
        return _baserow_trace_func(value, tracer, allow_nested=allow_nested)
    raise TypeError(
        "baserow_trace can only decorate functions, classmethods, or staticmethods"
    )


def baserow_trace_handler(handler_class):
    """
    Trace public methods declared by an explicitly selected main handler class.

    Handler methods use the domain-operation span level. Consequently, a handler
    called by a DRF view is visible, handler-to-handler calls collapse below their
    outer handler, and handlers called from an action don't duplicate the action span.
    Private helpers and methods already configured with ``@baserow_trace`` are left
    untouched.
    """

    tracer = get_tracer(handler_class.__module__)
    for attr, value in list(vars(handler_class).items()):
        if attr.startswith("_") or _get_baserow_trace_config(value) is not None:
            continue
        if not (
            inspect.isfunction(value) or isinstance(value, (classmethod, staticmethod))
        ):
            continue
        setattr(handler_class, attr, _trace_method_descriptor(value, tracer, False))
    return handler_class


class BaserowTraceMeta(ABCMeta):
    """
    Propagates ``@baserow_trace`` from base methods to subclass overrides.

    Use this metaclass only for base classes whose traced methods are implemented or
    overridden by subclasses. Concrete classes should decorate selected methods
    directly.
    """

    def __new__(cls, name, bases, local):
        created_class = super().__new__(cls, name, bases, local)
        for attr, value in local.items():
            if _get_baserow_trace_config(value) is not None:
                continue

            trace_config = cls._get_inherited_trace_config(
                attr, created_class.__mro__[1:]
            )
            if trace_config is None:
                continue

            tracer, allow_nested = trace_config
            setattr(
                created_class,
                attr,
                _trace_method_descriptor(value, tracer, allow_nested=allow_nested),
            )
        return created_class

    @staticmethod
    def _get_inherited_trace_config(attr, inherited_mro):
        for base in inherited_mro:
            if attr in base.__dict__:
                return _get_baserow_trace_config(base.__dict__[attr])
        return None


def baserow_trace(tracer, *, allow_nested: bool = False):
    """
    Decorates a function to send a span of its execution. This will let you see how
    long the function took in your telemetry platform.

    :param tracer: An otel Tracer, add `tracer = trace.get_tracer(__name__)` to the top
        of your file to get one.
    :param allow_nested: Whether this is an important phase which may create one span
        below a domain operation.
    """

    if not isinstance(tracer, Tracer):
        raise Exception(
            f"Must provider a tracer to baserow_trace, instead you gave me a "
            f"{type(tracer)}. Get "
            "one using "
            "`tracer = trace.get_tracer(__name__)`."
        )

    def inner(wrapped_function_or_cls):
        return _trace_method_descriptor(
            wrapped_function_or_cls, tracer, allow_nested=allow_nested
        )

    return inner


def add_baserow_trace_attrs(**kwargs):
    """
    Simple helper function for quickly adding attributes to the current span. The
    attribute names will be prefixed with the baserow. to namespace them properly.

    :param kwargs: Key value pairs, the key will be the attr name prefixed with
        baserow. and the value will be the span attribute value.
    """

    span = get_current_span()
    for key, value in kwargs.items():
        span.set_attribute(f"{BASEROW_OTEL_TRACE_ATTR_PREFIX}{key}", value)


def otel_is_enabled():
    env_var_set = bool(os.getenv("BASEROW_ENABLE_OTEL", False))
    not_in_tests = (
        os.getenv("DJANGO_SETTINGS_MODULE", "").strip()
        != "baserow.config.settings.test"
    )
    return env_var_set and not_in_tests
