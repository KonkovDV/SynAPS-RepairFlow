from repairflow.planner import plan
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_fifo_is_dirty_and_greed_is_verified() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    fifo = plan(problem, solver_config="FIFO")
    greed = plan(problem, solver_config="GREED")
    assert fifo.result.exit_code == 2
    assert len(fifo.result.violations) > 0
    assert greed.result.exit_code == 0
    assert greed.result.verified_feasible
    assert greed.result.status.value == "HEURISTIC_FEASIBLE"
    codes = {row.code for row in fifo.result.violations}
    assert ReasonCode.SKILL_MISMATCH in codes or ReasonCode.CENTER_OVERLAP in codes


def test_same_seed_same_input_hash() -> None:
    left = plan(synthesize("tiny", seed=1), solver_config="FIFO")
    right = plan(synthesize("tiny", seed=1), solver_config="FIFO")
    assert left.result.input_hash == right.result.input_hash
