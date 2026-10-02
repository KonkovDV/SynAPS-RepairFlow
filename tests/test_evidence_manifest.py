"""The evidence manifest names a commit that was actually checked."""

from __future__ import annotations

import json
from pathlib import Path

from repairflow.versions import SYNAPS_COMMIT, SYNAPS_REPO

_MANIFEST = Path("docs/evidence-manifest.json")


def test_evidence_manifest_matches_the_pinned_kernel() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema"] == "repairflow.evidence_manifest.v1"
    # The manifest names the kernel of the attested run. This tree's pin may be newer.
    assert payload["synaps_commit"] == "6178c93b705ff58be21fa74a98651883a2da1169"
    assert payload["attests_commit"] == "dc3327d802002e02a6f70b1413806ca9830cfd2e"
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
