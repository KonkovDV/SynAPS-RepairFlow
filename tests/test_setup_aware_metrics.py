from __future__ import annotations

from datetime import timedelta

from repairflow.metrics import compute_metrics
from repairflow.model import PlannedAssignment
from repairflow.synthetic import synthesize


def test_post_utilization_includes_setup_and_exposes_components() -> None:
    problem = synthesize("tiny", seed=1)
    operation = problem.operations[0]
    center = problem.work_centers[0]
    loaded = problem.model_copy(
        update={
            "work_centers": [
                center.model_copy(update={"max_parallel": 2}),
                *problem.work_centers[1:],
            ]
        }
    )
    start = loaded.planning_horizon.start + timedelta(minutes=10)
    assignment = PlannedAssignment(
        operation_id=operation.id,
        work_center_id=center.id,
        start=start,
        end=start + timedelta(minutes=operation.duration_min),
        setup_minutes=10,
    )

    metrics = compute_metrics(loaded, [assignment])
    horizon_minutes = int(
        (loaded.planning_horizon.end - loaded.planning_horizon.start).total_seconds() // 60
    )
    capacity_minutes = sum(row.max_parallel for row in loaded.work_centers) * horizon_minutes
    processing = operation.duration_min / capacity_minutes
    setup = 10 / capacity_minutes

    assert metrics["post_capacity_lanes"] == sum(row.max_parallel for row in loaded.work_centers)
    assert metrics["post_processing_utilization"] == round(processing, 6)
    assert metrics["post_setup_utilization"] == round(setup, 6)
    assert metrics["post_utilization"] == round(processing + setup, 6)
    assert metrics["post_utilization_denominator"] == "sum_work_center_max_parallel * horizon_minutes"


def test_parallel_capacity_is_in_the_utilization_denominator() -> None:
    problem = synthesize("tiny", seed=1)
    center = problem.work_centers[0]
    loaded = problem.model_copy(
        update={
            "work_centers": [
                center.model_copy(update={"max_parallel": 2}),
                *problem.work_centers[1:],
            ]
        }
    )
    start = loaded.planning_horizon.start + timedelta(minutes=10)
    assignments = [
        PlannedAssignment(
            operation_id=operation.id,
            work_center_id=center.id,
            start=start + timedelta(minutes=index * operation.duration_min),
            end=start + timedelta(minutes=(index + 1) * operation.duration_min),
        )
        for index, operation in enumerate(loaded.operations[:2])
    ]

    metrics = compute_metrics(loaded, assignments)

    assert metrics["post_processing_utilization"] <= 1.0
    assert metrics["post_utilization"] <= 1.0
