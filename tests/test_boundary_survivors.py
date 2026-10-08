"""Pin boundaries that a one-step mutant would move.

These tests are not part of mutation score 1227/1921. A missing
`suggested_relaxation` on a checker call is still equivalent, because
`_violation` fills it. The ledger builds `Violation` directly, so a missing
sentence there is not equivalent and is asserted below.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from repairflow.checker import check_domain_assignments
from repairflow.ledger import exchange_pool_violations
from repairflow.model import (
    Calendar,
    CalendarWindow,
    ExchangePool,
    FrozenAssignment,
    Operation,
    PlannedAssignment,
    PoolDemand,
    PredecessorLink,
    RepairFlowProblem,
    SpareNeed,
    SpareReceipt,
    Violation,
)
from repairflow.planner import plan
from repairflow.reasons import SUGGESTIONS, ReasonCode
from repairflow.synthetic import synthesize


def test_a_visit_that_touches_the_horizon_is_inside_it() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    row = _visit(op, problem.planning_horizon.start, end=problem.planning_horizon.end)
    assert not _codes(problem, [row], ReasonCode.HORIZON_VIOLATION)


def test_one_side_outside_the_horizon_is_still_outside() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    end = problem.planning_horizon.end + timedelta(minutes=1)
    start = problem.planning_horizon.end - timedelta(minutes=30)
    hit = _one(
        check_domain_assignments(problem, [_visit(op, start, end=end)]),
        ReasonCode.HORIZON_VIOLATION,
    )
    assert hit.start == start
    assert hit.end == end
    assert problem.planning_horizon.start <= start < problem.planning_horizon.end


def test_missing_aux_keeps_the_suggestion_from_the_table() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0].model_copy(update={"required_aux_ids": ["AUX-CRANE"]})
    loaded = _with_op(problem, op)
    start = problem.planning_horizon.start + timedelta(hours=8)
    hit = _one(check_domain_assignments(loaded, [_visit(op, start)]), ReasonCode.AUX_MISSING)
    assert hit.suggested_relaxation == SUGGESTIONS[ReasonCode.AUX_MISSING]


def test_finishing_on_latest_finish_is_inside_the_window() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    end = start + timedelta(minutes=op.duration_min)
    loaded = _with_op(problem, op.model_copy(update={"latest_finish": end}))
    messages = [row.message for row in check_domain_assignments(loaded, [_visit(op, start)])]
    assert not any("finishes after latest_finish" in message for message in messages)


def test_starting_on_earliest_start_is_inside_the_window() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    loaded = _with_op(problem, op.model_copy(update={"earliest_start": start}))
    messages = [row.message for row in check_domain_assignments(loaded, [_visit(op, start)])]
    assert not any("starts before earliest_start" in message for message in messages)


def test_finishing_on_the_due_date_and_the_deadline_is_not_late() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    end = start + timedelta(minutes=op.duration_min)
    loaded = _with_job_dates(problem, op.job_id, due=end, deadline=end)
    violations = check_domain_assignments(loaded, [_visit(op, start)])
    assert ReasonCode.DUE_MISSED not in {row.code for row in violations}
    assert ReasonCode.DEADLINE_MISSED not in {row.code for row in violations}


def test_a_due_date_one_minute_early_is_a_kpi() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    end = start + timedelta(minutes=op.duration_min)
    loaded = _with_job_dates(problem, op.job_id, due=end - timedelta(minutes=1), deadline=None)
    hit = _one(check_domain_assignments(loaded, [_visit(op, start)]), ReasonCode.DUE_MISSED)
    assert hit.severity == "kpi"
    assert hit.end == end


def test_min_policy_accepts_its_duration_and_rejects_a_shorter_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    attrs = {**op.domain_attributes, "duration_policy": "min"}
    loaded = _with_op(problem, op.model_copy(update={"domain_attributes": attrs}))
    start = problem.planning_horizon.start + timedelta(hours=8)
    exact = _visit(op, start)
    short = _visit(op, start, end=start + timedelta(minutes=op.duration_min - 1))
    assert not _codes(loaded, [exact], ReasonCode.INVALID_DURATION)
    hit = _one(check_domain_assignments(loaded, [short]), ReasonCode.INVALID_DURATION)
    assert (
        hit.message == f"scheduled {op.duration_min - 1} min is shorter than duration_min={op.duration_min}"
    )


def test_zero_quantity_is_unavailable_and_the_exact_start_is_available() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    empty = _spare_problem(problem, op, quantity=0, available_from=None, receipts=())
    assert any(
        "has quantity 0" in row.message for row in check_domain_assignments(empty, [_visit(op, start)])
    )
    opened = _spare_problem(problem, op, quantity=8, available_from=start, receipts=())
    messages = [row.message for row in check_domain_assignments(opened, [_visit(op, start)])]
    assert not any("not available until" in message for message in messages)


def test_using_the_whole_receipt_stock_is_not_short() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    later = start + timedelta(hours=4)
    loaded = _spare_problem(
        problem,
        op,
        quantity=1,
        available_from=None,
        receipts=(SpareReceipt(at=later, qty=1),),
        needs=(SpareNeed(spare_id="SP-BEARING", qty=1),),
    )
    messages = [row.message for row in check_domain_assignments(loaded, [_visit(op, start)])]
    assert not any("stock is short" in message for message in messages)


def test_receipt_draws_are_ordered_by_operation_id_not_by_quantity() -> None:
    problem = synthesize("tiny", seed=1)
    smaller, larger = sorted(problem.operations[:2], key=lambda row: row.id)
    start = problem.planning_horizon.start + timedelta(hours=8)
    later = start + timedelta(hours=4)
    operations = []
    for op in problem.operations:
        if op.id == smaller.id:
            operations.append(_demand(op, 1))
        elif op.id == larger.id:
            operations.append(_demand(op, 5))
        else:
            operations.append(op)
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    spares = [
        spare.model_copy(
            update={
                "quantity": 3,
                "receipts": [SpareReceipt(at=later, qty=1)],
                "domain_attributes": {"kind": "consumable"},
            }
        )
        if row.id == spare.id
        else row
        for row in problem.spares
    ]
    loaded = _reload(problem, operations=operations, spares=spares)
    rows = [_visit(smaller, start), _visit(larger, start)]
    short = [
        row.operation_id
        for row in check_domain_assignments(loaded, rows)
        if row.code == ReasonCode.SPARE_UNAVAILABLE and "stock is short" in row.message
    ]
    assert short == [larger.id]


def test_max_lag_allows_the_exact_gap_and_records_a_later_start() -> None:
    problem = synthesize("tiny", seed=1)
    pred = problem.operations[0]
    succ = next(row for row in problem.operations if row.id != pred.id and row.job_id == pred.job_id)
    linked = succ.model_copy(
        update={
            "predecessor_ids": [pred.id],
            "predecessors": [PredecessorLink(id=pred.id, max_lag_min=60)],
        }
    )
    loaded = _with_op(problem, linked)
    start = problem.planning_horizon.start + timedelta(hours=8)
    pred_row = _visit(pred, start)
    exact = _visit(succ, pred_row.end + timedelta(minutes=60))
    messages = [row.message for row in check_domain_assignments(loaded, [pred_row, exact])]
    assert not any("max lag" in message for message in messages)
    late = _visit(succ, pred_row.end + timedelta(minutes=61))
    hit = _one(check_domain_assignments(loaded, [pred_row, late]), ReasonCode.PRECEDENCE_BROKEN)
    assert "max lag" in hit.message
    assert hit.details == {"max_lag_min": 60}


def test_preemptive_setup_may_touch_both_edges_of_its_window() -> None:
    problem, op, center_id, moment = _preemptive_window()
    row = _visit(
        op,
        moment + timedelta(hours=1),
        end=moment + timedelta(hours=1, minutes=30),
        work_center_id=center_id,
        setup_minutes=60,
    )
    messages = [item.message for item in check_domain_assignments(problem, [row])]
    assert not any("setup is not contained" in message for message in messages)


def test_preemptive_visit_without_setup_does_not_consult_the_window() -> None:
    problem, op, center_id, moment = _preemptive_window()
    row = _visit(
        op,
        moment + timedelta(hours=3),
        end=moment + timedelta(hours=3, minutes=30),
        work_center_id=center_id,
        setup_minutes=0,
    )
    messages = [item.message for item in check_domain_assignments(problem, [row])]
    assert not any("setup is not contained" in message for message in messages)


def test_setup_overlap_counts_for_the_post_the_crew_and_the_aux() -> None:
    problem = synthesize("tiny", seed=1)
    first, second = problem.operations[0], problem.operations[1]
    post = first.eligible_work_center_ids[0]
    centers = [
        row.model_copy(update={"max_parallel": 1}) if row.id == post else row for row in problem.work_centers
    ]
    loaded = _reload(problem, work_centers=centers)
    start = problem.planning_horizon.start + timedelta(hours=8)
    crew = problem.crews[0].id
    rows = [
        _visit(
            first,
            start,
            end=start + timedelta(minutes=30),
            work_center_id=post,
            crew_id=crew,
            aux_ids=["AUX-JIG"],
        ),
        _visit(
            second,
            start + timedelta(minutes=30),
            end=start + timedelta(minutes=60),
            work_center_id=post,
            crew_id=crew,
            aux_ids=["AUX-JIG"],
            setup_minutes=10,
        ),
    ]
    violations = check_domain_assignments(loaded, rows)
    codes = {row.code for row in violations}
    assert ReasonCode.CENTER_OVERLAP in codes
    assert ReasonCode.CREW_OVERLAP in codes
    assert ReasonCode.AUX_OVERLAP in codes
    center = next(row for row in violations if row.code == ReasonCode.CENTER_OVERLAP)
    assert center.details["capacity"] == 1
    assert "other_operation_id" in center.details
    assert "active" in center.details


def test_unbound_frozen_crew_is_not_a_move() -> None:
    problem = synthesize("tiny", seed=1)
    issued = plan(problem, solver_config="GREED")
    assert issued.result.verified_feasible
    placed = next(row for row in issued.result.assignments if row.crew_id)
    frozen = _freeze(placed, crew_id=None)
    loaded = _reload(problem, frozen_assignments=[frozen])
    messages = [row.message for row in check_domain_assignments(loaded, list(issued.result.assignments))]
    assert not any("was moved" in message for message in messages)


def test_a_changed_frozen_crew_keeps_the_promised_slot() -> None:
    problem = synthesize("tiny", seed=1)
    issued = plan(problem, solver_config="GREED")
    placed = next(row for row in issued.result.assignments if row.crew_id)
    placed_crew = next(row for row in problem.crews if row.id == placed.crew_id)
    other = next(row for row in problem.crews if row.id != placed.crew_id)
    crews = [
        other.model_copy(update={"skills": list(placed_crew.skills), "skill_valid_until": {}})
        if row.id == other.id
        else row
        for row in problem.crews
    ]
    frozen = _freeze(placed, crew_id=other.id)
    loaded = _reload(problem, crews=crews, frozen_assignments=[frozen])
    hit = _one(check_domain_assignments(loaded, list(issued.result.assignments)), ReasonCode.FROZEN_MOVED)
    assert "was moved" in hit.message
    assert hit.details == {
        "expected_start": frozen.start.isoformat(),
        "expected_end": frozen.end.isoformat(),
        "expected_work_center_id": frozen.work_center_id,
    }


def test_a_tied_stockout_keeps_the_first_moment_and_the_sentence() -> None:
    problem = synthesize("tiny", seed=1)
    job = problem.jobs[0]
    op = next(row for row in problem.operations if row.job_id == job.id)
    moment = problem.planning_horizon.start
    finished = moment + timedelta(hours=2)
    pool = ExchangePool(
        unit_type=job.unit_type,
        initial_serviceable=1,
        demand=[PoolDemand(at=moment, qty=2), PoolDemand(at=finished, qty=1)],
        hard=True,
    )
    loaded = _reload(problem, operations=[op], exchange_pools=[pool])
    row = _visit(op, finished - timedelta(minutes=20), end=finished)
    hit = _one(exchange_pool_violations(loaded, [row]), ReasonCode.EXCHANGE_POOL_STOCKOUT)
    assert hit.start == moment
    assert hit.resource_id == job.unit_type
    assert hit.severity == "hard"
    assert hit.details == {"unit_type": job.unit_type, "min_stock": -1, "hard": True}
    assert hit.suggested_relaxation == SUGGESTIONS[ReasonCode.EXCHANGE_POOL_STOCKOUT]


def test_a_predecessor_in_another_job_does_not_withhold_the_return() -> None:
    problem = synthesize("tiny", seed=1)
    job_a, job_b = problem.jobs[0], problem.jobs[1]
    op_a = next(row for row in problem.operations if row.job_id == job_a.id)
    op_b = next(row for row in problem.operations if row.job_id == job_b.id)
    op_a = op_a.model_copy(update={"predecessor_ids": [], "predecessors": []})
    op_b = op_b.model_copy(
        update={"predecessor_ids": [op_a.id], "predecessors": [PredecessorLink(id=op_a.id)]}
    )
    end = problem.planning_horizon.start + timedelta(hours=9)
    pool = ExchangePool(
        unit_type=job_a.unit_type,
        initial_serviceable=0,
        demand=[PoolDemand(at=end + timedelta(minutes=1), qty=1)],
        hard=True,
    )
    loaded = _reload(problem, operations=[op_a, op_b], exchange_pools=[pool])
    row = _visit(op_a, end - timedelta(minutes=op_a.duration_min), end=end)
    assert not _codes_from(exchange_pool_violations(loaded, [row]), ReasonCode.EXCHANGE_POOL_STOCKOUT)


def test_the_sink_is_the_operation_with_no_successor() -> None:
    problem = synthesize("tiny", seed=1)
    job = problem.jobs[0]
    chain = [row for row in problem.operations if row.job_id == job.id]
    op1, op2 = chain[0], chain[1]
    op1 = op1.model_copy(update={"predecessor_ids": [], "predecessors": []})
    op2 = op2.model_copy(update={"predecessor_ids": [op1.id], "predecessors": [PredecessorLink(id=op1.id)]})
    start = problem.planning_horizon.start + timedelta(hours=8)
    first_end = start + timedelta(minutes=20)
    pool = ExchangePool(
        unit_type=job.unit_type,
        initial_serviceable=0,
        demand=[PoolDemand(at=first_end + timedelta(minutes=1), qty=1)],
        hard=True,
    )
    loaded = _reload(problem, operations=[op1, op2], exchange_pools=[pool])
    rows = [
        _visit(op1, start, end=first_end),
        _visit(op2, first_end, end=first_end + timedelta(minutes=20)),
    ]
    assert _codes_from(exchange_pool_violations(loaded, rows), ReasonCode.EXCHANGE_POOL_STOCKOUT)


def test_rotable_available_at_the_start_is_not_early() -> None:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if "SP-BEARING" in row.required_spare_ids)
    start = problem.planning_horizon.start + timedelta(hours=8)
    loaded = _rotable(problem, available_from=start, lag=0)
    rows = [_visit(op, start, end=start + timedelta(minutes=20))]
    messages = [row.message for row in exchange_pool_violations(loaded, rows)]
    assert not any("not available at operation start" in message for message in messages)


def test_rotable_findings_keep_their_suggestion_sentence() -> None:
    problem = synthesize("tiny", seed=1)
    users = [row for row in problem.operations if "SP-BEARING" in row.required_spare_ids][:2]
    start = problem.planning_horizon.start + timedelta(hours=8)
    early = _rotable(problem, available_from=start + timedelta(minutes=1), lag=0)
    early_hit = _one(
        exchange_pool_violations(early, [_visit(users[0], start, end=start + timedelta(minutes=20))]),
        ReasonCode.SPARE_UNAVAILABLE,
    )
    assert early_hit.suggested_relaxation == SUGGESTIONS[ReasonCode.SPARE_UNAVAILABLE]
    invalid = _rotable(problem, available_from=None, lag=True)
    invalid_hit = _one(exchange_pool_violations(invalid, []), ReasonCode.SPARE_UNAVAILABLE)
    assert invalid_hit.suggested_relaxation == SUGGESTIONS[ReasonCode.SPARE_UNAVAILABLE]
    clash = _rotable(problem, available_from=None, lag=0)
    clash_rows = [
        _visit(users[0], start, end=start + timedelta(minutes=20)),
        _visit(users[1], start, end=start + timedelta(minutes=20)),
    ]
    clash_hit = _one(exchange_pool_violations(clash, clash_rows), ReasonCode.SPARE_UNAVAILABLE)
    assert "reused before return" in clash_hit.message
    assert clash_hit.suggested_relaxation == SUGGESTIONS[ReasonCode.SPARE_UNAVAILABLE]


def _preemptive_window() -> tuple[RepairFlowProblem, Operation, str, datetime]:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if not row.required_aux_ids)
    moment = problem.planning_horizon.start + timedelta(hours=8)
    calendar = Calendar(
        id="CAL-EDGE",
        code="CAL-EDGE",
        windows=[CalendarWindow(start=moment, end=moment + timedelta(hours=1))],
    )
    center_id = op.eligible_work_center_ids[0]
    centers = [
        row.model_copy(update={"calendar_id": "CAL-EDGE"}) if row.id == center_id else row
        for row in problem.work_centers
    ]
    attrs = {**op.domain_attributes, "duration_policy": "preemptive"}
    edited = op.model_copy(update={"domain_attributes": attrs, "required_aux_ids": [], "duration_min": 30})
    loaded = _reload(
        _with_op(problem, edited),
        calendars=[*problem.calendars, calendar],
        work_centers=centers,
    )
    return loaded, edited, center_id, moment


def _rotable(
    problem: RepairFlowProblem,
    *,
    available_from: datetime | None,
    lag: object,
) -> RepairFlowProblem:
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    spares = [
        spare.model_copy(
            update={
                "quantity": 1,
                "available_from": available_from,
                "domain_attributes": {"kind": "rotable", "return_lag_min": lag},
            }
        )
        if row.id == spare.id
        else row
        for row in problem.spares
    ]
    return _reload(problem, spares=spares)


def _spare_problem(
    problem: RepairFlowProblem,
    op: Operation,
    *,
    quantity: int,
    available_from: datetime | None,
    receipts: tuple[SpareReceipt, ...],
    needs: tuple[SpareNeed, ...] = (),
) -> RepairFlowProblem:
    edited = _demand(op, needs[0].qty if needs else 1)
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    spares = [
        spare.model_copy(
            update={
                "quantity": quantity,
                "available_from": available_from,
                "receipts": list(receipts),
                "domain_attributes": {"kind": "consumable"},
            }
        )
        if row.id == spare.id
        else row
        for row in problem.spares
    ]
    operations = [edited if row.id == op.id else row for row in problem.operations]
    return _reload(problem, operations=operations, spares=spares)


def _demand(op: Operation, qty: int) -> Operation:
    return op.model_copy(
        update={
            "required_spare_ids": ["SP-BEARING"],
            "required_spares": [SpareNeed(spare_id="SP-BEARING", qty=qty)],
        }
    )


def _with_op(problem: RepairFlowProblem, edited: Operation) -> RepairFlowProblem:
    operations = [edited if row.id == edited.id else row for row in problem.operations]
    return _reload(problem, operations=operations)


def _with_job_dates(
    problem: RepairFlowProblem,
    job_id: str,
    *,
    due: datetime | None,
    deadline: datetime | None,
) -> RepairFlowProblem:
    jobs = [
        row.model_copy(update={"due_date": due, "deadline": deadline, "release_date": None})
        if row.id == job_id
        else row
        for row in problem.jobs
    ]
    return _reload(problem, jobs=jobs)


def _freeze(placed: PlannedAssignment, *, crew_id: str | None) -> FrozenAssignment:
    return FrozenAssignment(
        operation_id=placed.operation_id,
        work_center_id=placed.work_center_id,
        crew_id=crew_id,
        start=placed.start,
        end=placed.end,
        setup_minutes=placed.setup_minutes,
        immutable=True,
    )


def _visit(op: Operation, start: datetime, **updates: object) -> PlannedAssignment:
    end = updates.pop("end", start + timedelta(minutes=op.duration_min))
    work_center_id = updates.pop("work_center_id", op.eligible_work_center_ids[0])
    crew_id = updates.pop("crew_id", None)
    aux_ids = updates.pop("aux_ids", [])
    setup_minutes = updates.pop("setup_minutes", 0)
    return PlannedAssignment(
        operation_id=op.id,
        work_center_id=str(work_center_id),
        start=start,
        end=end,  # type: ignore[arg-type]
        crew_id=crew_id,  # type: ignore[arg-type]
        aux_ids=list(aux_ids),  # type: ignore[arg-type]
        setup_minutes=int(setup_minutes),  # type: ignore[arg-type]
    )


def _reload(problem: RepairFlowProblem, **updates: object) -> RepairFlowProblem:
    return RepairFlowProblem.model_validate(problem.model_copy(update=updates).model_dump(mode="python"))


def _codes(problem: RepairFlowProblem, rows: list[PlannedAssignment], code: ReasonCode) -> bool:
    return _codes_from(check_domain_assignments(problem, rows), code)


def _codes_from(violations: list[Violation], code: ReasonCode) -> bool:
    return any(row.code == code for row in violations)


def _one(violations: list[Violation], code: ReasonCode) -> Violation:
    found = [row for row in violations if row.code == code]
    assert len(found) == 1, [row.message for row in violations]
    return found[0]
