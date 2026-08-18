---

description: "Task list template for feature implementation"
---

# Tasks: Ollama GPU Acceleration

**Input**: Design documents from `/specs/003-ollama-gpu-acceleration/`

**Prerequisites**: plan.md, spec.md, research.md, quickstart.md (all present). No `data-model.md`/`contracts/` — this feature touches no data and exposes no interface (plan.md "Project Structure").

**Tests**: Included — spec FR-013/SC-003 require the automated suite to prove the GPU-scope shape without ever needing a real GPU, and the project constitution makes security/correctness-relevant test coverage NON-NEGOTIABLE (Principle XI). Both new tests extend the existing pure-PyYAML pattern in `tests/unit/test_docker_compose_provisioning.py` — no Docker daemon, no GPU, no `docker compose` CLI call.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P3). All three stories share a single blocking prerequisite (the actual GPU config edit), so it lives in a Foundational phase rather than being duplicated per story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Every task lists an exact file path

## Path Conventions

Single existing backend project (plan.md "Structure Decision": unchanged layout):

- Compose config: `docker-compose.yml` (repo root)
- Tests: `tests/unit/test_docker_compose_provisioning.py`
- Docs: `README.md` (repo root)
- Validation guide: `specs/003-ollama-gpu-acceleration/quickstart.md`

## Design Constraints Carried Into These Tasks

1. **Inline, single-file, always-on — no override file, no Compose profile**
   (spec FR-016, Clarifications 2026-08-18, research.md §4): the GPU device
   reservation lives directly in the `ollama` service block of the one
   existing `docker-compose.yml`. No new Compose file is created (T001).
2. **Scope stays limited to `ollama`** (spec FR-002/FR-003, research.md
   §3): `app`, `db`, `db-test`, and `ollama-init` are never touched by any
   task in this list — proven negatively by T005, not just by omission.
3. **Zero Python source changes** (spec FR-010, plan.md Summary): no task
   in this list touches `src/albercik_chatbot/`. `OllamaLLMProvider` and
   the rest of the application are already fully agnostic to whether the
   Ollama process behind the HTTP boundary uses a GPU.
4. **No GPU-presence detection anywhere** (spec FR-017, research.md §4): on
   a non-GPU host, `docker compose up` is expected to fail to start
   `ollama` until a human comments out the block — no task adds
   auto-detection or fallback logic to Compose or application code.
5. **`count: 1`, `driver: nvidia`, `capabilities: [gpu]`** is the exact
   device-reservation shape (research.md §1–§2) — T001 and its test (T002)
   must agree on this shape.

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: The one config change every user story depends on, either
directly (US1) or to verify its absence/unchanged-ness elsewhere (US2, US3)

**⚠️ CRITICAL**: No user story task can be verified until this phase is complete

- [ ] T001 Add an NVIDIA GPU device reservation to the `ollama` service only in `docker-compose.yml`: a `deploy.resources.reservations.devices` block with `driver: nvidia`, `count: 1`, `capabilities: [gpu]`, placed on `ollama` and no other service (research.md §1–§3)

**Checkpoint**: `docker-compose.yml` requests GPU access for `ollama` only; no other service definition changed. Ready for story-level verification.

---

## Phase 2: User Story 1 - GPU-Accelerated Local Inference on a Compatible Host (Priority: P1) 🎯 MVP

**Goal**: On a compatible host, `docker compose up` gives the `ollama` service real NVIDIA GPU access, and a real local-model inference visibly uses that GPU.

**Independent Test**: On a host with `nvidia-smi` working and NVIDIA Container Toolkit installed, run `docker compose up`, send a chatbot request, and confirm via `nvidia-smi` that the `ollama` process uses GPU compute/VRAM during that request (quickstart.md Scenario 1).

### Tests for User Story 1 ⚠️ write first, confirm it fails before T001, passes after

- [ ] T002 [P] [US1] Add a test asserting `services.ollama.deploy.resources.reservations.devices` exists with `driver: nvidia` and `gpu` in `capabilities`, in `tests/unit/test_docker_compose_provisioning.py` (depends on T001)

### Implementation for User Story 1

- [ ] T003 [P] [US1] Update `README.md`: rewrite the "Local Ollama backend" bullet that currently says GPU passthrough is *not* configured by default — describe the new inline default, the host requirements (NVIDIA driver, NVIDIA Container Toolkit, `nvidia-smi` working), and the manual edit needed to disable it on a non-GPU host; also update the matching "Known limitations" bullet ("No GPU passthrough configured for the local Ollama backend by default") so it no longer contradicts the new behavior (spec FR-012/SC-006, research.md §6) (depends on T001)
- [ ] T004 [US1] Manually execute quickstart.md Scenario 1 on a GPU-equipped host (the RTX 3070/8 GB VRAM verification target) and confirm `nvidia-smi` shows GPU utilization/VRAM usage by the `ollama` process during a real `qwen3:4b` chat request, per `specs/003-ollama-gpu-acceleration/quickstart.md` (spec SC-001) (depends on T001, T002)

**Checkpoint**: User Story 1 is independently verifiable — GPU acceleration works end-to-end on a compatible host, and the automated test proves the config shape without needing a GPU.

---

## Phase 3: User Story 2 - GPU Access Isolated to the Ollama Service (Priority: P2)

**Goal**: Confirm no service other than `ollama` ever declares or receives GPU device access, and that `db`, `db-test`, `app`, and `ollama-init` are otherwise unaffected on a GPU-equipped host.

