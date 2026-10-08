"""A skipped row must not swallow the next finding.

These tests target `continue` changed to `break` in the notary loops.
The mutation run that measured 1120/1921 did not include them.
"""

from __future__ import annotations

from datetime import timedelta

from repairflow.checker import _precedence, check_domain_assignments
from repairflow.model import FrozenAssignment, PlannedAssignment, PredecessorLink, RepairFlowProblem
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
