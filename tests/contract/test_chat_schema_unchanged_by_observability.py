"""T048 — contract test: feature 012-rag-observability does not change the
public `/chat` request/response contract (FR-039). `ChatRequest`/
`ChatResponse` in `api/schemas.py` are untouched by this feature; this test
pins their field sets so a future accidental change is caught here rather
than only by a downstream tracing test.
"""

from typing import get_args

from shiruno.api.schemas import ChatRequest, ChatResponse


def test_chat_request_schema_field_set_unchanged() -> None:
    assert set(ChatRequest.model_fields) == {"question"}
    assert ChatRequest.model_config.get("extra") == "forbid"


def test_chat_response_schema_field_set_unchanged() -> None:
    assert set(ChatResponse.model_fields) == {"outcome", "answer", "sources", "request_id"}
    outcome_field = ChatResponse.model_fields["outcome"]
    assert get_args(outcome_field.annotation) == (
        "grounded",
        "insufficient_information",
        "out_of_scope",
        "unavailable",
        "small_talk",
    )
