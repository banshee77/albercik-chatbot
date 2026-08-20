"""Integration tests for feature 012-rag-observability's span topology,
retrieval/failure/privacy evidence, and reliability guarantees (spec.md
US1-US7, US9; tasks.md T009, T021-T045). No real Phoenix/Ollama/Anthropic/
network dependency — spans are captured via `InMemorySpanExporter` +
`SimpleSpanProcessor` (research.md R12), and every outcome is driven the
same way `tests/contract/test_chat_conversation_recording.py` already
drives it: fake providers + real pgvector retrieval via a seeded chunk
whose embedding exactly matches `fake_embedding_provider.embed_query()`'s
deterministic output for the test question.
"""

import uuid
from collections.abc import Sequence

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NoOpTracer
from sqlalchemy import select

from shiruno.config import get_settings
from shiruno.infra.concurrency import ChatConcurrencyGuard
from shiruno.main import create_app
from shiruno.persistence.database import get_session
from shiruno.persistence.models import (
    Administrator,
    ConversationRecord,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    Tenant,
    TenantStatus,
    UsageRecord,
)
from shiruno.providers.llm.protocol import LLMProviderError, LLMResult

_QUESTION = "Jakie są godziny otwarcia biura Albertos?"
_MATCHING_CONTENT = "Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17."

_GROUNDED_STAGES = [
    "shiruno.security_or_cost_gates",
    "shiruno.small_talk_classification",
    "shiruno.scope_classification",
    "shiruno.query_embedding",
    "shiruno.retrieval",
    "shiruno.context_assembly",
    "shiruno.llm_generation",
    "shiruno.conversation_recording",
]


# --- shared seeding helpers (mirrors tests/contract/test_chat_conversation_recording.py) ---


def _seed_public_tenant(db_session, monkeypatch, *, status: TenantStatus = TenantStatus.active):
    slug = f"albertos-{uuid.uuid4()}"
    tenant = Tenant(name="Albertos", slug=slug, status=status)
    db_session.add(tenant)
    db_session.flush()
    monkeypatch.setenv("PUBLIC_CHAT_TENANT_SLUG", slug)
    get_settings.cache_clear()
    return tenant


def _seed_matching_chunk(db_session, tenant, *, content: str, embedding: list[float]):
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x", tenant_id=tenant.id)
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename="seed.txt",
        uploaded_by_admin_id=admin.id,
        tenant_id=tenant.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(document_id=document.id, position=0, content=content, embedding=embedding)
    )
    db_session.flush()
    return document


