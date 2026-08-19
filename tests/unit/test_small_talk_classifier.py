"""Unit tests for the deterministic small-talk classifier
(domain/small_talk.py, feature 007-conversational-chat-ux, FR-001-FR-005).
Mirrors tests/unit/test_scope.py's parametrized style. No provider calls,
no I/O — pure function tests.

Grows across User Stories 1-3 (tasks.md): this file starts with US1's five
categories (greeting/goodbye/thanks/courtesy/capability) and the negative
"must not swallow a real question" table; US3 (T021) adds identity-question
cases.
"""

import pytest

from shiruno.domain.small_talk import classify_small_talk

_GREETINGS = [
    "Cześć",
    "cześć",
    "Cześć!",
    "Cześć wszystkim",
    "Hej",
    "Hejka",
    "Witam",
    "Dzień dobry",
    "Dzień dobry!",
    "Dobry wieczór",
    "Siema",
    "Hi",
    "Hello",
    "Hey",
    "Good morning",
]

_GOODBYES = [
    "Do zobaczenia",
    "Do zobaczenia!",
    "Pa",
    "Papa",
    "Żegnaj",
    "Do widzenia",
    "Na razie",
    "Bye",
    "Goodbye",
    "See you",
]

_THANKS = [
    "Dzięki",
    "Dzięki!",
    "Dziękuję",
    "Dzięki bardzo",
    "Dziękuję bardzo",
    "Wielkie dzięki",
    "Thanks",
    "Thank you",
]

_COURTESY = [
    "Jak się masz?",
    "Jak się masz",
    "Jak leci?",
    "Co słychać?",
    "Jak tam?",
    "How are you?",
    "How's it going?",
]

_CAPABILITY = [
    "W czym możesz mi pomóc?",
    "W czym możesz pomóc?",
    "Co potrafisz?",
    "Co umiesz?",
    "Czym się zajmujesz?",
    "What can you help me with?",
    "What can I ask you?",
    "What do you know about?",
]

_IDENTITY = [
    "Czy jesteś człowiekiem?",
    "Czy rozmawiam z człowiekiem?",
    "Kim jesteś?",
    "Co to jest?",
    "Jesteś botem?",
    "Czy jesteś botem?",
    "Czy jesteś AI?",
    "Czy jesteś robotem?",
    "Z kim rozmawiam?",
    "Are you human?",
    "Are you a bot?",
    "What are you?",
]


@pytest.mark.parametrize("question", _GREETINGS)
def test_greeting_is_classified(question: str) -> None:
    assert classify_small_talk(question) == "greeting"


@pytest.mark.parametrize("question", _GOODBYES)
def test_goodbye_is_classified(question: str) -> None:
    assert classify_small_talk(question) == "goodbye"


@pytest.mark.parametrize("question", _THANKS)
def test_thanks_is_classified(question: str) -> None:
    assert classify_small_talk(question) == "thanks"


@pytest.mark.parametrize("question", _COURTESY)
def test_courtesy_is_classified(question: str) -> None:
    assert classify_small_talk(question) == "courtesy"


@pytest.mark.parametrize("question", _CAPABILITY)
def test_capability_question_is_classified(question: str) -> None:
    assert classify_small_talk(question) == "capability"


@pytest.mark.parametrize("question", _IDENTITY)
def test_identity_question_is_classified(question: str) -> None:
    assert classify_small_talk(question) == "identity"


@pytest.mark.parametrize(
    "question",
    [
        # spec.md worked examples (User Story 2 / FR-004): a greeting or
        # thanks prefix on a genuine factual question must never be
        # swallowed by the small-talk classifier.
        "Cześć, o której są treningi początkujących w Wierzbinie?",
        "Cześć, o której jest trening w Wierzbinie?",
        "Cześć, kiedy są treningi?",
        "Dzięki, a kiedy jest następny egzamin?",
        # Existing regression case (tests/contract/test_chat.py): a
        # differently-phrased "can you help me" that is a real, vague
        # question directed at the club/support team, not the assistant's
        # own capabilities — must keep going through retrieval, never be
        # mistaken for the "capability" small-talk category.
        "Możecie mi pomóc z czymś?",
        # A plain factual/off-topic question with no small-talk phrase at
        # all must obviously never classify as small talk either.
        "Jakie są godziny otwarcia biura Albertos?",
        "Napisz mi krótki wiersz o wiośnie.",
        "",
        "   ",
        # User Story 2 (feature 007-conversational-chat-ux, tasks.md T014):
        # additional combined greeting/thanks/courtesy + real-question
        # variants — a differently-worded greeting ("Dzień dobry" instead
        # of "Cześć"), a courtesy-phrase prefix, a thanks prefix with
        # different wording than the spec's own worked example, and two
        # *suffix* cases (the conversational phrase trailing the question
        # rather than leading it) — proving the whole-message anchor
        # rejects small-talk phrases in either position, not just as a
        # prefix.
        "Dzień dobry, ile kosztuje egzamin na 8 kyu?",
        "Jak się masz, o której są treningi dla dzieci?",
        "Dziękuję, jak się zapisać na zajęcia?",
        "O której są treningi początkujących? Dzięki!",
        "Ile kosztuje karnet? Jak się masz?",
        # User Story 3 (tasks.md T018/T021): an identity question combined
        # with a genuine factual question must never be swallowed by
        # identity handling — it must reach the normal RAG pipeline.
        "Kim jesteś i kiedy są treningi?",
        "Czy jesteś człowiekiem i ile kosztuje egzamin?",
        "Jesteś botem? A kiedy jest obóz?",
    ],
)
def test_message_with_distinguishable_content_is_not_small_talk(question: str) -> None:
    assert classify_small_talk(question) is None
