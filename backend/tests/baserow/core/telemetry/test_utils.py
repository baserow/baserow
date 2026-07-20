import abc
import inspect
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import baggage
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from baserow.core.telemetry.sampling import OTEL_FORCE_FULL_TRACE_ATTRIBUTE
from baserow.core.telemetry.utils import (
    BaserowTraceMeta,
    BatchBaggageSpanProcessor,
    baserow_trace,
    baserow_trace_entrypoint,
    baserow_trace_handler,
)


def _tracer_with_memory_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, provider.get_tracer(__name__), exporter


def test_baggage_processor_keeps_force_full_trace_attribute_boolean():
    processor = object.__new__(BatchBaggageSpanProcessor)
    span = MagicMock()
    parent_context = baggage.set_baggage(OTEL_FORCE_FULL_TRACE_ATTRIBUTE, "true")
    parent_context = baggage.set_baggage("user.id", "42", context=parent_context)

    with patch(
        "baserow.core.telemetry.utils.BatchSpanProcessor.on_start"
    ) as upstream_on_start:
        processor.on_start(span, parent_context)

    upstream_on_start.assert_called_once_with(span, parent_context)
    span.set_attribute.assert_any_call(OTEL_FORCE_FULL_TRACE_ATTRIBUTE, True)
    span.set_attribute.assert_any_call("user.id", "42")


def test_baserow_trace_collapses_nested_sync_function_spans():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    @baserow_trace(tracer)
    def inner():
        with tracer.start_as_current_span("dependency"):
            return "result"

    @baserow_trace(tracer)
    def outer():
        return inner()

    assert outer() == "result"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "dependency",
        "test_baserow_trace_collapses_nested_sync_function_spans.<locals>.outer",
    ]
    provider.shutdown()


@pytest.mark.asyncio
async def test_baserow_trace_collapses_nested_async_function_spans():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    @baserow_trace(tracer)
    async def inner():
        return "result"

    @baserow_trace(tracer)
    async def outer():
        return await inner()

    assert await outer() == "result"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_collapses_nested_async_function_spans.<locals>.outer"
    ]
    provider.shutdown()


def test_baserow_trace_keeps_one_nested_important_phase():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    @baserow_trace(tracer, allow_nested=True)
    def nested_phase():
        return nested_phase_detail()

    @baserow_trace(tracer, allow_nested=True)
    def nested_phase_detail():
        return "result"

    @baserow_trace(tracer)
    def outer_operation():
        return nested_phase()

    assert outer_operation() == "result"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_keeps_one_nested_important_phase.<locals>.nested_phase",
        "test_baserow_trace_keeps_one_nested_important_phase.<locals>.outer_operation",
    ]
    provider.shutdown()


def test_baserow_trace_keeps_entrypoint_operation_and_phase_hierarchy():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    @baserow_trace(tracer, allow_nested=True)
    def important_phase():
        return "phase"

    @baserow_trace(tracer)
    def nested_operation():
        return "nested"

    @baserow_trace(tracer)
    def domain_operation():
        assert nested_operation() == "nested"
        return important_phase()

    with baserow_trace_entrypoint(tracer, "ExampleView.get"):
        assert domain_operation() == "phase"

    phase_span, operation_span, entrypoint_span = exporter.get_finished_spans()
    assert [phase_span.name, operation_span.name, entrypoint_span.name] == [
        "test_baserow_trace_keeps_entrypoint_operation_and_phase_hierarchy."
        "<locals>.important_phase",
        "test_baserow_trace_keeps_entrypoint_operation_and_phase_hierarchy."
        "<locals>.domain_operation",
        "ExampleView.get",
    ]
    assert operation_span.parent.span_id == entrypoint_span.context.span_id
    assert phase_span.parent.span_id == operation_span.context.span_id
    provider.shutdown()


def test_baserow_trace_only_traces_decorated_methods_and_supports_descriptors():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    class Example:
        @baserow_trace(tracer)
        def operation(self):
            return "operation"

        def routine_helper(self):
            return "helper"

        @classmethod
        @baserow_trace(tracer)
        def class_operation(cls):
            return cls.__name__

        @baserow_trace(tracer)
        @staticmethod
        def static_operation():
            return "static"

    example = Example()

    assert example.routine_helper() == "helper"
    assert example.operation() == "operation"
    assert example.class_operation() == "Example"
    assert example.static_operation() == "static"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_only_traces_decorated_methods_and_supports_descriptors."
        "<locals>.Example.operation",
        "test_baserow_trace_only_traces_decorated_methods_and_supports_descriptors."
        "<locals>.Example.class_operation",
        "test_baserow_trace_only_traces_decorated_methods_and_supports_descriptors."
        "<locals>.Example.static_operation",
    ]
    provider.shutdown()


