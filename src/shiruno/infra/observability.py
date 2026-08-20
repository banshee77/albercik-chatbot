"""Vendor-neutral request tracing (feature 012-rag-observability,
research.md R1-R3; constitution Principle XIV's Observability boundary).

`configure_observability()` is called exactly once, in
`main.py::create_app()`, mirroring how the LLM/embedding providers are
built once and stored on `app.state` — never per request, never touched
via the OpenTelemetry global tracer-provider registry
(`opentelemetry.trace.set_tracer_provider()`), which is designed to be set
at most once per process and would otherwise make test isolation across a
`pytest` run order-dependent (research.md R1). When observability is
disabled (the default), this returns `opentelemetry.trace.NoOpTracer()`
directly: every `traced_stage()` call against it is a genuine no-op, so
disabled-by-default is a structural fact about which `Tracer` object exists
rather than a runtime branch repeated at every pipeline stage.

`traced_stage()` is the only way application code should open a span. It
distinguishes two very different failure modes:

- A failure in OpenTelemetry's own span-management machinery (a bad
  attribute value, a broken exporter setup) is swallowed here — logged at
  DEBUG, never raised — so a bug in this module's own callers can never
  break the request path it wraps (FR-032).
- A failure raised by the *wrapped business logic itself* (e.g. an LLM
  provider call failing) is never swallowed — it propagates exactly as it
  would without tracing. `record_exception`/`set_status_on_exception` are
  explicitly disabled so OpenTelemetry's own default behavior never
  attaches a raw exception message/traceback to a span as a side effect of
  that propagation (FR-026) — callers that want a *safe* failure category
  recorded do so explicitly via `safe_set_status(...)`.

`traced_stage()` only protects span *creation and teardown* — it does not
wrap every statement inside its `with` block. Callers that set attributes
or status on the yielded span from inside that block MUST use
`safe_set_attribute()`/`safe_set_status()` below rather than the span's own
methods directly, so a malformed value or a broken span implementation
still can never propagate into the request path (FR-032 applies just as
much to a single attribute write as it does to opening the span itself).
"""

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from enum import Enum

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Span, Status, StatusCode, Tracer

from shiruno.config import Settings
from shiruno.infra.logging import get_logger

logger = get_logger(__name__)

_TRACER_NAME = "shiruno"

_AttributeValue = str | bool | int | float | list[str] | list[bool] | list[int] | list[float]


def _parse_otlp_headers(raw: str) -> dict[str, str]:
    """Parses the `key1=value1,key2=value2` form matching the upstream
    `OTEL_EXPORTER_OTLP_HEADERS` env var convention. Header values are
    never logged (FR-005) — this function's return value is only ever
    passed to the exporter constructor, never to a log call."""
    headers: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        key = key.strip()
        if key:
            headers[key] = value.strip()
    return headers


def configure_observability(settings: Settings) -> Tracer:
    """Returns the single `Tracer` this process should use for the
    lifetime of the app. Never calls
    `opentelemetry.trace.set_tracer_provider()` (research.md R1)."""
    if not settings.OBSERVABILITY_ENABLED:
        return trace.NoOpTracer()

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    sampler = ParentBased(TraceIdRatioBased(settings.OTEL_TRACE_SAMPLE_RATE))
    provider = TracerProvider(resource=resource, sampler=sampler)

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            headers=_parse_otlp_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        # Fail safely (FR-004): tracing stays enabled and spans are still
        # created (a caller further downstream may still attach a
        # processor to this exact provider in tests), but nothing is ever
        # exported. Deliberately logs only that the endpoint is missing —
        # never the (empty) endpoint or header values themselves (FR-005).
        logger.warning(
            "OBSERVABILITY_ENABLED is true but OTEL_EXPORTER_OTLP_ENDPOINT is "
            "not set — traces will be created but never exported."
        )

    return provider.get_tracer(_TRACER_NAME)


def _sanitize(attributes: Mapping[str, object]) -> dict[str, _AttributeValue]:
    """Coerces `uuid.UUID`/enum values to `str` and drops `None` values —
    OpenTelemetry span attributes only accept a primitive or a homogeneous
    array of primitives."""
    sanitized: dict[str, _AttributeValue] = {}
    for key, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, str | bool | int | float):
            sanitized[key] = value
        elif isinstance(value, uuid.UUID):
            sanitized[key] = str(value)
        elif isinstance(value, Enum):
            sanitized[key] = str(value.value)
        elif isinstance(value, list):
            sanitized[key] = [
                str(item) if isinstance(item, uuid.UUID | Enum) else item for item in value
            ]
        else:
            sanitized[key] = str(value)
    return sanitized


@contextmanager
def traced_stage(tracer: Tracer, name: str, **attributes: object) -> Iterator[Span]:
    try:
        span_cm = tracer.start_as_current_span(
            name,
            attributes=_sanitize(attributes),
            record_exception=False,
            set_status_on_exception=False,
        )
        span = span_cm.__enter__()
    except Exception:
        logger.debug("traced_stage: failed to start span %r", name, exc_info=True)
        yield trace.INVALID_SPAN
        return

    try:
        yield span
    except Exception as exc:
        try:
            span_cm.__exit__(type(exc), exc, exc.__traceback__)
        except Exception:
            logger.debug(
                "traced_stage: failed to close span %r after an exception", name, exc_info=True
            )
        raise
    else:
        try:
            span_cm.__exit__(None, None, None)
        except Exception:
            logger.debug("traced_stage: failed to close span %r", name, exc_info=True)


def safe_set_attribute(span: Span, key: str, value: object) -> None:
    """Sets one span attribute defensively — the same failure-isolation
    guarantee `traced_stage()` gives span creation/teardown, applied to an
    individual attribute write made by a caller from inside a
    `traced_stage()` block (FR-032). Sanitizes `value` the same way
    `traced_stage()`'s own initial attributes are sanitized."""
    try:
        sanitized = _sanitize({key: value})
        if key in sanitized:
            span.set_attribute(key, sanitized[key])
    except Exception:
        logger.debug("safe_set_attribute: failed to set %r", key, exc_info=True)


def safe_set_status(span: Span, status_code: StatusCode, description: str | None = None) -> None:
    """Sets span status defensively — see `safe_set_attribute()`. Never
    used to record raw exception text (FR-026); `description` MUST always
    be one of this codebase's own short, safe category strings."""
    try:
        span.set_status(Status(status_code, description))
    except Exception:
        logger.debug("safe_set_status: failed to set status", exc_info=True)
