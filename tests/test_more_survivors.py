"""Edges the 1261/1921 run did not measure.

These tests are not part of that score. Dispatch 37829096222 is on the
previous main and does not include this file.
"""

from __future__ import annotations

from datetime import timedelta

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_domain_assignments, check_plan
from repairflow.ledger import exchange_pool_violations
from repairflow.model import (
    Calendar,
    CalendarWindow,
    ExchangePool,
    Operation,
    PlannedAssignment,
    PoolDemand,
    PredecessorLink,
    RepairFlowProblem,
    Violation,
)
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_an_unknown_duration_policy_names_the_three_allowed_values() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    attrs = {**op.domain_attributes, "duration_policy": "nope"}
    loaded = _with_op(problem, op.model_copy(update={"domain_attributes": attrs}))
    start = problem.planning_horizon.start + timedelta(hours=8)
    hit = _one(check_domain_assignments(loaded, [_visit(op, start)]), ReasonCode.INVALID_DURATION)
    assert hit.message == "duration_policy must be exact, min, or preemptive"


def test_a_missing_return_lag_is_zero() -> None:
    problem = synthesize("tiny", seed=1)
    users = [row for row in problem.operations if "SP-BEARING" in row.required_spare_ids][:2]
    loaded = _rotable(problem, {"mode": "rotable"})
    start = problem.planning_horizon.start + timedelta(hours=8)
    rows = [
        _visit(users[0], start, end=start + timedelta(minutes=20)),
        _visit(users[1], start + timedelta(minutes=20), end=start + timedelta(minutes=40)),
    ]
    messages = [row.message for row in exchange_pool_violations(loaded, rows)]
    assert not any(
        "invalid return_lag" in message or "reused before return" in message for message in messages
    )


def test_mode_alone_marks_a_spare_rotable() -> None:
    problem = synthesize("tiny", seed=1)
    users = [row for row in problem.operations if "SP-BEARING" in row.required_spare_ids][:2]
    loaded = _rotable(problem, {"mode": "rotable"})
    start = problem.planning_horizon.start + timedelta(hours=8)
    rows = [
        _visit(users[0], start, end=start + timedelta(minutes=20)),
        _visit(users[1], start, end=start + timedelta(minutes=20)),
    ]
    messages = [row.message for row in exchange_pool_violations(loaded, rows)]
    assert any("reused before return" in message for message in messages)
    assert not any("used" in message and "quantity" in message for message in messages)


def test_two_returns_at_one_moment_cover_a_demand_of_two() -> None:
    loaded, rows, _end = _two_returns()
    pool = ExchangePool(
        unit_type="ZZ-SAME",
        initial_serviceable=0,
        demand=[PoolDemand(at=rows[0].end + timedelta(minutes=1), qty=2)],
        hard=True,
    )
    loaded = _reload(loaded, exchange_pools=[pool])
    assert not _stockouts(exchange_pool_violations(loaded, rows))


def test_one_return_does_not_cover_a_demand_of_two() -> None:
    loaded, rows, end = _two_returns()
    pool = ExchangePool(
        unit_type="ZZ-SAME",
        initial_serviceable=0,
        demand=[PoolDemand(at=end + timedelta(minutes=1), qty=2)],
        hard=True,
    )
    loaded = _reload(loaded, exchange_pools=[pool])
    assert _stockouts(exchange_pool_violations(loaded, rows[:1]))


def test_a_job_with_no_operations_does_not_crash_the_ledger() -> None:
    problem = synthesize("tiny", seed=1)
    empty = problem.jobs[0].model_copy(update={"id": "JOB-EMPTY", "unit_type": "ZZ-EMPTY"})
    moment = problem.planning_horizon.start
    pool = ExchangePool(
        unit_type="ZZ-EMPTY",
        initial_serviceable=0,
        demand=[PoolDemand(at=moment, qty=1)],
        hard=True,
    )
    loaded = _reload(problem, jobs=[*problem.jobs, empty], exchange_pools=[pool])
    assert _stockouts(exchange_pool_violations(loaded, []))


