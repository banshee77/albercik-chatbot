"""Single tenant-scoped conversation fetch (feature
011-conversations-analytics, US2, contracts/conversations-api.md). A
missing or foreign-tenant conversation both raise the identical
`NotFoundAppError` — same pattern as `documents/get_document.py` (feature
010-knowledge-base-admin) — so a cross-tenant lookup is indistinguishable
from a lookup of a nonexistent record (FR-022, FR-035).
"""

import uuid

from sqlalchemy.orm import Session

from shiruno.api.errors import NotFoundAppError
from shiruno.persistence.models import ConversationRecord


def get_conversation(
    conversation_id: uuid.UUID, *, session: Session, tenant_id: uuid.UUID
) -> ConversationRecord:
    record = session.get(ConversationRecord, conversation_id)
    if record is None or record.tenant_id != tenant_id:
        raise NotFoundAppError("Conversation not found.")
    return record
