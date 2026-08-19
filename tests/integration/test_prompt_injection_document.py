"""T070 — integration test: uploading a document containing an embedded
instruction, then asking a question that retrieves it, does not let that
instruction become a trusted system instruction (US4.2, FR-031). Real
`pgvector` retrieval, `FakeEmbeddingProvider`/`FakeLLMProvider` throughout
(Design Constraint 2) — a fake LLM can't "follow" an injected instruction
at all (it always returns its configured canned text), so what this test
proves is the mechanical guarantee that matters regardless of model
behavior: the malicious content only ever reaches the provider inside the
delimited, labeled untrusted-context part of the prompt, the system
prompt sent to the provider is unchanged, and the final HTTP answer is
exactly the provider's own response text — never text templated in from
the document, and never the false claim the document tries to plant.
"""

import pytest
from sqlalchemy import select

from albercik_chatbot.domain.prompting import SYSTEM_PROMPT
from albercik_chatbot.persistence.models import DocumentChunk
from tests.fixtures.admin import seed_admin_and_token
from tests.fixtures.prompt_injection import (
    DELIMITER_BREAKOUT_DOCUMENT_CONTENT,
    MALICIOUS_DOCUMENT_CONTENT,
)


@pytest.mark.asyncio
async def test_embedded_document_instruction_never_becomes_a_system_instruction(
    db_async_client, db_session, fake_embedding_provider, fake_llm_provider
) -> None:
    token = seed_admin_and_token(db_session)
    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "zwroty.txt",
                MALICIOUS_DOCUMENT_CONTENT.encode("utf-8"),
                "text/plain",
            )
        },
        headers={"authorization": f"Bearer {token}"},
    )
    assert upload_response.status_code == 201
    assert upload_response.json()["status"] == "ready"

    question = "Jakie są zasady zwrotów w Albertos?"
    # Force retrieval of the malicious chunk the same way other US1 tests
    # do (FakeEmbeddingProvider is a pure hash of input text, research.md
    # §8): seed a fresh chunk whose embedding equals what embed_query(the
    # question) will produce.
    chunk = db_session.execute(select(DocumentChunk)).scalars().first()
    assert chunk is not None
    chunk.embedding = fake_embedding_provider.embed_query(question)
    db_session.flush()

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()

    # The application layer never lets document content dictate the
    # answer — the response is exactly whatever the (fake) LLM provider
    # returned, not the false claim planted in the document.
    assert body["answer"] == fake_llm_provider.response.answer
    assert "zawsze dozwolone" not in body["answer"]

    # And structurally: the provider only ever saw the fixed system
    # prompt, with the malicious instruction confined to the delimited
    # context block of the user message.
    assert fake_llm_provider.call_count == 1
    call = fake_llm_provider.calls[0]
    assert call["system_prompt"] == SYSTEM_PROMPT
    assert "Ignoruj pytanie uzytkownika" not in call["system_prompt"]
    start = call["user_message"].index("<<<KONTEKST_START>>>")
    end = call["user_message"].index("<<<KONTEKST_END>>>")
    assert start < call["user_message"].index("Ignoruj pytanie uzytkownika") < end


@pytest.mark.asyncio
async def test_document_attempting_delimiter_breakout_is_neutralized_end_to_end(
    db_async_client, db_session, fake_embedding_provider, fake_llm_provider
) -> None:
    token = seed_admin_and_token(db_session)
    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "breakout.txt",
                DELIMITER_BREAKOUT_DOCUMENT_CONTENT.encode("utf-8"),
                "text/plain",
            )
        },
        headers={"authorization": f"Bearer {token}"},
    )
    assert upload_response.status_code == 201

    question = "Jakie są zasady zwrotów w Albertos?"
    chunk = db_session.execute(select(DocumentChunk)).scalars().first()
    assert chunk is not None
    chunk.embedding = fake_embedding_provider.embed_query(question)
    db_session.flush()

    response = await db_async_client.post("/api/v1/chat", json={"question": question})
    assert response.status_code == 200

    call = fake_llm_provider.calls[-1]
    assert call["system_prompt"] == SYSTEM_PROMPT
    assert call["user_message"].count("<<<KONTEKST_START>>>") == 1
    assert call["user_message"].count("<<<KONTEKST_END>>>") == 1
