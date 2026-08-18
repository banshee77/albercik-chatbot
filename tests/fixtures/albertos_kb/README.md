# Albertos calibration knowledge base (development-only)

The `.txt` files in this directory are **synthetic calibration content**,
written for the Phase 3 RAG calibration checkpoint. They are not real
Albertos business facts (prices, hours, policies, contact details) — they
exist only to give the chunker, the real embedding model, and the
retrieval threshold something realistic-shaped to be measured against.

Do not:
- treat this content as production knowledge or seed it into a real
  deployment's database,
- copy it into `.env`, `src/`, or any migration/seed script,
- rely on any specific number/date/phone value here being meaningful.

If Albertos ever provides real content, it replaces this directory's role
entirely (uploaded via the admin document-upload flow, Phase 4+) — this
fixture set is calibration-only and lives under `tests/fixtures/`
specifically so it's obviously not shipped as application data.
