import os
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from django.core.handlers.asgi import ASGIRequest
from django.dispatch import Signal
from django.http import HttpResponse
from django.test import override_settings

import pytest
from opentelemetry import baggage, context
from opentelemetry.instrumentation.django.middleware.otel_middleware import (
    _DjangoMiddleware,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF
from opentelemetry.trace import SpanKind, TraceState
from opentelemetry.util.http import parse_excluded_urls

from baserow.core.telemetry.django import BaserowDjangoMiddleware
from baserow.core.telemetry.sampling import (
    OTEL_FORCE_FULL_TRACE_ATTRIBUTE,
    ForceFullTraceSampler,
)
from baserow.core.telemetry.telemetry import (
    _create_baserow_signal_send_wrapper,
    _create_drf_initial_wrapper,
    _create_drf_response_render_wrapper,
    _create_drf_view_dispatch_wrapper,
    _create_silk_response_processing_wrapper,
    _create_tracer_provider,
    _finish_request_span,
    _prepare_request_span,
    _setup_django_process_instrumentation,
    _setup_log_exporting,
    setup_baserow_signal_instrumentation,
    setup_django_lifecycle_instrumentation,
)
from baserow.core.telemetry.utils import (
    baserow_trace,
    baserow_trace_entrypoint,
    setup_user_in_baggage_and_spans,
)


@pytest.mark.parametrize("request_protocol", ["wsgi", "asgi"])
def test_django_request_with_remote_parent_starts_a_linked_root(
    api_request_factory, monkeypatch, request_protocol
):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    remote_trace_id = "0af7651916cd43dd8448eb211c80319c"
    remote_span_id = "b7ad6b7169203331"
    traceparent = f"00-{remote_trace_id}-{remote_span_id}-01"
    if request_protocol == "wsgi":
        request = api_request_factory.get(
            "/api/workspaces/",
            HTTP_TRACEPARENT=traceparent,
            HTTP_TRACESTATE="vendor=value",
            HTTP_BAGGAGE="user.id=42",
        )
    else:
        request = ASGIRequest(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/workspaces/",
                "query_string": b"",
                "headers": [
                    (b"host", b"testserver"),
                    (b"traceparent", traceparent.encode()),
                    (b"tracestate", b"vendor=value"),
                    (b"baggage", b"user.id=42"),
                ],
                "client": ("127.0.0.1", 1234),
                "server": ("testserver", 80),
                "scheme": "http",
            },
            BytesIO(),
        )

    monkeypatch.setattr(
        _DjangoMiddleware, "_tracer", provider.get_tracer("test.django")
    )
    monkeypatch.setattr(_DjangoMiddleware, "_excluded_urls", parse_excluded_urls(""))
    monkeypatch.setattr(_DjangoMiddleware, "_active_request_counter", MagicMock())
    monkeypatch.setattr(_DjangoMiddleware, "_duration_histogram_old", None)
    monkeypatch.setattr(_DjangoMiddleware, "_duration_histogram_new", None)
    monkeypatch.setattr(_DjangoMiddleware, "_otel_request_hook", None)
    monkeypatch.setattr(_DjangoMiddleware, "_otel_response_hook", None)

    def get_response(received_request):
        assert received_request.META["HTTP_TRACEPARENT"] == traceparent
        if request_protocol == "asgi":
            assert (b"traceparent", traceparent.encode()) in received_request.scope[
                "headers"
            ]
        assert baggage.get_baggage("user.id") == "42"
        return HttpResponse()

    response = BaserowDjangoMiddleware(get_response)(request)

    assert response.status_code == 200
    request_span = exporter.get_finished_spans()[0]
    assert request_span.parent is None
    assert request_span.context.trace_id != int(remote_trace_id, 16)
    assert len(request_span.links) == 1
    assert request_span.links[0].context.trace_id == int(remote_trace_id, 16)
    assert request_span.links[0].context.span_id == int(remote_span_id, 16)
    assert request_span.links[0].context.trace_state.get("vendor") == "value"
    provider.shutdown()


