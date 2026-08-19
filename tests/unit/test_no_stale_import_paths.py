"""Feature 008 (Shiruno Repository & Product Architecture) regression guard.

Verifies the `albercik_chatbot` -> `shiruno` package rename (research.md §1,
contracts/runtime-paths.md) doesn't silently regress: the renamed package
must import cleanly, and no runtime-relevant file may reintroduce the old
import path. Historical specs (001-007) are exempt — they legitimately
describe decisions made under the old name.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_THIS_FILE_RELATIVE_PATH = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()

_HISTORICAL_SPEC_RE = re.compile(r"^specs/00[1-7]-")


def test_shiruno_package_imports_cleanly() -> None:
    from shiruno.main import create_app

    assert callable(create_app)


def test_no_stale_albercik_chatbot_import_path_remains() -> None:
    tracked_files = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    offending: list[str] = []
    for relative_path in tracked_files:
        if _HISTORICAL_SPEC_RE.match(relative_path):
            continue
        # This file legitimately names the old import path in its own
        # docstring/test name to describe what it guards against — not a
        # stale reference to fix.
        if relative_path == _THIS_FILE_RELATIVE_PATH:
            continue
        if (
            not relative_path.endswith((".py", ".toml", ".ini", ".yml", ".yaml", ".cfg", ".sh"))
            and Path(relative_path).name != "Dockerfile"
        ):
            continue
        path = REPO_ROOT / relative_path
        if "albercik_chatbot" in path.read_text(encoding="utf-8", errors="ignore"):
            offending.append(relative_path)

    assert not offending, f"stale 'albercik_chatbot' import path found in: {offending}"
