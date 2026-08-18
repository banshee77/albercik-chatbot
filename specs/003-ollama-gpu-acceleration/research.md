# Phase 0 Research: Ollama GPU Acceleration

No `NEEDS CLARIFICATION` markers remain in the spec or Technical Context —
the one open decision (inline single-file GPU reservation vs. an
opt-in override file) was already resolved in the `/speckit-clarify`
session (spec.md Clarifications, 2026-08-18: inline, single-file). The
research below documents the mechanism decisions needed to implement that
resolved scope.

## 1. GPU passthrough mechanism for Docker Compose

**Decision**: Use the Compose Spec's `deploy.resources.reservations.devices`
block on the `ollama` service:

```yaml
  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ollama-data:/root/.ollama
    healthcheck: # unchanged
```

**Rationale**: This is the mechanism the Docker Compose CLI (v2, the `docker
compose` used throughout this project) honors outside of Swarm mode for GPU
reservation — despite `deploy.*` historically being a Swarm-only key, the
Compose CLI specifically interprets `deploy.resources.reservations.devices`
for local GPU passthrough when the NVIDIA Container Toolkit has registered
the `nvidia` driver with the Docker daemon. It requires no change to
Docker's default runtime and no `docker run --gpus` flag equivalent outside
Compose — `docker compose up` alone is sufficient on a correctly configured
host. This satisfies spec FR-001 (request GPU access via Docker Compose's
GPU passthrough) directly, using Compose's own documented primitive rather
than a custom script or wrapper.

**Alternatives considered**:
- **`runtime: nvidia` service key**: The older mechanism, requiring the
  operator to first register `nvidia` as Docker's *default* runtime (or set
  it explicitly per-service via a now-deprecated key) in `daemon.json`. Two
  extra host-level configuration steps beyond installing the NVIDIA
  Container Toolkit, and `runtime:` support varies across Compose Spec
  validators. Rejected in favor of `deploy.resources.reservations.devices`,
  which is the mechanism NVIDIA's and Docker's own current documentation
  recommends for Compose.
- **`docker run --gpus all` outside Compose**: Would mean running Ollama
  outside the Compose-managed stack entirely, breaking the existing
  `ollama-init`/`app` dependency chain (`depends_on: condition:
  service_healthy` / `service_completed_successfully`) that feature 002
  already relies on. Rejected — out of scope and unnecessary; the
  `deploy.resources.reservations.devices` block works within Compose.

## 2. GPU count / device selection

**Decision**: `count: 1` (reserve one GPU), not `count: all` or explicit
`device_ids`.

**Rationale**: The documented target/verification host (RTX 3070, single
GPU) only has one GPU to reserve, and the spec sets no multi-GPU
requirement. `count: 1` is the simplest option that satisfies "the ollama
service receives GPU access" (spec FR-001) without introducing
multi-GPU-selection complexity nothing in the spec asks for (Principle
XIII — Simplicity for MVP).

**Alternatives considered**:
- **`count: all`**: Reserves every GPU on the host for the `ollama`
  container. Unnecessary for the single-GPU dev/test target and would
  silently change behavior on a future multi-GPU host without any spec
  requirement driving that. Rejected as speculative.
- **`device_ids: ["0"]`**: Pins to a specific GPU index. More fragile
  across hosts (index 0 isn't guaranteed to be the intended GPU on every
  machine) and adds a configuration knob nothing in the spec calls for.
  Rejected in favor of the simpler `count: 1`.

## 3. Scope isolation (only `ollama` gets the block)

**Decision**: The `deploy.resources.reservations.devices` block is added to
the `ollama` service definition only. `app`, `db`, `db-test`, and
`ollama-init` are not touched in any way.

**Rationale**: Directly satisfies spec FR-002/FR-003 and the Clarifications-
confirmed scope. `ollama-init` reuses the same `ollama/ollama` image as
`ollama` (feature 002) but is a one-shot CLI/model-pull step, not an
inference server — it has no use for GPU access and must not receive it
(spec FR-007). The in-process embedding functionality lives inside `app`
and was never a separate container to begin with (spec Assumptions), so
there is nothing to add a device block to there either.

## 4. CPU-only hosts and the existing `ollama-init` → `app` dependency chain

