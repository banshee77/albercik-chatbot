"""Static training-session (schedule) content for the public website
(fictional demo content — feature 005-public-club-website)."""

from albercik_chatbot.public_site.models import TrainingSession

SESSIONS: tuple[TrainingSession, ...] = (
    TrainingSession(
        location_slug="grodzin-sp2",
        day="Wtorek",
        time_range="15:30–16:25",
        age_level="Początkujący",
    ),
    TrainingSession(
        location_slug="grodzin-sp2",
        day="Czwartek",
        time_range="15:30–16:25",
        age_level="Początkujący",
    ),
    TrainingSession(
        location_slug="wierzbin-sp3",
        day="Poniedziałek",
        time_range="17:30–18:25",
        age_level="Początkujący",
    ),
    TrainingSession(
        location_slug="wierzbin-sp3",
        day="Środa",
        time_range="17:30–18:25",
        age_level="Początkujący",
    ),
    TrainingSession(
        location_slug="wierzbin-sp3",
        day="Poniedziałek",
        time_range="18:30–19:25",
        age_level="Zielony–niebieski pas",
    ),
    TrainingSession(
        location_slug="wierzbin-sp3",
        day="Środa",
        time_range="18:30–19:25",
        age_level="Zielony–niebieski pas",
    ),
    TrainingSession(
        location_slug="grodzin-sp5",
        day="Poniedziałek",
        time_range="16:00–16:55",
        age_level="Początkujący",
    ),
    TrainingSession(
        location_slug="grodzin-sp5",
        day="Środa",
        time_range="16:00–16:55",
        age_level="Początkujący",
    ),
    TrainingSession(
        location_slug="grodzin-sp5",
        day="Poniedziałek",
        time_range="17:00–17:55",
        age_level="Zielony–niebieski pas",
    ),
    TrainingSession(
        location_slug="grodzin-sp5",
        day="Środa",
        time_range="17:00–17:55",
        age_level="Zielony–niebieski pas",
    ),
)