**Independent Test**: Inspect the Compose configuration and confirm only `ollama` has a GPU device reservation; confirm the other four services start and pass their existing health checks identically to before this feature (quickstart.md Scenario 2).

### Tests for User Story 2 ⚠️ write first, confirm it fails before T001, passes after

- [ ] T005 [US2] Add a test asserting `services.app`, `services.db`, `services["db-test"]`, and `services["ollama-init"]` each have no `deploy` key (or no GPU device reservation within it), in `tests/unit/test_docker_compose_provisioning.py` (depends on T001, T002 — same file, sequential)

### Implementation for User Story 2

- [ ] T006 [P] [US2] Manually execute quickstart.md Scenario 2: run `docker compose config` and confirm programmatically that only `ollama` carries a `deploy` block, per `specs/003-ollama-gpu-acceleration/quickstart.md` (spec FR-002/FR-003) (depends on T001)

**Checkpoint**: User Stories 1–2 both independently verifiable — GPU access is proven both present on `ollama` and absent everywhere else.

---

## Phase 4: User Story 3 - Model Configuration and Provisioning Stay Unchanged (Priority: P3)

**Goal**: Confirm the existing automatic model-provisioning behavior from feature 002 (default `qwen3:4b`, `OLLAMA_MODEL` override, volume persistence, `app` gated on `ollama-init` completion) is completely unaffected by adding GPU access.

**Independent Test**: Start the stack fresh (no pre-existing volume) on a GPU-equipped host with `OLLAMA_MODEL` unset, confirm `qwen3:4b` provisions automatically; repeat with an override (quickstart.md Scenario 3).

### Implementation for User Story 3

- [ ] T007 [US3] Manually execute quickstart.md Scenario 3 on a GPU-equipped host: fresh-volume default-model provisioning, `OLLAMA_MODEL` override provisioning, and idempotent restart (no re-download), per `specs/003-ollama-gpu-acceleration/quickstart.md` (spec FR-005–FR-008) (depends on T001)

**Checkpoint**: All three user stories independently verifiable — this story requires no new code, only confirmation that feature 002's existing behavior and its existing tests (`tests/unit/test_docker_compose_provisioning.py`'s pre-existing `ollama-init` assertions) still hold unchanged.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verification that spans all three stories rather than belonging to one

- [ ] T008 [P] Manually execute quickstart.md Scenario 4: confirm `docker compose config` still succeeds on a host without a GPU, and confirm running CPU-only requires only the documented manual edit (commenting out the `ollama` device block), per `specs/003-ollama-gpu-acceleration/quickstart.md` (spec FR-009/FR-017/SC-004) (depends on T001)
- [ ] T009 Run `uv run pytest` (full suite, including the two new assertions from T002/T005) on a machine without a GPU and confirm 100% pass with no GPU required (spec FR-013/SC-003) (depends on T002, T005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — can start immediately. BLOCKS every user story task (all of them either read or verify the config it introduces).
- **User Story 1 (Phase 2)**: Depends on Phase 1 only.
- **User Story 2 (Phase 3)**: Depends on Phase 1; T005 additionally depends on T002 (same test file, sequential edit — not a story-level dependency, a file-level one).
- **User Story 3 (Phase 4)**: Depends on Phase 1 only — independent of US1/US2's tasks.
- **Polish (Phase 5)**: T008 depends on Phase 1 only; T009 depends on both test tasks (T002, T005) existing.

### Within Each User Story

- Tests before/alongside the verification they cover (US1: T002 before T004; US2: T005 before T006 is not required, but T005 must follow T002 for file-edit ordering)
- Doc updates (T003) can proceed in parallel with test edits (T002) — different files
- Manual quickstart verification tasks (T004, T006, T007, T008) are the "independent test" proof for each story and require nothing beyond T001 plus (for T004) T002

### Parallel Opportunities

- T002 and T003 (different files: test file vs. `README.md`) can run in parallel once T001 is done
- T006, T007, and T008 (all manual verification against already-built config, different scenarios) can run in parallel once T001 is done
- T005 cannot run in parallel with T002 (same file)
- T009 must wait for both T002 and T005

---

## Parallel Example: After Foundational (T001)

```bash
# Launch in parallel:
Task: "Add GPU-reservation test for ollama in tests/unit/test_docker_compose_provisioning.py"   # T002
Task: "Update README.md GPU documentation"                                                        # T003
```

```bash
# Later, once T001/T002 exist, launch in parallel:
Task: "Manually verify quickstart.md Scenario 2 (isolation)"     # T006
Task: "Manually verify quickstart.md Scenario 3 (provisioning)"  # T007
Task: "Manually verify quickstart.md Scenario 4 (CPU fallback)"  # T008
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Foundational (T001) — the actual GPU config change
2. Complete Phase 2: User Story 1 (T002–T004) — proves GPU acceleration works and is documented
3. **STOP and VALIDATE**: run quickstart.md Scenario 1 on the RTX 3070 test machine
4. This alone already satisfies the feature's stated goal; US2/US3 are safety/regression proofs, not additional user value

### Incremental Delivery

1. Foundational (T001) → config exists
2. User Story 1 (T002–T004) → GPU acceleration proven and documented (MVP)
3. User Story 2 (T005–T006) → isolation proven
4. User Story 3 (T007) → no regression to existing provisioning behavior proven
5. Polish (T008–T009) → CPU-fallback path and full automated suite confirmed clean

### Total Scope

9 tasks, 1 file with a real edit (`docker-compose.yml`), 1 test file extended with 2 assertions, 1 doc file updated in 2 places, 4 manual verification passes against `quickstart.md`. No new service, no new dependency, no `src/` change.
