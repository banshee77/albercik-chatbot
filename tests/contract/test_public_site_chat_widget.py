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

from fastapi.testclient import TestClient

from albercik_chatbot.main import create_app
from tests.fakes.fake_embedding_provider import FakeEmbeddingProvider
from tests.fakes.fake_llm_provider import FakeLLMProvider

client = TestClient(
    create_app(llm_provider=FakeLLMProvider(), embedding_provider=FakeEmbeddingProvider())
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
