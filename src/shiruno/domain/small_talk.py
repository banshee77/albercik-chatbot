"""Deterministic small-talk classifier (feature 007-conversational-chat-ux;
FR-001-FR-005). Mirrors `domain/scope.py`'s shape — plain compiled `re`
patterns, no provider call, no LLM-based intent detection (Principle X
cost safety; spec Scope §1's explicit "do not introduce an LLM-based
intent classifier").

Unlike `domain/scope.py` (substring-anywhere, optimistic-by-default —
right for "does this message contain any off-topic marker"), this
classifier anchors each pattern to the **entire** normalized message via
`re.Pattern.fullmatch`. That is the mechanism behind FR-004 ("must not
classify a real Albertos question as small talk merely because it
contains a greeting or courtesy phrase"): a greeting *prefix* on an
otherwise-real question ("Cześć, o której są treningi w Wierzbinie?")
normalizes to a string no single category pattern fully matches, so it
falls through to `None` — the caller (`application/ask_question.py`) then
routes it through the existing, unmodified scope/retrieval/LLM pipeline
exactly as if the greeting weren't there. No separate "does this also look
like a question" heuristic is needed; the whole-message anchor gives that
safety property for free (research.md §2).

User Story 2 review checkpoint (tasks.md T017): the negative table in
tests/unit/test_small_talk_classifier.py — including suffix cases (a
small-talk phrase trailing the question, not just leading it) and
combined-category messages ("Cześć, jak się masz?") — already passed
against this implementation without any pattern change. No stripping/
recursive re-classification of a recognized prefix was introduced (and
none is needed): the `fullmatch` anchor is conservative by construction,
so a message combining small talk with anything else simply falls through
to `None` (routed to the normal RAG pipeline) rather than risking a false
positive. This is the intended tradeoff — a rare false negative (treating
borderline pure conversational filler as a real question) is always safer
than a false positive (swallowing a real question as small talk).
"""

import re
from typing import Literal

SmallTalkCategory = Literal["greeting", "goodbye", "thanks", "courtesy", "capability", "identity"]

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = re.compile(r"^[!?.,;:…]+|[!?.,;:…]+$")


def _normalize(question: str) -> str:
    """Lowercase, collapse internal whitespace, and strip leading/trailing
    punctuation only — internal punctuation (e.g. the comma in "Cześć, o
    której...") is deliberately left in place, since it's exactly what
    keeps a mixed-intent message from ever fullmatching a single-phrase
    small-talk pattern."""
    text = _WHITESPACE.sub(" ", question.strip().lower())
    return _EDGE_PUNCTUATION.sub("", text).strip()


# Populated per user story (tasks.md): US1 (T011) added greeting/goodbye/
# thanks/courtesy/capability; US3 (T021) added identity. A category with no
# entry here simply never matches — safe by construction, never a
# `KeyError` at classification time (only `small_talk_reply` requires the
# category to be present, and it is only ever called with a category
# `classify_small_talk` just returned).
#
# Each pattern is deliberately a specific, hand-picked phrase/variant, not
# a broad single-word pattern — e.g. capability uses "co potrafisz", never
# a bare `\bpomóc\b`-style pattern, so a genuine support request like
# "Możecie mi pomóc z czymś?" (tests/contract/test_chat.py's ambiguous-
# question regression case) can never be mistaken for a question about the
# assistant's own capabilities.
_PATTERNS: dict[SmallTalkCategory, tuple[re.Pattern[str], ...]] = {
    "greeting": tuple(
        re.compile(pattern)
        for pattern in (
            r"cześć(?:\s+wszystkim)?",
            r"czesc",
            r"hej(?:ka)?",
            r"witam",
            r"siema",
            r"elo",
            r"dzień dobry",
            r"dzien dobry",
            r"dobry wieczór",
            r"hi",
            r"hello",
            r"hey",
            r"good morning",
            r"good evening",
        )
    ),
    "goodbye": tuple(
        re.compile(pattern)
        for pattern in (
            r"do zobaczenia",
            r"pa+",
            r"papa",
            r"żegnaj",
            r"do widzenia",
            r"na razie",
            r"bye",
            r"goodbye",
            r"see you(?:\s+later)?",
        )
    ),
    "thanks": tuple(
        re.compile(pattern)
        for pattern in (
            r"dzięki(?:\s+(?:bardzo|wielkie|serdecznie))?",
            r"dziękuję(?:\s+(?:bardzo|wielkie|serdecznie))?",
            r"wielkie dzięki",
            r"thanks?(?:\s+a\s+lot)?",
            r"thank you(?:\s+very\s+much)?",
        )
    ),
    "courtesy": tuple(
        re.compile(pattern)
        for pattern in (
            r"jak się masz",
            r"jak się miewasz",
            r"jak leci",
            r"co słychać",
            r"jak tam",
            r"how are you(?:\s+doing)?",
            r"how'?s it going",
        )
    ),
    "capability": tuple(
        re.compile(pattern)
        for pattern in (
            r"w czym możesz (?:mi )?pomóc",
            r"jak możesz mi pomóc",
            r"co potrafisz",
            r"co umiesz",
            r"czym się zajmujesz",
            r"co możesz dla mnie zrobić",
            r"what can you help me with",
            r"what can i ask you",
            r"what do you know about",
        )
    ),
    "identity": tuple(
        re.compile(pattern)
        for pattern in (
            r"czy jesteś człowiekiem",
            r"czy rozmawiam z człowiekiem",
            r"kim jesteś",
            r"co to jest",
            r"jesteś botem",
            r"czy jesteś botem",
            r"czy jesteś (?:ai|sztuczną inteligencją)",
            r"czy jesteś robotem",
            r"z kim rozmawiam",
            r"are you human",
            r"are you a bot",
            r"what are you",
        )
    ),
}

_REPLIES: dict[SmallTalkCategory, str] = {
    "greeting": "Cześć! 👋 W czym mogę Ci pomóc?",
    "goodbye": "Do zobaczenia! 👋",
    "thanks": "Nie ma sprawy! 🙂",
    "courtesy": "U mnie wszystko gra, dzięki! W czym mogę Ci pomóc?",
    "capability": (
        "Mogę pomóc w sprawach związanych z klubem Albertos — na przykład "
        "treningami, grafikiem, sekcjami, trenerami, egzaminami i obozami."
    ),
    # Must never claim to be human, a trainer, or a club employee (spec
    # Scope §4) — explicitly states "virtual" and names the assistant,
    # never leaves the question ambiguous.
    "identity": (
        "Nie — jestem wirtualnym Asystentem Albertos. Mogę pomóc Ci "
        "znaleźć informacje o klubie i jego działalności."
    ),
}


def classify_small_talk(question: str) -> SmallTalkCategory | None:
    """Returns the matched small-talk category, or `None` if the entire
    normalized message doesn't fullmatch any known category's patterns —
    `None` means "not small talk," and the caller must route the message
    through the existing retrieval/RAG pipeline unchanged."""
    normalized = _normalize(question)
    if not normalized:
        return None
    for category, patterns in _PATTERNS.items():
        if any(pattern.fullmatch(normalized) for pattern in patterns):
            return category
    return None


def small_talk_reply(category: SmallTalkCategory) -> str:
    """Fixed, developer-authored Polish reply text for `category` — never
    derived from the input question, never templated with user-supplied
    text (FR-003)."""
    return _REPLIES[category]