def test_baserow_trace_handler_traces_public_methods_and_collapses_nested_calls():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    with patch("baserow.core.telemetry.utils.get_tracer", return_value=tracer):

        @baserow_trace_handler
        class ExampleHandler:
            def get_item(self):
                self.check_permissions()
                return self.list_items()

            def list_items(self):
                return ["item"]

            @baserow_trace(tracer, allow_nested=True)
            def check_permissions(self):
                return True

            def _build_item(self):
                return "item"

    handler = ExampleHandler()

    assert handler.get_item() == ["item"]
    assert handler.list_items() == ["item"]
    assert handler._build_item() == "item"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_handler_traces_public_methods_and_collapses_nested_calls."
        "<locals>.ExampleHandler.check_permissions",
        "test_baserow_trace_handler_traces_public_methods_and_collapses_nested_calls."
        "<locals>.ExampleHandler.get_item",
        "test_baserow_trace_handler_traces_public_methods_and_collapses_nested_calls."
        "<locals>.ExampleHandler.list_items",
    ]
    provider.shutdown()


def test_baserow_trace_meta_propagates_to_subclass_classmethod_override():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    class Base(metaclass=BaserowTraceMeta):
        @classmethod
        @baserow_trace(tracer)
        @abc.abstractmethod
        def run(cls):
            pass

    assert inspect.isabstract(Base)

    class Implementation(Base):
        @classmethod
        def run(cls):
            return cls.__name__

    assert Implementation.run() == "Implementation"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_meta_propagates_to_subclass_classmethod_override."
        "<locals>.Implementation.run"
    ]
    provider.shutdown()


def test_baserow_trace_meta_preserves_nested_config_on_subclass_override():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    class Base(metaclass=BaserowTraceMeta):
        @baserow_trace(tracer, allow_nested=True)
        def permission_check(self):
            return True

    class Example(Base):
        @baserow_trace(tracer)
        def operation(self):
            return self.permission_check()

        def permission_check(self):
            return True

    assert Example().operation() is True
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_meta_preserves_nested_config_on_subclass_override."
        "<locals>.Example.permission_check",
        "test_baserow_trace_meta_preserves_nested_config_on_subclass_override."
        "<locals>.Example.operation",
    ]
    provider.shutdown()


@pytest.mark.asyncio
async def test_baserow_trace_meta_propagates_static_and_async_methods():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    class Base(metaclass=BaserowTraceMeta):
        @staticmethod
        @baserow_trace(tracer)
        def static_operation():
            return "base"

        @baserow_trace(tracer)
        async def async_operation(self):
            return "base"

    class Implementation(Base):
        @staticmethod
        def static_operation():
            return "static"

        async def async_operation(self):
            return "async"

    implementation = Implementation()

    assert implementation.static_operation() == "static"
    assert await implementation.async_operation() == "async"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_meta_propagates_static_and_async_methods.<locals>."
        "Implementation.static_operation",
        "test_baserow_trace_meta_propagates_static_and_async_methods.<locals>."
        "Implementation.async_operation",
    ]
    provider.shutdown()


def test_baserow_trace_meta_finds_traced_contract_method_through_mro():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    class TracedMixin:
        @baserow_trace(tracer)
        def undo(self):
            return "base"

    class Base(TracedMixin, metaclass=BaserowTraceMeta):
        pass

    class Implementation(Base):
        def undo(self):
            return "implementation"

    assert Implementation().undo() == "implementation"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_meta_finds_traced_contract_method_through_mro.<locals>."
        "Implementation.undo"
    ]
    provider.shutdown()


def test_baserow_trace_meta_stops_at_first_method_definition_in_mro():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    class UntracedMixin:
        def operation(self):
            return "untraced"

    class TracedMixin:
        @baserow_trace(tracer)
        def operation(self):
            return "traced"

    class Base(UntracedMixin, TracedMixin, metaclass=BaserowTraceMeta):
        pass

    class Implementation(Base):
        def operation(self):
            return "implementation"

    assert Implementation().operation() == "implementation"
    assert exporter.get_finished_spans() == ()
    provider.shutdown()


def test_baserow_trace_meta_does_not_double_wrap_explicitly_decorated_override():
    provider, tracer, exporter = _tracer_with_memory_exporter()

    class Base(metaclass=BaserowTraceMeta):
        @baserow_trace(tracer)
        def operation(self):
            return "base"

    class Implementation(Base):
        @baserow_trace(tracer)
        def operation(self):
            return "implementation"

    assert Implementation().operation() == "implementation"
    assert [span.name for span in exporter.get_finished_spans()] == [
        "test_baserow_trace_meta_does_not_double_wrap_explicitly_decorated_override."
        "<locals>.Implementation.operation"
    ]
    provider.shutdown()


def test_baserow_trace_meta_rejects_non_method_override_of_traced_contract():
    provider, tracer, _ = _tracer_with_memory_exporter()

    class Base(metaclass=BaserowTraceMeta):
        @baserow_trace(tracer)
        def operation(self):
            return "base"

    with pytest.raises(TypeError, match="can only decorate functions"):

        class Implementation(Base):
            operation = property(lambda self: "implementation")

    provider.shutdown()
