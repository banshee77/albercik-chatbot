# Feature Specification: Ollama GPU Acceleration

**Feature Branch**: `[003-ollama-gpu-acceleration]`

**Created**: 2026-08-18

**Status**: Draft

**Input**: User description: "Add NVIDIA GPU acceleration for the existing Ollama Docker Compose service. Create this as a new small feature. Goal: Allow the existing Ollama service to use an NVIDIA GPU when the application is run through Docker Compose on a compatible host. Requirements: Only the ollama service receives GPU access; FastAPI, PostgreSQL, ollama-init and the local embedding service remain CPU-only; use Docker Compose NVIDIA GPU passthrough; target development environment includes WSL2/Linux with NVIDIA Container Toolkit; current test machine has an NVIDIA RTX 3070 with 8 GB VRAM; preserve qwen3:4b as the default Ollama model; keep OLLAMA_MODEL configurable; do not expose port 11434 publicly; keep ollama-init independent of GPU access; automatic model provisioning and persistent Ollama volume behavior must remain unchanged; application behavior must remain identical whether Ollama runs on CPU or GPU; do not add CUDA-specific logic to Python application code; do not add GPU detection to domain/application code; do not add Kubernetes, GPU scheduling, vLLM, or another model server. Verification: nvidia-smi works on the host; Ollama container receives NVIDIA GPU access; a real qwen3:4b inference uses GPU/VRAM; docker compose config remains valid; existing automated test suite remains unchanged and must not require a GPU; document CPU fallback / host requirements accurately. Security: GPU support must not change API exposure or existing security controls."

## Clarifications

### Session 2026-08-18

- Q: When a host does not have a working NVIDIA GPU/driver/Container Toolkit, must `docker compose up` still succeed and run the `ollama` service CPU-only automatically, or is it acceptable that the operator must manually edit the compose file (e.g., comment out the GPU device block) to run on such a host? → A: Manual edit required — the GPU device reservation is added directly and permanently to the `ollama` service in the single `docker-compose.yml`, making GPU the built-in default. On a host without GPU support, `docker compose up` fails to start `ollama` until the operator comments out or removes that block. No separate override file or Compose profile is introduced.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - GPU-Accelerated Local Inference on a Compatible Host (Priority: P1)

An operator running the chatbot stack on a machine with a supported NVIDIA GPU (e.g., the RTX 3070 development/test machine) starts the stack with `docker compose up`. The local LLM (Ollama) service automatically uses that GPU for inference, so locally-generated chatbot answers are produced with GPU-accelerated performance instead of CPU-only speed, with no extra manual steps beyond having the host correctly set up for GPU use.

**Why this priority**: This is the entire point of the feature — without it, there is no user-visible value at all. Everything else in this feature exists to make this happen safely and without side effects.

**Independent Test**: On a host with `nvidia-smi` working and NVIDIA Container Toolkit installed, run `docker compose up`, send a chatbot request that triggers a real local-model inference, and confirm via host GPU monitoring (`nvidia-smi`) that the Ollama process is actively using GPU compute and VRAM during that request.

**Acceptance Scenarios**:

1. **Given** a host with a working NVIDIA GPU, driver, and NVIDIA Container Toolkit, **When** the operator runs `docker compose up`, **Then** the Ollama container starts successfully and has access to the host's NVIDIA GPU.
2. **Given** the stack is running on such a host with the default configuration, **When** a request causes the local model (`qwen3:4b`) to run inference, **Then** GPU utilization and VRAM usage for the Ollama process are observable on the host via `nvidia-smi` during that inference.

---

### User Story 2 - GPU Access Isolated to the Ollama Service (Priority: P2)

An operator inspects the running stack and confirms that GPU access was added only to the Ollama service. The FastAPI application, PostgreSQL (primary and test databases), the one-shot model-provisioning step (`ollama-init`), and the in-process embedding functionality never declare, request, or receive any GPU device reservation of their own — CPU-only, with no new resource requirements and no new dependency on GPU drivers for those services specifically. (On a GPU-equipped host, all of them start and behave exactly as before; on a non-GPU host, `ollama-init` and `app` are still gated behind `ollama` becoming healthy — an existing dependency from feature 002 — so they do not become ready until the operator performs the documented manual CPU-only edit, but this is `ollama` failing to start, not GPU access spreading to those other services.)

**Why this priority**: GPU passthrough that leaked to other services would be a correctness and security regression (unnecessary privilege/resource grants). This must hold before the feature can be considered safe to ship.

**Independent Test**: With the GPU configuration in place, inspect the Compose configuration and confirm no service other than `ollama` has any GPU device reservation. On a GPU-equipped host, confirm `db`, `db-test`, `app`, and `ollama-init` start and pass their existing health checks identically to before this feature.

