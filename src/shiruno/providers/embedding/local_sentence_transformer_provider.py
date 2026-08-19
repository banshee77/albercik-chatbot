"""LocalSentenceTransformerEmbeddingProvider — the only file in the
codebase importing `sentence_transformers` (Principle VI; Design
Constraint 2, tasks.md).

Runs entirely in-process, CPU-only — no external embedding API, no
embedding-provider API key, no separate embedding-serving process
(research.md §4/§4a). The underlying `SentenceTransformer` model is loaded
**at most once per application process**: `_load_model` is process-cache
keyed by model name, so even repeated `LocalSentenceTransformerEmbeddingProvider`
construction (which `main.py`, T021, avoids anyway by building one instance
at startup) never re-triggers a load.

Offline-only runtime loading (post-Phase-2 validation fix): the Docker
image pre-downloads model weights at build time (Dockerfile), so the
container has its own local Hugging Face cache before the app ever starts.
`HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` are set here — before importing
`sentence_transformers`, so `huggingface_hub`'s offline-mode constants pick
them up — as a process-wide belt, and `local_files_only=True` is passed
explicitly to `SentenceTransformer(...)` as the suspenders: even if some
call path ignores the env vars, the constructor itself is forced to the
local cache and raises immediately instead of reaching out to
huggingface.co. `setdefault` lets an operator explicitly opt back into
online mode (e.g. to warm a fresh cache outside the Docker build) without a
code change.

E5 query/passage prefixing (post-Phase-3 calibration fix): `intfloat/
multilingual-e5-small` is trained asymmetrically and documents that
queries and passages must be prefixed with `"query: "` / `"passage: "`
respectively to get its intended retrieval quality. This class is the
*only* place in the codebase that knows that — `EmbeddingProvider`'s
`embed_query`/`embed_passages` split (protocol.py) exists precisely so
`domain/`/`application/` code can ask for a query or a passage embedding
without ever knowing which concrete model, or prefixing convention, is
behind it (Principle VI).
"""

import os
from collections.abc import Sequence
from functools import cache

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from sentence_transformers import SentenceTransformer  # noqa: E402

from albercik_chatbot.providers.embedding.protocol import EMBEDDING_DIMENSIONS  # noqa: E402

_QUERY_PREFIX = "query: "
_PASSAGE_PREFIX = "passage: "


@cache
def _load_model(model_name: str) -> SentenceTransformer:
    model: SentenceTransformer = SentenceTransformer(model_name, local_files_only=True)
    return model


class LocalSentenceTransformerEmbeddingProvider:
    def __init__(self, *, model_name: str) -> None:
        self._model_name = model_name
        self._model = _load_model(model_name)

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(f"{_QUERY_PREFIX}{text}", normalize_embeddings=True)
        result = vector.tolist()
        assert len(result) == EMBEDDING_DIMENSIONS, (
            f"{self._model_name} produced {len(result)}-dim output, "
            f"expected {EMBEDDING_DIMENSIONS} (data-model.md vector(384) contract)"
        )
        return result

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        prefixed = [f"{_PASSAGE_PREFIX}{text}" for text in texts]
        vectors = self._model.encode(prefixed, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]
