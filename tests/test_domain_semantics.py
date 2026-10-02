"""Predecessor lags, consumable receipts, and skill expiry."""

from __future__ import annotations

from datetime import timedelta

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_plan
from repairflow.model import (
    PlannedAssignment,
    PredecessorLink,
    RepairFlowProblem,
    SpareNeed,
    SpareReceipt,
)
from repairflow.normalize import load_problem, write_csv_bundle
from repairflow.planner import plan, recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def _codes(problem: RepairFlowProblem, rows: list[PlannedAssignment]) -> list[str]:
    schedule, id_map = to_schedule_problem(problem)
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=rows,
        id_map=id_map,
        kernel_status="feasible",
    )
    return [row.code for row in found]


def test_predecessor_ids_stay_lag_zero() -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    assert outcome.result.verified_feasible
    assert not any(row.code == ReasonCode.PRECEDENCE_BROKEN for row in outcome.result.violations)


def test_min_lag_rejects_an_immediate_successor() -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    by_op = {row.operation_id: row for row in outcome.result.assignments}
    successor = next(op for op in problem.operations if op.predecessor_ids)
    predecessor = by_op[successor.predecessor_ids[0]]
    updated = successor.model_copy(
        update={"predecessors": [PredecessorLink(id=successor.predecessor_ids[0], min_lag_min=30)]}
    )
    operations = [updated if op.id == successor.id else op for op in problem.operations]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"operations": operations}).model_dump(mode="python")
    )
    held = by_op[successor.id].end - by_op[successor.id].start
    moved = by_op[successor.id].model_copy(update={"start": predecessor.end, "end": predecessor.end + held})
    rows = [moved if row.operation_id == successor.id else row for row in outcome.result.assignments]
    assert ReasonCode.PRECEDENCE_BROKEN in _codes(loaded, rows)


def test_receipts_do_not_cover_demand_before_they_arrive() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    spare = problem.spares[0].model_copy(
        update={
            "quantity": 2,
            "available_from": None,
            "receipts": [SpareReceipt(at=start + timedelta(hours=12), qty=2)],
        }
    )
    users = problem.operations[:3]
    user_ids = {row.id for row in users}
    operations = [
        op.model_copy(
            update={
                "required_spare_ids": [],
                "required_spares": [SpareNeed(spare_id=spare.id, qty=1)],
                "domain_attributes": {"duration_policy": "min"},
            }
        )
        if op.id in user_ids
        else op.model_copy(update={"required_spare_ids": [], "required_spares": []})
        for op in problem.operations
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"spares": [spare], "operations": operations}).model_dump(mode="python")
    )
    rows = []
    cursor = start + timedelta(hours=8)
    for op in users:
        rows.append(
            PlannedAssignment(
                operation_id=op.id,
                work_center_id=op.eligible_work_center_ids[0],
                start=cursor,
                end=cursor + timedelta(minutes=10),
            )
        )
        cursor += timedelta(minutes=10)
    assert ReasonCode.SPARE_UNAVAILABLE in _codes(loaded, rows)


def test_receipts_cover_demand_after_they_arrive() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    spare = problem.spares[0].model_copy(
        update={
            "quantity": 2,
            "available_from": None,
            "receipts": [SpareReceipt(at=start + timedelta(hours=8), qty=2)],
        }
    )
    users = problem.operations[:3]
    operations = [
        op.model_copy(
            update={
                "required_spare_ids": [],
                "required_spares": [SpareNeed(spare_id=spare.id, qty=1)],
            }
        )
        if op.id in {row.id for row in users}
        else op.model_copy(update={"required_spare_ids": [], "required_spares": []})
        for op in problem.operations
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"spares": [spare], "operations": operations}).model_dump(mode="python")
    )
    rows = []
    cursor = start + timedelta(hours=9)
    for op in users:
        rows.append(
            PlannedAssignment(
                operation_id=op.id,
                work_center_id=op.eligible_work_center_ids[0],
                start=cursor,
                end=cursor + timedelta(minutes=10),
            )
        )
        cursor += timedelta(minutes=10)
    assert ReasonCode.SPARE_UNAVAILABLE not in _codes(loaded, rows)


def test_expired_skill_is_not_verified() -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    row = outcome.result.assignments[0]
    operation = next(op for op in problem.operations if op.id == row.operation_id)
    assert row.crew_id is not None
    skill = operation.required_skills[0]
    crews = [
        crew.model_copy(update={"skill_valid_until": {skill: row.start}}) if crew.id == row.crew_id else crew
        for crew in problem.crews
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"crews": crews}).model_dump(mode="python")
    )
    checked = recheck(
        loaded,
        assignments=list(outcome.result.assignments),
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert any(item.code == ReasonCode.SKILL_EXPIRED for item in checked.result.violations)
    assert checked.result.verified_feasible is False


def test_structured_fields_round_trip_through_csv(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    successor = next(op for op in problem.operations if op.predecessor_ids)
    lag = PredecessorLink(id=successor.predecessor_ids[0], min_lag_min=15, max_lag_min=90)
    operations = [
        successor.model_copy(update={"predecessors": [lag]}) if op.id == successor.id else op
        for op in problem.operations
    ]
    start = problem.planning_horizon.start
    spare = problem.spares[0].model_copy(
        update={"receipts": [SpareReceipt(at=start + timedelta(hours=12), qty=2)]}
    )
    skill = problem.crews[0].skills[0]
    crews = [
        problem.crews[0].model_copy(update={"skill_valid_until": {skill: start + timedelta(hours=18)}}),
        *problem.crews[1:],
    ]
    sourced = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={"operations": operations, "spares": [spare, *problem.spares[1:]], "crews": crews}
        ).model_dump(mode="python")
    )
    bundle = tmp_path / "semantics"
    write_csv_bundle(bundle, sourced)
    loaded = load_problem(bundle)
    found = next(op for op in loaded.operations if op.id == successor.id)
    assert found.predecessors[0].min_lag_min == 15
    assert found.predecessors[0].max_lag_min == 90
    assert loaded.spares[0].receipts[0].qty == 2
    assert skill in loaded.crews[0].skill_valid_until