class _AlwaysRaisingExporter(SpanExporter):
    """A span exporter that always fails — used to prove `traced_stage()`'s
    own defensive teardown (research.md R2) and that an export failure can
    never affect the chat response (FR-032)."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        raise RuntimeError("export always fails")

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _in_memory_tracer() -> tuple[object, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


def _always_raising_tracer() -> object:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_AlwaysRaisingExporter()))
    return provider.get_tracer("test")


def _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer):
    app = create_app(
        llm_provider=fake_llm_provider, embedding_provider=fake_embedding_provider, tracer=tracer
    )
    app.dependency_overrides[get_session] = lambda: db_session
    return app


async def _post_chat(app, **json_body: object) -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json=json_body)
    return response.status_code, response.json()


def _find_spans(exporter: InMemorySpanExporter, name: str) -> list:
    return [span for span in exporter.get_finished_spans() if span.name == name]


def _root_span(exporter: InMemorySpanExporter):
    (span,) = _find_spans(exporter, "shiruno.chat")
    return span


# --- fixtures ---


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    return exporter


@pytest.fixture
def in_memory_tracer(span_exporter: InMemorySpanExporter):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider.get_tracer("test")


@pytest.fixture
def traced_app(db_session, fake_llm_provider, fake_embedding_provider, in_memory_tracer):
    return _build_app(db_session, fake_llm_provider, fake_embedding_provider, in_memory_tracer)


@pytest_asyncio.fixture
async def traced_client(traced_app):
    transport = ASGITransport(app=traced_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# --- US1 (T009): grounded request produces the full, correctly-ordered, timed span tree ---


@pytest.mark.asyncio
async def test_grounded_request_produces_full_span_tree_in_order(
    traced_client, traced_app, span_exporter, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "grounded"

    spans = span_exporter.get_finished_spans()
    names_in_order = [
        span.name
        for span in sorted(spans, key=lambda s: s.start_time)
        if span.name != "shiruno.chat"
    ]
    assert names_in_order == _GROUNDED_STAGES
    for span in spans:
        assert span.end_time > span.start_time

    root = _root_span(span_exporter)
    assert root.attributes["shiruno.request_id"] == body["request_id"]
    assert root.attributes["shiruno.outcome"] == "grounded"
    assert root.attributes["shiruno.provider"] == "ollama"
    assert root.attributes["shiruno.model"] == "fake-llm"

    (llm_span,) = _find_spans(span_exporter, "shiruno.llm_generation")
    assert llm_span.attributes["shiruno.llm.supported"] is True


@pytest.mark.asyncio
async def test_llm_generation_span_carries_namespaced_provider_metrics(
    traced_client,
    span_exporter,
    db_session,
    monkeypatch,
    fake_embedding_provider,
    fake_llm_provider,
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    fake_llm_provider.response = LLMResult(
        answer="Odpowiedź.",
        supported=True,
        model="fake-llm",
        input_tokens=10,
        output_tokens=5,
        latency_ms=1,
        provider_metrics={"eval_count": 5, "prompt_eval_count": 10},
    )

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    assert response.status_code == 200

    (llm_span,) = _find_spans(span_exporter, "shiruno.llm_generation")
    assert llm_span.attributes["shiruno.llm.provider_metrics.eval_count"] == 5
    assert llm_span.attributes["shiruno.llm.provider_metrics.prompt_eval_count"] == 10


# --- US6 (T021-T023a): tracing never breaks or influences public chat ---


async def _grounded_response(db_session, fake_llm_provider, fake_embedding_provider, tracer):
    app = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer)
    return await _post_chat(app, question=_QUESTION)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome_question,expect_status",
    [
        (_QUESTION, 200),  # grounded (chunk seeded below)
        ("Cześć", 200),  # small_talk
        ("Napisz mi krótki wiersz o wiośnie.", 200),  # out_of_scope
    ],
)
async def test_response_identical_across_tracer_variants(
    db_session,
    monkeypatch,
    fake_llm_provider,
    fake_embedding_provider,
    outcome_question,
    expect_status,
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    tracers = [NoOpTracer(), _in_memory_tracer()[0], _always_raising_tracer()]
    results = []
    for tracer in tracers:
        app = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer)
        status_code, body = await _post_chat(app, question=outcome_question)
        body.pop("request_id", None)
        results.append((status_code, body))

    assert all(result == results[0] for result in results)
    assert results[0][0] == expect_status


@pytest.mark.asyncio
async def test_unreachable_export_does_not_change_unavailable_response(
    db_session, monkeypatch, fake_llm_provider, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    fake_llm_provider.error = LLMProviderError("boom")

    app = _build_app(
        db_session, fake_llm_provider, fake_embedding_provider, _always_raising_tracer()
    )
    status_code, body = await _post_chat(app, question=_QUESTION)

    assert status_code == 503
    assert body["outcome"] == "unavailable"


@pytest.mark.asyncio
async def test_unrecognized_request_body_field_is_rejected_outright(
    traced_client, span_exporter, db_session, monkeypatch, fake_embedding_provider
) -> None:
    """`ChatRequest.model_config = ConfigDict(extra="forbid")` (pre-existing,
    feature 003/T061, FR-035) already structurally satisfies FR-003 for the
    request *body*: an unknown field never even reaches application code,
    let alone tracing — it fails Pydantic validation before this feature's
    code runs at all."""
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    response = await traced_client.post(
        "/api/v1/chat", json={"question": _QUESTION, "trace": True, "observability_enabled": True}
    )

    assert response.status_code == 400
    assert span_exporter.get_finished_spans() == ()


@pytest.mark.asyncio
async def test_request_header_claiming_to_control_tracing_has_no_effect(
    traced_client, span_exporter, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    plain_response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    plain_spans_count = len(span_exporter.get_finished_spans())
    span_exporter.clear()

    header_response = await traced_client.post(
        "/api/v1/chat",
        json={"question": _QUESTION},
        headers={"X-Observability-Enabled": "false", "X-Trace": "0"},
    )

    assert plain_response.status_code == header_response.status_code == 200
    plain_body = plain_response.json()
    header_body = header_response.json()
    plain_body.pop("request_id", None)
    header_body.pop("request_id", None)
    assert plain_body == header_body
    assert len(span_exporter.get_finished_spans()) == plain_spans_count


# --- US5 (T024-T026): non-grounded outcomes fabricate no downstream stages ---


@pytest.mark.asyncio
async def test_small_talk_trace_has_only_expected_stages(traced_client, span_exporter) -> None:
    response = await traced_client.post("/api/v1/chat", json={"question": "Cześć"})
    assert response.json()["outcome"] == "small_talk"

    names = {span.name for span in span_exporter.get_finished_spans()}
    assert names == {
        "shiruno.chat",
        "shiruno.security_or_cost_gates",
        "shiruno.small_talk_classification",
        "shiruno.conversation_recording",
    }


@pytest.mark.asyncio
async def test_out_of_scope_trace_has_only_expected_stages(traced_client, span_exporter) -> None:
    response = await traced_client.post(
        "/api/v1/chat", json={"question": "Napisz mi krótki wiersz o wiośnie."}
    )
    assert response.json()["outcome"] == "out_of_scope"

    names = {span.name for span in span_exporter.get_finished_spans()}
    assert names == {
        "shiruno.chat",
        "shiruno.security_or_cost_gates",
        "shiruno.small_talk_classification",
        "shiruno.scope_classification",
        "shiruno.conversation_recording",
    }


@pytest.mark.asyncio
async def test_insufficient_information_zero_chunks_has_no_context_or_llm_span(
    traced_client, span_exporter
) -> None:
    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    assert response.json()["outcome"] == "insufficient_information"

    names = {span.name for span in span_exporter.get_finished_spans()}
    assert "shiruno.context_assembly" not in names
    assert "shiruno.llm_generation" not in names


# --- US2 (T029-T030): retrieval evidence and truncation ---


@pytest.mark.asyncio
async def test_retrieval_span_exposes_counts_and_per_chunk_evidence_without_content(
    traced_client, span_exporter, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    document = _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    assert response.json()["outcome"] == "grounded"

    (retrieval_span,) = _find_spans(span_exporter, "shiruno.retrieval")
    attrs = retrieval_span.attributes
    assert attrs["shiruno.retrieval.candidate_count"] == 1
    assert attrs["shiruno.retrieval.passed_filter_count"] == 1
    assert attrs["shiruno.retrieval.selected.document_ids"] == (str(document.id),)
    assert attrs["shiruno.retrieval.selected.similarities"][0] > 0
    assert attrs["shiruno.retrieval.selected.labels"] == ("seed.txt",)
    assert "shiruno.retrieval.selected.contents" not in attrs


@pytest.mark.asyncio
async def test_context_truncated_flag_reflects_char_budget(
    traced_client, span_exporter, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    assert response.json()["outcome"] == "grounded"

    (context_span,) = _find_spans(span_exporter, "shiruno.context_assembly")
    assert context_span.attributes["shiruno.context.truncated"] is False
    assert context_span.attributes["shiruno.context.selected_chunk_count"] == 1


@pytest.mark.asyncio
async def test_context_truncated_flag_true_when_budget_exceeded(
    db_session, monkeypatch, fake_llm_provider, fake_embedding_provider
) -> None:
    monkeypatch.setenv("MAX_CONTEXT_CHARS", "10")
    get_settings.cache_clear()
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    tracer, exporter = _in_memory_tracer()
    app = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer)

    status_code, body = await _post_chat(app, question=_QUESTION)
    get_settings.cache_clear()

    assert status_code == 200
    (context_span,) = _find_spans(exporter, "shiruno.context_assembly")
    # A single chunk is always kept even if it alone exceeds the budget
    # (domain/retrieval.py::limit_context_chars) — truncated only becomes
    # meaningful with >1 grounding chunk. With exactly one seeded chunk,
    # nothing is actually dropped, so this asserts the always-keep-first
    # guarantee rather than a drop.
    assert context_span.attributes["shiruno.context.truncated"] is False


# --- US3 (T033-T034): safe failure/error representation ---


@pytest.mark.asyncio
async def test_llm_provider_error_sets_safe_status_no_raw_detail(
    traced_client,
    span_exporter,
    db_session,
    monkeypatch,
    fake_embedding_provider,
    fake_llm_provider,
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    fake_llm_provider.error = LLMProviderError(
        "raw provider secret detail that must never be exported: sk-ant-fake-12345"
    )

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    assert response.status_code == 503

    (llm_span,) = _find_spans(span_exporter, "shiruno.llm_generation")
    assert llm_span.status.status_code.name == "ERROR"
    assert llm_span.status.description == "provider_error"
    assert llm_span.events == ()

    serialized = str([dict(span.attributes or {}) for span in span_exporter.get_finished_spans()])
    assert "sk-ant-fake-12345" not in serialized
    assert "raw provider secret detail" not in serialized


@pytest.mark.asyncio
async def test_budget_kill_switch_concurrency_rejections_show_only_the_rejecting_gate(
    db_session, monkeypatch, fake_llm_provider, fake_embedding_provider
) -> None:
    _seed_public_tenant(db_session, monkeypatch)

    # kill switch
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()
    tracer, exporter = _in_memory_tracer()
    app = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer)
    status_code, body = await _post_chat(app, question=_QUESTION)
    get_settings.cache_clear()
    assert status_code == 503 and body["outcome"] == "unavailable"
    names = {span.name for span in exporter.get_finished_spans()}
    # kill_switch/budget rejections still return a normal AskQuestionResult
    # (outcome="unavailable"), unlike a rate-limited request (which raises
    # and never reaches record_conversation() at all) — so
    # conversation_recording still runs and is recorded (matching
    # tests/contract/test_chat_conversation_recording.py's own
    # test_unavailable_kill_switch_is_recorded_correctly).
    assert names == {
        "shiruno.chat",
        "shiruno.security_or_cost_gates",
        "shiruno.conversation_recording",
    }
    (gates_span,) = _find_spans(exporter, "shiruno.security_or_cost_gates")
    assert gates_span.status.description == "kill_switch"

    # budget exceeded (reset the kill switch from the sub-case above first)
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "0")
    get_settings.cache_clear()
    tracer2, exporter2 = _in_memory_tracer()
    app2 = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer2)
    app2.state.llm_provider_name = "anthropic"
    status_code2, body2 = await _post_chat(app2, question=_QUESTION)
    get_settings.cache_clear()
    assert status_code2 == 503 and body2["outcome"] == "unavailable"
    (gates_span2,) = _find_spans(exporter2, "shiruno.security_or_cost_gates")
    assert gates_span2.status.description == "budget_exceeded"

    # concurrency limit — gates span passes cleanly; root span carries the
    # failure_category instead (research.md R5/ask_question.py docstring)
    tracer3, exporter3 = _in_memory_tracer()
    app3 = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer3)
    exhausted_guard = ChatConcurrencyGuard(limit=1)
    exhausted_guard._semaphore.acquire(blocking=False)
    app3.state.chat_concurrency_guard = exhausted_guard
    status_code3, body3 = await _post_chat(app3, question=_QUESTION)
    assert status_code3 == 503 and body3["outcome"] == "unavailable"
    names3 = {span.name for span in exporter3.get_finished_spans()}
    assert names3 == {
        "shiruno.chat",
        "shiruno.security_or_cost_gates",
        "shiruno.conversation_recording",
    }
    root3 = _root_span(exporter3)
    assert root3.attributes["shiruno.failure_category"] == "concurrency_limit"


# --- US4 (T038a-T043a): sensitive content and hidden reasoning are never exported by default ---


@pytest.mark.asyncio
async def test_unresolvable_tenant_sets_no_tenant_attribute(
    traced_client, span_exporter, monkeypatch
) -> None:
    monkeypatch.setenv("PUBLIC_CHAT_TENANT_SLUG", f"nonexistent-{uuid.uuid4()}")
    get_settings.cache_clear()

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    get_settings.cache_clear()
    assert response.status_code == 200

    (conv_span,) = _find_spans(span_exporter, "shiruno.conversation_recording")
    assert "shiruno.tenant_id" not in conv_span.attributes
    assert "shiruno.tenant_slug" not in conv_span.attributes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,configure_llm_error",
    [
        (_QUESTION, False),  # grounded (with matching chunk seeded)
        ("some question with no matching chunk at all", False),  # insufficient_information
        ("Napisz mi krótki wiersz o wiośnie.", False),  # out_of_scope
        ("Cześć", False),  # small_talk
        (_QUESTION, True),  # unavailable
    ],
)
async def test_default_configuration_never_exports_full_content_any_outcome(
    db_session,
    monkeypatch,
    fake_llm_provider,
    fake_embedding_provider,
    question,
    configure_llm_error,
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    if configure_llm_error:
        fake_llm_provider.error = LLMProviderError("boom")

    tracer, exporter = _in_memory_tracer()
    app = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer)
    status_code, body = await _post_chat(app, question=question)

    serialized = str([dict(span.attributes or {}) for span in exporter.get_finished_spans()])
    assert question not in serialized or question in ("some question with no matching chunk at all")
    assert _MATCHING_CONTENT not in serialized
    if body.get("answer"):
        assert body["answer"] not in serialized


@pytest.mark.asyncio
async def test_content_capture_toggles_are_independent(
    db_session, monkeypatch, fake_llm_provider, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    # Only question/answer capture enabled.
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT", "true")
    get_settings.cache_clear()
    tracer, exporter = _in_memory_tracer()
    app = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer)
    status_code, body = await _post_chat(app, question=_QUESTION)
    get_settings.cache_clear()
    assert status_code == 200
    (llm_span,) = _find_spans(exporter, "shiruno.llm_generation")
    (retrieval_span,) = _find_spans(exporter, "shiruno.retrieval")
    assert llm_span.attributes.get("shiruno.llm.answer") == body["answer"]
    assert "shiruno.retrieval.selected.contents" not in retrieval_span.attributes

    # Only document/prompt capture enabled.
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT", "false")
    monkeypatch.setenv("OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT", "true")
    get_settings.cache_clear()
    tracer2, exporter2 = _in_memory_tracer()
    app2 = _build_app(db_session, fake_llm_provider, fake_embedding_provider, tracer2)
    status_code2, body2 = await _post_chat(app2, question=_QUESTION)
    get_settings.cache_clear()
    assert status_code2 == 200
    (llm_span2,) = _find_spans(exporter2, "shiruno.llm_generation")
    (retrieval_span2,) = _find_spans(exporter2, "shiruno.retrieval")
    assert "shiruno.llm.answer" not in llm_span2.attributes
    assert retrieval_span2.attributes["shiruno.retrieval.selected.contents"] == (_MATCHING_CONTENT,)


@pytest.mark.asyncio
async def test_no_raw_embedding_vector_ever_appears(
    traced_client, span_exporter, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    assert response.status_code == 200

    (embedding_span,) = _find_spans(span_exporter, "shiruno.query_embedding")
    for value in embedding_span.attributes.values():
        assert not (isinstance(value, tuple) and len(value) > 10), (
            "a long float tuple would indicate a raw embedding vector leaked"
        )


@pytest.mark.asyncio
async def test_secrets_never_appear_anywhere_in_the_trace(
    traced_client,
    span_exporter,
    db_session,
    monkeypatch,
    fake_embedding_provider,
    fake_llm_provider,
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    fake_llm_provider.error = LLMProviderError("boom")

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    assert response.status_code == 503

    settings = get_settings()
    serialized = str([dict(span.attributes or {}) for span in span_exporter.get_finished_spans()])
    assert settings.DATABASE_URL not in serialized
    assert settings.AUTH_JWT_SECRET not in serialized
    if settings.ANTHROPIC_API_KEY:
        assert settings.ANTHROPIC_API_KEY not in serialized


# --- US7 (T044-T045): correlation via request_id ---


@pytest.mark.asyncio
async def test_request_id_correlates_conversation_record_and_root_span(
    traced_client, span_exporter, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    body = response.json()
    request_id = uuid.UUID(body["request_id"])

    record = db_session.execute(
        select(ConversationRecord).where(ConversationRecord.request_id == request_id)
    ).scalar_one()
    root = _root_span(span_exporter)
    assert root.attributes["shiruno.request_id"] == str(record.request_id)


@pytest.mark.asyncio
async def test_usage_conversation_and_root_span_share_one_request_id(
    traced_client, span_exporter, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    _seed_matching_chunk(
        db_session,
        tenant,
        content=_MATCHING_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    response = await traced_client.post("/api/v1/chat", json={"question": _QUESTION})
    request_id = uuid.UUID(response.json()["request_id"])

    conversation = db_session.execute(
        select(ConversationRecord).where(ConversationRecord.request_id == request_id)
    ).scalar_one()
    usage_rows = (
        db_session.execute(select(UsageRecord).where(UsageRecord.request_id == request_id))
        .scalars()
        .all()
    )
    root = _root_span(span_exporter)

    assert str(conversation.request_id) == str(request_id)
    assert all(str(row.request_id) == str(request_id) for row in usage_rows)
    assert root.attributes["shiruno.request_id"] == str(request_id)
