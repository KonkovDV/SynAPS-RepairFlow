from repairflow.planner import plan
from repairflow.synthetic import synthesize


def _skilled_ops_have_named_crews(solver_config: str) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config=solver_config)
    ops = {op.id: op for op in problem.operations}
    skilled = [row for row in outcome.result.assignments if ops[row.operation_id].required_skills]
    assert skilled
    assert all(row.crew_id for row in skilled)
    crews = {crew.id for crew in problem.crews}
    assert all(row.crew_id in crews for row in skilled)


def test_greed_assigns_a_named_crew() -> None:
    _skilled_ops_have_named_crews("GREED")


def test_cpsat_assigns_a_named_crew() -> None:
    _skilled_ops_have_named_crews("CPSAT-10")


def test_rhc_assigns_a_named_crew() -> None:
    _skilled_ops_have_named_crews("RHC-GREEDY-COVER")
