"""Contract tests for the additive `small_talk` outcome on
`POST /api/v1/chat` (feature 007-conversational-chat-ux, User Story 1;
contracts/small-talk-classification-contract.md). Uses the existing fake
LLM/embedding providers (research.md §8) to prove small talk touches
neither — no real Ollama, Anthropic, GPU, or network access required.

Also proves the Clarifications (2026-08-19) safeguard-ordering guarantee:
rate limiting, the LLM kill switch, the budget check, and the concurrency
guard all still apply to a small-talk-shaped request exactly as they do to
any other request, since small-talk classification runs strictly after
all of them in `application/ask_question.py` (SC-009).

User Story 2 (tasks.md T015/T016): a greeting/thanks/courtesy prefix or
suffix on a genuine factual question must never be swallowed by the
small-talk short-circuit — these messages must reach the existing,
unmodified scope/retrieval/LLM pipeline exactly as the same question would
without the small-talk phrase, and plain factual/off-topic questions with
no small-talk phrase at all must keep producing the exact same
`insufficient_information`/`out_of_scope` outcomes as before this feature.
"""

import uuid

import pytest
from sqlalchemy import select

from shiruno.config import get_settings
from shiruno.infra.concurrency import ChatConcurrencyGuard
from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    ProviderKind,
    ProviderName,
    Tenant,
    UsageRecord,
)
from tests.fixtures.provider_app import build_app, client_for


