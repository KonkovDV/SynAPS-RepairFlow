from repairflow.diff import diff_plans
from repairflow.model import FrozenAssignment
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_compare_fifo_and_greed() -> None:
    problem = synthesize("tiny", seed=1)
    fifo = plan(problem, solver_config="FIFO")
    greed = plan(problem, solver_config="GREED")
    payload = diff_plans(problem, fifo.result, greed.result)
    assert payload["schema_version"] == "repairflow.diff.v1"
    assert payload["metrics"]["baseline_violations"] >= payload["metrics"]["candidate_violations"]


def test_a_changed_setup_breaks_the_freeze() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    row = greed.result.assignments[0]
    frozen = problem.model_copy(
        update={
            "frozen_assignments": [
                FrozenAssignment(
                    operation_id=row.operation_id,
                    work_center_id=row.work_center_id,
                    crew_id=row.crew_id,
                    start=row.start,
                    end=row.end,
                    setup_minutes=row.setup_minutes,
                )
            ]
        }
    )
    changed = row.model_copy(update={"setup_minutes": row.setup_minutes + 5})
    candidate = greed.result.model_copy(
        update={
            "assignments": [
                changed if item.operation_id == row.operation_id else item
                for item in greed.result.assignments
            ]
        }
    )
    payload = diff_plans(frozen, greed.result, candidate)
    assert payload["churn"]["broken_frozen"] == 1
    held = diff_plans(frozen, greed.result, greed.result)
    assert held["churn"]["broken_frozen"] == 0