def test_prepare_request_span_uses_forwarded_for(api_request_factory):
    request = api_request_factory.get(
        "/api/workspaces/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_FORWARDED_FOR="203.0.113.50, 70.41.3.18",
    )
    span = MagicMock()
    span.is_recording.return_value = True

    with patch(
        "baserow.core.telemetry.telemetry.monotonic_ns", return_value=1_000_000_000
    ):
        _prepare_request_span(span, request)

    span.set_attribute.assert_any_call("client.address", "203.0.113.50")
    span.set_attribute.assert_any_call("net.peer.ip", "203.0.113.50")
    assert span.set_attribute.call_count == 2


def test_prepare_request_span_falls_back_to_real_ip(api_request_factory):
    request = api_request_factory.get(
        "/api/workspaces/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_REAL_IP="203.0.113.51",
    )
    span = MagicMock()
    span.is_recording.return_value = True

    with patch(
        "baserow.core.telemetry.telemetry.monotonic_ns", return_value=1_000_000_000
    ):
        _prepare_request_span(span, request)

    span.set_attribute.assert_any_call("client.address", "203.0.113.51")
    span.set_attribute.assert_any_call("net.peer.ip", "203.0.113.51")
    assert span.set_attribute.call_count == 2


def test_prepare_request_span_marks_force_full_trace_requests(api_request_factory):
    request = api_request_factory.get("/api/workspaces/?force_full_otel_trace=true")
    span = MagicMock()
    span.is_recording.return_value = True

    with patch(
        "baserow.core.telemetry.telemetry.monotonic_ns", return_value=1_000_000_000
    ):
        _prepare_request_span(span, request)

    span.set_attribute.assert_any_call("baserow.force_full_otel_trace", True)


@override_settings(BASEROW_OTEL_SLOW_REQUEST_THRESHOLD_SECONDS=10)
def test_finish_request_span_marks_slow_requests(api_request_factory):
    request = api_request_factory.get("/api/workspaces/")
    span = MagicMock()
    span.is_recording.return_value = True

    with patch(
        "baserow.core.telemetry.telemetry.monotonic_ns",
        side_effect=[1_000_000_000, 11_000_000_000],
    ):
        _prepare_request_span(span, request)
        _finish_request_span(span, request, MagicMock(status_code=200))

    span.set_attribute.assert_any_call("baserow.http.request.duration_ms", 10_000.0)
    span.set_attribute.assert_any_call("baserow.http.request.slow", True)


@override_settings(BASEROW_OTEL_SLOW_REQUEST_THRESHOLD_SECONDS=10)
def test_finish_request_span_does_not_mark_fast_requests(api_request_factory):
    request = api_request_factory.get("/api/workspaces/")
    span = MagicMock()
    span.is_recording.return_value = True

    with patch(
        "baserow.core.telemetry.telemetry.monotonic_ns",
        side_effect=[1_000_000_000, 10_999_999_999],
    ):
        _prepare_request_span(span, request)
        _finish_request_span(span, request, MagicMock(status_code=200))

    span.set_attribute.assert_any_call("baserow.http.request.duration_ms", 9_999.999999)
    assert not any(
        call.args == ("baserow.http.request.slow", True)
        for call in span.set_attribute.call_args_list
    )


@override_settings(BASEROW_OTEL_SLOW_REQUEST_THRESHOLD_SECONDS=0)
def test_finish_request_span_zero_threshold_disables_slow_marking(
    api_request_factory,
):
    request = api_request_factory.get("/api/workspaces/")
    span = MagicMock()
    span.is_recording.return_value = True

    with patch(
        "baserow.core.telemetry.telemetry.monotonic_ns",
        side_effect=[1_000_000_000, 101_000_000_000],
    ):
        _prepare_request_span(span, request)
        _finish_request_span(span, request, MagicMock(status_code=200))

    assert not any(
        call.args == ("baserow.http.request.slow", True)
        for call in span.set_attribute.call_args_list
    )


