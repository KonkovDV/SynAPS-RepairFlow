"""Temporal rotable-spare ledger tests with an independent small oracle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_plan
from repairflow.ledger import exchange_pool_violations
from repairflow.model import PlannedAssignment, RepairFlowProblem
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def _problem(*, lag: int, available_from: datetime | None = None) -> tuple[RepairFlowProblem, list[str]]:
    base = synthesize("tiny", seed=1)
    candidates = [row for row in base.operations if row.required_spare_ids]
    first, second = candidates[:2]
    operations = [
        row.model_copy(update={"required_spare_ids": ["SP-BEARING"]})
        if row.id in {first.id, second.id}
        else row
        for row in base.operations
    ]
    spares = [
        row.model_copy(
            update={
                "quantity": 1,
                "available_from": available_from,
                "domain_attributes": {"kind": "rotable", "return_lag_min": lag},
            }
        )
        if row.id == "SP-BEARING"
        else row
        for row in base.spares
    ]
    problem = RepairFlowProblem.model_validate(
        base.model_copy(update={"operations": operations, "spares": spares}).model_dump(mode="python")
    )
    return problem, [first.id, second.id]


def _assignments(
    problem: RepairFlowProblem,
    operation_ids: list[str],
    second_start: datetime,
) -> list[PlannedAssignment]:
    start = problem.planning_horizon.start + timedelta(hours=8)
    return [
        PlannedAssignment(
            operation_id=operation_ids[0],
            work_center_id=problem.operations[0].eligible_work_center_ids[0],
            start=start,
            end=start + timedelta(minutes=20),
        ),
        PlannedAssignment(
            operation_id=operation_ids[1],
            work_center_id=problem.operations[1].eligible_work_center_ids[0],
            start=second_start,
            end=second_start + timedelta(minutes=20),
        ),
    ]


def _checker_spare_hits(
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
) -> list[str]:
    schedule, id_map = to_schedule_problem(problem)
    violations = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=rows,
        id_map=id_map,
        kernel_status="feasible",
    )
    return [
        row.message
        for row in violations
        if row.code == ReasonCode.SPARE_UNAVAILABLE and row.resource_id == "SP-BEARING"
    ]


def test_checker_accepts_sequential_rotable_reuse() -> None:
    problem, operation_ids = _problem(lag=0)
    first_start = problem.planning_horizon.start + timedelta(hours=8)
    messages = _checker_spare_hits(
        problem,
        _assignments(problem, operation_ids, first_start + timedelta(minutes=20)),
    )
    assert messages == []


def test_checker_still_rejects_overlapping_rotable_reuse() -> None:
    problem, operation_ids = _problem(lag=0)
    first_start = problem.planning_horizon.start + timedelta(hours=8)
    messages = _checker_spare_hits(
        problem,
        _assignments(problem, operation_ids, first_start),
    )
    assert any("reused before return" in message for message in messages)


def test_checker_still_counts_consumable_reuse() -> None:
    problem, operation_ids = _problem(lag=0)
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    consumable = problem.model_copy(
        update={
            "spares": [
                spare.model_copy(update={"domain_attributes": {"kind": "consumable"}}),
                *[row for row in problem.spares if row.id != spare.id],
            ]
        }
    )
    loaded = RepairFlowProblem.model_validate(consumable.model_dump(mode="python"))
    first_start = loaded.planning_horizon.start + timedelta(hours=8)
    messages = _checker_spare_hits(
        loaded,
        _assignments(loaded, operation_ids, first_start + timedelta(minutes=20)),
    )
    assert any("used 2 times" in message for message in messages)


def test_rotable_spare_can_be_reused_after_return() -> None:
    problem, operation_ids = _problem(lag=0)
    first_start = problem.planning_horizon.start + timedelta(hours=8)
    violations = exchange_pool_violations(
        problem,
        _assignments(problem, operation_ids, first_start + timedelta(minutes=20)),
    )
    assert not any(row.code == ReasonCode.SPARE_UNAVAILABLE for row in violations)


def test_rotable_spare_is_busy_during_return_lag() -> None:
    problem, operation_ids = _problem(lag=10)
    first_start = problem.planning_horizon.start + timedelta(hours=8)
    violations = exchange_pool_violations(
        problem,
        _assignments(problem, operation_ids, first_start + timedelta(minutes=20)),
    )
    hits = [row for row in violations if row.code == ReasonCode.SPARE_UNAVAILABLE]
    assert hits
    assert hits[0].details["return_lag_min"] == 10
    assert hits[0].details["other_operation_id"] == operation_ids[0]


def test_rotable_spare_available_from_is_hard() -> None:
    available = datetime(2026, 1, 12, 18, tzinfo=UTC)
    problem, operation_ids = _problem(lag=0, available_from=available)
    first_start = problem.planning_horizon.start + timedelta(hours=8)
    violations = exchange_pool_violations(
        problem,
        _assignments(problem, operation_ids, first_start),
    )
    assert any(
        row.code == ReasonCode.SPARE_UNAVAILABLE and row.operation_id == operation_ids[0]
        for row in violations
    )


def test_rotable_spare_rejects_non_integer_return_lag() -> None:
    problem, operation_ids = _problem(lag=0)
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    broken = problem.model_copy(
        update={
            "spares": [
                spare.model_copy(
                    update={
                        "domain_attributes": {
                            "kind": "rotable",
                            "return_lag_min": True,
                        }
                    }
                ),
                *[row for row in problem.spares if row.id != spare.id],
            ]
        }
    )
    start = broken.planning_horizon.start + timedelta(hours=8)
    violations = exchange_pool_violations(
        broken,
        _assignments(broken, operation_ids, start + timedelta(minutes=20)),
    )
    assert any(row.code == ReasonCode.SPARE_UNAVAILABLE for row in violations)
    assert any(row.details.get("return_lag_min") is True for row in violations)