**Decision**: No compensating logic is added anywhere for hosts without a
GPU. Per the Clarifications session, `docker compose up` on such a host
will fail to start `ollama` (Docker Engine cannot satisfy the GPU device
reservation), which — via the *existing*, *unmodified* feature-002
dependency chain (`ollama-init` waits on `ollama: service_healthy`; `app`
waits on `ollama-init: service_completed_successfully`) — blocks the rest
of the default stack until the operator manually comments out or removes
the device block.

**Rationale**: This is the simplest option that satisfies "Do not add GPU
detection to domain/application code" and "do not add CUDA-specific logic
to Python application code" (spec constraints) — there is no runtime
detection anywhere, Compose-level or application-level. It also matches
this project's existing precedent (README, pre-feature): GPU passthrough
was already documented as something "an operator adds... themselves" when
wanted; this feature simply flips the default from off to on, while
keeping the mechanism (a device block an operator can add or remove by
hand) identical. The cascading block on `app`/`ollama-init` is pre-existing
behavior from feature 002 (they already depend on `ollama` being healthy)
— this feature does not add new coupling, it just changes what can prevent
`ollama` from becoming healthy in the first place.

**Alternatives considered**:
- **Compose override file** (`docker-compose.gpu.yml`, applied via a second
  `-f` flag): Would keep the base file always CPU-safe. Explicitly rejected
  during `/speckit-clarify` in favor of the simpler single-file inline
  approach (spec FR-016).
- **Compose profile** gating the GPU block: Same rejection — adds a second
  invocation shape (`--profile gpu`) for a "small feature" whose explicit
  goal is that GPU passthrough already exists and is on by default on a
  compatible host.

## 5. Test strategy

**Decision**: Extend the existing `tests/unit/test_docker_compose_provisioning.py`
(pure PyYAML parsing of `docker-compose.yml`, no Docker daemon, no GPU) with:
- An assertion that `services.ollama.deploy.resources.reservations.devices`
  exists and contains an entry with `driver: nvidia` and `gpu` in
  `capabilities`.
- Assertions that `services.app`, `services.db`, `services["db-test"]`, and
  `services["ollama-init"]` each have no `deploy` key (or, if present for
  an unrelated reason in the future, no GPU device reservation within it).

**Rationale**: Matches the project's existing pattern exactly (same file,
same `_load_services()` helper, same style as the feature-002 provisioning
tests already in that file) and satisfies spec FR-013/SC-003: the automated
suite proves the *shape* of the GPU configuration without ever needing a
real GPU, NVIDIA Container Toolkit, or `docker compose up` call. Real GPU
utilization (spec SC-001, "a real qwen3:4b inference uses GPU/VRAM") is
manually verified via `nvidia-smi` per the Assumptions section of the spec
— that verification is intentionally not automatable in CI and is not
attempted here.

**Alternatives considered**:
- **A `docker compose config` subprocess-based test**: Would additionally
  prove the merged config is syntactically valid (spec FR-009), but the
  project's existing convention for this file is pure YAML parsing with no
  subprocess/Docker-daemon dependency, and `docker compose config`'s
  validity is already exercised manually/in CI tooling outside pytest.
  Rejected to stay consistent with the established test file's zero-
  dependency style; `docker compose config` validation remains a
  documented manual/CI verification step (quickstart.md), not a pytest
  assertion.

## 6. Documentation updates required

**Decision**: Update two places in `README.md`:
1. The "Local Ollama backend" bullet that currently reads "GPU acceleration
   ... is supported by Ollama itself, but **no GPU passthrough is
   configured in `docker-compose.yml` by default**..." — replace with a
   description of the new inline default, host requirements (NVIDIA driver,
   NVIDIA Container Toolkit, `nvidia-smi` working), and the manual edit
   needed to disable it on a non-GPU host.
2. The "Known limitations" bullet "No GPU passthrough configured for the
   local Ollama backend by default" — remove or replace, since it is no
   longer accurate once this feature ships.

**Rationale**: Directly satisfies spec FR-012/SC-006 (documentation must
describe host requirements and CPU-fallback accurately) and keeps the two
existing GPU-related mentions in the README from contradicting the new
behavior.
