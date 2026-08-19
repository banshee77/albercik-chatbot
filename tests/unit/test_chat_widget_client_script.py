"""Static-source assertions on the public chat widget's client script
(feature 006-public-chat-widget). `chat.js` only ever runs in a browser, so
these tests read the shipped file as plain text and assert on the
safety-relevant properties the specification requires — no Node.js
runner, no browser automation (spec SC-008; research.md §8):

- the client references only the existing `/api/v1/chat` endpoint and no
  other API path (FR-006; contracts/chat-widget-client-contract.md's
  negative contract),
- the request body it constructs carries only the `question` field, never
  a provider/model/token/budget override (FR-007),
- model-derived text is always inserted via `.textContent`, never
  `.innerHTML` (FR-021/FR-022).

This file grows across User Stories 1-4 (each adds assertions for the
behavior it introduces), matching tasks.md.
"""

import re
from pathlib import Path

_CHAT_JS_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "albercik_chatbot"
    / "public_site"
    / "static"
    / "js"
    / "chat.js"
)

_FORBIDDEN_OVERRIDE_KEYS = (
    "model",
    "provider",
    "llm_provider",
    "max_tokens",
    "top_k",
    "system_prompt",
    "temperature",
    "think",
    "retries",
    "retry_count",
    "budget",
)


def _read_chat_js() -> str:
    return _CHAT_JS_PATH.read_text(encoding="utf-8")


def test_chat_js_exists() -> None:
    assert _CHAT_JS_PATH.is_file()


def test_references_only_the_existing_chat_endpoint() -> None:
    source = _read_chat_js()

    assert source.count("/api/v1/chat") >= 1
    # Every "/api/" occurrence must be part of "/api/v1/chat" — no other
    # API path literal is present anywhere in the file.
    assert source.count("/api/") == source.count("/api/v1/chat")


def test_request_body_never_contains_a_provider_or_model_override_field() -> None:
    """Matches the word only in JS object-key position (`name:` or
    `"name":`), so prose mentions elsewhere in the file (e.g. a comment
    referencing "data-model.md") don't produce a false positive."""
    source = _read_chat_js()

    assert "question" in source
    for forbidden_key in _FORBIDDEN_OVERRIDE_KEYS:
        pattern = re.compile(r"""['"]?\b""" + re.escape(forbidden_key) + r"""\b['"]?\s*:""")
        assert pattern.search(source) is None, f"found forbidden key literal: {forbidden_key!r}"


def test_never_uses_innerhtml() -> None:
    """Checks for actual `.innerHTML` assignment/usage, not the word
    appearing in an explanatory comment (e.g. "never use innerHTML")."""
    source = _read_chat_js()

    assert re.search(r"\.innerHTML\s*[+]?=", source) is None


def test_uses_textcontent_for_message_rendering() -> None:
    source = _read_chat_js()

    assert ".textContent" in source


def _branch_window(source: str, literal: str, window: int = 300) -> str:
    """Text following an explicit `=== "literal"` comparison, used to
    inspect what a specific outcome branch actually does."""
    match = re.search(r'===\s*"' + re.escape(literal) + r'"', source)
    assert match is not None, f'no explicit `=== "{literal}"` comparison found'
    return source[match.end() : match.end() + window]


def test_insufficient_information_and_out_of_scope_have_explicit_branches() -> None:
    """User Story 2 (FR-010/FR-011): both outcomes must be named
    explicitly in the outcome-handling code, not merely handled by an
    implicit fallthrough/default case."""
    source = _read_chat_js()

    _branch_window(source, "insufficient_information")
    _branch_window(source, "out_of_scope")


def test_insufficient_information_and_out_of_scope_never_render_sources() -> None:
    """FR-010/FR-011: neither outcome ever produces a 'Źródła:' line."""
    source = _read_chat_js()

    for outcome in ("insufficient_information", "out_of_scope"):
        window = _branch_window(source, outcome)
        assert "dedupeSourceLabels" not in window
        assert "Źródła" not in window


def test_rate_limit_branch_reads_retry_after_header() -> None:
    """User Story 3 (FR-018/FR-019): a 429 branch exists and reads the
    `Retry-After` response header."""
    source = _read_chat_js()

    assert "429" in source
    assert "Retry-After" in source


def test_unavailable_status_branch_exists() -> None:
    """User Story 3 (FR-012/FR-018): a 503 branch exists."""
    source = _read_chat_js()

    assert "503" in source


def test_network_failure_is_caught() -> None:
    """User Story 3 (FR-018): a rejected `fetch` promise (network failure,
    not just a non-2xx response) must be caught, not left unhandled."""
    source = _read_chat_js()

    assert source.count(".catch(") >= 2


def test_single_shared_fallback_path_for_malformed_or_unexpected_responses() -> None:
    """User Story 3 (FR-018a, Clarifications 2026-08-19): a malformed body,
    a network failure, and any status outside 200/429/503 must all reach
    the *same* fallback function, not three separately-authored messages."""
    source = _read_chat_js()

    match = re.search(r"function\s+(\w*[Ff]allback\w*)\s*\(", source)
    assert match is not None, "no shared fallback function found"
    fallback_name = match.group(1)
    # Defined once, called from at least 2 other sites (malformed body,
    # network failure, and/or any other status).
    assert source.count(fallback_name) >= 3


def test_escape_key_closes_the_panel() -> None:
    """User Story 4 (FR-031)."""
    source = _read_chat_js()

    assert re.search(r"""key\s*===\s*["']Esc(ape)?["']""", source) is not None


def test_focus_moves_into_panel_on_open_and_back_to_launcher_on_close() -> None:
    """User Story 4 (FR-030): at least two distinct `.focus()` call sites —
    one moving focus into the panel, one returning it to the launcher."""
    source = _read_chat_js()

    assert source.count(".focus()") >= 2


def test_tab_key_focus_trap_present() -> None:
    """User Story 4 (FR-030/FR-031): a Tab/Shift+Tab wrap-around check
    exists so focus never leaves the panel while it's open."""
    source = _read_chat_js()

    assert re.search(r"""key\s*[!=]==\s*["']Tab["']""", source) is not None
    assert "shiftKey" in source
