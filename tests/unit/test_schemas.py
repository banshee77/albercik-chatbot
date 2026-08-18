"""Unit tests for `ChatRequest` validation (T057, T061): question length
is enforced dynamically against `settings.MAX_QUESTION_LENGTH_CHARS`
(pipeline step "question length validation") entirely at the Pydantic
layer — before any route/application code ever runs — and unknown/extra
fields (an attempted client override of model/max-tokens/etc., FR-035)
are rejected outright rather than silently ignored.
"""

import pytest
from pydantic import ValidationError

from albercik_chatbot.api.schemas import ChatRequest
from albercik_chatbot.config import get_settings


def test_question_within_configured_limit_is_accepted() -> None:
    limit = get_settings().MAX_QUESTION_LENGTH_CHARS
    ChatRequest(question="a" * limit)


def test_question_over_configured_limit_is_rejected() -> None:
    limit = get_settings().MAX_QUESTION_LENGTH_CHARS
    with pytest.raises(ValidationError):
        ChatRequest(question="a" * (limit + 1))


def test_empty_question_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question="")


def test_unknown_fields_are_rejected_not_silently_ignored() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question="Jakie są godziny otwarcia?", model="gpt-4")  # type: ignore[call-arg]