def test_an_incomplete_earlier_job_does_not_drop_the_next_return() -> None:
    problem = synthesize("tiny", seed=1)
    first, second = problem.jobs[0], problem.jobs[1]
    op_first = next(row for row in problem.operations if row.job_id == first.id)
    op_second = next(row for row in problem.operations if row.job_id == second.id)
    op_first = op_first.model_copy(update={"predecessor_ids": [], "predecessors": []})
    op_second = op_second.model_copy(update={"predecessor_ids": [], "predecessors": []})
    end = problem.planning_horizon.start + timedelta(hours=9)
    pool = ExchangePool(
        unit_type=second.unit_type,
        initial_serviceable=0,
        demand=[PoolDemand(at=end + timedelta(minutes=1), qty=1)],
        hard=True,
    )
    loaded = _reload(problem, operations=[op_first, op_second], exchange_pools=[pool])
    row = _visit(op_second, end - timedelta(minutes=20), end=end)
    assert not _stockouts(exchange_pool_violations(loaded, [row]))


def test_preemptive_unattended_work_ignores_a_closed_calendar() -> None:
    problem, op, center_id, start = _preemptive_center(unattended=True, window_covers_visit=False)
    row = _visit(op, start, end=start + timedelta(minutes=60), work_center_id=center_id)
    messages = [item.message for item in check_domain_assignments(problem, [row])]
    assert not any("open minutes" in message for message in messages)


def test_preemptive_duration_uses_only_the_aux_on_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if not row.required_aux_ids)
    start = problem.planning_horizon.start + timedelta(hours=8)
    open_window = CalendarWindow(start=start, end=start + timedelta(hours=4))
    calendars = [
        *problem.calendars,
        Calendar(id="CAL-OPEN", code="CAL-OPEN", windows=[open_window]),
        Calendar(id="CAL-SHUT", code="CAL-SHUT", windows=[]),
    ]
    center_id = op.eligible_work_center_ids[0]
    centers = [
        row.model_copy(update={"domain_attributes": {"attendance": "unattended"}})
        if row.id == center_id
        else row
        for row in problem.work_centers
    ]
    auxes = []
    for row in problem.aux_resources:
        if row.id == "AUX-JIG":
            auxes.append(row.model_copy(update={"calendar_id": "CAL-OPEN"}))
        elif row.id == "AUX-CRANE":
            auxes.append(row.model_copy(update={"calendar_id": "CAL-SHUT"}))
        else:
            auxes.append(row)
    attrs = {**op.domain_attributes, "duration_policy": "preemptive"}
    edited = op.model_copy(update={"domain_attributes": attrs, "required_aux_ids": [], "duration_min": 60})
    loaded = _reload(
        _with_op(problem, edited),
        calendars=calendars,
        work_centers=centers,
        aux_resources=auxes,
    )
    row = _visit(
        edited, start, end=start + timedelta(minutes=60), work_center_id=center_id, aux_ids=["AUX-JIG"]
    )
    messages = [item.message for item in check_domain_assignments(loaded, [row])]
    assert not any("open minutes" in message for message in messages)


def test_a_preemptive_unknown_post_or_crew_does_not_raise() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    attrs = {**op.domain_attributes, "duration_policy": "preemptive"}
    loaded = _with_op(problem, op.model_copy(update={"domain_attributes": attrs}))
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, work_center_id="POST-NOPE", crew_id="CREW-NOPE")
    violations = check_domain_assignments(loaded, [row])
    messages = [item.message for item in violations]
    assert any("unknown work center" in message for message in messages)
    assert any("unknown crew" in message for message in messages)


def test_findings_sort_by_operation_id() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    rows = [
        _visit(op, start, operation_id="OP-B"),
        _visit(op, start + timedelta(hours=1), operation_id="OP-A"),
    ]
    found = [
        row.operation_id
        for row in check_domain_assignments(problem, rows)
        if row.message == "assignment references an unknown operation"
    ]
    assert found == ["OP-A", "OP-B"]


def test_stockouts_sort_by_resource_id() -> None:
    problem = synthesize("tiny", seed=1)
    moment = problem.planning_horizon.start
    pools = [
        ExchangePool(
            unit_type="ZZ-B", initial_serviceable=0, demand=[PoolDemand(at=moment, qty=1)], hard=True
        ),
        ExchangePool(
            unit_type="ZZ-A", initial_serviceable=0, demand=[PoolDemand(at=moment, qty=1)], hard=True
        ),
    ]
    loaded = _reload(problem, exchange_pools=pools)
    found = [
        row.resource_id
        for row in check_domain_assignments(loaded, [])
        if row.code == ReasonCode.EXCHANGE_POOL_STOCKOUT
    ]
    assert found == ["ZZ-A", "ZZ-B"]


