"""POST/GET /api/v1/documents, DELETE /api/v1/documents/{document_id} —
User Story 2 (T052). Every route depends on
`api.deps.get_current_administrator` (FR-003, FR-004, FR-007) — FastAPI
resolves that dependency before any route body runs, so an unauthenticated
or invalid-token request never reaches upload/list/delete logic at all,
and no knowledge-base state changes as a side effect of a rejected
request (SC-004).
"""

import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from albercik_chatbot.api.deps import get_current_administrator, get_embedding_provider
from albercik_chatbot.api.errors import NotFoundAppError, PayloadTooLargeError
from albercik_chatbot.api.schemas import DocumentSummary
from albercik_chatbot.application.delete_document import delete_document
from albercik_chatbot.application.list_documents import list_documents
from albercik_chatbot.application.upload_document import upload_document
from albercik_chatbot.config import get_settings
from albercik_chatbot.infra.audit import log_audit_event
from albercik_chatbot.persistence.database import get_session
from albercik_chatbot.persistence.models import Administrator, DocumentStatus, KnowledgeDocument
from albercik_chatbot.providers.embedding.protocol import EmbeddingProvider

router = APIRouter(prefix="/api/v1", tags=["documents"])

# Pre-Phase-5 security checkpoint (2026-08-17): read size, not a config
# knob — an internal implementation detail of how bounded reading works,
# not a product-level threshold (that's MAX_UPLOAD_SIZE_BYTES).
_UPLOAD_READ_CHUNK_BYTES = 64 * 1024


async def _read_upload_bounded(file: UploadFile, *, max_size_bytes: int) -> bytes:
    """Reads `file` in bounded chunks instead of one `await file.read()`
    call, so this handler never materializes more than
    `max_size_bytes` (+ one chunk) into a single `bytes` object, and stops
    pulling further chunks from the upload the moment the configured
    maximum is crossed — it does not keep draining the rest of an
    oversized upload just to compute a final length. Content is never
    written to the filesystem either way (data-model.md).

    Note: this bounds *this application's* buffering. Starlette's own
    multipart parser has already read the request body into an
    `UploadFile` (an in-memory/spooled-temp-file object) by the time this
    function runs — true network-level early rejection before that would
    need ASGI middleware inspecting the body as it arrives, which is
    exactly the kind of streaming infrastructure this checkpoint's scope
    excludes. Documented as a residual limitation, not fixed here.
    """
    chunks: list[bytes] = []
    total_bytes = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_size_bytes:
            raise PayloadTooLargeError("File exceeds the configured maximum size.")
        chunks.append(chunk)
    return b"".join(chunks)


def _to_summary(document: KnowledgeDocument) -> DocumentSummary:
    return DocumentSummary(
        id=document.id,
        filename=document.original_filename,
        status=document.status.value,
        uploaded_at=document.uploaded_at,
    )


@router.post("/documents", response_model=DocumentSummary, status_code=201)
async def post_document(
    file: UploadFile,
    session: Session = Depends(get_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    current_admin: Administrator = Depends(get_current_administrator),
) -> DocumentSummary:
    settings = get_settings()
    content_bytes = await _read_upload_bounded(file, max_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES)
    document = upload_document(
        filename=file.filename or "upload.txt",
        content_bytes=content_bytes,
        session=session,
        embedding_provider=embedding_provider,
        uploaded_by=current_admin,
        max_upload_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
        chunk_size_chars=settings.CHUNK_SIZE_CHARS,
        chunk_overlap_chars=settings.CHUNK_OVERLAP_CHARS,
        embedding_model_name=settings.EMBEDDING_MODEL_NAME,
    )
    log_audit_event(
        "document_upload",
        outcome="success" if document.status == DocumentStatus.ready else "failure",
        administrator_id=current_admin.id,
        document_id=document.id,
    )
    return _to_summary(document)


@router.get("/documents", response_model=list[DocumentSummary])
def get_documents(
    session: Session = Depends(get_session),
    current_admin: Administrator = Depends(get_current_administrator),
) -> list[DocumentSummary]:
    return [_to_summary(document) for document in list_documents(session)]


@router.delete("/documents/{document_id}", status_code=204)
def delete_document_route(
    document_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_admin: Administrator = Depends(get_current_administrator),
) -> None:
    try:
        delete_document(document_id, session=session)
    except NotFoundAppError:
        log_audit_event(
            "document_delete",
            outcome="not_found",
            administrator_id=current_admin.id,
            document_id=document_id,
        )
        raise
    log_audit_event(
        "document_delete",
        outcome="success",
        administrator_id=current_admin.id,
        document_id=document_id,
    )
