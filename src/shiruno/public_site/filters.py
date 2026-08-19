"""Pure filtering functions for the schedule and news pages
(feature 005-public-club-website, data-model.md's "Behavior" notes).

Server-side, not client-side (research.md §2): kept here as plain,
independently unit-testable functions so the JS progressive-enhancement
layer never has to duplicate this logic.
"""

from albercik_chatbot.public_site.models import NewsPost, TrainingSession


def filter_sessions(
    sessions: tuple[TrainingSession, ...],
    *,
    location: str | None = None,
    day: str | None = None,
    level: str | None = None,
) -> tuple[TrainingSession, ...]:
    return tuple(
        session
        for session in sessions
        if (location is None or session.location_slug == location)
        and (day is None or session.day == day)
        and (level is None or session.age_level == level)
    )


def filter_news(
    posts: tuple[NewsPost, ...],
    *,
    category: str | None = None,
) -> tuple[NewsPost, ...]:
    if category is None:
        return posts
    return tuple(post for post in posts if post.category == category)
