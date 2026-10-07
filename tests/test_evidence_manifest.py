"""The evidence manifest names a commit that was actually checked."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from repairflow.attestation import render_attestation_markdown
from repairflow.planner import plan
from repairflow.synthetic import synthesize
from repairflow.versions import SYNAPS_COMMIT, SYNAPS_REPO

_MANIFEST = Path("docs/evidence-manifest.json")


def test_evidence_manifest_matches_the_pinned_kernel() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema"] == "repairflow.evidence_manifest.v1"
    assert payload["synaps_commit"] == SYNAPS_COMMIT
    assert payload["synaps_commit"] == "f939727cd9369fd9b36438bfac7198f0c39c6d3b"
    lock = Path("requirements-lock.txt").read_text(encoding="utf-8")
    project = Path("pyproject.toml").read_text(encoding="utf-8")
    versions = Path("src/repairflow/versions.py").read_text(encoding="utf-8")
    assert SYNAPS_COMMIT in lock
    assert SYNAPS_COMMIT in project
    assert SYNAPS_COMMIT in versions
    # The manifest lands in a later docs commit than the one it names.
    assert payload["stale"] is True
    assert payload["attests_commit"] == "fc14c76b71ae3e13626c687b8974bd4061e51ae8"
    assert payload["ci_run_id"] == "37690925608"
    assert payload["synaps_repo"] == SYNAPS_REPO
    assert len(SYNAPS_COMMIT) == 40
    assert payload["ci_result"] == "success"
    assert payload["ci_includes_test_slow"] is True
    assert payload["claim_level"] == "experiment"
    assert payload["trl"] == 4
    assert len(payload["attests_commit"]) == 40
    assert payload["ci_run_url"].endswith("/" + payload["ci_run_id"])
    text = _MANIFEST.read_text(encoding="utf-8")
    assert "production readiness" in payload["not_claimed"]
    assert "safety certification" in payload["not_claimed"]
    assert "heuristic optimality" in payload["not_claimed"]
    assert "CP-MUS" in text
    assert "внедрено" not in text


def test_fault_campaign_denominator_is_committed() -> None:
    payload = json.loads(Path("docs/fault-campaign.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "repairflow.fault_campaign.v2"
    assert payload["checked"] >= 10_000
    assert payload["false_accept"] == 0
    assert payload["must_reject"] + payload["may_pass"] == payload["checked"]
    assert isinstance(payload["false_reject"], int)
    assert payload["false_reject_reason"]
    assert payload["oracle"] == "tests.oracle_minutes"
    assert payload["per_baseline"] == 56
    assert payload["seeds"] == list(range(1, 31))
    assert payload["presets"] == ["tiny", "repair-site-mvp"]
    assert payload["solvers"] == ["GREED", "EDD", "ATC"]
    assert {"duplicate", "spare_overuse", "rotable_clash", "shift_frozen", "setup_zero"} <= set(
        payload["by_mutator"]
    )
    for counts in payload["by_mutator"].values():
        assert counts["false_accept"] == 0
        assert counts["checked"] >= 1
    assert payload["synaps_commit"] == SYNAPS_COMMIT
    assert payload["claim_level"] == "experiment"
    assert payload["data_provenance"] == "synthetic"
    assert len(payload["input_hash"]) == 64


def _lf_sha256(path: Path) -> str:
    """Hash the LF form. Git stores these evidence files with LF endings."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def test_readme_evidence_table_is_generated() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    benchmark_path = Path("benchmark/results/benchmark.json")
    digest = _lf_sha256(benchmark_path)
    sums = Path("benchmark/results/SHA256SUMS").read_text(encoding="utf-8")
    assert sums.strip() == f"{digest}  benchmark.json"
    campaign = json.loads(Path("docs/fault-campaign.json").read_text(encoding="utf-8"))
    rendered = render_attestation_markdown(manifest, benchmark_sha256=digest, campaign=campaign)
    readme = Path("README.md").read_text(encoding="utf-8")
    begin = "<!-- evidence:begin -->"
    end = "<!-- evidence:end -->"
    assert begin in readme and end in readme
    block = readme.split(begin, 1)[1].split(end, 1)[0].strip()
    assert block == rendered.strip()


def test_committed_benchmark_rows_carry_hashes() -> None:
    payload = json.loads(Path("benchmark/results/benchmark.json").read_text(encoding="utf-8"))
    assert payload["synaps_commit"] == SYNAPS_COMMIT
    assert payload["claim_level"] == "experiment"
    assert payload["data_provenance"] == "synthetic"
    rows = payload["rows"]
    assert len(rows) >= 12
    for row in rows:
        assert len(row["input_hash"]) == 64
        assert len(row["config_hash"]) == 64
        assert len(row["result_hash"]) == 64
    tiny = next(
        row for row in rows if row["preset"] == "tiny" and row["seed"] == 1 and row["solver"] == "GREED"
    )
    fresh = plan(synthesize("tiny", seed=1), solver_config="GREED")
    # result_hash includes runtime_manifest, so it identifies the snapshot
    # machine. The schedule itself is what must match on every runner.
    objective = fresh.result.objective
    assert fresh.result.input_hash == tiny["input_hash"]
    assert fresh.result.status.value == tiny["status"]
    assert fresh.result.exit_code == tiny["exit_code"]
    assert fresh.result.verified_feasible is True
    assert fresh.result.verified_feasible == tiny["verified"]
    assert len(fresh.result.violations) == tiny["violations"]
    assert float(objective["makespan_minutes"]) == tiny["makespan_min"]
    assert float(objective["coverage"]) == tiny["coverage"]
