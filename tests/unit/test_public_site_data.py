"""T004 — static-content integrity checks for the public ALBERTOS website
(feature 005-public-club-website, data-model.md's validation rules).

This is fixed, hand-authored project content, not user input — these tests
protect against authoring mistakes (a typo'd slug reference, too few
example entries), not against malicious input.
"""

from shiruno.public_site.data.glossary import GLOSSARY_TERMS
from shiruno.public_site.data.locations import LOCATIONS
from shiruno.public_site.data.news import NEWS_POSTS
from shiruno.public_site.data.sessions import SESSIONS
from shiruno.public_site.data.trainers import TRAINERS

_REQUIRED_NEWS_CATEGORIES = {
    "Sezon",
    "Obóz",
    "Egzaminy",
    "Wydarzenia",
    "Nowa grupa",
}


def test_locations_have_at_least_two_entries_with_unique_slugs() -> None:
    assert len(LOCATIONS) >= 2
    slugs = [location.slug for location in LOCATIONS]
    assert len(slugs) == len(set(slugs))


def test_trainers_have_at_least_three_entries_with_unique_slugs() -> None:
    assert len(TRAINERS) >= 3
    slugs = [trainer.slug for trainer in TRAINERS]
    assert len(slugs) == len(set(slugs))


def test_every_trainer_location_slug_resolves_to_a_real_location() -> None:
    location_slugs = {location.slug for location in LOCATIONS}
    for trainer in TRAINERS:
        assert trainer.location_slugs, f"{trainer.slug} teaches nowhere"
        for slug in trainer.location_slugs:
            assert slug in location_slugs, f"{trainer.slug} references unknown location {slug!r}"


def test_every_location_trainer_slug_resolves_to_a_real_trainer() -> None:
    trainer_slugs = {trainer.slug for trainer in TRAINERS}
    for location in LOCATIONS:
        assert location.trainer_slug in trainer_slugs
        assert location.groups, f"{location.slug} has no groups"


def test_every_session_location_slug_resolves_to_a_real_location() -> None:
    location_slugs = {location.slug for location in LOCATIONS}
    assert len(SESSIONS) >= 1
    for session in SESSIONS:
        assert session.location_slug in location_slugs


def test_news_posts_cover_the_required_example_categories() -> None:
    assert len(NEWS_POSTS) >= 5
    slugs = [post.slug for post in NEWS_POSTS]
    assert len(slugs) == len(set(slugs))
    categories = {post.category for post in NEWS_POSTS}
    assert _REQUIRED_NEWS_CATEGORIES.issubset(categories)


def test_glossary_has_at_least_eight_distinct_terms() -> None:
    assert len(GLOSSARY_TERMS) >= 8
    terms = [entry.term for entry in GLOSSARY_TERMS]
    assert len(terms) == len(set(terms))
