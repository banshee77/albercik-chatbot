"""Static content entity shapes for the public ALBERTOS website
(feature 005-public-club-website, data-model.md).

Every instance of these types is fixed, hand-authored project content
defined in `public_site/data/*.py` — never user input, never persisted,
never mutated at runtime. Kept entirely separate from `domain/`,
`application/`, and `providers/` (the RAG-specific packages) per spec
FR-034.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Location:
    slug: str
    name: str
    address: str
    groups: tuple[str, ...]
    age_level: str
    days_hours: str
    trainer_slug: str


@dataclass(frozen=True)
class Trainer:
    slug: str
    name: str
    role: str
    grade: str
    specialization: str
    bio: str
    location_slugs: tuple[str, ...]
    has_photo: bool = False


@dataclass(frozen=True)
class TrainingSession:
    location_slug: str
    day: str
    time_range: str
    age_level: str


@dataclass(frozen=True)
class NewsPost:
    slug: str
    title: str
    date: date
    category: str
    summary: str
    body: tuple[str, ...]
    image_alt: str | None = None


@dataclass(frozen=True)
class GlossaryTerm:
    term: str
    category: str
    explanation: str
