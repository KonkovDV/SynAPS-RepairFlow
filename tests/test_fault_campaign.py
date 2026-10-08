"""Prefix coverage for the oracle-labelled fault campaign."""

from __future__ import annotations

import json
from pathlib import Path

from tests.fault_campaign import _apply, _judge, _selected_keys, covered_names

from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_committed_nightly_is_the_uncapped_matrix() -> None:
    nightly = json.loads(Path("docs/fault-campaign-nightly.json").read_text(encoding="utf-8"))
    prefix = json.loads(Path("docs/fault-campaign.json").read_text(encoding="utf-8"))
    assert nightly["schema"] == "repairflow.fault_campaign.v2"
    assert nightly["per_baseline"] is None
    assert nightly["checked"] == 109665
    assert nightly["false_accept"] == 0
    assert nightly["false_reject"] == 0
    assert nightly["must_reject"] == 102105
    assert nightly["may_pass"] == 7560
    assert nightly["input_hash"] == prefix["input_hash"]
    assert nightly["synaps_commit"] == prefix["synaps_commit"]
    assert prefix["checked"] == 10080
    assert prefix["per_baseline"] == 56
    assert nightly["by_mutator"]["shift-1"]["may_pass"] == 315
    assert nightly["by_mutator"]["shift-1"]["false_accept"] == 0


def test_prefix_includes_every_mutator_family() -> None:
    for preset in ("tiny", "repair-site-mvp"):
        problem = synthesize(preset, seed=1)
        rows = list(plan(problem, solver_config="GREED").result.assignments)
        assert covered_names(problem, rows, limit=56) == covered_names(problem, rows, limit=None)


def test_duplicate_is_a_must_reject() -> None:
    problem = synthesize("tiny", seed=1)
    rows = list(plan(problem, solver_config="GREED").result.assignments)
    key = next(item for item in _selected_keys(problem, rows, None) if item[0] == "duplicate")
    applied = _apply(problem, rows, key)
    assert applied is not None
    name, mutated, changed, operation_id = applied
    outcome = _judge("tiny", 1, "GREED", name, operation_id, mutated, changed)
    assert outcome["label"] == "must_reject"
    assert outcome["false_accept"] is False
    assert "DUPLICATE_ASSIGNMENT" in outcome["example"]["oracle"]
