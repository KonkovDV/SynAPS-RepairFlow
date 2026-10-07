"""The notary mutation run is configured, and it is not a score."""

from __future__ import annotations

import tomllib
from pathlib import Path

_TARGETS = (
    "src/repairflow/checker.py",
    "src/repairflow/capacity.py",
    "src/repairflow/ledger.py",
    "src/repairflow/lane_setup.py",
)


def test_mutmut_targets_are_the_notary_modules() -> None:
    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    mutmut = payload["tool"]["mutmut"]
    assert mutmut["source_paths"] == ["src/repairflow"]
    assert mutmut["only_mutate"] == list(_TARGETS)
    assert "src" not in mutmut["also_copy"]
    assert "src/repairflow" not in mutmut["also_copy"]
    assert "tools" in mutmut["also_copy"]
    assert "docs" in mutmut["also_copy"]
    assert mutmut["pytest_add_cli_args_test_selection"] == ["-m", "not slow", "tests"]
    for path in _TARGETS:
        text = Path(path).read_text(encoding="utf-8")
        assert "pragma: no mutate" not in text


def test_mutation_job_runs_on_linux_outside_pull_requests() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    job = text.split("  mutation:", 1)[1]
    assert "runs-on: ubuntu-latest" in job
    assert "timeout-minutes: 360" in job
    assert "mutmut==3.8.0" in job
    assert "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'" in job
    assert "pull_request" not in job.split("steps:", 1)[0]
