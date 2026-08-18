"""T027 — unit tests for the Albertos-scope classifier (domain/scope.py,
FR-027c, FR-030, FR-030a, Clarification 2026-08-17: mixed intent -> whole
message out-of-scope). Deterministic, no provider calls.
"""

import pytest

from albercik_chatbot.domain.scope import is_albertos_scope


@pytest.mark.parametrize(
    "question",
    [
        "Jakie są godziny otwarcia biura Albertos?",
        "Czy Albertos oferuje wysyłkę za granicę?",
        "Jak mogę zwrócić zamówiony produkt?",
        "Jaka jest polityka reklamacji Albertos?",
    ],
)
def test_albertos_related_question_is_in_scope(question: str) -> None:
    assert is_albertos_scope(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "Jaka jest stolica Francji?",
        "Napisz mi funkcję w Pythonie do sortowania listy.",
        "Napisz mi krótki wiersz o wiośnie.",
        "Opowiedz mi dowcip.",
        "Jaka będzie jutro pogoda w Warszawie?",
        "Kto jest obecnie prezydentem?",
        "Zaśpiewaj mi piosenkę.",
        "Czy umiesz śpiewać?",
    ],
)
def test_clearly_unrelated_question_is_out_of_scope(question: str) -> None:
    assert is_albertos_scope(question) is False


def test_mixed_intent_message_is_entirely_out_of_scope() -> None:
    question = "Jakie są stawki za wysyłkę w Albertos, a przy okazji napisz mi wiersz o wiośnie?"

    assert is_albertos_scope(question) is False


def test_mixed_intent_singing_request_regression() -> None:
    """Phase 3 calibration checkpoint (2026-08-17): this exact message was
    a discovered false negative — classified in-scope even though the
    "sing a song" half makes it a mixed-intent, whole-message-out-of-scope
    case per Clarification 2026-08-17. Guards against reintroducing it."""
    question = "Czy sklep jest czynny w niedzielę, i czy umiesz zaśpiewać piosenkę?"

    assert is_albertos_scope(question) is False
