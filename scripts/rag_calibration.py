"""Phase 3 RAG calibration checkpoint — development tool, NOT part of the
automated test suite and NOT imported by any pytest test. Loads the real
`intfloat/multilingual-e5-small` model (never used in `tests/unit` or
`tests/contract`, which use `FakeEmbeddingProvider` exclusively) against
the synthetic fixture knowledge base in `tests/fixtures/albertos_kb/`.

Re-run after the E5 query/passage prefix fix (research.md §6 addendum,
2026-08-17): compares BEFORE (raw, unprefixed text — what the provider
used to send) against AFTER (via `LocalSentenceTransformerEmbeddingProvider
.embed_query`/`.embed_passages`, which now applies E5's documented
`"query: "`/`"passage: "` prefixes internally) side by side, for the same
23 questions across all 7 calibration categories.

Run with the repo virtualenv, and with HF_HUB_OFFLINE explicitly disabled
if the model isn't cached locally yet (the provider module defaults it to
"1" via `setdefault` for the Phase 1/2 offline-startup fix):

    HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 uv run python scripts/rag_calibration.py

No Anthropic call is made anywhere in this script — retrieval is
evaluated independently of the LLM.
"""

import math
from pathlib import Path

from sentence_transformers import SentenceTransformer

from shiruno.domain.chunking import chunk_text
from shiruno.domain.scope import is_albertos_scope
from shiruno.providers.embedding.local_sentence_transformer_provider import (
    LocalSentenceTransformerEmbeddingProvider,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "albertos_kb"
CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150
THRESHOLD = 0.80  # matches config.py's interim RETRIEVAL_RELEVANCE_THRESHOLD default
TOP_K = 5

QUESTIONS: dict[str, list[str]] = {
    "1_answerable": [
        "Ile dni mam na zwrot towaru?",
        "Jakie są koszty dostawy kurierem?",
        "Czy mogę zapłacić przy odbiorze?",
        "W jakich godzinach czynne jest biuro obsługi klienta?",
        "Jak mogę skontaktować się z Albertos mailowo?",
        "Co zrobić, jeśli produkt jest niedostępny?",
    ],
    "2_albertos_no_support": [
        "Czy Albertos ma program lojalnościowy dla stałych klientów?",
        "Czy mogę zmienić adres dostawy po złożeniu zamówienia?",
        "Jakie są ceny konkretnych produktów Albertos?",
    ],
    "3_unrelated": [
        "Jaka jest stolica Norwegii?",
        "Napisz mi wiersz o jesieni.",
        "Jaka będzie jutro pogoda?",
    ],
    "4_ambiguous": [
        "Jak to działa?",
        "Ile to kosztuje?",
        "Czy to jest dobre?",
    ],
    "5_paraphrase_no_keyword_overlap": [
        "Chcę oddać zakupioną rzecz, bo się rozmyśliłem, jak to zrobić?",
        "O której mogę zadzwonić, żeby ktoś odebrał?",
        "Czy muszę coś dopłacić, żeby paczka do mnie dotarła?",
    ],
    "6_very_short": [
        "Zwroty?",
        "Dostawa?",
        "Kontakt?",
    ],
    "7_mixed_intent": [
        "Jakie są koszty dostawy, a przy okazji opowiedz mi dowcip?",
        "Czy sklep jest czynny w niedzielę, i czy umiesz zaśpiewać piosenkę?",
    ],
}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


def load_chunks() -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    for path in sorted(FIXTURES_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        for piece in chunk_text(
            text, chunk_size_chars=CHUNK_SIZE_CHARS, chunk_overlap_chars=CHUNK_OVERLAP_CHARS
        ):
            chunks.append((path.name, piece))
    return chunks


def top_k(
    query_vector: list[float],
    chunks: list[tuple[str, str]],
    chunk_vectors: list[list[float]],
    k: int,
) -> list[tuple[str, str, float]]:
    scored = [
        (fname, content, cosine_similarity(query_vector, vec))
        for (fname, content), vec in zip(chunks, chunk_vectors, strict=True)
    ]
    scored.sort(key=lambda row: row[2], reverse=True)
    return scored[:k]


def main() -> None:
    chunks = load_chunks()

    print("Loading provider (AFTER: real E5 query/passage prefixing)...")
    provider = LocalSentenceTransformerEmbeddingProvider(
        model_name="intfloat/multilingual-e5-small"
    )

    print("Loading a second, independent raw model instance (BEFORE: no prefixing)...")
    raw_model = SentenceTransformer("intfloat/multilingual-e5-small", local_files_only=True)

    contents = [content for _, content in chunks]
    raw_vectors = raw_model.encode(contents, normalize_embeddings=True)
    chunk_vectors_before = [v.tolist() for v in raw_vectors]
    chunk_vectors_after = provider.embed_passages(contents)

    for category, questions in QUESTIONS.items():
        print(f"\n\n########## CATEGORY: {category} ##########")
        for question in questions:
            scope_result = is_albertos_scope(question)

            q_vector_before = raw_model.encode(question, normalize_embeddings=True).tolist()
            q_vector_after = provider.embed_query(question)

            results_before = top_k(q_vector_before, chunks, chunk_vectors_before, TOP_K)
            results_after = top_k(q_vector_after, chunks, chunk_vectors_after, TOP_K)

            print(f"\n--- Q: {question!r}")
            print(f"    scope_classifier: {'IN_SCOPE' if scope_result else 'OUT_OF_SCOPE'}")

            print("    [BEFORE: no E5 prefix] top results:")
            for fname, content, score in results_before[:3]:
                accept = "ACCEPT" if score >= THRESHOLD else "reject"
                snippet = content[:70].replace("\n", " ")
                print(f"      {score:.4f} [{accept}] {fname}: {snippet}...")

            print("    [AFTER: query:/passage: prefixed] top results:")
            for fname, content, score in results_after[:3]:
                accept = "ACCEPT" if score >= THRESHOLD else "reject"
                snippet = content[:70].replace("\n", " ")
                print(f"      {score:.4f} [{accept}] {fname}: {snippet}...")


if __name__ == "__main__":
    main()
