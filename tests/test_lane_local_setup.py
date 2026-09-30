"""Reference tests for lane-local setup transitions."""

from __future__ import annotations

from datetime import timedelta

import pytest

from repairflow.lane_setup import lane_local_setup_placements
from repairflow.model import PlannedAssignment
from repairflow.synthetic import synthesize


def test_parallel_lanes_keep_independent_setup_state() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    loaded = problem.model_copy(
        update={
            "work_centers": [
                row.model_copy(update={"max_parallel": 2}) if row.id == post else row
                for row in problem.work_centers
            ]
        }
    )
    start = loaded.planning_horizon.start + timedelta(hours=8)
    operations = [row for row in loaded.operations if post in row.eligible_work_center_ids][:3]
    rows = [
        PlannedAssignment(
            operation_id=operations[0].id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=20),
        ),
        PlannedAssignment(
            operation_id=operations[1].id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=30),
        ),
        PlannedAssignment(
            operation_id=operations[2].id,
            work_center_id=post,
            start=start + timedelta(minutes=20),
            end=start + timedelta(minutes=40),
        ),
    ]
    placements = lane_local_setup_placements(loaded, rows)
    by_id = {row.operation_id: row for row in placements}
    assert by_id[operations[0].id].lane_index == 0
    assert by_id[operations[1].id].lane_index == 1
    assert by_id[operations[2].id].lane_index == 0
    assert by_id[operations[2].id].previous_operation_id == operations[0].id


def test_setup_occupancy_is_half_open_for_lane_reuse() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    operation_a, operation_b = [
        row for row in problem.operations if post in row.eligible_work_center_ids
    ][:2]
    start = problem.planning_horizon.start + timedelta(hours=8)
    rows = [
        PlannedAssignment(
            operation_id=operation_a.id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=20),
        ),
        PlannedAssignment(
            operation_id=operation_b.id,
            work_center_id=post,
            start=start + timedelta(minutes=20),
            end=start + timedelta(minutes=40),
        ),
    ]
    placements = lane_local_setup_placements(problem, rows)
    assert [row.lane_index for row in placements] == [0, 0]


def test_parallel_capacity_overflow_is_explicit() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    start = problem.planning_horizon.start + timedelta(hours=8)
    operations = [row for row in problem.operations if post in row.eligible_work_center_ids][:2]
    rows = [
        PlannedAssignment(
            operation_id=operation.id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=20),
        )
        for operation in operations
    ]
    with pytest.raises(ValueError, match="exceed capacity"):
        lane_local_setup_placements(problem, rows)
