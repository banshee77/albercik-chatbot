"""FastAPI dependency helpers.

Provider-access dependencies live here (rather than in `main.py`, which
constructs the providers) so that `api.routers.*` never imports `main` —
avoiding a circular import (`main` -> routers -> `main`).

`get_current_administrator` (T048) is the single server-side authorization
gate for every knowledge-base management route (FR-005, FR-006, FR-007):
it is a FastAPI dependency, resolved before any route body executes, so an
unauthenticated/invalid/inactive-account request never reaches
`application/upload_document.py` et al. A missing token, a malformed or
expired token, an unknown administrator id, and an inactive account all
raise the exact same `UnauthorizedError` — no signal is given to the
caller about which case applied (FR-008).
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from albercik_chatbot.api.errors import PayloadTooLargeError, UnauthorizedError
from albercik_chatbot.config import get_settings
from albercik_chatbot.infra.concurrency import ChatConcurrencyGuard
from albercik_chatbot.infra.security import verify_access_token
from albercik_chatbot.persistence.database import get_session
from albercik_chatbot.persistence.models import Administrator
from albercik_chatbot.providers.embedding.protocol import EmbeddingProvider
from albercik_chatbot.providers.llm.protocol import LLMProvider

_GENERIC_AUTH_FAILURE = "Authentication required."

# auto_error=False: a missing Authorization header must produce the same
# generic 401 as an invalid one (FastAPI's HTTPBearer default raises 403
# on a missing header, which we don't want — see class docstring above).
_bearer_scheme = HTTPBearer(auto_error=False)


def get_llm_provider(request: Request) -> LLMProvider:
    provider: LLMProvider = request.app.state.llm_provider
    return provider


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    provider: EmbeddingProvider = request.app.state.embedding_provider
    return provider


def get_chat_concurrency_guard(request: Request) -> ChatConcurrencyGuard:
    guard: ChatConcurrencyGuard = request.app.state.chat_concurrency_guard
    return guard


def require_bounded_request_body(request: Request) -> None:
    """Depends()-based request-body-size guard (Phase 5, T057; "HTTP/
    payload validation", the pipeline's first and cheapest step). Reads
    the client-declared `Content-Length` header — which FastAPI resolves
    ALL `Depends()` before it parses/validates the request body, so this
    always runs before `ChatRequest` is ever built — rejecting an
    oversized declared body before it's read into memory at all.

    Residual limitation, matching the same documented gap in
    `api/routers/documents.py::_read_upload_bounded`: a client that omits
    `Content-Length` and streams a chunked-encoded body without declaring
    its size bypasses this specific check. The question's own char-length
    limit (`api/schemas.py::ChatRequest`, enforced against the decoded,
    parsed value) is the backstop for that case.
    """
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        declared_size = int(content_length)
    except ValueError:
        return
    if declared_size > settings.MAX_CHAT_REQUEST_BODY_BYTES:
        raise PayloadTooLargeError("Request exceeds the configured maximum size.")


def get_current_administrator(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: Session = Depends(get_session),
) -> Administrator:
    if credentials is None:
        raise UnauthorizedError(_GENERIC_AUTH_FAILURE)

    settings = get_settings()
    administrator_id = verify_access_token(
        credentials.credentials,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
    )
    if administrator_id is None:
        raise UnauthorizedError(_GENERIC_AUTH_FAILURE)

    administrator = session.get(Administrator, administrator_id)
    if administrator is None or not administrator.is_active:
        raise UnauthorizedError(_GENERIC_AUTH_FAILURE)

    return administrator
