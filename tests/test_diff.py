from repairflow.diff import diff_plans
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_compare_fifo_and_greed() -> None:
    problem = synthesize("tiny", seed=1)
    fifo = plan(problem, solver_config="FIFO")
    greed = plan(problem, solver_config="GREED")
    payload = diff_plans(problem, fifo.result, greed.result)
    assert payload["schema_version"] == "repairflow.diff.v1"
    assert payload["metrics"]["baseline_violations"] >= payload["metrics"]["candidate_violations"]
