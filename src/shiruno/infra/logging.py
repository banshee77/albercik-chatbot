"""Structured, privacy-conscious logging config (FR-052, Principle IX).

Logs MUST NOT contain passwords, authentication tokens, API keys, full
document/prompt content, full embeddings, system instructions, or
unnecessary personal data. Callers are responsible for only passing safe
fields (e.g. an admin's username for audit logging, not their password) —
this module configures *how* logs are formatted/routed, not what callers
choose to log.
"""

import logging
import sys

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent: safe to call multiple times (e.g. once from main.py, once
    from cli.py) without duplicating handlers."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
