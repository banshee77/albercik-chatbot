"""Public website page routes (feature 005-public-club-website).

Every route here is an unauthenticated, read-only `GET` rendering a static,
in-memory Python data set through Jinja2 (research.md §1) — no database, no
provider call, no import from `domain/`, `application/`, or `providers/`
(spec FR-034). Wired into the app by `main.py::create_app()`, purely
additively alongside the existing `/api/v1/*`/`/health` routers.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from shiruno.public_site.data.glossary import GLOSSARY_TERMS
from shiruno.public_site.data.locations import LOCATIONS
from shiruno.public_site.data.news import NEWS_POSTS
from shiruno.public_site.data.sessions import SESSIONS
from shiruno.public_site.data.trainers import TRAINERS
from shiruno.public_site.filters import filter_news, filter_sessions

router = APIRouter(tags=["public-site"])

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# The 8 primary pages (spec.md's minimum page set), in nav display order.
# A module-level Jinja global rather than a per-route context value, since
# every page's nav is identical (FR-003).
NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("/", "Strona główna"),
    ("/karate-do", "O Karate-Do"),
    ("/o-klubie", "O klubie"),
    ("/trenerzy", "Trenerzy"),
    ("/sekcje", "Sekcje"),
    ("/grafik", "Grafik"),
    ("/aktualnosci", "Aktualności"),
    ("/kontakt", "Kontakt"),
)
templates.env.globals["nav_items"] = NAV_ITEMS

_HOME_PREVIEW_COUNT = 3


_SCHEDULE_DAYS = tuple(dict.fromkeys(session.day for session in SESSIONS))
_SCHEDULE_LEVELS = tuple(dict.fromkeys(session.age_level for session in SESSIONS))
_SCHEDULE_LOCATIONS = tuple((location.slug, location.name) for location in LOCATIONS)


@router.get("/grafik", response_class=HTMLResponse)
def schedule(
    request: Request,
    location: str | None = None,
    day: str | None = None,
    level: str | None = None,
) -> HTMLResponse:
    sessions = filter_sessions(SESSIONS, location=location, day=day, level=level)
    location_names = {loc.slug: loc.name for loc in LOCATIONS}
    return templates.TemplateResponse(
        request,
        "grafik.html",
        {
            "sessions": sessions,
            "location_names": location_names,
            "filter_locations": _SCHEDULE_LOCATIONS,
            "filter_days": _SCHEDULE_DAYS,
            "filter_levels": _SCHEDULE_LEVELS,
            "selected_location": location,
            "selected_day": day,
            "selected_level": level,
        },
    )


@router.get("/sekcje", response_class=HTMLResponse)
def sections(request: Request) -> HTMLResponse:
    trainer_names = {trainer.slug: trainer.name for trainer in TRAINERS}
    return templates.TemplateResponse(
        request,
        "sekcje.html",
        {"locations": LOCATIONS, "trainer_names": trainer_names},
    )


def _group_glossary_by_category() -> dict[str, list]:
    grouped: dict[str, list] = {}
    for term in GLOSSARY_TERMS:
        grouped.setdefault(term.category, []).append(term)
    return grouped


_NEWS_CATEGORIES = tuple(dict.fromkeys(post.category for post in NEWS_POSTS))
_NEWS_BY_SLUG = {post.slug: post for post in NEWS_POSTS}


@router.get("/kontakt", response_class=HTMLResponse)
def contact(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "kontakt.html", {"locations": LOCATIONS})


@router.get("/aktualnosci", response_class=HTMLResponse)
def news_list(request: Request, category: str | None = None) -> HTMLResponse:
    posts = sorted(
        filter_news(NEWS_POSTS, category=category), key=lambda post: post.date, reverse=True
    )
    return templates.TemplateResponse(
        request,
        "aktualnosci.html",
        {
            "posts": posts,
            "categories": _NEWS_CATEGORIES,
            "selected_category": category,
        },
    )


@router.get("/aktualnosci/{slug}", response_class=HTMLResponse)
def news_detail(request: Request, slug: str) -> HTMLResponse:
    post = _NEWS_BY_SLUG.get(slug)
    if post is None:
        raise HTTPException(status_code=404, detail="News post not found")
    return templates.TemplateResponse(request, "aktualnosci_detail.html", {"post": post})


@router.get("/o-klubie", response_class=HTMLResponse)
def history(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "historia.html", {})


@router.get("/karate-do", response_class=HTMLResponse)
def karate_do(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "karate_do.html",
        {"glossary_by_category": _group_glossary_by_category()},
    )


@router.get("/trenerzy", response_class=HTMLResponse)
def trainers(request: Request) -> HTMLResponse:
    location_names = {location.slug: location.name for location in LOCATIONS}
    return templates.TemplateResponse(
        request,
        "trenerzy.html",
        {"trainers": TRAINERS, "location_names": location_names},
    )


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    news_preview = sorted(NEWS_POSTS, key=lambda post: post.date, reverse=True)[
        :_HOME_PREVIEW_COUNT
    ]
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "news_preview": news_preview,
            "locations_preview": LOCATIONS[:_HOME_PREVIEW_COUNT],
            "trainer_preview": TRAINERS[0],
        },
    )
