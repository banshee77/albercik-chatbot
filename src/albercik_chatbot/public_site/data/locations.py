"""Static training-location content for the public website (demo/fictional
content — feature 005-public-club-website)."""

from albercik_chatbot.public_site.models import Location

LOCATIONS: tuple[Location, ...] = (
    Location(
        slug="grodzin-sp2",
        name="Grodzin — SP-2",
        address="ul. Lipowa 18A, Grodzin",
        groups=("Początkujący", "Białe, żółte i pomarańczowe pasy"),
        age_level="Dzieci i młodzież, początkujący–pomarańczowy pas",
        days_hours="Wtorek i czwartek, 15:30–16:25",
        trainer_slug="anna-nowak",
    ),
    Location(
        slug="wierzbin-sp3",
        name="Wierzbin — SP-3",
        address="ul. Polna 5, Wierzbin",
        groups=("Początkujący", "Zielone, niebieskie, brązowe i czarne pasy"),
        age_level="Dzieci, młodzież i dorośli",
        days_hours="Poniedziałek i środa, 17:30–19:25",
        trainer_slug="marek-kowalski",
    ),
    Location(
        slug="grodzin-sp5",
        name="Grodzin — SP-5",
        address="ul. Kwiatowa 7, Grodzin",
        groups=("Początkujący", "Zielone i niebieskie pasy"),
        age_level="Dzieci i młodzież",
        days_hours="Poniedziałek i środa, 16:00–16:55",
        trainer_slug="anna-nowak",
    ),
)
