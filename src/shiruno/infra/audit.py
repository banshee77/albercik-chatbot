"""Privacy-conscious audit logging for security-relevant administrator
actions (FR-053, Principle IX; tasks.md T074).

A dedicated logger (`shiruno.audit`), not a new persistence table
or external logging service — `infra/logging.py`'s existing structured
handler (stderr, one line per record) is the delivery mechanism; this
module only defines *what* gets logged. `log_audit_event`'s parameter list
is exactly (action, outcome, administrator identity, target document id,
tenant id — feature 009-admin-platform-foundation, FR-025) — there is no
parameter here that could carry a password, JWT, API key, document
content, embedding, or system prompt, so a caller cannot accidentally log
one even by mistake; this is a structural guarantee, not just a
convention callers are trusted to follow. Chat questions are likewise
never routed through this module at all — auditing only ever covers
administrator actions (login, upload, delete), not visitor messages.
"""

import uuid
from typing import Literal

from shiruno.infra.logging import get_logger

_audit_logger = get_logger("shiruno.audit")

AuditAction = Literal["login_success", "login_failure", "document_upload", "document_delete"]
AuditOutcome = Literal["success", "failure", "not_found"]


def log_audit_event(
    action: AuditAction,
    *,
    outcome: AuditOutcome,
    administrator_id: uuid.UUID | None = None,
    username: str | None = None,
    document_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> None:
    _audit_logger.info(
        "audit action=%s outcome=%s administrator_id=%s username=%s document_id=%s tenant_id=%s",
        action,
        outcome,
        administrator_id,
        username,
        document_id,
        tenant_id,
    )
