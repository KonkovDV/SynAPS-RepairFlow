from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_fifo_hashes_are_stable() -> None:
    problem = synthesize("tiny", seed=7)
    left = plan(problem, solver_config="FIFO")
    right = plan(problem, solver_config="FIFO")
    assert left.result.input_hash == right.result.input_hash
    assert left.result.config_hash == right.result.config_hash
    assert left.result.result_hash == right.result.result_hash
    assert [row.model_dump() for row in left.result.assignments] == [
        row.model_dump() for row in right.result.assignments
    ]
