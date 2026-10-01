from __future__ import annotations

from datetime import timedelta

import pytest

from repairflow.atc_baseline import ATCConfig, atc_order, atc_priority
from repairflow.synthetic import synthesize


def test_atc_order_is_deterministic_for_an_explicit_ready_set() -> None:
    problem = synthesize("tiny", seed=42)
    operation_ids = [operation.id for operation in problem.operations[:4]]
    now = problem.planning_horizon.start

    left = atc_order(problem, operation_ids, now=now)
    right = atc_order(problem, list(reversed(operation_ids)), now=now)

    assert left == right
    assert sorted(left) == sorted(operation_ids)


def test_atc_priority_increases_as_due_time_becomes_immediate() -> None:
    problem = synthesize("tiny", seed=42)
    operation = problem.operations[0]
    average = float(operation.duration_min)
    due = next(job.due_date for job in problem.jobs if job.id == operation.job_id)
    before_due = atc_priority(
        problem,
        operation.id,
        now=problem.planning_horizon.start,
        average_processing_min=average,
    )
    at_due = atc_priority(
        problem,
        operation.id,
        now=due,
        average_processing_min=average,
    )

    assert at_due >= before_due
    assert at_due > 0


def test_atc_contract_rejects_ambiguous_inputs_and_does_not_schedule() -> None:
    problem = synthesize("tiny", seed=42)
    now = problem.planning_horizon.start

    with pytest.raises(ValueError, match="unique"):
        atc_order(problem, [problem.operations[0].id] * 2, now=now)
    with pytest.raises(ValueError, match="unknown"):
        atc_order(problem, ["missing-operation"], now=now)
    with pytest.raises(ValueError, match="positive"):
        atc_priority(
            problem,
            problem.operations[0].id,
            now=now,
            average_processing_min=1.0,
            config=ATCConfig(k=0),
        )


def test_atc_now_is_explicit_and_has_no_clock_dependence() -> None:
    problem = synthesize("tiny", seed=42)
    operation_ids = [operation.id for operation in problem.operations[:3]]
    now = problem.planning_horizon.start

    first = atc_order(problem, operation_ids, now=now)
    second = atc_order(problem, operation_ids, now=now + timedelta(minutes=1))

    assert first == atc_order(problem, operation_ids, now=now)
    assert sorted(first) == sorted(second)
