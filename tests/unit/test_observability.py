"""Unit tests for `infra/observability.py` (feature 012-rag-observability,
Foundational phase, research.md R12). No real OTLP backend, no network
call — `configure_observability()` is exercised directly with explicit
`Settings` overrides, and span assertions use the SDK's own
`InMemorySpanExporter` + `SimpleSpanProcessor`. `OTLPSpanExporter` itself is
monkeypatched with an inert fake in every "enabled with a valid endpoint"
test: this proves `configure_observability()` wires up a real exporter
without ever letting that exporter attempt a genuine network call (research
requires tests never need network access — a real `OTLPSpanExporter`
pointed at *any* endpoint string still tries to dial it once at interpreter
shutdown, since `TracerProvider` registers an `atexit` flush by default).
"""

import logging
import uuid
from collections.abc import Sequence

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from shiruno.config import Settings
from shiruno.infra.observability import configure_observability, traced_stage


class _FakeOTLPSpanExporter:
    """Stands in for the real `OTLPSpanExporter` in tests — same shape
    (constructed with `endpoint=`/`headers=`), but never performs any I/O."""

    def __init__(self, *, endpoint: str | None = None, headers: dict[str, str] | None = None):
        self.endpoint = endpoint
        self.headers = headers

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {"AUTH_JWT_SECRET": "x" * 32}
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _configure_observability_no_network(
    monkeypatch: pytest.MonkeyPatch, **settings_overrides: object
) -> trace.Tracer:
    monkeypatch.setattr("shiruno.infra.observability.OTLPSpanExporter", _FakeOTLPSpanExporter)
    return configure_observability(_settings(**settings_overrides))


def _tracer_with_in_memory_exporter() -> tuple[trace.Tracer, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


class TestConfigureObservability:
    def test_disabled_returns_noop_tracer(self) -> None:
        tracer = configure_observability(_settings(OBSERVABILITY_ENABLED=False))

        assert isinstance(tracer, trace.NoOpTracer)

    def test_enabled_with_valid_endpoint_returns_real_tracer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tracer = _configure_observability_no_network(
            monkeypatch,
            OBSERVABILITY_ENABLED=True,
            OTEL_EXPORTER_OTLP_ENDPOINT="http://phoenix:6006/v1/traces",
        )

        assert not isinstance(tracer, trace.NoOpTracer)
        with tracer.start_as_current_span("probe") as span:
            assert span.is_recording()

    def test_enabled_with_missing_endpoint_logs_warning_and_does_not_crash(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            tracer = configure_observability(
                _settings(OBSERVABILITY_ENABLED=True, OTEL_EXPORTER_OTLP_ENDPOINT="")
            )

        assert not isinstance(tracer, trace.NoOpTracer)
        assert any("OTEL_EXPORTER_OTLP_ENDPOINT" in record.message for record in caplog.records)
        # No processor was attached, so spans are created but never
        # exported — this itself must not raise.
        with tracer.start_as_current_span("probe"):
            pass

    def test_sample_rate_zero_produces_no_exported_spans(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tracer = _configure_observability_no_network(
            monkeypatch,
            OBSERVABILITY_ENABLED=True,
            OTEL_EXPORTER_OTLP_ENDPOINT="http://phoenix:6006/v1/traces",
            OTEL_TRACE_SAMPLE_RATE=0.0,
        )
        with tracer.start_as_current_span("probe") as span:
            assert not span.is_recording()

    def test_sample_rate_one_produces_recording_spans(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tracer = _configure_observability_no_network(
            monkeypatch,
            OBSERVABILITY_ENABLED=True,
            OTEL_EXPORTER_OTLP_ENDPOINT="http://phoenix:6006/v1/traces",
            OTEL_TRACE_SAMPLE_RATE=1.0,
        )
        with tracer.start_as_current_span("probe") as span:
            assert span.is_recording()

    def test_otlp_headers_never_logged(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        secret_header_value = "super-secret-otlp-header-value"
        with caplog.at_level(logging.DEBUG):
            _configure_observability_no_network(
                monkeypatch,
                OBSERVABILITY_ENABLED=True,
                OTEL_EXPORTER_OTLP_ENDPOINT="http://phoenix:6006/v1/traces",
                OTEL_EXPORTER_OTLP_HEADERS=f"authorization={secret_header_value}",
            )

        assert all(secret_header_value not in record.message for record in caplog.records)


class TestTracedStage:
    def test_sets_sanitized_attributes(self) -> None:
        tracer, exporter = _tracer_with_in_memory_exporter()
        document_id = uuid.uuid4()

        with traced_stage(tracer, "shiruno.retrieval", document_id=document_id, count=3):
            pass

        (span,) = exporter.get_finished_spans()
        assert span.name == "shiruno.retrieval"
        assert span.attributes is not None
        assert span.attributes["document_id"] == str(document_id)
        assert span.attributes["count"] == 3

    def test_body_exception_propagates_and_is_not_swallowed(self) -> None:
        tracer, _ = _tracer_with_in_memory_exporter()

        with pytest.raises(ValueError, match="boom"):
            with traced_stage(tracer, "shiruno.llm_generation"):
                raise ValueError("boom")

    def test_no_record_exception_side_effect_on_body_failure(self) -> None:
        tracer, exporter = _tracer_with_in_memory_exporter()

        with pytest.raises(RuntimeError):
            with traced_stage(tracer, "shiruno.llm_generation"):
                raise RuntimeError("raw provider detail that must never be exported")

        (span,) = exporter.get_finished_spans()
        assert span.events == ()

    def test_swallows_exception_from_broken_tracer(self) -> None:
        class _BrokenTracer:
            def start_as_current_span(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("instrumentation bug")

        executed = False
        with traced_stage(_BrokenTracer(), "shiruno.retrieval") as span:  # type: ignore[arg-type]
            executed = True
            span.set_attribute("a", "b")  # no-op span must not raise either

        assert executed

    def test_yields_usable_noop_span_on_start_failure(self) -> None:
        class _BrokenTracer:
            def start_as_current_span(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("instrumentation bug")

        with traced_stage(_BrokenTracer(), "shiruno.retrieval") as span:  # type: ignore[arg-type]
            span.set_status(trace.Status(trace.StatusCode.ERROR, "x"))
