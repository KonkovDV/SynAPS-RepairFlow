from datetime import timedelta

from repairflow.planner import plan, recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import corrupt_plan, synthesize


def test_checker_flags_overlap_skill_and_moved_slot() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    assert greed.result.verified_feasible
    broken = corrupt_plan([row.model_dump(mode="json") for row in greed.result.assignments])
    from repairflow.model import PlannedAssignment

    outcome = recheck(
        problem,
        assignments=[PlannedAssignment.model_validate(row) for row in broken],
        kernel_status=greed.result.kernel_status,
        solver_config="broken",
    )
    assert outcome.result.exit_code == 2
    codes = {row.code for row in outcome.result.violations}
    assert ReasonCode.CENTER_OVERLAP in codes or ReasonCode.CREW_OVERLAP in codes
    assert ReasonCode.SKILL_MISMATCH in codes


def test_missing_kernel_status_is_not_green() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    outcome = recheck(
        problem,
        assignments=list(greed.result.assignments),
        kernel_status=None,
        solver_config="recheck",
    )
    assert outcome.result.exit_code == 2
    assert any(row.code == ReasonCode.KERNEL_STATUS_MISSING for row in outcome.result.violations)


def test_broken_precedence_is_caught() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    by_id = {row.operation_id: row for row in greed.result.assignments}
    child = next(op for op in problem.operations if op.predecessor_ids)
    pred = by_id[child.predecessor_ids[0]]
    rows = []
    for row in greed.result.assignments:
        if row.operation_id == child.id:
            start = pred.start - timedelta(minutes=5)
            rows.append(row.model_copy(update={"start": start, "end": start + timedelta(minutes=30)}))
        else:
            rows.append(row.model_copy(deep=True))
    outcome = recheck(
        problem,
        assignments=rows,
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert any(row.code == ReasonCode.PRECEDENCE_BROKEN for row in outcome.result.violations)
