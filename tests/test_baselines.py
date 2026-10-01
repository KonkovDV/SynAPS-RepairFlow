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
    assert greed.result.claim_status == "verified"
    codes = {row.code for row in fifo.result.violations}
    assert ReasonCode.SKILL_MISMATCH in codes or ReasonCode.CENTER_OVERLAP in codes


def test_edd_is_verified_baseline_and_not_optimal() -> None:
    outcome = plan(synthesize("tiny", seed=42), solver_config="EDD")

    assert outcome.result.exit_code == 0
    assert outcome.result.verified_feasible is True
    assert outcome.result.status.value == "HEURISTIC_FEASIBLE"
    assert outcome.result.claim_status == "verified"
    assert outcome.result.claim_status != "optimal"
    assert outcome.result.solver_class == "baseline"
    assert outcome.result.objective["origin"] == "horizon_start"


def test_atc_is_a_local_verified_baseline_and_not_a_synaps_solver() -> None:
    from synaps.solvers.registry import available_solver_configs

    assert "ATC" not in set(available_solver_configs())
    problem = synthesize("tiny", seed=42)
    outcome = plan(problem, solver_config="ATC")
    again = plan(problem, solver_config="ATC")

    assert outcome.result.exit_code == 0
    assert outcome.result.verified_feasible is True
    assert outcome.result.status.value == "HEURISTIC_FEASIBLE"
    assert outcome.result.claim_status == "verified"
    assert outcome.result.claim_status != "optimal"
    assert outcome.result.solver_class == "baseline"
    assert outcome.result.objective["origin"] == "horizon_start"
    assert outcome.schedule.solver_name == "ATC"
    assert outcome.schedule.metadata.get("dispatch_rule") == "repairflow_atc"
    assert outcome.schedule.metadata.get("atc_k") == 2.0
    assert [
        (row.operation_id, row.start, row.end, row.setup_minutes) for row in outcome.result.assignments
    ] == [(row.operation_id, row.start, row.end, row.setup_minutes) for row in again.result.assignments]


def test_same_seed_same_input_hash() -> None:
    left = plan(synthesize("tiny", seed=1), solver_config="FIFO")
    right = plan(synthesize("tiny", seed=1), solver_config="FIFO")
    assert left.result.input_hash == right.result.input_hash
