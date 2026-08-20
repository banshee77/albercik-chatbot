"""T010 — unit test: `normalize_question` (feature 011-conversations-analytics,
research.md §6, FR-028). Deterministic lowercase + whitespace-collapse
only — no punctuation stripping, no stemming, no semantic processing.
"""

from shiruno.domain.question_normalization import normalize_question


def test_lowercases() -> None:
    assert normalize_question("Jakie SA Godziny Otwarcia?") == "jakie sa godziny otwarcia?"


def test_collapses_internal_whitespace() -> None:
    assert normalize_question("Jakie   sa\tgodziny\n\notwarcia?") == "jakie sa godziny otwarcia?"


def test_strips_leading_and_trailing_whitespace() -> None:
    assert normalize_question("   Jakie sa godziny otwarcia?   ") == "jakie sa godziny otwarcia?"


def test_preserves_punctuation() -> None:
    assert normalize_question("Godziny otwarcia?!") == "godziny otwarcia?!"


def test_identical_questions_normalize_identically() -> None:
    a = normalize_question("Jakie są godziny otwarcia?")
    b = normalize_question("jakie   są godziny otwarcia?")
    assert a == b


def test_is_idempotent() -> None:
    once = normalize_question("Jakie SA godziny otwarcia?")
    twice = normalize_question(once)
    assert once == twice


def test_empty_string() -> None:
    assert normalize_question("") == ""


def test_does_not_merge_genuinely_different_questions() -> None:
    assert normalize_question("Jakie sa godziny?") != normalize_question("Jakie sa ceny?")
