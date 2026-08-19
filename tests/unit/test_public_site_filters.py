"""T018/T035 — unit tests for the pure schedule/news filter functions
(feature 005-public-club-website, data-model.md's "Behavior" notes).
"""

from datetime import date

from albercik_chatbot.public_site.filters import filter_news, filter_sessions
from albercik_chatbot.public_site.models import NewsPost, TrainingSession

_SESSIONS = (
    TrainingSession(location_slug="a", day="Poniedziałek", time_range="17:00", age_level="Beg"),
    TrainingSession(location_slug="a", day="Środa", time_range="17:00", age_level="Beg"),
    TrainingSession(location_slug="b", day="Poniedziałek", time_range="18:00", age_level="Adv"),
)


def test_filter_sessions_with_no_filters_returns_all() -> None:
    assert filter_sessions(_SESSIONS) == _SESSIONS


def test_filter_sessions_by_location_narrows_correctly() -> None:
    result = filter_sessions(_SESSIONS, location="a")
    assert result == (_SESSIONS[0], _SESSIONS[1])


def test_filter_sessions_by_day_narrows_correctly() -> None:
    result = filter_sessions(_SESSIONS, day="Poniedziałek")
    assert result == (_SESSIONS[0], _SESSIONS[2])


def test_filter_sessions_combined_criteria_narrow_further() -> None:
    result = filter_sessions(_SESSIONS, location="a", day="Poniedziałek", level="Beg")
    assert result == (_SESSIONS[0],)


def test_filter_sessions_unrecognized_value_returns_empty_not_an_error() -> None:
    result = filter_sessions(_SESSIONS, location="does-not-exist")
    assert result == ()


_NEWS = (
    NewsPost(
        slug="p1", title="P1", date=date(2026, 1, 1), category="Sezon", summary="s", body=("b",)
    ),
    NewsPost(
        slug="p2", title="P2", date=date(2026, 1, 2), category="Obóz", summary="s", body=("b",)
    ),
)


def test_filter_news_with_no_category_returns_all() -> None:
    assert filter_news(_NEWS) == _NEWS


def test_filter_news_by_category_narrows_correctly() -> None:
    assert filter_news(_NEWS, category="Obóz") == (_NEWS[1],)


def test_filter_news_unrecognized_category_returns_empty() -> None:
    assert filter_news(_NEWS, category="does-not-exist") == ()
