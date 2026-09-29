import re
from typing import Sequence

from opentelemetry import baggage, trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace.sampling import Decision, Sampler, SamplingResult
from opentelemetry.trace import Link, SpanKind
from opentelemetry.trace.span import TraceState
from opentelemetry.util.types import Attributes

OTEL_FORCE_FULL_TRACE_QUERY_PARAMETER = "force_full_otel_trace"
OTEL_FORCE_FULL_TRACE_ATTRIBUTE = "baserow.force_full_otel_trace"
OTEL_METRIC_OBSERVATION_ATTRIBUTE = "baserow.metric.observation"

_ALLOWED_ROOT_SPAN_KINDS = frozenset((SpanKind.SERVER, SpanKind.CONSUMER))

_FORCE_FULL_TRACE_QUERY_PATTERN = re.compile(
    rf"(?:^|[?&]){OTEL_FORCE_FULL_TRACE_QUERY_PARAMETER}=true(?:$|[&#])"
)


class DropOrphanImplementationSpansSampler(Sampler):
    """
    Prevent implementation details from becoming one-span traces.

    Client and internal instrumentation can execute without an active request or task
    context, for example during startup, an excluded health request, or background
    framework work. OpenTelemetry otherwise treats those spans as roots. Only server
    requests, task consumers, and intentional metric observations may start a Baserow
    trace; every span kind remains eligible when it has a valid parent.
    """

    def __init__(self, delegate: Sampler):
        self.delegate = delegate

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        parent_span_context = trace.get_current_span(parent_context).get_span_context()
        is_metric_observation = (attributes or {}).get(
            OTEL_METRIC_OBSERVATION_ATTRIBUTE
        ) is not None
        if (
            not parent_span_context.is_valid
            and kind not in _ALLOWED_ROOT_SPAN_KINDS
            and not is_metric_observation
        ):
            return SamplingResult(Decision.DROP, trace_state=trace_state)

        return self.delegate.should_sample(
            parent_context,
            trace_id,
            name,
            kind,
            attributes,
            links,
            trace_state,
        )

    def get_description(self) -> str:
        return (
            f"DropOrphanImplementationSpansSampler({self.delegate.get_description()})"
        )


class ForceFullTraceSampler(Sampler):
    """
    Preserve the explicit force-full-trace escape hatch around one global sampler.

    Django supplies URL attributes when it asks the SDK to create the server span, so
    a force request can override head sampling before that root span is discarded. The
    marker is then copied to every descendant sampling result, keeping the decision
    consistent across the complete trace and making it visible to a tail sampler.
    """

    def __init__(self, delegate: Sampler):
        self.delegate = delegate

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        parent_span = trace.get_current_span(parent_context)
        parent_attributes = getattr(parent_span, "attributes", None) or {}
        force_full_trace = (
            parent_attributes.get(OTEL_FORCE_FULL_TRACE_ATTRIBUTE) is True
            or baggage.get_baggage(
                OTEL_FORCE_FULL_TRACE_ATTRIBUTE, context=parent_context
            )
            == "true"
            or (attributes or {}).get(OTEL_FORCE_FULL_TRACE_ATTRIBUTE) is True
        )

        if not force_full_trace:
            for key, value in (attributes or {}).items():
                if (
                    isinstance(key, str)
                    and isinstance(value, str)
                    and key.startswith(("http.", "url."))
                    and _FORCE_FULL_TRACE_QUERY_PATTERN.search(value)
                ):
                    force_full_trace = True
                    break

        if force_full_trace:
            return SamplingResult(
                Decision.RECORD_AND_SAMPLE,
                {**(attributes or {}), OTEL_FORCE_FULL_TRACE_ATTRIBUTE: True},
                trace_state,
            )

        return self.delegate.should_sample(
            parent_context,
            trace_id,
            name,
            kind,
            attributes,
            links,
            trace_state,
        )

    def get_description(self) -> str:
        return f"ForceFullTraceSampler({self.delegate.get_description()})"
