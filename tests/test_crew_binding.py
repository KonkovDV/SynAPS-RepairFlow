from repairflow.model import RepairFlowProblem
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def _without_auxiliary_calendars(problem: RepairFlowProblem) -> RepairFlowProblem:
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def _skilled_ops_have_named_crews(solver_config: str, *, kernel: bool) -> None:
    problem = synthesize("tiny", seed=1)
    if kernel:
        problem = _without_auxiliary_calendars(problem)
    outcome = plan(problem, solver_config=solver_config)
    ops = {op.id: op for op in problem.operations}
    skilled = [row for row in outcome.result.assignments if ops[row.operation_id].required_skills]
    assert skilled
    assert all(row.crew_id for row in skilled)
    crews = {crew.id for crew in problem.crews}
    assert all(row.crew_id in crews for row in skilled)


def test_greed_assigns_a_named_crew() -> None:
    _skilled_ops_have_named_crews("GREED", kernel=False)


def test_cpsat_assigns_a_named_crew_without_auxiliary_calendars() -> None:
    _skilled_ops_have_named_crews("CPSAT-10", kernel=True)


def test_rhc_assigns_a_named_crew_without_auxiliary_calendars() -> None:
    _skilled_ops_have_named_crews("RHC-GREEDY-COVER", kernel=True)
