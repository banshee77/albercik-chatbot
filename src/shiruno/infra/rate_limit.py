"""Postgres-backed fixed-window rate limiter (research.md §2; tasks.md
T062).

No Redis — this reuses the same always-present Postgres dependency
everything else uses (Principle XIV); correctness across multiple app
processes/instances is exactly what an in-process in-memory counter
cannot give, and that correctness is a Principle X (Cost Safety) concern.

The window is a plain 60-second wall-clock bucket: every request rounds
`now` down to the current minute boundary and atomically increments that
bucket's counter via `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`, so
the limit check needs no separate `SELECT` and there is no race between
"read the count" and "increment it" — concurrent requests for the same
`(source_key, window_start)` serialize on that row's write lock in
Postgres.

`resolve_client_ip` deliberately does NOT trust an arbitrary
client-supplied `X-Forwarded-For` header. This deployment
(docker-compose.yml) exposes the `app` service directly with no reverse
proxy in front of it today, so the safe default (`TRUSTED_PROXY_COUNT=0`)
is to always use the direct TCP peer address and ignore the header
entirely — a client cannot forge that. When this app is one day deployed
behind N trusted reverse proxies, operators set `TRUSTED_PROXY_COUNT=N`
and the Nth-from-the-right entry in `X-Forwarded-For` (the address the
outermost trusted proxy itself observed) is used instead: everything to
its right is something a trusted proxy appended, everything to its left
is untrusted, client-controllable text that is never used as the
rate-limit identity.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from shiruno.persistence.models import RateLimitWindow

_WINDOW_SECONDS = 60


def resolve_client_ip(request: Request, *, trusted_proxy_count: int) -> str:
    if trusted_proxy_count > 0:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
            if len(hops) >= trusted_proxy_count:
                return hops[-trusted_proxy_count]
    client = request.client
    return client.host if client is not None else "unknown"


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


def _window_start(now: datetime) -> datetime:
    return now.replace(second=0, microsecond=0)


def check_and_increment(
    session: Session, *, source_key: str, limit_per_minute: int, now: datetime | None = None
) -> RateLimitResult:
    current_time = now or datetime.now(UTC)
    window_start = _window_start(current_time)

    stmt = (
        insert(RateLimitWindow)
        .values(source_key=source_key, window_start=window_start, request_count=1)
        .on_conflict_do_update(
            index_elements=[RateLimitWindow.source_key, RateLimitWindow.window_start],
            set_={"request_count": RateLimitWindow.request_count + 1},
        )
        .returning(RateLimitWindow.request_count)
    )
    request_count = session.execute(stmt).scalar_one()

    if request_count > limit_per_minute:
        seconds_left = (
            window_start + timedelta(seconds=_WINDOW_SECONDS) - current_time
        ).total_seconds()
        return RateLimitResult(allowed=False, retry_after_seconds=max(int(seconds_left), 1))
    return RateLimitResult(allowed=True, retry_after_seconds=0)
