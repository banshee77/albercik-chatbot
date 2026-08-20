"""Deterministic question normalization for knowledge-gap and
common-question grouping (feature 011-conversations-analytics, research.md
§6, FR-028). Lowercasing and whitespace-collapsing only — no punctuation
stripping, no stemming, no semantic processing of any kind. This is what
makes exact/normalized-text grouping a structural guarantee rather than a
heuristic: two questions group together if and only if this function
produces the same string for both, never based on speculative similarity.
"""


def normalize_question(text: str) -> str:
    return " ".join(text.split()).lower()
