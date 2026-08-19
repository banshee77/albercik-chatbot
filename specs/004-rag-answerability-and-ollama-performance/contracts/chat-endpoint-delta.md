# Contract Delta: `POST /api/v1/chat`

This feature makes exactly one public API contract change, additive only,
against the baseline defined in
`specs/001-albertos-rag-chatbot/contracts/openapi.yaml`. Everything else
about the endpoint — request shape, `outcome` values, status codes,
rate-limit/size/budget error responses — is unchanged; see that file for
the full existing contract instead of duplicating it here.

## `ChatResponse` — one new field

```diff
 ChatResponse:
   type: object
   required: [outcome, answer]
   properties:
     outcome:
       type: string
       enum: [grounded, insufficient_information, out_of_scope, unavailable]
       description: >
         grounded = FR-027(a); insufficient_information = FR-027(b);
         out_of_scope = FR-027(c); unavailable = FR-043/FR-044 safe
         fallback (LLM disabled or budget exhausted).
     answer:
       type: string
       description: Polish-language response text in every case (FR-030a).
     sources:
       type: array
       items:
         $ref: '#/components/schemas/SourceReferenceOut'
+    request_id:
+      type: string
+      format: uuid
+      description: >
+        Correlation id for this request, also stored on the corresponding
+        usage_records row. Non-sensitive; enables dev tooling (e.g.
+        scripts/run_eval.py) to look up per-request token/latency/telemetry
+        data without exposing it directly in this public response
+        (research.md §9, feature 004-rag-answerability-and-ollama-performance).
```

`request_id` is **not** added to `required` — existing consumers that
ignore unknown response fields are unaffected, and no error path changes
shape.

## What did *not* change

- `ChatRequest` — still exactly `{question: string}`, `extra="forbid"`
  (Principle X unaffected).
- `outcome` enum values — unchanged. `grounded` now means "the model's
  structured `supported` field was `true`" instead of "the model returned
  any text"; `insufficient_information` now also covers "the model's
  structured output parsed successfully and its `supported` field was
  `false`" (previously it only covered "no chunk cleared the relevance
  threshold"). A malformed/schema-invalid/unparseable structured response
  is **not** folded into `insufficient_information` — it raises
  `LLMProviderError` and surfaces as the existing `unavailable` outcome,
  the same as any other provider/protocol failure (FR-008). The *set* of
  possible outcomes and their public meaning to a caller is unchanged.
- Status codes (`400`, `413`, `429`, `503`) and their triggers — unchanged.
- No new request field, no new way for a client to influence provider
  selection, thinking mode, or the structured-output schema (Principle X).

## Internal-only surface (not part of this contract)

- `usage_records.provider_metrics` (new nullable column) is never exposed
  via any API response — read only by `scripts/run_eval.py` via a direct
  database query (research.md §9), and only in the dev/eval environment
  that already has `DATABASE_URL` access.
