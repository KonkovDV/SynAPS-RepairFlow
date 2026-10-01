from __future__ import annotations

import pytest

from repairflow.evidence_table import build_evidence_table
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_evidence_table_unifies_metrics_and_provenance() -> None:
    problem = synthesize("tiny", seed=1)
    results = {
        solver: plan(problem, solver_config=solver).result
        for solver in ("FIFO", "GREED", "EDD")
    }

    table = build_evidence_table(problem, results)

    assert table["schema"] == "repairflow.evidence_table.v1"
    assert len(table["table_hash"]) == 64
    assert table["metric_contract"]["makespan_origin"] == "planning_horizon.start"
    assert [row["solver"] for row in table["rows"]] == ["EDD", "FIFO", "GREED"]
    assert all(row["input_hash"] == results["GREED"].input_hash for row in table["rows"])
    assert all("metrics" in row and "post_utilization" in row["metrics"] for row in table["rows"])
    assert table["rows"][0]["solver_class"] == "baseline"
    assert table["rows"][2]["solver_class"] == "heuristic"


def test_evidence_table_rejects_mixed_inputs() -> None:
    first_problem = synthesize("tiny", seed=1)
    second_problem = synthesize("tiny", seed=42)
    results = {
        "first": plan(first_problem, solver_config="GREED").result,
        "second": plan(second_problem, solver_config="GREED").result,
    }

    with pytest.raises(ValueError, match="different input hashes"):
        build_evidence_table(first_problem, results)
