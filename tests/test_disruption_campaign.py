"""The committed disruption report is the 5×30 tiny measurement."""

from __future__ import annotations

import json
from pathlib import Path

from tests.disruption_campaign import run_disruption_campaign

_REPORT = Path("docs/disruption-campaign.json")


def test_disruption_campaign_matches_the_committed_report() -> None:
    fresh = run_disruption_campaign()
    stored = json.loads(_REPORT.read_text(encoding="utf-8"))
    assert stored["schema"] == "repairflow.disruption_campaign.v1"
    assert stored["checked"] == 150
    assert stored["false_accept"] == 0
    assert stored["replanned"] == 150
    assert stored["seeds"] == [1, 30]
    assert set(stored["by_kind"]) == {
        "POST_DOWN",
        "CREW_ABSENT",
        "PART_DELAY",
        "DURATION_OVERRUN",
        "URGENT_JOB",
    }
    for kind, row in stored["by_kind"].items():
        assert row == {"checked": 30, "false_accept": 0, "replanned": 30}
        assert fresh["by_kind"][kind] == row
    assert fresh["checked"] == stored["checked"]
    assert fresh["false_accept"] == 0
    assert abs(fresh["mean_churn"] - stored["mean_churn"]) < 1e-9