**Acceptance Scenarios**:

1. **Given** the updated Compose configuration, **When** it is inspected, **Then** only the `ollama` service declares GPU device access; no other service does.
2. **Given** the stack is started on a GPU-equipped host, **When** `db`, `db-test`, `app`, and `ollama-init` start, **Then** they behave exactly as they did before this feature — no new startup requirements, no new resource grants for those services.

---

### User Story 3 - Model Configuration and Provisioning Stay Unchanged (Priority: P3)

An operator relies on the existing automatic model-provisioning behavior: the default model `qwen3:4b` is pulled automatically on first start, `OLLAMA_MODEL` can be overridden to use a different model, and previously-pulled models persist across restarts via the existing Ollama volume. After GPU acceleration is added, all of this continues to work exactly as before, whether Ollama ends up running on GPU or CPU.

**Why this priority**: This protects an already-working feature (feature 002's automatic provisioning) from regressing while this feature is added. It's lower priority than P1/P2 only because it is fundamentally a "don't break this" requirement rather than new value, but it is still required for the feature to be safe to ship.

**Independent Test**: Start the stack fresh (no pre-existing Ollama volume) on a GPU-equipped host with `OLLAMA_MODEL` unset, and confirm `qwen3:4b` is pulled automatically before the application becomes available. Separately, set `OLLAMA_MODEL` to a different model and confirm that model is pulled instead, on the same GPU-equipped host.

**Acceptance Scenarios**:

1. **Given** a fresh environment with no prior Ollama volume and `OLLAMA_MODEL` unset, **When** the stack starts on a GPU-equipped host, **Then** `qwen3:4b` is pulled automatically and the application becomes available only after provisioning completes successfully.
2. **Given** `OLLAMA_MODEL` set to a different valid model name, **When** the stack starts on a GPU-equipped host, **Then** that model is pulled instead of `qwen3:4b`, using the same automatic provisioning mechanism as before.
3. **Given** a model already present in the persistent Ollama volume from a previous run, **When** the stack is restarted, **Then** provisioning completes without re-downloading the model, identically to pre-GPU behavior.

### Edge Cases

- What happens when the host does not have a working NVIDIA driver / NVIDIA Container Toolkit? Because the GPU device reservation is declared directly and permanently in the single `docker-compose.yml`, `docker compose up` for the `ollama` service fails to start on such a host until the operator manually comments out or removes that reservation block; this manual step and its exact effect must be clearly documented.
- What happens to the application's answers/functional output when Ollama runs on GPU vs. CPU? They must be identical — GPU acceleration must only affect inference speed, never the functional behavior or content of chatbot responses.
- What happens if `OLLAMA_MODEL` is overridden to a model whose resource needs exceed the GPU's VRAM? Out of scope for this feature to solve (existing Ollama behavior applies); the documentation should note that the 8 GB VRAM test target was validated against the default `qwen3:4b` model.
- What happens in CI or on any developer machine without a GPU? `docker compose config` validation and the existing automated test suite must continue to succeed without a GPU, an NVIDIA driver, or the NVIDIA Container Toolkit present, since neither invokes `docker compose up`.
- What happens to the rest of the stack (`app`, `ollama-init`) if `docker compose up` is run unmodified on a non-GPU host? Because `ollama-init` already depends on `ollama` being healthy, and `app` already depends on `ollama-init` completing successfully, the `ollama` container failing to start on a non-GPU host cascades to block `ollama-init` and `app` too — the whole default stack, not just `ollama`, stays unavailable until the operator performs the documented manual edit. `ollama-init` waits for `ollama` to become healthy regardless of the configured `LLM_PROVIDER` value, so switching `LLM_PROVIDER` away from `ollama` does not avoid this. This is an existing dependency chain from feature 002, not new coupling introduced by this feature.
- What happens to network exposure of Ollama after this change? Port 11434 must remain unpublished/unreachable from outside the Compose network, exactly as before.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Ollama service definition MUST request NVIDIA GPU device access via Docker Compose's GPU passthrough mechanism.
- **FR-002**: No service other than `ollama` (specifically: `app`/FastAPI, `db`, `db-test`, and `ollama-init`) MUST declare or receive GPU device access.
- **FR-003**: The in-process embedding functionality (which runs inside the `app` service, not as a separate container) MUST remain CPU-only and MUST NOT be granted or require GPU access.
- **FR-004**: Ollama's network exposure MUST remain unchanged: port 11434 MUST NOT be published to the host machine or any public interface.
- **FR-005**: The default value used for the Ollama model MUST remain `qwen3:4b` when `OLLAMA_MODEL` is not set.
- **FR-006**: `OLLAMA_MODEL` MUST remain overridable via environment variable, and the override MUST apply identically to model provisioning regardless of whether Ollama is running on GPU or CPU.
- **FR-007**: The `ollama-init` provisioning service's behavior — waiting for `ollama` to be healthy, pulling the configured model once, and gating the application's startup on successful completion — MUST remain unchanged and MUST NOT require, request, or depend on GPU access.
- **FR-008**: The persistent Ollama data volume (name, mount path, and persistence-across-restart behavior) MUST remain unchanged.
- **FR-009**: `docker compose config` MUST validate the Compose configuration successfully after GPU support is added, with or without a GPU present on the validating host.
- **FR-010**: This feature MUST NOT require changes to Python application source code (API layer, application/service layer, RAG/domain logic, or LLM/embedding provider-boundary code) to implement GPU support.
- **FR-011**: The functional behavior of the chatbot (API responses and RAG pipeline output for a given input) MUST be identical regardless of whether the Ollama container is using a GPU or running CPU-only; GPU acceleration MUST affect only inference performance.
- **FR-012**: Project documentation MUST describe the host requirements for GPU acceleration (NVIDIA GPU, NVIDIA driver, NVIDIA Container Toolkit) and MUST describe what happens / what to do when those requirements are not met (CPU-only operation).
- **FR-013**: The existing automated test suite MUST continue to pass unchanged on a host without a GPU, without an NVIDIA driver, and without the NVIDIA Container Toolkit installed.
- **FR-014**: This feature MUST NOT introduce Kubernetes, GPU scheduling infrastructure, vLLM, or any additional model-serving component; Ollama remains the sole local model server.
- **FR-015**: This feature MUST NOT change API exposure or any existing security control (authentication, rate limiting, request/response validation, etc.) beyond granting the `ollama` container access to the host GPU device.
- **FR-016**: The GPU device reservation MUST be declared directly in the single `docker-compose.yml` (not via a separate override file or Compose profile), making GPU access the built-in default for the `ollama` service rather than an opt-in add-on.
- **FR-017**: On a host without a working NVIDIA GPU/driver/Container Toolkit, `docker compose up` MAY fail to start the `ollama` service; running CPU-only on such a host MUST be achievable only via a documented manual edit (commenting out or removing the GPU device reservation block), not automatic detection or fallback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a host with a supported NVIDIA GPU and NVIDIA Container Toolkit installed, starting the stack with a single `docker compose up` command results in the local LLM service actively using the GPU during inference, confirmed via host GPU monitoring.
- **SC-002**: On a GPU-equipped host, 100% of non-Ollama services (database, application, model-provisioning step) start and behave with no observable difference — same startup sequencing, same health checks, same configuration surface — before and after this feature is added.
- **SC-003**: 100% of the existing automated test suite passes unchanged on a machine that has no GPU, no NVIDIA driver, and no NVIDIA Container Toolkit.
- **SC-004**: `docker compose config` succeeds (exit code 0, valid merged configuration) both on a GPU-equipped host and on a host without GPU support.
- **SC-005**: No new network port or externally reachable endpoint exists after this feature is added; Ollama remains reachable only from within the internal Compose network.
- **SC-006**: An operator can determine, from project documentation alone (no trial and error), whether their host qualifies for GPU acceleration and exactly what to do if it does not.
- **SC-007**: For a given chatbot question, the generated answer content is the same whether the underlying Ollama instance served that request on GPU or on CPU.

## Assumptions

- "Compatible host" means a host where `nvidia-smi` already works and the NVIDIA Container Toolkit is already installed and configured for Docker — this feature wires Docker Compose to use that existing capability; it does not install drivers, the Container Toolkit, or otherwise configure the host operating system.
- On a host that does not meet those GPU prerequisites, running Ollama requires a documented manual adjustment by the operator: commenting out or removing the GPU device reservation block from the `ollama` service in `docker-compose.yml` (Clarifications, 2026-08-18). This feature intentionally does not add automatic GPU-presence detection or fallback logic to Compose or application code, consistent with the requirement not to add GPU detection to domain/application code, and does not introduce a separate override file or Compose profile for this purpose.
- "Local embedding service" in the source requirements refers to the in-process embedding functionality that already runs inside the `app` service (there is no separate embedding container in the current architecture); it is unaffected by this feature and remains CPU-only by virtue of not being touched.
- Verifying real `qwen3:4b` GPU inference (via `nvidia-smi` VRAM/utilization observation) is a manual, host-level verification step for this feature, not an addition to the automated test suite — the automated suite must keep working without a GPU.
- The RTX 3070 (8 GB VRAM) machine is the manual verification target for this feature; `qwen3:4b` is already known to fit comfortably within that VRAM budget, so no model-sizing decision is introduced by this feature.
