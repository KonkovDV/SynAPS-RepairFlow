from datetime import timedelta

from repairflow.diff import diff_plans
from repairflow.planner import plan, replan_after_disruption
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_frozen_assignment_survives_replan() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    greed = plan(problem, solver_config="GREED")
    assert greed.result.verified_feasible
    disrupted = ["JOB-06-02"]
    repaired = replan_after_disruption(
        problem,
        base=greed,
        disrupted_operation_ids=disrupted,
    )
    payload = diff_plans(problem, greed.result, repaired.result)
    assert payload["broken_frozen_assignments"] == []
    assert payload["unchanged_frozen_assignments"]


def test_moved_frozen_is_a_hard_violation() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    greed = plan(problem, solver_config="GREED")
    frozen = problem.frozen_assignments[0]
    rows = []
    for row in greed.result.assignments:
        if row.operation_id == frozen.operation_id:
            rows.append(row.model_copy(update={"start": row.start + timedelta(hours=3)}))
        else:
            rows.append(row)
    from repairflow.planner import recheck

    outcome = recheck(
        problem,
        assignments=rows,
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert any(row.code == ReasonCode.FROZEN_MOVED for row in outcome.result.violations)
    assert outcome.result.exit_code == 2