def test_create_tracer_provider_uses_one_sampler_for_every_instrumentation_scope(
    monkeypatch,
):
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
    # Existing deployments may still set the retired override. It must not split the
    # sampling decision between Django and its child spans.
    monkeypatch.setenv(
        "OTEL_PER_MODULE_SAMPLER_OVERRIDES",
        "opentelemetry.instrumentation.django=always_on",
    )

    provider = _create_tracer_provider()

    django_tracer = provider.get_tracer("opentelemetry.instrumentation.django")
    application_tracer = provider.get_tracer("baserow.core.handler")
    assert django_tracer.sampler is provider.sampler
    assert application_tracer.sampler is provider.sampler


@pytest.mark.parametrize("span_kind", [SpanKind.INTERNAL, SpanKind.CLIENT])
def test_create_tracer_provider_drops_orphan_implementation_spans(
    monkeypatch, span_kind
):
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")
    provider = _create_tracer_provider()
    tracer = provider.get_tracer("test")

    with tracer.start_as_current_span("orphan", kind=span_kind) as orphan_span:
        assert not orphan_span.is_recording()

    provider.shutdown()


@pytest.mark.parametrize("span_kind", [SpanKind.SERVER, SpanKind.CONSUMER])
def test_create_tracer_provider_keeps_legitimate_root_spans(monkeypatch, span_kind):
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")
    provider = _create_tracer_provider()
    tracer = provider.get_tracer("test")

    with tracer.start_as_current_span("root", kind=span_kind) as root_span:
        assert root_span.is_recording()
        with tracer.start_as_current_span(
            "implementation", kind=SpanKind.INTERNAL
        ) as implementation_span:
            assert implementation_span.is_recording()

    provider.shutdown()


