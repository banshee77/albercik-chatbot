# Quickstart: Ollama GPU Acceleration

Validates this feature end-to-end against `spec.md`'s acceptance scenarios
and the project's verification requirements. Assumes the base
`001-albertos-rag-chatbot` and `002-add-ollama-provider` quickstarts have
already been completed at least once (database migrated, an Administrator
account exists, the default `LLM_PROVIDER=ollama` stack already works
CPU-only).

## Prerequisites

**For the GPU scenarios (1–3 below)**:
- A host with a supported NVIDIA GPU, an installed NVIDIA driver, and the
  NVIDIA Container Toolkit configured for Docker (WSL2 or native Linux).
  Verify with `nvidia-smi` on the host **before** touching Docker — if this
  doesn't show your GPU, fix that first; nothing in this feature installs
  drivers or the Container Toolkit for you (spec Assumptions).
- The manual verification target used to validate this feature: an NVIDIA
  RTX 3070, 8 GB VRAM.

**For the CPU-only scenario (4 below) and the automated test suite**:
- No GPU, driver, or NVIDIA Container Toolkit required at all.

**Stale cached image**: if your locally cached `ollama/ollama:latest`
predates support for the configured model, `ollama-init` fails with
something like `pull model manifest: 412: ... requires a newer version of
Ollama`. Fix: `docker pull ollama/ollama:latest` (refreshes the tag), then
`docker compose up -d ollama --force-recreate` (recreates the container on
the refreshed image), then retry provisioning. This is an operational
recovery step only — the project does not add any automatic image-pulling
logic anywhere.

## Scenario 1 — GPU-accelerated inference on a compatible host (US1, SC-001)

```bash
nvidia-smi                    # confirm the host sees the GPU first
uv sync
docker compose up -d db
uv run alembic upgrade head
docker compose up -d          # ollama now requests GPU device access
docker compose ps ollama      # expect: running / healthy
```

**Expected**: `ollama` starts successfully (it would fail to start instead
if the GPU device reservation could not be satisfied). Confirm the GPU is
actually visible *inside* the container — not just requested — before
trusting anything downstream:

```bash
docker exec "$(docker compose ps -q ollama)" nvidia-smi -L
```

**Expected**: lists your GPU (e.g. `GPU 0: NVIDIA GeForce RTX 3070 ...`).
Don't proceed to claim GPU acceleration works if this step fails — it
means the device reservation wasn't actually satisfied by the runtime, and
the CPU-only fallback in Scenario 4 applies instead. Then, in a second
terminal, watch the GPU while triggering a real local-model inference:

```bash
watch -n1 nvidia-smi           # leave running in terminal 2
curl -s localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "What are Albertos support hours?"}'
```

**Expected**: while the request is in flight, `nvidia-smi` (terminal 2)
shows GPU utilization and VRAM usage attributable to the `ollama` process —
this is the manual proof for spec SC-001 / the "real qwen3:4b inference
uses GPU/VRAM" verification requirement. This is a host-level observation,
not an automated test (spec Assumptions).

## Scenario 2 — GPU access isolated to `ollama` only (US2, FR-002/FR-003)

```bash
docker compose config | python3 -c "
import sys, yaml
services = yaml.safe_load(sys.stdin)['services']
for name in ('app', 'db', 'db-test', 'ollama-init'):
    assert 'deploy' not in services[name], f'{name} unexpectedly has a deploy/GPU block'
assert 'deploy' in services['ollama'], 'ollama is missing its GPU device reservation'
print('OK: GPU access is isolated to the ollama service')
"
```

**Expected**: `OK: GPU access is isolated to the ollama service`. `db`,
`db-test`, `app`, and `ollama-init` all started in Scenario 1 exactly as
they did before this feature — same health checks, same startup order, no
new requirements.

## Scenario 3 — Model configuration/provisioning unaffected by GPU (US3)

```bash
docker compose down -v         # fresh state: no pre-existing ollama-data volume
docker compose up -d
docker compose logs ollama-init   # expect a real pull of qwen3:4b (default)
curl -s localhost:8000/health     # expect {"status": "ok"} only after provisioning completes

# now try an override
echo 'OLLAMA_MODEL=qwen3:8b' >> .env
docker compose up -d
docker compose logs ollama-init   # expect a pull of qwen3:8b instead
```

**Expected**: identical behavior to the pre-GPU feature-002 quickstart —
default model pulls automatically, override via `OLLAMA_MODEL` works, `app`
only becomes healthy after provisioning completes. Nothing about this
sequence changed by adding GPU acceleration (spec FR-005/FR-006/FR-007/
FR-008). Revert `.env` afterward if you don't want to keep the 8b override.

## Scenario 4 — CPU-only host / no GPU (edge case, FR-017, SC-004)

On a host **without** a working NVIDIA GPU/driver/Container Toolkit (or to
simulate one on a GPU host):

```bash
docker compose config          # MUST still succeed — exit code 0 (FR-009/SC-004)
docker compose up -d ollama    # EXPECTED TO FAIL to start ollama — no GPU available
```

To run CPU-only on such a host, comment out or delete the
`deploy.resources.reservations.devices` block under the `ollama` service in
`docker-compose.yml`, then:

```bash
docker compose up -d           # ollama, ollama-init, app all start CPU-only,
                                #   exactly like every host before this feature
```

**Expected**: `docker compose config` never fails regardless of GPU
presence (it's static validation only). Actually starting the GPU-reserved
`ollama` service without a GPU fails until the manual edit above is applied
— this is the intended, documented behavior (spec FR-017, Clarifications
2026-08-18), not a bug. Confirmed by simulating this on the RTX
3070 verification machine (temporarily removing the `deploy:` block):
`docker compose config` still succeeded, `ollama` started and became
healthy without any GPU device request, `nvidia-smi` was unavailable
inside that container (as expected for a CPU-only start), and the
persisted model in `ollama-data` remained present throughout — restoring
the `deploy:` block afterward brought GPU access back with no other
change required.

## Automated test suite (no GPU required)

```bash
uv run pytest tests/unit/test_docker_compose_provisioning.py -v
```

**Expected**: all tests pass on any machine, GPU or not — they only parse
`docker-compose.yml` with PyYAML (spec FR-013/SC-003). The full suite
(`uv run pytest`) is likewise unaffected and requires no GPU.
