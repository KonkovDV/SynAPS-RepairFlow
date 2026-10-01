from __future__ import annotations

from repairflow.model import RepairFlowProblem
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def _without_auxiliary_calendars(problem: RepairFlowProblem) -> RepairFlowProblem:
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def _diamond(seed: int = 1) -> RepairFlowProblem:
    problem = _without_auxiliary_calendars(synthesize("tiny", seed=seed))
    operations = list(problem.operations)
    job_id = operations[0].job_id
    chain = sorted((op for op in operations if op.job_id == job_id), key=lambda op: op.sequence)
    trunk, branch, sink = chain[0], chain[1], chain[2]
    parallel = branch.model_copy(
        update={
            "id": f"{branch.id}-B",
            "sequence": branch.sequence + 1,
            "predecessor_ids": [trunk.id],
            "required_spare_ids": [],
            "required_aux_ids": [],
        }
    )
    joined = sink.model_copy(
        update={
            "sequence": sink.sequence + 1,
            "predecessor_ids": [branch.id, parallel.id],
        }
    )
    payload = problem.model_dump(mode="python")
    payload["operations"] = [joined if row.id == sink.id else row for row in operations] + [parallel]
    return RepairFlowProblem.model_validate(payload)


def test_compiled_dag_never_escapes_into_an_optimal_claim() -> None:
    outcome = plan(_diamond(), solver_config="CPSAT-10")

    assert outcome.result.metadata["optimality_scope"] == "compiled_windows"
    assert outcome.result.claim_status != "optimal"
    assert outcome.result.status.value != "OPTIMAL"
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0


def test_linear_chain_keeps_the_exact_optimal_claim() -> None:
    outcome = plan(_without_auxiliary_calendars(synthesize("tiny", seed=1)), solver_config="CPSAT-10")

    assert outcome.result.metadata["optimality_scope"] == "original_chain"
    assert outcome.result.claim_status == "optimal"
    assert outcome.result.status.value == "OPTIMAL"
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0