def _seed_document_with_chunk(db_session, *, filename: str, content: str, embedding: list[float]):
    tenant = Tenant(name=f"Tenant {uuid.uuid4()}", slug=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    db_session.flush()
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x", tenant_id=tenant.id)
    db_session.add(admin)
    db_session.flush()

    document = KnowledgeDocument(
        original_filename=filename,
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


_SMALL_TALK_EXAMPLES = [
    pytest.param("Cześć", id="greeting"),
    pytest.param("Dzięki!", id="thanks"),
    pytest.param("Do zobaczenia", id="goodbye"),
    pytest.param("Jak się masz?", id="courtesy"),
    pytest.param("W czym możesz mi pomóc?", id="capability"),
    pytest.param("Czy jesteś człowiekiem?", id="identity"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("question", _SMALL_TALK_EXAMPLES)
async def test_small_talk_message_returns_small_talk_outcome_with_zero_provider_calls(
    question: str,
    db_async_client,
    db_session,
    fake_llm_provider,
    fake_embedding_provider,
) -> None:
    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "small_talk"
    assert body["answer"]
    assert body["sources"] == []

    # Zero embedding/retrieval and zero LLM invocation (testing
    # requirements 11-12): the fakes' own call logs are the proof, not an
    # assumption about what the classifier "should" have skipped.
    assert fake_llm_provider.call_count == 0
    assert fake_embedding_provider.embed_calls == []

    # No LLM usage record is ever written for a small_talk outcome
    # (mirrors the existing out_of_scope/pre-retrieval-insufficient
    # behavior) — testing requirement 11.
    usage_rows = db_session.execute(select(UsageRecord)).scalars().all()
    assert usage_rows == []


@pytest.mark.asyncio
async def test_rate_limit_still_applies_to_a_small_talk_shaped_request(
    db_async_client, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "2")
    get_settings.cache_clear()

    for _ in range(2):
        response = await db_async_client.post("/api/v1/chat", json={"question": "Cześć"})
        assert response.status_code == 200

    embed_calls_before = len(fake_embedding_provider.embed_calls)
    llm_calls_before = fake_llm_provider.call_count

    response = await db_async_client.post("/api/v1/chat", json={"question": "Cześć"})

    get_settings.cache_clear()

    assert response.status_code == 429
    assert "retry-after" in {k.lower() for k in response.headers.keys()}
    # The rejected request never even reaches small-talk classification,
    # let alone retrieval/the LLM.
    assert len(fake_embedding_provider.embed_calls) == embed_calls_before
    assert fake_llm_provider.call_count == llm_calls_before


@pytest.mark.asyncio
async def test_kill_switch_off_short_circuits_a_small_talk_shaped_request_before_classification(
    db_async_client, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    response = await db_async_client.post("/api/v1/chat", json={"question": "Cześć"})

    get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    # The kill switch resolves to "unavailable" before small-talk
    # classification is ever reached — "Cześć" is never allowed to
    # override a kill-switched pipeline into answering anyway.
    assert body["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0
    assert fake_embedding_provider.embed_calls == []


@pytest.mark.asyncio
async def test_exhausted_budget_short_circuits_a_small_talk_shaped_request(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "1")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    db_session.add(
        UsageRecord(
            request_id=uuid.uuid4(),
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName.anthropic,
            provider_model="claude-sonnet-4-5",
            input_tokens=10,
            output_tokens=5,
            success=True,
            latency_ms=100,
        )
    )
    db_session.flush()

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": "Cześć"})

    get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_concurrency_guard_short_circuits_a_small_talk_shaped_request(
    db_async_client, test_app, fake_llm_provider, fake_embedding_provider
) -> None:
    guard = ChatConcurrencyGuard(limit=1)
    test_app.state.chat_concurrency_guard = guard
    guard._semaphore.acquire()  # simulates an already in-flight paid LLM call
    try:
        response = await db_async_client.post("/api/v1/chat", json={"question": "Cześć"})
    finally:
        guard._semaphore.release()

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0
    assert fake_embedding_provider.embed_calls == []


# --- User Story 2: greeting/thanks/courtesy-prefixed real questions must
# reach the normal RAG pipeline, never the small-talk short-circuit ---

_MIXED_INTENT_EXAMPLES = [
    pytest.param("Cześć, o której są treningi początkujących w Wierzbinie?", id="greeting_prefix"),
    pytest.param("Dzień dobry, ile kosztuje egzamin na 8 kyu?", id="different_greeting_prefix"),
    pytest.param("O której są treningi początkujących? Dzięki!", id="thanks_suffix"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("question", _MIXED_INTENT_EXAMPLES)
async def test_mixed_intent_question_with_matching_content_is_grounded_not_small_talk(
    question: str, db_async_client, db_session, fake_embedding_provider
) -> None:
    document = _seed_document_with_chunk(
        db_session,
        filename="egzaminy.txt",
        content="Treningi początkujących w Wierzbinie i koszt egzaminu na 8 kyu.",
        embedding=fake_embedding_provider.embed_query(question),
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "grounded"
    assert body["outcome"] != "small_talk"
    assert body["sources"] == [{"document_id": str(document.id), "label": "egzaminy.txt"}]
    # Retrieval *was* invoked for this message — proof it actually reached
    # the RAG pipeline rather than short-circuiting.
    assert question in fake_embedding_provider.embed_calls


@pytest.mark.asyncio
async def test_mixed_intent_question_with_no_matching_content_is_insufficient_information(
    db_async_client, fake_embedding_provider
) -> None:
    question = "Dzięki, a kiedy jest następny egzamin?"

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    assert body["outcome"] != "small_talk"
    assert body["sources"] == []
    assert question in fake_embedding_provider.embed_calls


@pytest.mark.asyncio
async def test_plain_factual_question_insufficient_information_outcome_is_unchanged(
    db_async_client,
) -> None:
    """Regression (FR-005, SC-003): a plain factual question with no
    small-talk phrase at all must produce the exact same
    `insufficient_information` outcome/message as pre-feature 006/004
    behavior — byte-for-byte, not just "still an error"."""
    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    assert (
        body["answer"] == "Nie mam wystarczających informacji w bazie wiedzy Albertos, "
        "aby odpowiedzieć na to pytanie."
    )
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_plain_off_topic_question_out_of_scope_outcome_is_unchanged(
    db_async_client,
) -> None:
    """Regression (FR-005, SC-003): a plain off-topic question with no
    small-talk phrase at all must produce the exact same `out_of_scope`
    outcome/message as pre-feature behavior."""
    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Napisz mi krótki wiersz o wiośnie."}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "out_of_scope"
    assert (
        body["answer"]
        == "Odpowiadam wyłącznie na pytania związane z Albertos. Nie mogę pomóc z tym pytaniem."
    )
    assert body["sources"] == []


# --- User Story 3: identity questions must not claim to be human, must
# never introduce a new outcome value (still "small_talk"), and a real
# question mixed with an identity question must still reach RAG ---

_IDENTITY_QUESTIONS = [
    pytest.param("Czy jesteś człowiekiem?", id="czy_jestes_czlowiekiem"),
    pytest.param("Kim jesteś?", id="kim_jestes"),
    pytest.param("Jesteś botem?", id="jestes_botem"),
]

# Words that would indicate the assistant is misrepresenting itself as
# human, an employee, or a trainer — none may appear in the identity reply.
_MISLEADING_CLAIM_WORDS = ("jestem człowiekiem", "trenerem", "pracownikiem", "instruktorem")


@pytest.mark.asyncio
@pytest.mark.parametrize("question", _IDENTITY_QUESTIONS)
async def test_identity_question_returns_small_talk_with_a_non_misleading_reply(
    question: str, db_async_client, db_session, fake_llm_provider, fake_embedding_provider
) -> None:
    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    # No new outcome value was introduced for identity — it is still the
    # same additive "small_talk" outcome from User Story 1.
    assert body["outcome"] == "small_talk"

    answer_lower = body["answer"].lower()
    assert "wirtualn" in answer_lower
    assert "asystent" in answer_lower
    for misleading in _MISLEADING_CLAIM_WORDS:
        assert misleading not in answer_lower

    assert fake_llm_provider.call_count == 0
    assert fake_embedding_provider.embed_calls == []
    usage_rows = db_session.execute(select(UsageRecord)).scalars().all()
    assert usage_rows == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "Kim jesteś i kiedy są treningi?",
        "Czy jesteś człowiekiem i ile kosztuje egzamin?",
        "Jesteś botem? A kiedy jest obóz?",
    ],
)
async def test_identity_question_combined_with_real_question_reaches_rag_pipeline(
    question: str, db_async_client, db_session, fake_embedding_provider
) -> None:
    _seed_document_with_chunk(
        db_session,
        filename="obozy.txt",
        content="Treningi, egzaminy i obozy Albertos — terminy i koszty.",
        embedding=fake_embedding_provider.embed_query(question),
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] != "small_talk"
    assert body["outcome"] == "grounded"
    assert question in fake_embedding_provider.embed_calls
