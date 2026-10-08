"""A skipped row must not swallow the next finding.

These tests target `continue` changed to `break` in the notary loops.
The first three are part of run 37743200619 (score 1161/1921). The spare,
auxiliary, and same-post setup tests below that run are not.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from repairflow.checker import _precedence, check_domain_assignments
from repairflow.model import (
    Calendar,
    FrozenAssignment,
    Operation,
    PlannedAssignment,
    PredecessorLink,
    RepairFlowProblem,
    Spare,
    SpareNeed,
    SpareReceipt,
    Violation,
)
from repairflow.planner import plan
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_unknown_row_does_not_hide_the_next_row() -> None:
    problem = synthesize("tiny", seed=1)
    operation = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    held = timedelta(minutes=operation.duration_min)
    rows = [
        PlannedAssignment(
            operation_id="OP-MISSING",
            work_center_id=operation.eligible_work_center_ids[0],
            start=start,
            end=start + held,
        ),
        PlannedAssignment(
            operation_id=operation.id,
            work_center_id="POST-NOPE",
            start=start,
            end=start + held,
        ),
    ]
    violations = check_domain_assignments(problem, rows)
    found = {item.code for item in violations}
    assert ReasonCode.UNKNOWN_OPERATION in found
    assert ReasonCode.UNKNOWN_RESOURCE in found
    assert ReasonCode.ELIGIBLE_CENTER_MISMATCH in found
    assert ReasonCode.MISSING_SETUP in found
    unknown = next(item for item in violations if item.code == ReasonCode.UNKNOWN_OPERATION)
    assert unknown.start == rows[0].start
    assert unknown.end == rows[0].end
    missing_post = next(
        item
        for item in violations
        if item.code == ReasonCode.UNKNOWN_RESOURCE and item.resource_id == "POST-NOPE"
    )
    assert missing_post.start == rows[1].start
    assert missing_post.end == rows[1].end
    assert missing_post.operation_id == operation.id


def test_mutable_freeze_does_not_hide_later_frozen_rows() -> None:
    problem = synthesize("tiny", seed=1)
    issued = plan(problem, solver_config="GREED")
    assert issued.result.verified_feasible
    first, second, third = issued.result.assignments[:3]
    frozen = [
        FrozenAssignment(
            operation_id=first.operation_id,
            work_center_id=first.work_center_id,
            crew_id=first.crew_id,
            start=first.start,
            end=first.end,
            setup_minutes=first.setup_minutes,
            immutable=False,
        ),
        FrozenAssignment(
            operation_id=second.operation_id,
            work_center_id=second.work_center_id,
            crew_id=second.crew_id,
            start=second.start,
            end=second.end,
            setup_minutes=second.setup_minutes,
            immutable=True,
        ),
        FrozenAssignment(
            operation_id=third.operation_id,
            work_center_id=third.work_center_id,
            crew_id=third.crew_id,
            start=third.start,
            end=third.end,
            setup_minutes=third.setup_minutes,
            immutable=True,
        ),
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"frozen_assignments": frozen}).model_dump(mode="python")
    )
    moved = third.model_copy(
        update={"start": third.start + timedelta(minutes=30), "end": third.end + timedelta(minutes=30)}
    )
    violations = check_domain_assignments(loaded, [first, moved])
    frozen_ids = {
        row.operation_id
        for row in violations
        if row.code == ReasonCode.FROZEN_MOVED and row.operation_id is not None
    }
    assert second.operation_id in frozen_ids
    assert third.operation_id in frozen_ids


def test_one_predecessor_does_not_hide_the_next() -> None:
    problem = synthesize("tiny", seed=1)
    successor = next(op for op in problem.operations if op.predecessor_ids)
    descendants: set[str] = set()
    stack = [successor.id]
    while stack:
        node = stack.pop()
        for op in problem.operations:
            if node in op.predecessor_ids and op.id not in descendants:
                descendants.add(op.id)
                stack.append(op.id)
    earlier = next(
        op
        for op in problem.operations
        if op.id != successor.id and op.id not in successor.predecessor_ids and op.id not in descendants
    )
    present_id = successor.predecessor_ids[0]
    links = [
        PredecessorLink(id=earlier.id, min_lag_min=0),
        PredecessorLink(id=present_id, min_lag_min=0),
    ]
    operations = [
        successor.model_copy(update={"predecessor_ids": [earlier.id, present_id], "predecessors": links})
        if op.id == successor.id
        else op
        for op in problem.operations
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"operations": operations}).model_dump(mode="python")
    )
    start = loaded.planning_horizon.start + timedelta(hours=8)
    successor_row = PlannedAssignment(
        operation_id=successor.id,
        work_center_id=successor.eligible_work_center_ids[0],
        start=start,
        end=start + timedelta(minutes=successor.duration_min),
    )
    present = PlannedAssignment(
        operation_id=present_id,
        work_center_id=successor.eligible_work_center_ids[0],
        start=start + timedelta(hours=2),
        end=start + timedelta(hours=2, minutes=30),
    )
    for ignore_absent in (False, True):
        found = _precedence(loaded, [successor_row, present], ignore_absent=ignore_absent)
        assert any(row.operation_id == successor.id and "lag" in row.message for row in found), ignore_absent
        if not ignore_absent:
            assert any(row.details.get("missing_predecessor") == earlier.id for row in found)


def test_unknown_operation_does_not_hide_a_short_receipt() -> None:
    problem = synthesize("tiny", seed=1)
    user = problem.operations[0]
    start = problem.planning_horizon.start
    short = _spare(
        problem,
        "SP-BEARING",
        quantity=0,
        available_from=None,
        receipts=[SpareReceipt(at=start + timedelta(hours=12), qty=1)],
    )
    loaded = _reload(
        problem,
        spares=_replaced(problem.spares, short),
        operations=_demand(problem, user.id, [short.id], {short.id: 1}),
    )
    visit = start + timedelta(hours=8)
    rows = [
        _row("OP-MISSING", user, visit, minutes=10),
        _row(user.id, user, visit, minutes=user.duration_min),
    ]
    hit = _one(
        check_domain_assignments(loaded, rows),
        ReasonCode.SPARE_UNAVAILABLE,
        operation_id=user.id,
        resource_id=short.id,
    )
    assert hit.message == f"spare {short.code} stock is short at {visit.isoformat()}"
    assert hit.start == visit


def test_plain_spare_does_not_hide_a_short_receipt() -> None:
    problem = synthesize("tiny", seed=1)
    user = problem.operations[0]
    start = problem.planning_horizon.start
    plain = _spare(problem, "SP-SEAL", quantity=8, available_from=None, receipts=[])
    short = _spare(
        problem,
        "SP-BEARING",
        quantity=0,
        available_from=None,
        receipts=[SpareReceipt(at=start + timedelta(hours=12), qty=1)],
    )
    loaded = _reload(
        problem,
        spares=_replaced(problem.spares, plain, short),
        operations=_demand(problem, user.id, [plain.id, short.id], {plain.id: 1, short.id: 1}),
    )
    visit = start + timedelta(hours=8)
    hit = _one(
        check_domain_assignments(loaded, [_row(user.id, user, visit, minutes=user.duration_min)]),
        ReasonCode.SPARE_UNAVAILABLE,
        operation_id=user.id,
        resource_id=short.id,
    )
    assert hit.message == f"spare {short.code} stock is short at {visit.isoformat()}"
    assert hit.start == visit


def test_unknown_operation_does_not_hide_an_early_release() -> None:
    problem = synthesize("tiny", seed=1)
    user = problem.operations[0]
    visit = problem.planning_horizon.start + timedelta(hours=8)
    release = visit + timedelta(days=1)
    jobs = [
        job.model_copy(update={"release_date": release}) if job.id == user.job_id else job
        for job in problem.jobs
    ]
    loaded = _reload(problem, jobs=jobs)
    end = visit + timedelta(minutes=user.duration_min)
    rows = [
        _row("OP-MISSING", user, visit, minutes=10),
        _row(user.id, user, visit, minutes=user.duration_min),
    ]
    hit = _one(
        check_domain_assignments(loaded, rows),
        ReasonCode.RELEASE_VIOLATION,
        operation_id=user.id,
    )
    assert hit.message == f"operation {user.id} starts before job release_date"
    assert hit.job_id == user.job_id
    assert hit.start == visit
    assert hit.end == end


def test_receipt_spare_does_not_hide_a_later_spare() -> None:
    problem = synthesize("tiny", seed=1)
    user = problem.operations[0]
    visit = problem.planning_horizon.start + timedelta(hours=8)
    stocked = _spare(
        problem,
        "SP-BEARING",
        quantity=5,
        available_from=None,
        receipts=[SpareReceipt(at=visit, qty=1)],
    )
    ready = visit + timedelta(hours=2)
    delayed = _spare(problem, "SP-SEAL", quantity=5, available_from=ready, receipts=[])
    loaded = _reload(
        problem,
        spares=_replaced(problem.spares, stocked, delayed),
        operations=_demand(
            problem,
            user.id,
            [stocked.id, delayed.id],
            {stocked.id: 1, delayed.id: 1},
        ),
    )
    end = visit + timedelta(minutes=user.duration_min)
    hit = _one(
        check_domain_assignments(loaded, [_row(user.id, user, visit, minutes=user.duration_min)]),
        ReasonCode.SPARE_UNAVAILABLE,
        operation_id=user.id,
        resource_id=delayed.id,
    )
    assert hit.message == f"spare {delayed.code} is not available until {ready.isoformat()}"
    assert hit.job_id == user.job_id
    assert hit.start == visit
    assert hit.end == end


def test_unknown_operation_does_not_hide_spare_overuse() -> None:
    problem = synthesize("tiny", seed=1)
    user = problem.operations[0]
    visit = problem.planning_horizon.start + timedelta(hours=8)
    seal = _spare(problem, "SP-SEAL", quantity=1, available_from=None, receipts=[])
    loaded = _reload(
        problem,
        spares=_replaced(problem.spares, seal),
        operations=_demand(problem, user.id, [seal.id], {seal.id: 2}),
    )
    rows = [
        _row("OP-MISSING", user, visit, minutes=10),
        _row(user.id, user, visit, minutes=user.duration_min),
    ]
    hit = _one(
        check_domain_assignments(loaded, rows),
        ReasonCode.SPARE_UNAVAILABLE,
        resource_id=seal.id,
    )
    assert hit.message == f"spare {seal.code} used 2 times with quantity {seal.quantity}"


def test_receipt_spare_does_not_hide_consumable_overuse() -> None:
    problem = synthesize("tiny", seed=1)
    user = problem.operations[0]
    visit = problem.planning_horizon.start + timedelta(hours=8)
    stocked = _spare(
        problem,
        "SP-BEARING",
        quantity=5,
        available_from=None,
        receipts=[SpareReceipt(at=visit, qty=1)],
    )
    seal = _spare(problem, "SP-SEAL", quantity=1, available_from=None, receipts=[])
    loaded = _reload(
        problem,
        spares=_replaced(problem.spares, stocked, seal),
        operations=_demand(problem, user.id, [stocked.id, seal.id], {stocked.id: 1, seal.id: 2}),
    )
    hit = _one(
        check_domain_assignments(loaded, [_row(user.id, user, visit, minutes=user.duration_min)]),
        ReasonCode.SPARE_UNAVAILABLE,
        resource_id=seal.id,
    )
    assert hit.message == f"spare {seal.code} used 2 times with quantity {seal.quantity}"


def test_unknown_aux_does_not_hide_a_closed_aux_calendar() -> None:
    problem = synthesize("tiny", seed=1)
    user = problem.operations[0]
    visit = problem.planning_horizon.start + timedelta(hours=8)
    closed = Calendar(id="CAL-SHUT", code="CAL-SHUT", windows=[])
    auxes = [
        aux.model_copy(update={"calendar_id": closed.id}) if aux.id == "AUX-JIG" else aux
        for aux in problem.aux_resources
    ]
    operations = [
        op.model_copy(update={"required_aux_ids": []}) if op.id == user.id else op
        for op in problem.operations
    ]
    loaded = _reload(
        problem,
        calendars=[*problem.calendars, closed],
        aux_resources=auxes,
        operations=operations,
    )
    end = visit + timedelta(minutes=user.duration_min)
    row = _row(user.id, user, visit, minutes=user.duration_min).model_copy(
        update={"aux_ids": ["AAA-MISSING", "AUX-JIG"]}
    )
    hit = _one(
        check_domain_assignments(loaded, [row]),
        ReasonCode.CALENDAR_BROKEN,
        resource_id="AUX-JIG",
    )
    assert hit.message == f"calendar {closed.id} has no open windows"
    assert hit.operation_id == user.id
    assert hit.start == visit
    assert hit.end == end


def test_unknown_operation_does_not_hide_setup_on_the_same_post() -> None:
    problem = synthesize("tiny", seed=1)
    user = problem.operations[0]
    visit = problem.planning_horizon.start + timedelta(hours=8)
    later = visit + timedelta(minutes=30)
    end = later + timedelta(minutes=user.duration_min)
    rows = [
        _row("OP-MISSING", user, visit, minutes=30),
        _row(user.id, user, later, minutes=user.duration_min),
    ]
    hit = _one(
        check_domain_assignments(problem, rows),
        ReasonCode.MISSING_SETUP,
        operation_id=user.id,
    )
    assert hit.resource_id == user.eligible_work_center_ids[0]
    assert hit.job_id == user.job_id
    assert hit.start == later
    assert hit.end == end
    assert hit.message.startswith("no setup cell ")


def _reload(problem: RepairFlowProblem, **updates: object) -> RepairFlowProblem:
    return RepairFlowProblem.model_validate(problem.model_copy(update=updates).model_dump(mode="python"))


def _spare(
    problem: RepairFlowProblem,
    spare_id: str,
    *,
    quantity: int,
    available_from: datetime | None,
    receipts: list[SpareReceipt],
) -> Spare:
    current = next(row for row in problem.spares if row.id == spare_id)
    return current.model_copy(
        update={"quantity": quantity, "available_from": available_from, "receipts": receipts}
    )


def _replaced(spares: list[Spare], *updated: Spare) -> list[Spare]:
    by_id = {row.id: row for row in updated}
    return [by_id.get(row.id, row) for row in spares]


def _demand(
    problem: RepairFlowProblem,
    operation_id: str,
    spare_ids: list[str],
    quantities: dict[str, int],
) -> list[Operation]:
    needs = [SpareNeed(spare_id=spare_id, qty=quantities[spare_id]) for spare_id in spare_ids]
    return [
        op.model_copy(update={"required_spare_ids": spare_ids, "required_spares": needs})
        if op.id == operation_id
        else op
        for op in problem.operations
    ]


def _row(
    operation_id: str,
    user: Operation,
    start: datetime,
    *,
    minutes: int,
) -> PlannedAssignment:
    center = user.eligible_work_center_ids[0]
    return PlannedAssignment(
        operation_id=operation_id,
        work_center_id=center,
        start=start,
        end=start + timedelta(minutes=minutes),
    )


def _one(
    violations: list[Violation],
    code: str,
    *,
    operation_id: str | None = None,
    resource_id: str | None = None,
) -> Violation:
    found = [
        row
        for row in violations
        if row.code == code
        and (operation_id is None or row.operation_id == operation_id)
        and (resource_id is None or row.resource_id == resource_id)
    ]
    assert len(found) == 1, [(row.code, row.operation_id, row.resource_id, row.message) for row in found]
    return found[0]