def test_create_tracer_provider_keeps_root_metric_observations(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")
    provider = _create_tracer_provider()
    tracer = provider.get_tracer("test")

    with tracer.start_as_current_span(
        "metric-observation",
        attributes={"baserow.metric.observation": "example"},
    ) as observation_span:
        assert observation_span.is_recording()

    provider.shutdown()


def test_create_tracer_provider_forces_complete_trace_from_query_attribute(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
    provider = _create_tracer_provider()
    tracer = provider.get_tracer("test")

    for url_attributes in (
        {"url.query": "force_full_otel_trace=true"},
        {"http.target": "/api/workspaces/?force_full_otel_trace=true"},
    ):
        with tracer.start_as_current_span(
            "request",
            kind=SpanKind.SERVER,
            attributes=url_attributes,
        ) as root_span:
            assert root_span.is_recording()
            assert root_span.get_span_context().trace_flags.sampled
            assert root_span.attributes["baserow.force_full_otel_trace"] is True
            assert all(
                root_span.attributes[key] == value
                for key, value in url_attributes.items()
            )

            with tracer.start_as_current_span("child") as child_span:
                assert child_span.is_recording()
                assert child_span.get_span_context().trace_flags.sampled
                assert child_span.attributes["baserow.force_full_otel_trace"] is True

    with tracer.start_as_current_span(
        "ordinary-request",
        kind=SpanKind.SERVER,
        attributes={"url.query": "force_full_otel_trace=false"},
    ) as ordinary_span:
        assert not ordinary_span.is_recording()

    provider.shutdown()


def test_force_full_trace_sampler_preserves_trace_state():
    sampler = ForceFullTraceSampler(ALWAYS_OFF)
    trace_state = TraceState((("vendor", "state"),))

    result = sampler.should_sample(
        None,
        1,
        "request",
        attributes={OTEL_FORCE_FULL_TRACE_ATTRIBUTE: True},
        trace_state=trace_state,
    )

    assert result.trace_state is trace_state


def test_authenticated_user_id_is_recorded_on_request_span(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")
    provider = _create_tracer_provider()
    tracer = provider.get_tracer("test")
    user = SimpleNamespace(id=42, untrusted_client_session_id="session-id")
    request = SimpleNamespace(user_token=SimpleNamespace(id=84))

    with (
        patch("baserow.core.telemetry.utils.otel_is_enabled", return_value=True),
        tracer.start_as_current_span("request", kind=SpanKind.SERVER) as request_span,
    ):
        with setup_user_in_baggage_and_spans(user, request):
            pass

        assert request_span.attributes["user.id"] == 42
        assert request_span.attributes["user.token_id"] == 84

    provider.shutdown()


@override_settings(
    BASEROW_BACKEND_LOG_LEVEL="INFO",
    BASEROW_OTEL_LOG_LEVEL="WARNING",
)
def test_setup_log_exporting_has_a_separate_log_level():
    logger = MagicMock()

    with patch(
        "baserow.core.telemetry.telemetry.LogGuruCompatibleLoggerHandler"
    ) as handler:
        _setup_log_exporting(logger)

    handler.assert_called_once_with(level="WARNING", logger_provider=ANY)
    logger.add.assert_called_once_with(
        handler.return_value,
        format="{message}",
        level="WARNING",
    )


def test_setup_django_process_instrumentation_registers_request_hooks():
    with patch(
        "baserow.core.telemetry.django.BaserowDjangoInstrumentor.instrument"
    ) as instrument:
        _setup_django_process_instrumentation()

    instrument.assert_called_once_with(
        request_hook=_prepare_request_span,
        response_hook=_finish_request_span,
        excluded_urls="_health",
    )


@pytest.mark.parametrize(
    "environment_variable",
    ["OTEL_PYTHON_DJANGO_EXCLUDED_URLS", "OTEL_PYTHON_EXCLUDED_URLS"],
)
def test_django_instrumentation_merges_operator_excluded_urls(environment_variable):
    with (
        patch.dict(
            os.environ,
            {environment_variable: "metrics,internal"},
            clear=True,
        ),
        patch(
            "baserow.core.telemetry.django.BaserowDjangoInstrumentor.instrument"
        ) as instrument,
    ):
        _setup_django_process_instrumentation()

    instrument.assert_called_once_with(
        request_hook=_prepare_request_span,
        response_hook=_finish_request_span,
        excluded_urls="metrics,internal,_health",
    )


@pytest.mark.parametrize("request_as_kwarg", [False, True])
def test_drf_dispatch_creates_concrete_api_view_entrypoint_span(request_as_kwarg):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)

    class GridViewView:
        pass

    request = SimpleNamespace(method="GET")
    response = SimpleNamespace(status_code=200)
    dispatch = MagicMock(return_value=response)
    trace_dispatch = _create_drf_view_dispatch_wrapper(tracer)
    args = () if request_as_kwarg else (request,)
    kwargs = {"request": request} if request_as_kwarg else {}

    with tracer.start_as_current_span("GET /api/database/views/grid/{view_id}/"):
        assert trace_dispatch(dispatch, GridViewView(), args, kwargs) is response

    if request_as_kwarg:
        dispatch.assert_called_once_with(request=request)
    else:
        dispatch.assert_called_once_with(request)
    view_span, request_span = exporter.get_finished_spans()
    assert view_span.name == "GridViewView.get"
    assert view_span.parent.span_id == request_span.context.span_id
    assert view_span.attributes == {
        "baserow.api.view": "GridViewView",
        "baserow.api.view_module": __name__,
        "baserow.api.method": "get",
    }
    provider.shutdown()


def test_drf_initial_traces_authentication_permissions_and_throttling_phase():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)

    class GridViewView:
        pass

    initial = MagicMock(return_value=None)
    trace_initial = _create_drf_initial_wrapper(tracer)

    with baserow_trace_entrypoint(tracer, "GridViewView.get"):
        assert trace_initial(initial, GridViewView(), (SimpleNamespace(),), {}) is None

    initial.assert_called_once_with(SimpleNamespace())
    initial_span, entrypoint_span = exporter.get_finished_spans()
    assert initial_span.name == "DRF.initial"
    assert initial_span.parent.span_id == entrypoint_span.context.span_id
    assert initial_span.attributes == {
        "baserow.api.view": "GridViewView",
        "baserow.api.view_module": __name__,
    }
    provider.shutdown()


def test_action_operation_and_signal_hooks_are_separate_spans():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)
    signal = Signal()

    def action_done_receiver(sender, **kwargs):
        return kwargs["result"]

    action_done_receiver.__module__ = "baserow.core.action.receivers"
    signal.connect(action_done_receiver, weak=False)
    trace_send = _create_baserow_signal_send_wrapper(tracer)

    class ExampleActionType:
        pass

    @baserow_trace(tracer)
    def action_do():
        return trace_send(
            signal.send,
            signal,
            (ExampleActionType,),
            {"result": "handled"},
        )

    with baserow_trace_entrypoint(tracer, "ExampleView.post"):
        responses = action_do()

    assert responses == [(action_done_receiver, "handled")]
    signal_span, action_span, entrypoint_span = exporter.get_finished_spans()
    assert signal_span.name == "Signal.send action_done_receiver"
    assert action_span.name.endswith(".<locals>.action_do")
    assert action_span.parent.span_id == entrypoint_span.context.span_id
    assert signal_span.parent.span_id == action_span.context.span_id
    assert signal_span.attributes["baserow.signal.receiver_count"] == 1
    assert signal_span.attributes["baserow.signal.sender"].endswith(
        ".ExampleActionType"
    )
    assert signal_span.attributes["baserow.signal.receivers"] == (
        "baserow.core.action.receivers."
        "test_action_operation_and_signal_hooks_are_separate_spans."
        "<locals>.action_done_receiver",
    )
    provider.shutdown()


