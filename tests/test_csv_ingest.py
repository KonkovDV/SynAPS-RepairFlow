from repairflow.normalize import load_problem, write_csv_bundle
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_csv_bundle_roundtrip(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    bundle = tmp_path / "tiny-csv"
    write_csv_bundle(bundle, problem)
    loaded = load_problem(bundle)
    assert [op.id for op in loaded.operations] == [op.id for op in problem.operations]
    assert [job.id for job in loaded.jobs] == [job.id for job in problem.jobs]
    greed = plan(loaded, solver_config="GREED")
    assert greed.result.verified_feasible
    assert greed.result.exit_code == 0