def test_subset_mode_ignores_a_missing_predecessor() -> None:
    problem = synthesize("tiny", seed=1)
    pred = problem.operations[0]
    succ = problem.operations[1].model_copy(
        update={
            "predecessor_ids": [pred.id],
            "predecessors": [PredecessorLink(id=pred.id)],
        }
    )
    loaded = _with_op(problem, succ)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(succ, start)
    message = f"{succ.id} is scheduled but predecessor {pred.id} is not"
    assert any(item.message == message for item in check_domain_assignments(loaded, [row]))
    schedule, id_map = to_schedule_problem(loaded)
    subset = check_plan(
        loaded,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
        subset_mode=True,
    )
    assert not any(item.message == message for item in subset)


def _two_returns() -> tuple[RepairFlowProblem, list[PlannedAssignment], object]:
    problem = synthesize("tiny", seed=1)
    first, second = problem.jobs[0], problem.jobs[1]
    op_first = next(row for row in problem.operations if row.job_id == first.id)
    op_second = next(row for row in problem.operations if row.job_id == second.id)
    op_first = op_first.model_copy(update={"predecessor_ids": [], "predecessors": []})
    op_second = op_second.model_copy(update={"predecessor_ids": [], "predecessors": []})
    jobs = [
        row.model_copy(update={"unit_type": "ZZ-SAME"}) if row.id in {first.id, second.id} else row
        for row in problem.jobs
    ]
    end = problem.planning_horizon.start + timedelta(hours=9)
    loaded = _reload(problem, jobs=jobs, operations=[op_first, op_second])
    rows = [
        _visit(op_first, end - timedelta(minutes=20), end=end),
        _visit(op_second, end - timedelta(minutes=20), end=end),
    ]
    return loaded, rows, end


def _preemptive_center(
    *,
    unattended: bool,
    window_covers_visit: bool,
) -> tuple[RepairFlowProblem, Operation, str, object]:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if not row.required_aux_ids)
    start = problem.planning_horizon.start + timedelta(hours=8)
    window_start = start if window_covers_visit else problem.planning_horizon.start
    calendar = Calendar(
        id="CAL-EDGE",
        code="CAL-EDGE",
        windows=[CalendarWindow(start=window_start, end=window_start + timedelta(hours=1))],
    )
    center_id = op.eligible_work_center_ids[0]
    attendance = {"attendance": "unattended"} if unattended else {}
    centers = [
        row.model_copy(update={"calendar_id": "CAL-EDGE", "domain_attributes": attendance})
        if row.id == center_id
        else row
        for row in problem.work_centers
    ]
    attrs = {**op.domain_attributes, "duration_policy": "preemptive"}
    edited = op.model_copy(update={"domain_attributes": attrs, "required_aux_ids": [], "duration_min": 60})
    loaded = _reload(
        _with_op(problem, edited),
        calendars=[*problem.calendars, calendar],
        work_centers=centers,
    )
    return loaded, edited, center_id, start


def _rotable(problem: RepairFlowProblem, attributes: dict[str, str]) -> RepairFlowProblem:
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    spares = [
        spare.model_copy(update={"quantity": 1, "domain_attributes": attributes})
        if row.id == spare.id
        else row
        for row in problem.spares
    ]
    return _reload(problem, spares=spares)


def _with_op(problem: RepairFlowProblem, edited: Operation) -> RepairFlowProblem:
    operations = [edited if row.id == edited.id else row for row in problem.operations]
    return _reload(problem, operations=operations)


def _visit(op: Operation, start: object, **updates: object) -> PlannedAssignment:
    end = updates.pop("end", start + timedelta(minutes=op.duration_min))  # type: ignore[operator]
    work_center_id = updates.pop("work_center_id", op.eligible_work_center_ids[0])
    return PlannedAssignment(
        operation_id=str(updates.pop("operation_id", op.id)),
        work_center_id=str(work_center_id),
        start=start,  # type: ignore[arg-type]
        end=end,  # type: ignore[arg-type]
        crew_id=updates.pop("crew_id", None),  # type: ignore[arg-type]
        aux_ids=list(updates.pop("aux_ids", [])),  # type: ignore[arg-type]
    )


def _reload(problem: RepairFlowProblem, **updates: object) -> RepairFlowProblem:
    return RepairFlowProblem.model_validate(problem.model_copy(update=updates).model_dump(mode="python"))


def _stockouts(violations: list[Violation]) -> bool:
    return any(row.code == ReasonCode.EXCHANGE_POOL_STOCKOUT for row in violations)


def _one(violations: list[Violation], code: ReasonCode) -> Violation:
    found = [row for row in violations if row.code == code]
    assert len(found) == 1, [row.message for row in violations]
    return found[0]