def test_drf_response_render_creates_root_child_phase_span():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)

    class JSONRenderer:
        pass

    response = SimpleNamespace(accepted_renderer=JSONRenderer())
    render = MagicMock(return_value=response)
    trace_render = _create_drf_response_render_wrapper(tracer)

    with tracer.start_as_current_span("GET /api/database/views/grid/{view_id}/"):
        assert trace_render(render, response, (), {}) is response

    render.assert_called_once_with()
    render_span, request_span = exporter.get_finished_spans()
    assert render_span.name == "DRFResponse.render"
    assert render_span.parent.span_id == request_span.context.span_id
    assert render_span.attributes == {"baserow.response.renderer": "JSONRenderer"}
    provider.shutdown()


def test_silk_profile_persistence_is_one_span_with_dependencies_suppressed():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)

    def persist_profile():
        assert context.get_value("suppress_instrumentation") is True
        return "response"

    trace_processing = _create_silk_response_processing_wrapper(tracer)

    with tracer.start_as_current_span("GET /api/database/views/grid/{view_id}/"):
        assert trace_processing(persist_profile, MagicMock(), (), {}) == "response"

    silk_span, request_span = exporter.get_finished_spans()
    assert silk_span.name == "Silk.persist_profile"
    assert silk_span.parent.span_id == request_span.context.span_id
    provider.shutdown()


@override_settings(MIDDLEWARE=["silk.middleware.SilkyMiddleware"])
def test_django_lifecycle_instrumentation_registers_bounded_framework_phases(
    monkeypatch,
):
    monkeypatch.setattr(
        "baserow.core.telemetry.telemetry._django_lifecycle_instrumented", False
    )

    with (
        patch("baserow.core.telemetry.telemetry.otel_is_enabled", return_value=True),
        patch("wrapt.wrap_function_wrapper") as wrap_function,
    ):
        setup_django_lifecycle_instrumentation()

    assert [call.args[:2] for call in wrap_function.call_args_list] == [
        ("rest_framework.views", "APIView.dispatch"),
        ("rest_framework.views", "APIView.initial"),
        ("rest_framework.response", "Response.render"),
        ("silk.middleware", "SilkyMiddleware.process_response"),
    ]


def test_signal_instrumentation_wraps_django_signal_send_once(monkeypatch):
    monkeypatch.setattr(
        "baserow.core.telemetry.telemetry._baserow_signal_instrumented", False
    )

    with patch("wrapt.wrap_function_wrapper") as wrap_function:
        setup_baserow_signal_instrumentation()
        setup_baserow_signal_instrumentation()

    wrap_function.assert_called_once_with(
        "django.dispatch.dispatcher",
        "Signal.send",
        ANY,
    )
