"""Pre-Phase-5 security checkpoint (2026-08-17): dedicated unit tests for
`infra/security.py`'s JWT issuance/verification, proving the properties
reviewed at that checkpoint — expiration is enforced, the signing/
verification algorithm is a fixed server-side value never derived from the
token itself (the classic JWT "algorithm confusion" class of
vulnerability), and malformed/expired/mismatched tokens are all rejected
the same generic way (a `None` return, mapped to a 401 by
`api/deps.py::get_current_administrator`). No DB, no network.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from albercik_chatbot.infra.security import issue_access_token, verify_access_token

_SECRET = "test-secret-not-a-real-one-but-long-enough-for-hs256"
_ALGORITHM = "HS256"


def test_issued_token_round_trips_to_the_same_administrator_id() -> None:
    admin_id = uuid.uuid4()
    issued = issue_access_token(
        administrator_id=admin_id, secret=_SECRET, algorithm=_ALGORITHM, expire_minutes=60
    )

    result = verify_access_token(issued.access_token, secret=_SECRET, algorithm=_ALGORITHM)
    assert result == admin_id


def test_issued_token_has_an_expiration_claim() -> None:
    issued = issue_access_token(
        administrator_id=uuid.uuid4(), secret=_SECRET, algorithm=_ALGORITHM, expire_minutes=60
    )

    payload = jwt.decode(issued.access_token, _SECRET, algorithms=[_ALGORITHM])
    assert "exp" in payload


def test_expired_token_is_rejected() -> None:
    issued = issue_access_token(
        administrator_id=uuid.uuid4(), secret=_SECRET, algorithm=_ALGORITHM, expire_minutes=-1
    )

    assert verify_access_token(issued.access_token, secret=_SECRET, algorithm=_ALGORITHM) is None


def test_token_signed_with_a_different_algorithm_is_rejected() -> None:
    """The server always passes a fixed, server-controlled `algorithms`
    allow-list to `jwt.decode` — never derived from the token's own
    header — so a token claiming a different algorithm than configured is
    rejected outright rather than silently accepted."""
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        _SECRET,
        algorithm="HS384",
    )

    assert verify_access_token(token, secret=_SECRET, algorithm=_ALGORITHM) is None


def test_token_with_wrong_secret_is_rejected() -> None:
    issued = issue_access_token(
        administrator_id=uuid.uuid4(), secret=_SECRET, algorithm=_ALGORITHM, expire_minutes=60
    )

    result = verify_access_token(
        issued.access_token,
        secret="a-completely-different-secret-also-long-enough",
        algorithm=_ALGORITHM,
    )
    assert result is None


def test_malformed_token_is_rejected() -> None:
    assert verify_access_token("not-a-real-token", secret=_SECRET, algorithm=_ALGORITHM) is None


def test_token_missing_sub_claim_is_rejected() -> None:
    token = jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(minutes=5)}, _SECRET, algorithm=_ALGORITHM
    )

    assert verify_access_token(token, secret=_SECRET, algorithm=_ALGORITHM) is None


def test_token_with_non_uuid_sub_claim_is_rejected() -> None:
    token = jwt.encode(
        {"sub": "not-a-uuid", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        _SECRET,
        algorithm=_ALGORITHM,
    )

    assert verify_access_token(token, secret=_SECRET, algorithm=_ALGORITHM) is None
