"""Albertos-scope classifier (T033; FR-027c, FR-030, FR-030a).

Deterministic, keyword-based, and free of any provider call by design —
classifying scope is not worth an LLM/embedding call (Principle X cost
safety) and the constitution requires auth/scope decisions to never be
delegated to the model (Principle II/FR-006 analogue for scope). Optimistic
by default: a question that doesn't clearly match a known-unrelated pattern
is treated as Albertos-related and left to retrieval
(domain/retrieval.py) to decide whether the knowledge base actually
supports it — this keeps the classifier cheap and simple while still
satisfying Clarification 2026-08-17: a message mixing an Albertos-related
request with ANY clearly unrelated request is out-of-scope in its
entirety, since a single deny-list match anywhere in the message is enough
to reject the whole thing.
"""

import re

# Polish-language markers for requests that have nothing to do with
# Albertos customer support. Deliberately a small, explicit, hand-curated
# list rather than a general classifier model (see final report: this is
# an open RAG-quality decision, not a robust NLU classifier).
_OFF_TOPIC_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bwiersz\w*",
        r"\bopowiadani\w*",
        r"\bnapisz\b.{0,20}?\b(?:kod\w*|program\w*|funkcj\w*|skrypt\w*)\b",
        r"\bkod\s+(?:w\s+)?python\w*",
        r"\bdowcip\w*",
        r"\bżart\w*",
        r"\bprzepis\s+na\b",
        r"\bpogod\w*",
        r"\bstolic\w+\s+\w+",
        r"\bile\s+to\s+jest\s+\d",
        r"\boblicz\w*",
        r"\bmecz\w*",
        r"\bprezydent\w*",
        r"\bhoroskop\w*",
        # Phase 3 calibration checkpoint (2026-08-17): "Czy sklep jest
        # czynny w niedzielę, i czy umiesz zaśpiewać piosenkę?" was a
        # false negative — a mixed-intent message wrongly classified
        # in-scope because nothing caught the "sing a song" request.
        r"\b(?:za)?śpiewa\w*",
        r"\bpiosenk\w*",
    )
)


def is_albertos_scope(question: str) -> bool:
    """Returns False if `question` contains any clearly-unrelated request
    (whole message or as part of a mixed message); True otherwise, meaning
    the question should be routed through retrieval to determine whether
    the knowledge base actually supports it."""
    return not any(pattern.search(question) for pattern in _OFF_TOPIC_PATTERNS)
