"""Static trainer profiles for the public website (fictional demo
content — feature 005-public-club-website)."""

from shiruno.public_site.models import Trainer

TRAINERS: tuple[Trainer, ...] = (
    Trainer(
        slug="marek-kowalski",
        name="Marek Kowalski",
        role="Główny instruktor",
        grade="4 Dan",
        specialization="Kata i technika stójki",
        bio=(
            "Marek trenuje karate tradycyjne od ponad 20 lat. Prowadzi grupy "
            "dorosłych i zaawansowanej młodzieży, kładąc nacisk na precyzję "
            "techniki i spokój w kata."
        ),
        location_slugs=("wierzbin-sp3",),
    ),
    Trainer(
        slug="anna-nowak",
        name="Anna Nowak",
        role="Instruktorka",
        grade="2 Dan",
        specialization="Praca z dziećmi i grupy początkujące",
        bio=(
            "Anna specjalizuje się w prowadzeniu najmłodszych adeptów karate — "
            "łączy naukę podstaw z zabawą, budując pewność siebie i dyscyplinę "
            "od pierwszego treningu."
        ),
        location_slugs=("grodzin-sp2", "grodzin-sp5"),
    ),
    Trainer(
        slug="piotr-wisniewski",
        name="Piotr Wiśniewski",
        role="Instruktor",
        grade="1 Dan",
        specialization="Kumite i przygotowanie do egzaminów",
        bio=(
            "Piotr pomaga zawodnikom przygotować się do egzaminów na kolejne "
            "stopnie oraz do startów w zawodach, dbając o solidne podstawy "
            "kihon."
        ),
        location_slugs=("wierzbin-sp3", "grodzin-sp2"),
    ),
)
