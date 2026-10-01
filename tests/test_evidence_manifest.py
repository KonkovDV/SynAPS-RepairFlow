"""The evidence manifest names a commit that was actually checked."""

from __future__ import annotations

import json
from pathlib import Path

from repairflow.versions import SYNAPS_COMMIT, SYNAPS_REPO

_MANIFEST = Path("docs/evidence-manifest.json")


def test_evidence_manifest_matches_the_pinned_kernel() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema"] == "repairflow.evidence_manifest.v1"
    assert payload["synaps_commit"] == SYNAPS_COMMIT
    assert payload["synaps_repo"] == SYNAPS_REPO
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
