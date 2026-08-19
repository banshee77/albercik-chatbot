"""Contract tests for the public ALBERTOS website (feature
005-public-club-website, contracts/pages.md). These routes have no
LLM/embedding/DB dependency of their own, but `create_app()` still
constructs an `LLMProvider`/`EmbeddingProvider` for the *other* routers —
fakes are injected here per this project's established test convention
(Design Constraint 2, main.py) so building the test app never triggers a
real model load or network call.
"""

from fastapi.testclient import TestClient

from shiruno.main import create_app
from shiruno.public_site.data.glossary import GLOSSARY_TERMS
from shiruno.public_site.data.locations import LOCATIONS
from shiruno.public_site.data.news import NEWS_POSTS
from shiruno.public_site.data.sessions import SESSIONS
from shiruno.public_site.data.trainers import TRAINERS
from tests.fakes.fake_embedding_provider import FakeEmbeddingProvider
from tests.fakes.fake_llm_provider import FakeLLMProvider

client = TestClient(
    create_app(llm_provider=FakeLLMProvider(), embedding_provider=FakeEmbeddingProvider())
)


def test_home_page_has_hero_and_both_ctas_and_previews() -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "ALBERTOS" in body
    assert "Traditional Karate-Do" in body or "Karate-Do" in body
    assert "Dołącz do nas" in body or "Przyjdź na pierwszy trening" in body
    assert 'href="/grafik"' in body
    assert 'href="/kontakt"' in body
    assert NEWS_POSTS[0].title in body
    assert LOCATIONS[0].name in body
    assert TRAINERS[0].name in body


def test_home_page_readable_on_mobile_sized_markup() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'name="viewport"' in response.text


def test_schedule_page_unfiltered_lists_every_session() -> None:
    response = client.get("/grafik")

    assert response.status_code == 200
    assert response.text.count('training-session"') == len(SESSIONS)


def test_schedule_page_filters_by_location() -> None:
    target_location = SESSIONS[0].location_slug
    expected = [s for s in SESSIONS if s.location_slug == target_location]

    response = client.get("/grafik", params={"location": target_location})

    assert response.status_code == 200
    assert response.text.count('training-session"') == len(expected)


def test_schedule_page_filters_by_day_and_level_combined() -> None:
    target = SESSIONS[0]
    expected = [s for s in SESSIONS if s.day == target.day and s.age_level == target.age_level]

    response = client.get("/grafik", params={"day": target.day, "level": target.age_level})

    assert response.status_code == 200
    assert response.text.count('training-session"') == len(expected)


def test_schedule_page_shows_empty_state_for_non_matching_combination() -> None:
    response = client.get("/grafik", params={"location": "does-not-exist"})

    assert response.status_code == 200
    assert "brak zajęć" in response.text.lower()
    assert 'training-session"' not in response.text


def test_sections_page_lists_every_location_with_full_attributes() -> None:
    response = client.get("/sekcje")

    assert response.status_code == 200
    body = response.text
    for location in LOCATIONS:
        assert location.name in body
        assert location.address in body
        assert location.age_level in body
        assert location.days_hours in body
        assert f'href="/trenerzy#{location.trainer_slug}"' in body


def test_trainers_page_lists_every_trainer_with_full_attributes_and_placeholder() -> None:
    response = client.get("/trenerzy")

    assert response.status_code == 200
    body = response.text
    for trainer in TRAINERS:
        assert f'id="{trainer.slug}"' in body
        assert trainer.name in body
        assert trainer.role in body
        assert trainer.grade in body
        assert trainer.specialization in body
        assert trainer.bio in body
    assert body.count("placeholder-portrait") == len(TRAINERS)


def test_karate_do_page_covers_required_topics_and_full_glossary() -> None:
    response = client.get("/karate-do")

    assert response.status_code == 200
    body = response.text
    for topic in ("kihon", "kata", "kumite", "etykiet", "pas", "dzieci", "dorosł"):
        assert topic in body.lower()
    for entry in GLOSSARY_TERMS:
        assert entry.term in body
        assert entry.explanation in body


def test_history_page_covers_required_narrative_beats() -> None:
    response = client.get("/o-klubie")

    assert response.status_code == 200
    body = response.text.lower()
    for beat in ("początk", "pierwsz", "sekcj", "egzamin", "społeczność"):
        assert beat in body
    assert "obóz" in body or "obozy" in body or "obozów" in body


def test_news_page_unfiltered_lists_every_post_newest_first() -> None:
    response = client.get("/aktualnosci")

    assert response.status_code == 200
    body = response.text
    assert body.count('news-post"') == len(NEWS_POSTS)
    newest = sorted(NEWS_POSTS, key=lambda p: p.date, reverse=True)[0]
    oldest = sorted(NEWS_POSTS, key=lambda p: p.date)[0]
    assert body.index(newest.title) < body.index(oldest.title)


def test_news_page_filters_by_category() -> None:
    target_category = NEWS_POSTS[0].category
    expected = [p for p in NEWS_POSTS if p.category == target_category]

    response = client.get("/aktualnosci", params={"category": target_category})

    assert response.status_code == 200
    assert response.text.count('news-post"') == len(expected)


def test_news_page_shows_empty_state_for_non_matching_category() -> None:
    response = client.get("/aktualnosci", params={"category": "does-not-exist"})

    assert response.status_code == 200
    assert "brak aktualności" in response.text.lower()
    assert 'news-post"' not in response.text


def test_news_detail_page_shows_full_content_for_a_real_slug() -> None:
    post = NEWS_POSTS[0]

    response = client.get(f"/aktualnosci/{post.slug}")

    assert response.status_code == 200
    assert post.title in response.text
    for paragraph in post.body:
        assert paragraph in response.text


def test_news_detail_page_404s_for_an_unknown_slug() -> None:
    response = client.get("/aktualnosci/does-not-exist")

    assert response.status_code == 404


def test_home_page_news_preview_links_into_the_news_page() -> None:
    response = client.get("/")

    assert 'href="/aktualnosci"' in response.text
    assert f'href="/aktualnosci/{NEWS_POSTS[0].slug}"' in response.text or any(
        f'href="/aktualnosci/{post.slug}"' in response.text for post in NEWS_POSTS
    )


def test_contact_page_shows_required_contact_information() -> None:
    response = client.get("/kontakt")

    assert response.status_code == 200
    body = response.text
    assert "+48" in body or "tel" in body.lower()
    assert "@" in body
    for location in LOCATIONS:
        assert location.name in body
        assert location.address in body
    assert "facebook" in body.lower() or "instagram" in body.lower()


def test_contact_form_has_no_backend_route_to_submit_to() -> None:
    response = client.post("/kontakt")

    assert response.status_code in (404, 405)
