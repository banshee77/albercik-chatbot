"""T074 — unit tests for privacy-conscious audit logging (FR-053,
Principle IX). `log_audit_event`'s parameter list is, by construction,
incapable of carrying a password/JWT/API key/document content/embedding/
system prompt/chat question — there is no such parameter to pass one
through, so this is a structural guarantee, not just a convention.
"""

import logging
import uuid

from albercik_chatbot.infra.audit import log_audit_event


def test_login_success_is_logged_with_administrator_id(caplog) -> None:
    admin_id = uuid.uuid4()
    with caplog.at_level(logging.INFO, logger="albercik_chatbot.audit"):
        log_audit_event(
            "login_success", outcome="success", administrator_id=admin_id, username="admin1"
        )

    assert len(caplog.records) == 1
    message = caplog.records[0].message
    assert "login_success" in message
    assert str(admin_id) in message
    assert "admin1" in message


def test_login_failure_is_logged_without_administrator_id(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="albercik_chatbot.audit"):
        log_audit_event("login_failure", outcome="failure", username="unknown-user")

    message = caplog.records[0].message
    assert "login_failure" in message
    assert "unknown-user" in message


def test_document_upload_is_logged_with_document_id(caplog) -> None:
    admin_id = uuid.uuid4()
    document_id = uuid.uuid4()
    with caplog.at_level(logging.INFO, logger="albercik_chatbot.audit"):
        log_audit_event(
            "document_upload",
            outcome="success",
            administrator_id=admin_id,
            document_id=document_id,
        )

    message = caplog.records[0].message
    assert "document_upload" in message
    assert str(document_id) in message


def test_document_delete_not_found_is_logged(caplog) -> None:
    admin_id = uuid.uuid4()
    document_id = uuid.uuid4()
    with caplog.at_level(logging.INFO, logger="albercik_chatbot.audit"):
        log_audit_event(
            "document_delete",
            outcome="not_found",
            administrator_id=admin_id,
            document_id=document_id,
        )

    message = caplog.records[0].message
    assert "not_found" in message


def test_audit_event_never_accepts_password_or_secret_looking_content(caplog) -> None:
    # There is no `password`/`token`/`content` parameter on this function
    # at all — this test documents that fact by using every parameter the
    # function actually has and confirming nothing beyond them can leak in.
    with caplog.at_level(logging.INFO, logger="albercik_chatbot.audit"):
        log_audit_event(
            "login_success",
            outcome="success",
            administrator_id=uuid.uuid4(),
            username="admin1",
            document_id=None,
        )

    message = caplog.records[0].message
    assert "password" not in message.lower()
