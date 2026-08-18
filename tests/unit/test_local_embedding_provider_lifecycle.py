"""T020 — proves LocalSentenceTransformerEmbeddingProvider loads its model
at most once per process (Design Constraint 2, tasks.md). Mocks
`sentence_transformers.SentenceTransformer` so no real weights are ever
downloaded or loaded — this test must run fast and offline.

Also proves the offline-startup fix (post-Phase-2 validation): the module
sets HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE before importing
`sentence_transformers`, and always constructs `SentenceTransformer` with
`local_files_only=True`, so no test or runtime code path can accidentally
trigger a Hugging Face Hub network call.

Also proves the E5 query/passage prefixing fix (post-Phase-3 calibration):
`embed_query`/`embed_passages` must send `"query: "`/`"passage: "`-prefixed
text to the underlying model — this is the only place in the codebase that
knows the concrete model is E5 (Principle VI).
"""

import os

import numpy as np

from albercik_chatbot.providers.embedding import local_sentence_transformer_provider as mod


class _FakeSentenceTransformer:
    """Stands in for `sentence_transformers.SentenceTransformer`. Counts
    constructions at the class level, records constructor kwargs, and
    records every text passed to `encode()` so tests can assert on
    offline-loading flags and E5 prefixing."""

    construction_count = 0
    last_kwargs: dict[str, object] = {}
    encode_calls: list[str | list[str]] = []

    def __init__(self, model_name: str, **kwargs: object) -> None:
        type(self).construction_count += 1
        type(self).last_kwargs = kwargs
        self.model_name = model_name

    def encode(self, text_or_texts, normalize_embeddings: bool = True):  # noqa: ANN001
        type(self).encode_calls.append(text_or_texts)
        if isinstance(text_or_texts, str):
            return np.zeros(384, dtype=np.float32)
        return np.zeros((len(text_or_texts), 384), dtype=np.float32)


def test_model_loaded_at_most_once_across_multiple_provider_instances(monkeypatch) -> None:
    _FakeSentenceTransformer.construction_count = 0
    monkeypatch.setattr(mod, "SentenceTransformer", _FakeSentenceTransformer)
    mod._load_model.cache_clear()

    model_name = "fake-model-lifecycle-test"

    provider_a = mod.LocalSentenceTransformerEmbeddingProvider(model_name=model_name)
    provider_b = mod.LocalSentenceTransformerEmbeddingProvider(model_name=model_name)

    provider_a.embed_query("pierwsze pytanie")
    provider_a.embed_query("drugie pytanie")
    provider_b.embed_passages(["fragment A", "fragment B"])

    assert _FakeSentenceTransformer.construction_count == 1

    mod._load_model.cache_clear()


def test_embed_query_returns_384_dimensional_vector(monkeypatch) -> None:
    monkeypatch.setattr(mod, "SentenceTransformer", _FakeSentenceTransformer)
    mod._load_model.cache_clear()

    provider = mod.LocalSentenceTransformerEmbeddingProvider(model_name="fake-model-dim-test")
    vector = provider.embed_query("test")

    assert len(vector) == 384

    mod._load_model.cache_clear()


def test_embed_passages_empty_list_returns_empty_without_calling_model(monkeypatch) -> None:
    calls = {"encode": 0}

    class _CountingFake(_FakeSentenceTransformer):
        def encode(self, text_or_texts, normalize_embeddings: bool = True):  # noqa: ANN001
            calls["encode"] += 1
            return super().encode(text_or_texts, normalize_embeddings)

    monkeypatch.setattr(mod, "SentenceTransformer", _CountingFake)
    mod._load_model.cache_clear()

    provider = mod.LocalSentenceTransformerEmbeddingProvider(model_name="fake-model-empty-test")
    result = provider.embed_passages([])

    assert result == []
    assert calls["encode"] == 0

    mod._load_model.cache_clear()


def test_load_model_forces_local_files_only(monkeypatch) -> None:
    """Guards against a regression to the pre-fix behavior where startup
    silently made HTTP calls to huggingface.co despite pre-downloaded
    weights — the constructor call itself must request cache-only loading."""
    monkeypatch.setattr(mod, "SentenceTransformer", _FakeSentenceTransformer)
    mod._load_model.cache_clear()

    mod.LocalSentenceTransformerEmbeddingProvider(model_name="fake-model-offline-test")

    assert _FakeSentenceTransformer.last_kwargs.get("local_files_only") is True

    mod._load_model.cache_clear()


def test_module_defaults_hf_hub_offline_env_vars() -> None:
    """The module must set these before importing `sentence_transformers`
    (Design constraint: no runtime Hugging Face Hub network access)."""
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"


def test_embed_query_applies_e5_query_prefix(monkeypatch) -> None:
    """Guards against a regression to the pre-fix behavior where queries
    were sent to the model unprefixed, contrary to E5's documented usage
    (Phase 3 calibration checkpoint finding)."""
    _FakeSentenceTransformer.encode_calls = []
    monkeypatch.setattr(mod, "SentenceTransformer", _FakeSentenceTransformer)
    mod._load_model.cache_clear()

    provider = mod.LocalSentenceTransformerEmbeddingProvider(model_name="fake-model-prefix-test")
    provider.embed_query("Jakie są godziny otwarcia?")

    assert _FakeSentenceTransformer.encode_calls == ["query: Jakie są godziny otwarcia?"]

    mod._load_model.cache_clear()


def test_embed_passages_applies_e5_passage_prefix_to_every_text(monkeypatch) -> None:
    _FakeSentenceTransformer.encode_calls = []
    monkeypatch.setattr(mod, "SentenceTransformer", _FakeSentenceTransformer)
    mod._load_model.cache_clear()

    provider = mod.LocalSentenceTransformerEmbeddingProvider(model_name="fake-model-prefix-test")
    provider.embed_passages(["Fragment jeden.", "Fragment dwa."])

    expected = [["passage: Fragment jeden.", "passage: Fragment dwa."]]
    assert _FakeSentenceTransformer.encode_calls == expected

    mod._load_model.cache_clear()
