"""Exception -> HTTP response mapping (FR-049, FR-050, Principle VIII).

Client-facing error responses MUST NOT include stack tracebacks,
credentials, internal infrastructure details, AI provider configuration,
embeddings, or system instructions — only a short, safe `detail` string
(contracts/openapi.yaml `ErrorResponse`). Unhandled exceptions are logged
server-side with full detail and returned to the client as a generic 500.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from albercik_chatbot.infra.logging import get_logger

logger = get_logger(__name__)


class ErrorResponse(BaseModel):
    detail: str


class AppError(Exception):
    """Base for application-level errors that map to a specific, safe HTTP
    response. Raise a subclass; never let a raw internal exception's
    message reach the client (FR-049)."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    safe_detail: str = "Invalid request."
    headers: dict[str, str] | None = None

    def __init__(
        self, safe_detail: str | None = None, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(safe_detail or self.safe_detail)
        if safe_detail is not None:
            self.safe_detail = safe_detail
        if headers is not None:
            self.headers = headers


class ValidationAppError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    safe_detail = "The request was invalid."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    safe_detail = "Authentication required or invalid."


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    safe_detail = "Not permitted."


class NotFoundAppError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    safe_detail = "Not found."


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    safe_detail = "Request exceeds the configured maximum size."


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    safe_detail = "Too many requests."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(detail=exc.safe_detail).model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(detail="The request was invalid.").model_dump(),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        # Full detail goes to the server-side log only — never to the client.
        logger.exception("Unhandled exception while processing request", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(detail="An internal error occurred.").model_dump(),
        )
