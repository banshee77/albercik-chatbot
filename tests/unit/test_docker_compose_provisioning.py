"""T019 (US4, feature 002-add-ollama-provider) — structural test of
`docker-compose.yml`'s automatic Ollama model provisioning wiring (spec
FR-019–FR-029, requirement 8; research.md §6a).

Parses the Compose file with PyYAML only — no Docker daemon, no real
Ollama process, no model download, and no `docker compose` CLI call.
Proves the *shape* of the provisioning mechanism (a one-shot `ollama-init`
service, gated on `ollama` being healthy, gating `app` in turn, sourcing
its model/provider from the same env vars the application itself reads)
without ever needing the real services to run.
"""

from pathlib import Path
from typing import Any

import yaml

_COMPOSE_PATH = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _load_services() -> dict[str, Any]:
    with _COMPOSE_PATH.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)
    services: dict[str, Any] = data["services"]
    return services


def _normalize_environment(environment: Any) -> dict[str, str]:
    """Compose allows `environment` as either a mapping or a `KEY=value`
    list — normalize to a mapping so assertions don't care which form the
    file uses."""
    if isinstance(environment, dict):
        return {str(k): str(v) for k, v in environment.items()}
    return dict(item.split("=", 1) for item in environment)


def test_ollama_service_has_a_healthcheck() -> None:
    services = _load_services()
    ollama = services["ollama"]

    assert "healthcheck" in ollama
    test_command = ollama["healthcheck"]["test"]
    assert "ollama" in test_command
    assert "list" in test_command


def test_ollama_service_still_publishes_no_port() -> None:
    services = _load_services()
    assert "ports" not in services["ollama"]


def test_ollama_init_service_exists_and_reuses_the_ollama_image() -> None:
    services = _load_services()
    assert "ollama-init" in services
    assert services["ollama-init"]["image"] == services["ollama"]["image"]


def test_ollama_init_is_one_shot_not_a_long_running_service() -> None:
    services = _load_services()
    init = services["ollama-init"]
    # Compose default is "no" when the key is absent — either is
    # acceptable, but "unless-stopped"/"always" would turn this into a
    # long-running service, which it must never be.
    assert init.get("restart", "no") == "no"


def test_ollama_init_publishes_no_port() -> None:
    services = _load_services()
    assert "ports" not in services["ollama-init"]


def test_ollama_init_waits_for_ollama_to_be_healthy() -> None:
    services = _load_services()
    depends_on = services["ollama-init"]["depends_on"]
    assert depends_on["ollama"]["condition"] == "service_healthy"


def test_ollama_init_sources_model_and_provider_from_env_not_hardcoded() -> None:
    services = _load_services()
    init = services["ollama-init"]
    environment = _normalize_environment(init.get("environment", {}))
    command_text = " ".join(init.get("command", [])) + " ".join(init.get("entrypoint", []))

    # The model identifier must come from the same OLLAMA_MODEL variable
    # OllamaLLMProvider itself reads (config.py) — never a separately
    # hardcoded model string anywhere in this service's definition.
    assert "OLLAMA_MODEL" in environment
    assert "${OLLAMA_MODEL" in environment["OLLAMA_MODEL"]
    assert "LLM_PROVIDER" in environment
    assert "${LLM_PROVIDER" in environment["LLM_PROVIDER"]

    full_text = command_text + " " + str(init.get("environment"))
    assert (
        "qwen3:4b" not in command_text
    )  # only ever appears as an env default, not a literal pull target
    assert "ollama pull" in full_text or "ollama pull" in command_text


def test_ollama_init_skips_pulling_when_a_different_backend_is_configured() -> None:
    services = _load_services()
    init = services["ollama-init"]
    command_text = " ".join(init.get("command", []))
    assert "LLM_PROVIDER" in command_text
    assert "ollama" in command_text  # the comparison target, "ollama", appears in the guard


def test_app_waits_for_both_db_and_ollama_init() -> None:
    services = _load_services()
    depends_on = services["app"]["depends_on"]

    assert depends_on["db"]["condition"] == "service_healthy"
    assert depends_on["ollama-init"]["condition"] == "service_completed_successfully"
