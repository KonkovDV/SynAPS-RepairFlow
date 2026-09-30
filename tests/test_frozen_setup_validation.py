"""Fail-closed ingest tests for immutable fragments and setup cells."""

from __future__ import annotations

from datetime import timedelta

import pytest

from repairflow.model import RepairFlowProblem
from repairflow.synthetic import synthesize


def test_duplicate_setup_cell_is_rejected_deterministically() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    payload = problem.model_dump(mode="python")
    payload["setup_matrix"].append(payload["setup_matrix"][0])
    with pytest.raises(ValueError, match="duplicate setup_matrix cells"):
        RepairFlowProblem.model_validate(payload)


def test_overlapping_immutable_fragment_is_rejected() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    first = problem.frozen_assignments[0]
    second_operation = None
    for operation in problem.operations:
        if operation.id == first.operation_id:
            continue
        if first.work_center_id not in operation.eligible_work_center_ids:
            continue
        second_operation = operation
        break
    assert second_operation is not None
    second = first.model_copy(update={"operation_id": second_operation.id})
    second = second.model_copy(update={"crew_id": None})
    payload = problem.model_dump(mode="python")
    payload["frozen_assignments"].append(second.model_dump(mode="python"))
    with pytest.raises(ValueError, match="frozen overlap"):
        RepairFlowProblem.model_validate(payload)


def test_immutable_fragment_outside_calendar_is_rejected() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    first = problem.frozen_assignments[0]
    duration = first.end - first.start
    start = problem.planning_horizon.start - timedelta(minutes=30)
    moved = first.model_copy(update={"start": start})
    moved = moved.model_copy(update={"end": start + duration})
    payload = problem.model_dump(mode="python")
    payload["frozen_assignments"][0] = moved.model_dump(mode="python")
    with pytest.raises(ValueError, match="outside calendar"):
        RepairFlowProblem.model_validate(payload)


def test_valid_immutable_fragment_remains_accepted() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    loaded = RepairFlowProblem.model_validate(problem.model_dump(mode="python"))
    assert loaded.frozen_assignments
    assert all(row.immutable for row in loaded.frozen_assignments)
