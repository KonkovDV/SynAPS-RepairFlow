from repairflow.cli import main


def test_broken_demo_exits_2(tmp_path) -> None:
    problem = tmp_path / "tiny.json"
    plan_path = tmp_path / "greed.json"
    assert main(["synthesize", "--preset", "tiny", "--out", str(problem)]) == 0
    assert main(["solve", str(problem), "--preset", "GREED", "--out", str(plan_path)]) == 0
    from json import loads

    from repairflow.model import PlannedAssignment, RepairFlowProblem, RepairFlowResult
    from repairflow.planner import recheck
    from repairflow.synthetic import corrupt_plan

    instance = RepairFlowProblem.model_validate_json(problem.read_text(encoding="utf-8"))
    result = RepairFlowResult.model_validate_json(plan_path.read_text(encoding="utf-8"))
    broken = corrupt_plan([row.model_dump(mode="json") for row in result.assignments])
    outcome = recheck(
        instance,
        assignments=[PlannedAssignment.model_validate(row) for row in broken],
        kernel_status=result.kernel_status,
        solver_config="broken-seed42",
    )
    assert outcome.result.exit_code == 2
    assert not outcome.result.verified_feasible
    assert loads(plan_path.read_text(encoding="utf-8"))["verified_feasible"] is True
