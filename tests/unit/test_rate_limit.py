"""Unit tests for the Postgres-backed fixed-window rate limiter (T054;
research.md §2). Uses the real `db_session` fixture (Postgres/pgvector via
`db-test`) since there is no in-memory substitute for the atomic
`INSERT ... ON CONFLICT DO UPDATE ... RETURNING` this relies on —
`resolve_client_ip`'s pure-Python trusted-proxy logic needs no DB at all.
"""

from datetime import UTC, datetime

from starlette.datastructures import Headers
from starlette.requests import Request

from albercik_chatbot.infra.rate_limit import check_and_increment, resolve_client_ip


def _make_request(*, client_host: str | None, headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "headers": Headers(headers or {}).raw,
        "client": (client_host, 12345) if client_host is not None else None,
    }
    return Request(scope)


def test_resolve_client_ip_uses_direct_peer_when_no_proxies_trusted() -> None:
    request = _make_request(
        client_host="203.0.113.5", headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
    )
    assert resolve_client_ip(request, trusted_proxy_count=0) == "203.0.113.5"


def test_resolve_client_ip_ignores_missing_header_when_proxies_trusted() -> None:
    request = _make_request(client_host="203.0.113.5")
    assert resolve_client_ip(request, trusted_proxy_count=1) == "203.0.113.5"


def test_resolve_client_ip_uses_nth_hop_from_right_when_proxies_trusted() -> None:
    # Client -> real attacker-controlled hop -> trusted proxy -> app.
    # With one trusted proxy, only the right-most entry (what the trusted
    # proxy itself observed) is used — never client-supplied text.
    request = _make_request(
        client_host="10.0.0.1",  # the trusted proxy's own connection to the app
        headers={"x-forwarded-for": "attacker-spoofed, 198.51.100.9"},
    )
    assert resolve_client_ip(request, trusted_proxy_count=1) == "198.51.100.9"


def test_resolve_client_ip_falls_back_when_header_has_fewer_hops_than_trusted_proxies() -> None:
    request = _make_request(client_host="10.0.0.1", headers={"x-forwarded-for": "198.51.100.9"})
    assert resolve_client_ip(request, trusted_proxy_count=2) == "10.0.0.1"


def test_first_request_in_a_window_is_allowed(db_session) -> None:
    result = check_and_increment(
        db_session, source_key="1.2.3.4", limit_per_minute=5, now=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert result.allowed is True


def test_requests_over_the_limit_in_the_same_window_are_rejected(db_session) -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    source_key = f"rate-limit-test-{now.isoformat()}"
    for _ in range(3):
        result = check_and_increment(db_session, source_key=source_key, limit_per_minute=3, now=now)
        assert result.allowed is True

    result = check_and_increment(db_session, source_key=source_key, limit_per_minute=3, now=now)
    assert result.allowed is False
    assert result.retry_after_seconds > 0


def test_different_source_keys_do_not_share_a_window(db_session) -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    for _ in range(3):
        check_and_increment(db_session, source_key="key-a", limit_per_minute=3, now=now)

    result = check_and_increment(db_session, source_key="key-b", limit_per_minute=3, now=now)
    assert result.allowed is True


def test_a_new_window_resets_the_count(db_session) -> None:
    source_key = "window-reset-test"
    first_minute = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    next_minute = datetime(2026, 1, 1, 12, 1, 0, tzinfo=UTC)

    for _ in range(3):
        check_and_increment(db_session, source_key=source_key, limit_per_minute=3, now=first_minute)
    result = check_and_increment(
        db_session, source_key=source_key, limit_per_minute=3, now=first_minute
    )
    assert result.allowed is False

    result = check_and_increment(
        db_session, source_key=source_key, limit_per_minute=3, now=next_minute
    )
    assert result.allowed is True
