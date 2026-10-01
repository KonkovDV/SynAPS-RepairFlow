from repairflow.model import RepairFlowProblem
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def _kernel_compatible_problem() -> RepairFlowProblem:
    problem = synthesize("tiny", seed=1)
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def test_cpsat_tiny_is_optimal_and_verified() -> None:
    outcome = plan(_kernel_compatible_problem(), solver_config="CPSAT-10")
    assert outcome.result.status.value == "OPTIMAL"
    assert outcome.result.claim_status == "optimal"
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0
    assert len(outcome.result.assignments) == len(outcome.problem.operations)


def test_rhc_greedy_cover_tiny_is_verified() -> None:
    outcome = plan(_kernel_compatible_problem(), solver_config="RHC-GREEDY-COVER")
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0
    assert outcome.result.status.value == "HEURISTIC_FEASIBLE"
