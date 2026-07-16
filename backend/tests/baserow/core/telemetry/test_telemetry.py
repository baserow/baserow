import os
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from django.test import override_settings

import pytest
from opentelemetry import context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from baserow.core.telemetry.telemetry import (
    _create_drf_response_render_wrapper,
    _create_drf_view_dispatch_wrapper,
    _create_silk_response_processing_wrapper,
    _create_tracer_provider,
    _finish_request_span,
    _prepare_request_span,
    _setup_django_process_instrumentation,
    _setup_log_exporting,
    setup_django_lifecycle_instrumentation,
)
from baserow.core.telemetry.utils import setup_user_in_baggage_and_spans


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
            attributes=url_attributes,
        ) as root_span:
            assert root_span.is_recording()
            assert root_span.get_span_context().trace_flags.sampled
            assert root_span.attributes["baserow.force_full_otel_trace"] is True

            with tracer.start_as_current_span("child") as child_span:
                assert child_span.is_recording()
                assert child_span.get_span_context().trace_flags.sampled
                assert child_span.attributes["baserow.force_full_otel_trace"] is True

    with tracer.start_as_current_span(
        "ordinary-request",
        attributes={"url.query": "force_full_otel_trace=false"},
    ) as ordinary_span:
        assert not ordinary_span.is_recording()

    provider.shutdown()


def test_authenticated_user_id_is_recorded_on_request_span(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")
    provider = _create_tracer_provider()
    tracer = provider.get_tracer("test")
    user = SimpleNamespace(id=42, untrusted_client_session_id="session-id")
    request = SimpleNamespace(user_token=SimpleNamespace(id=84))

    with (
        patch("baserow.core.telemetry.utils.otel_is_enabled", return_value=True),
        tracer.start_as_current_span("request") as request_span,
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
        "opentelemetry.instrumentation.django.DjangoInstrumentor.instrument"
    ) as instrument:
        _setup_django_process_instrumentation()

    instrument.assert_called_once_with(
        request_hook=_prepare_request_span,
        response_hook=_finish_request_span,
        excluded_urls="_health",
    )


def test_django_instrumentation_merges_operator_excluded_urls():
    with (
        patch.dict(
            os.environ, {"OTEL_PYTHON_DJANGO_EXCLUDED_URLS": "metrics,internal"}
        ),
        patch(
            "opentelemetry.instrumentation.django.DjangoInstrumentor.instrument"
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
        ("rest_framework.response", "Response.render"),
        ("silk.middleware", "SilkyMiddleware.process_response"),
    ]
