"""Contract tests for the public ALBERTOS website's chat widget markup
(feature 006-public-chat-widget). This feature adds no new backend route —
these tests only assert on the server-rendered launcher/panel skeleton
that `base.html` sends on every public page (contracts/
chat-widget-client-contract.md). Actual conversational behavior requires
JavaScript execution and is validated manually per quickstart.md, not here
(spec SC-008 — no browser automation in the normal automated suite).

Fakes are injected exactly per this project's established test convention
(Design Constraint 2, main.py) so building the test app never triggers a
real model load or network call — same pattern as
tests/contract/test_public_site_pages.py.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from shiruno.main import create_app
from tests.fakes.fake_embedding_provider import FakeEmbeddingProvider
from tests.fakes.fake_llm_provider import FakeLLMProvider

client = TestClient(
    create_app(llm_provider=FakeLLMProvider(), embedding_provider=FakeEmbeddingProvider())
)

_SITE_CSS_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "shiruno"
    / "public_site"
    / "static"
    / "css"
    / "site.css"
)
_AVATAR_SVG_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "shiruno"
    / "public_site"
    / "static"
    / "img"
    / "assistant-avatar.svg"
)

PUBLIC_PAGES = (
    "/",
    "/karate-do",
    "/o-klubie",
    "/trenerzy",
    "/sekcje",
    "/grafik",
    "/aktualnosci",
    "/kontakt",
)


def test_launcher_and_panel_skeleton_present_on_every_public_page() -> None:
    for path in PUBLIC_PAGES:
        response = client.get(path)

        assert response.status_code == 200, path
        body = response.text

        assert body.count('id="chat-launcher"') == 1, path
        assert "aria-label=" in body.split('id="chat-launcher"')[1][:200], path
        assert "Zapytaj Albertos" in body, path

        assert 'id="chat-panel"' in body, path
        assert 'role="dialog"' in body, path
        assert 'aria-modal="true"' in body, path
        assert 'aria-labelledby="chat-panel-title"' in body, path
        assert 'id="chat-panel-title"' in body, path

        assert "Zapytaj o treningi, grafik, trenerów, sekcje i informacje o klubie." in body, path

        assert 'id="chat-messages"' in body, path
        assert 'role="log"' in body, path

        assert 'id="chat-status"' in body, path
        assert 'role="status"' in body, path

        assert 'id="chat-form"' in body, path
        assert 'id="chat-input"' in body, path
        assert 'id="chat-send"' in body, path

        assert 'id="chat-close"' in body, path
        assert "aria-label=" in body.split('id="chat-close"')[1][:200], path


def test_chat_script_is_referenced_on_every_public_page() -> None:
    for path in PUBLIC_PAGES:
        response = client.get(path)

        assert 'src="/static/site/js/chat.js"' in response.text, path


def test_chat_widget_markup_has_no_interactive_attribute_that_works_without_js() -> None:
    """User Story 5 (FR-025): the launcher/panel must never appear
    interactive via markup alone, on any public page — no href/inline-
    handler that would make it seem to do something without chat.js
    actually running."""
    for path in PUBLIC_PAGES:
        response = client.get(path)
        body = response.text

        launcher_open = body.rindex("<button", 0, body.index('id="chat-launcher"'))
        launcher_close = body.index("</button>", launcher_open) + len("</button>")
        launcher_element = body[launcher_open:launcher_close]
        assert "href=" not in launcher_element, path
        assert "onclick=" not in launcher_element, path


def test_all_public_pages_still_return_200_with_widget_present() -> None:
    """User Story 5 non-regression: adding the widget must not change any
    existing page's availability (spec SC-005)."""
    for path in PUBLIC_PAGES:
        response = client.get(path)

        assert response.status_code == 200, path


_TECHNICAL_TERMS_NOT_ALLOWED_IN_VISITOR_FACING_MARKUP = (
    "AI chatbot",
    "LLM",
    "RAG",
    "Ollama",
)


def test_panel_title_is_asystent_albertos_not_albertos_ai() -> None:
    """User Story 3 (FR-009, spec Acceptance Scenario US3.3): the widget's
    own chrome must present a consistent, non-technical "Asystent Albertos"
    identity, not the earlier "Albertos AI" title."""
    for path in PUBLIC_PAGES:
        response = client.get(path)
        body = response.text

        title_open = body.index('id="chat-panel-title"')
        title_close = body.index("</h2>", title_open)
        title_element = body[title_open:title_close]

        assert "Asystent Albertos" in title_element, path
        assert "Albertos AI" not in title_element, path


def test_no_technical_ai_terminology_in_visitor_facing_markup() -> None:
    """User Story 3 (FR-009): the public widget must not primarily present
    itself using technical terminology such as "AI chatbot", "LLM", "RAG",
    or "Ollama" anywhere in the rendered page."""
    for path in PUBLIC_PAGES:
        response = client.get(path)
        body = response.text

        for term in _TECHNICAL_TERMS_NOT_ALLOWED_IN_VISITOR_FACING_MARKUP:
            assert term not in body, f"{path}: found forbidden technical term {term!r}"


# --- User Story 4 (avatar): decorative, local-only, launcher accessible
# name preserved, widget resilient to a failed avatar load ---


def test_avatar_asset_file_exists_locally() -> None:
    """FR-010: a local, lightweight SVG asset — not a remote/CDN image."""
    assert _AVATAR_SVG_PATH.is_file()
    assert _AVATAR_SVG_PATH.suffix == ".svg"


def test_avatar_element_present_on_launcher_and_marked_decorative() -> None:
    """FR-010/FR-011: an avatar element is present on the launcher and
    marked `aria-hidden="true"` (decorative — never announced as its own
    control), while the launcher's own accessible name (via `aria-label`
    on the button itself) is unaffected."""
    response = client.get("/")
    body = response.text

    launcher_open = body.index('id="chat-launcher"')
    launcher_close = body.index("</button>", launcher_open)
    launcher_element = body[launcher_open:launcher_close]

    assert 'class="chat-avatar"' in launcher_element
    avatar_open = launcher_element.index('class="chat-avatar"')
    avatar_span_start = launcher_element.rindex("<span", 0, avatar_open)
    avatar_span_end = launcher_element.index(">", avatar_open)
    avatar_span = launcher_element[avatar_span_start : avatar_span_end + 1]
    assert 'aria-hidden="true"' in avatar_span

    # The launcher button itself keeps its own accessible name — the
    # avatar is additive decoration, not a replacement for it.
    assert 'aria-label="Zapytaj Albertos — otwórz czat"' in launcher_element


def test_chat_avatar_styling_references_only_a_local_static_asset() -> None:
    """FR-010: the avatar's CSS references the new local asset under
    `/static/site/img/` — no external/CDN URL anywhere in the stylesheet."""
    css = _SITE_CSS_PATH.read_text(encoding="utf-8")

    assert ".chat-avatar" in css
    assert "/static/site/img/assistant-avatar.svg" in css
    assert "http://" not in css
    assert "https://" not in css


def test_chat_avatar_rule_has_a_background_color_fallback() -> None:
    """FR-012: the `.chat-avatar` rule must declare a `background-color`
    on top of its `background-image`, so a failed/blocked image load still
    renders a neutral shape instead of an empty box or a broken-image
    glyph — the widget's layout never depends on the image loading."""
    css = _SITE_CSS_PATH.read_text(encoding="utf-8")

    rule_start = css.index(".chat-avatar")
    rule_open = css.index("{", rule_start)
    rule_close = css.index("}", rule_open)
    rule_body = css[rule_open:rule_close]

    assert "background-image" in rule_body
    assert "background-color" in rule_body
