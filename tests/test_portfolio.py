from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_cpsat_tiny_is_optimal_and_verified() -> None:
    outcome = plan(synthesize("tiny", seed=1), solver_config="CPSAT-10")
    assert outcome.result.status.value == "OPTIMAL"
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0
    assert len(outcome.result.assignments) == len(outcome.problem.operations)


def test_rhc_greedy_cover_tiny_is_verified() -> None:
    outcome = plan(synthesize("tiny", seed=1), solver_config="RHC-GREEDY-COVER")
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0
    assert outcome.result.status.value == "HEURISTIC_FEASIBLE"
