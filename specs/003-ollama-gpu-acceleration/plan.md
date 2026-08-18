# Implementation Plan: Ollama GPU Acceleration

**Branch**: `003-ollama-gpu-acceleration` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-ollama-gpu-acceleration/spec.md`

## Summary

Add NVIDIA GPU passthrough to the `ollama` service in `docker-compose.yml`
using Docker Compose's native `deploy.resources.reservations.devices` GPU
device-reservation block — the standard, non-Swarm-only mechanism the
`docker compose` v2 CLI already honors. The block is declared directly and
permanently on the `ollama` service only (per the Clarifications session:
no override file, no Compose profile); `app`, `db`, `db-test`, and
`ollama-init` are untouched. No Python source code changes anywhere —
`OllamaLLMProvider` and the rest of the application are already fully
provider/hardware-agnostic (they talk to Ollama over HTTP; whether the
Ollama *process* on the other end uses a GPU is invisible to them). The
existing static-YAML-parsing test file
(`tests/unit/test_docker_compose_provisioning.py`) gets new assertions
proving the device block is present on `ollama` and absent everywhere else,
without requiring a GPU or a Docker daemon. README.md's existing "no GPU
passthrough by default" language (added in feature 002) is updated to
reflect the new default, including the manual CPU-fallback edit for hosts
without a compatible GPU.

## Technical Context

**Language/Version**: Python 3.14 (unchanged — no application code touched
by this feature)

**Primary Dependencies**: None added. This feature uses only Docker
Compose's built-in GPU device-reservation syntax (Compose Spec
`deploy.resources.reservations.devices`), already available in the
project's existing Docker Compose (Principle XIV — no new dependency
category)

**Storage**: N/A — no schema, table, or migration change

**Testing**: pytest, extending the existing static Compose-YAML parsing
pattern in `tests/unit/test_docker_compose_provisioning.py` (PyYAML only —
no Docker daemon, no GPU, no `docker compose` CLI invocation), consistent
with spec FR-013/SC-003

**Target Platform**: Linux / WSL2 Docker host with NVIDIA driver + NVIDIA
Container Toolkit installed (manual GPU verification target: RTX 3070, 8 GB
VRAM); CI and non-GPU developer machines are unaffected since the automated
suite only parses YAML

**Project Type**: Single existing backend web service (unchanged) — this
feature is a deployment/infrastructure-config change plus documentation, not
an application feature

**Performance Goals**: Not independently quantified (spec Assumptions/
Outstanding item — GPU speedup is inherently hardware- and model-dependent).
Verified qualitatively: `nvidia-smi` shows GPU compute/VRAM utilization by
the `ollama` process during a real `qwen3:4b` inference (spec SC-001)

**Constraints**: GPU device access MUST be limited to the `ollama` service
only (spec FR-002); port 11434 MUST remain unpublished (FR-004); zero
Python/domain code changes (FR-010); `docker compose config` MUST validate
successfully regardless of whether the host actually has a GPU (FR-009);
the existing automated test suite MUST pass without a GPU (FR-013); the GPU
device reservation is declared inline in the single `docker-compose.yml`,
not a separate override file or profile (FR-016, Clarifications 2026-08-18)

**Scale/Scope**: One service block edited (`ollama` in `docker-compose.yml`,
~6 added lines); one existing test file extended with new assertions; two
documentation sections updated (`README.md`'s "Local Ollama backend" bullet
list and "Known limitations" list). Zero new services, zero new files under
`src/`, zero new top-level Compose services.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| I. Security by Default | GPU device access is a host-level resource grant to one already-internal-only container, not a secret or credential; nothing new to protect. | PASS |
| II. Tenancy Posture | Untouched — no tenant/org concept anywhere in this feature. | N/A |
| III. Secure RAG | Untouched — GPU acceleration changes only inference *speed* for the already-existing `OllamaLLMProvider` backend process; prompt assembly, untrusted-content handling, and grounding logic are unmodified (spec FR-011). | N/A |
| IV. Secure Document Ingestion | Untouched — ingestion pipeline unmodified. | N/A |
| V. LLM Provider Neutrality | `OllamaLLMProvider` and the `LLMProvider` Protocol boundary are untouched; GPU vs. CPU is a runtime characteristic of the Ollama process behind that boundary, invisible to `application/ask_question.py` (spec FR-010). | PASS |
| VI. Embedding Provider Neutrality | Untouched — in-process `sentence-transformers` embeddings stay CPU-only, not part of this feature (spec FR-003). | PASS |
| VII. Provider and Cloud Neutrality | NVIDIA GPU passthrough is an optional *host-hardware* capability, not a cloud-provider dependency; the application remains deployable without a GPU (CPU-only, via the documented manual edit) and to any cloud/host. | PASS (noted) |
| VIII. API Security | No API surface, endpoint, or auth change. | N/A |
| IX. Privacy and Logging | No logging change. | N/A |
| X. Cost Safety (NON-NEGOTIABLE) | Ollama usage is already outside the paid-Anthropic-budget path (feature 002); this feature grants no new client-controllable capability and doesn't touch budget/kill-switch/rate-limit logic. | PASS |
| XI. Testing Discipline (NON-NEGOTIABLE) | `tests/unit/test_docker_compose_provisioning.py` gains assertions that only `ollama` declares a GPU device reservation and that `app`/`db`/`db-test`/`ollama-init` do not — pure static YAML parsing, no real GPU or Docker daemon required (spec FR-013). | PASS |
| XII. Engineering Quality | Single, narrowly-scoped config addition at an already-existing seam (`ollama`'s service block); no new abstraction, pattern, or module introduced. | PASS |
| XIII. Simplicity for MVP | Explicitly no Kubernetes, GPU scheduler, vLLM, or second model server (spec FR-014); reuses Docker Compose's own native GPU-passthrough primitive instead of new infrastructure; no override file/profile mechanism added either (spec FR-016) — the simplest option that satisfies the requirement. | PASS |
| XIV. Approved MVP Technology Stack | Docker / Docker Compose is already an approved stack element; this feature adds no new dependency, SDK, or infrastructure category — only a config block using Compose's existing spec. | PASS |

No violations requiring justification — **Complexity Tracking is empty.**

**Post-Design Re-check** (after Phase 0 `research.md` and Phase 1
`quickstart.md` were written): the design confirms zero new dependencies,
zero new services, and zero Python source changes — strictly a Compose
config addition plus test/doc updates. Nothing in Phase 0/1 introduced any
new principle exposure (no new secrets, no new endpoint, no new provider
abstraction, no cost-control surface touched). All 14 principles remain as
assessed above; the gate is still clean.

## Project Structure

### Documentation (this feature)

```text
specs/003-ollama-gpu-acceleration/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command — NOT created by /speckit-plan)
```

No `data-model.md`: this feature introduces no entity, field, table, or
migration — nothing in the spec's scope touches persisted data.

No `contracts/`: this feature exposes no interface of its own and changes
no existing one. `/api/v1/chat`'s contract
(`specs/001-albertos-rag-chatbot/contracts/openapi.yaml`) is unchanged;
Ollama's own HTTP API (a third-party interface the application already
depends on, documented in feature 002's research.md) is unaffected — GPU
acceleration changes which hardware serves that API, not its shape.

### Source Code (repository root)

```text
docker-compose.yml                   # EDITED — `ollama` service gains a
                                      #   `deploy.resources.reservations.
                                      #   devices` GPU block (research.md
                                      #   §1). No other service touched.

tests/unit/
└── test_docker_compose_provisioning.py   # EXTENDED — new assertions:
                                      #   `ollama` has a GPU device
                                      #   reservation with driver `nvidia`
                                      #   and capability `gpu`; `app`, `db`,
                                      #   `db-test`, and `ollama-init` have
                                      #   no `deploy`/GPU device block.

README.md                            # EDITED — "Local Ollama backend"
                                      #   bullet list updated to describe
                                      #   GPU as the new inline default
                                      #   (was "no GPU passthrough by
                                      #   default"), plus host requirements
                                      #   and the manual CPU-fallback edit;
                                      #   "Known limitations" bullet updated
                                      #   to match.
```

No `src/albercik_chatbot/` changes. No new Alembic migration. No new Docker
image or Compose service.

**Structure Decision**: Single existing backend project, unchanged layout.
This feature touches exactly one existing infrastructure file
(`docker-compose.yml`), extends one existing test file, and updates existing
documentation — no new top-level module, no new service process, no new
project structure of any kind.

## Complexity Tracking

*No entries — Constitution Check reported no violations requiring
justification.*
