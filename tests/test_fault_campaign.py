"""Prefix coverage for the oracle-labelled fault campaign."""

from __future__ import annotations

from tests.fault_campaign import _apply, _judge, _selected_keys, covered_names

from repairflow.planner import plan
from repairflow.synthetic import synthesize


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
