# Quickstart: LLM / RAG Observability

**Feature**: `012-rag-observability` | **Spec**: [spec.md](./spec.md)

This validates the feature end-to-end against the live local Docker stack,
including the optional Phoenix trace-visualization backend (US8, SC-007).
It is a manual/live validation guide — automated coverage lives in the test
suite per research.md R12 and does not require any of the steps below.

## Prerequisites

- Normal local stack already working: `docker compose up -d` (per the
  project's existing `README`/quickstart from earlier features).
- `.env` has `OBSERVABILITY_ENABLED=true` and
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:6006/v1/traces` set (both
  commented-out/`false`/empty by default in `.env.example` — this feature
  is opt-in).

## 1. Confirm normal operation is unaffected without Phoenix running

```sh
docker compose up -d
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Jakie są godziny treningów?"}' | jq
```

Expected: a normal `ChatResponse` (200, with `outcome`/`answer`/`sources`),
identical to before this feature, even though `OBSERVABILITY_ENABLED=true`
and no `phoenix` service is running yet (FR-036, FR-032 — the OTLP export
attempt fails silently in the background).

## 2. Start the optional Phoenix backend

```sh
docker compose --profile observability up -d phoenix
```

Open the Phoenix UI at **http://localhost:6006**.

## 3. Send a traced grounded request and find it in Phoenix

```sh
REQUEST_ID_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Jakie są godziny treningów?"}')
echo "$REQUEST_ID_RESPONSE" | jq -r .request_id
```

In the Phoenix UI: open the `shiruno` project's trace list, and either
browse to the most recent trace or filter by the `shiruno.request_id`
attribute using the `request_id` value printed above. Confirm:

- One root `shiruno.chat` span, with child spans in order:
  `shiruno.security_or_cost_gates` → `shiruno.small_talk_classification` →
  `shiruno.scope_classification` → `shiruno.query_embedding` →
  `shiruno.retrieval` → `shiruno.context_assembly` →
  `shiruno.llm_generation` → `shiruno.conversation_recording`.
- The `shiruno.retrieval` span shows candidate/selected counts and, for
  each selected chunk, a similarity score and source label — no full chunk
  text (content capture is off by default).
- The `shiruno.llm_generation` span shows provider/model/token counts and
  `shiruno.llm.supported` — no full answer text.
- Neither the visitor's question nor the assistant's answer text appears
  anywhere in the trace (default configuration).

## 4. Send a small-talk message and confirm no fabricated stages

```sh
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Cześć!"}' | jq
```

In Phoenix: the resulting trace shows only
`shiruno.security_or_cost_gates` → `shiruno.small_talk_classification` →
`shiruno.conversation_recording` — no embedding, retrieval, or generation
spans (US5, SC-006).

## 5. Confirm correlation with the Feature 011 conversation record

```sh
# Using an existing tenant admin token (see Feature 011's own quickstart
# for how to obtain one):
curl -s http://localhost:8000/api/v1/admin/conversations \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.items[0].request_id'
```

Confirm the `request_id` returned here matches a `shiruno.request_id`
attribute value on a trace in Phoenix (US7, SC-005) — no `trace_id` lookup
is needed on either side (research.md R9).

## 6. Confirm an unreachable backend still doesn't break chat

```sh
docker compose --profile observability stop phoenix
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Jakie są godziny treningów?"}' | jq
```

Expected: identical successful `ChatResponse` as step 1/3, even with
`OBSERVABILITY_ENABLED=true` and Phoenix stopped (US6, FR-032).

## 7. Optional: enable content capture locally and see richer traces

Set both `OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT=true` and
`OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT=true` in `.env`, restart
`app` (`docker compose up -d app`), repeat step 3, and confirm the visitor
question, assistant answer, retrieved chunk text, and assembled prompt now
appear on the relevant spans — clearly demonstrating both settings are
independent (Edge Cases) and off unless explicitly turned on.

## Cleanup

```sh
docker compose --profile observability down
```

Leaves the normal `db`/`ollama`/`app` stack untouched.
