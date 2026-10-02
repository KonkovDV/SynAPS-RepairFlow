"""The evidence manifest names a commit that was actually checked."""

from __future__ import annotations

import json
from pathlib import Path

from repairflow.planner import plan
from repairflow.synthetic import synthesize
from repairflow.versions import SYNAPS_COMMIT, SYNAPS_REPO

_MANIFEST = Path("docs/evidence-manifest.json")


def test_evidence_manifest_matches_the_pinned_kernel() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema"] == "repairflow.evidence_manifest.v1"
    assert payload["synaps_commit"] == SYNAPS_COMMIT
    assert payload["synaps_commit"] == "f939727cd9369fd9b36438bfac7198f0c39c6d3b"
    assert payload["attests_commit"] == "9ea5a200ebc4e469fd59a35539781db7c5c16898"
    assert payload["ci_run_id"] == "36987936535"
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
    assert payload["schema"] == "repairflow.fault_campaign.v1"
    assert payload["checked"] >= 10_000
    assert payload["false_accept"] == 0
    assert payload["synaps_commit"] == SYNAPS_COMMIT
    assert payload["claim_level"] == "experiment"
    assert payload["data_provenance"] == "synthetic"
    assert len(payload["input_hash"]) == 64


def test_committed_benchmark_rows_carry_hashes() -> None:
    payload = json.loads(Path("docs/benchmark-results.json").read_text(encoding="utf-8"))
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
    assert fresh.result.input_hash == tiny["input_hash"]
    assert fresh.result.result_hash == tiny["result_hash"]
    assert fresh.result.verified_feasible is True
