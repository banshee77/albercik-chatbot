# Quickstart: Knowledge Base UI

**Feature**: `014-knowledge-base-ui` | **Spec**: [spec.md](./spec.md)

Manual/live validation against the real local stack. Automated coverage
(component tests, backend regression suite) lives in the test suite per
research.md R10 and does not require any of the steps below — this guide
proves the feature end-to-end for a human, not the automated gate.

## Prerequisites

- Backend running with CORS enabled for the admin frontend's origin
  (`CORS_ALLOWED_ORIGINS=http://localhost:5173` in the root `.env`) —
  identical prerequisite to Feature 013's own quickstart.
- A tenant administrator account exists (Feature 013's quickstart already
  covers creating one if none does):
  ```sh
  uv run python -m shiruno.cli create-tenant --name "Quickstart Co" --slug quickstart
  uv run python -m shiruno.cli create-admin --tenant quickstart --username admin --password <a-real-password>
  ```
- A small verification text file to upload, e.g.:
  ```sh
  printf 'Shiruno Feature 014 quickstart verification document.\n' > /tmp/f014-verification.txt
  ```

## 1. Start the Admin frontend

```sh
cd apps/admin
npm install   # first time only
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`).

## 2. Log in and open Knowledge

Log in with the administrator credentials from Prerequisites, then select
"Knowledge" from primary navigation.

Expected: `/app/knowledge` loads — either an intentional empty state
("No knowledge has been added yet.") if this tenant has no documents yet,
or a health summary + document list if it does (spec US1).

## 3. Upload the verification document

Choose the upload action, select `/tmp/f014-verification.txt`, confirm.

Expected: an explicit "uploading and indexing" state appears, then the
document appears in the list with status "Ready," the health summary's
counts update, and a success message is shown — no browser reload (spec
US2).

## 4. Open the document's detail

Select the verification document from the list.

Expected: a detail panel shows its filename, "Ready" status, content
type, and upload/update/indexed dates — no raw chunk text, embeddings, or
tenant ID anywhere (spec FR-014/FR-015).

## 5. Re-index the document

From the detail panel (or the row), choose "Re-index" (worded as
rebuilding the search index).

Expected: an intentional pending state appears, then the document's
status and the health summary both refresh, with a success message (spec
US3, FR-017–FR-019).

## 6. Replace the document

Choose "Replace," select a second small text file (e.g. edit and re-save
`/tmp/f014-verification.txt` with different content), confirm the
lightweight replacement confirmation.

Expected: the confirmation explains the current document keeps serving
the assistant until the replacement succeeds; after it succeeds, the list
shows the new version as active, the old one no longer appears in the
active list, and the health summary refreshes (spec US4).

## 7. Confirm no tenant-selection control exists

Inspect the Knowledge page.

Expected: no dropdown, tenant ID field, or similar control anywhere that
would let this administrator choose a different tenant's knowledge (spec
FR-031).

## 8. Delete the verification document

Choose "Delete" on the replacement document, confirm the deliberate
confirmation step (which names the document by its filename), confirm.

Expected: the document disappears from the active list, the health
summary refreshes, and a success message is shown — no browser reload
(spec US5).

## 9. Confirm cleanup

Reload the Knowledge page (a real browser refresh this time, to prove
persistence rather than trusting only in-memory state) and confirm the
verification document is gone from both the list and the health counts.
No manual SQL is used at any point in this walkthrough — deletion goes
through the same UI/API flow a real administrator would use.

## 10. Log out and re-check protection

Log out, then navigate directly to `/app/knowledge` again.

Expected: redirected to `/login` — no knowledge data shown after logout
(reusing Feature 013's existing session behavior, spec US6).

## 11. Narrower viewport check

Using browser dev-tools device emulation, resize to a common tablet width
(~768px) and repeat steps 2–4.

Expected: the health summary and document list remain usable (via
horizontal scroll, responsive layout, or column reduction) and every
action stays reachable — no layout overlap or clipped content (spec
FR-039).

## Cleanup

```sh
# apps/admin/: Ctrl-C the `npm run dev` process
rm -f /tmp/f014-verification.txt
```

No real LLM call, Ollama, Phoenix, or Anthropic credential is needed at
any point in this walkthrough — Knowledge upload/replace/re-index only
exercise the local embedding provider Feature 010 already uses, and never
invoke `/api/v1/chat` or any observability path.
