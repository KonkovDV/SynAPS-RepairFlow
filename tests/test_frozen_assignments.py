from datetime import timedelta

import pytest

from repairflow.diff import diff_plans
from repairflow.model import RepairFlowProblem
from repairflow.planner import plan, recheck, replan_after_disruption
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
    outcome = recheck(
        problem,
        assignments=rows,
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert any(row.code == ReasonCode.FROZEN_MOVED for row in outcome.result.violations)
    assert outcome.result.exit_code == 2


def test_frozen_crew_matches_operation_skills_across_unit_types() -> None:
    for seed, expected_crew in ((42, "CREW-MECH"), (7, "CREW-ELEC"), (99, "CREW-ELEC")):
        problem = synthesize("repair-site-mvp", seed=seed)
        frozen = problem.frozen_assignments[0]
        operation = next(op for op in problem.operations if op.id == frozen.operation_id)
        crew = next(row for row in problem.crews if row.id == frozen.crew_id)
        assert frozen.crew_id == expected_crew
        assert set(operation.required_skills) <= set(crew.skills)
        greed = plan(problem, solver_config="GREED")
        assert greed.result.verified_feasible, seed
        assert greed.result.exit_code == 0


def test_ingest_rejects_frozen_skill_mismatch() -> None:
    problem = synthesize("repair-site-mvp", seed=7)
    payload = problem.model_dump(mode="python")
    payload["frozen_assignments"][0]["crew_id"] = "CREW-MECH"
    with pytest.raises(ValueError, match="lacks skills"):
        RepairFlowProblem.model_validate(payload)
