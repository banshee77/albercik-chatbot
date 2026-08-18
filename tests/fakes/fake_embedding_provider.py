"""Deterministic in-memory EmbeddingProvider test double (research.md
§4a/§8). MUST NOT import `sentence_transformers` — this is the only
`EmbeddingProvider` any automated test injects (Design Constraint 2,
tasks.md); the real `LocalSentenceTransformerEmbeddingProvider` is never
exercised by the test suite.

The same input text always produces the same 384-dim, unit-normalized
vector (matching the real provider's `normalize_embeddings=True`
behavior), so `pgvector` cosine-similarity tests get consistent, repeatable
results without loading real model weights. Deliberately does NOT
replicate the real provider's E5 query/passage prefixing — that's a
model-specific implementation detail this fake has no reason to know
about (Principle VI); `embed_query(text)` and `embed_passages([text])[0]`
return the same vector for the same `text`, which is what makes the
"seed a chunk's embedding as the exact vector a question will produce"
testing trick (tests/contract/test_chat.py, tests/integration/
test_retrieval_pgvector.py) work.
"""

import hashlib
import math
import random
from collections.abc import Sequence

from albercik_chatbot.providers.embedding.protocol import EMBEDDING_DIMENSIONS


def _deterministic_vector(text: str) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    raw = [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIMENSIONS)]
    norm = math.sqrt(sum(component * component for component in raw)) or 1.0
    return [component / norm for component in raw]


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.embed_calls: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return _deterministic_vector(text)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]
