"""Parity gaps the pinned kernel does not model, and explanations that do not judge."""

from __future__ import annotations

from pathlib import Path

from tests.test_dag_compiler import _diamond

from repairflow.dag_compiler import compile_dag
from repairflow.explanations import deletion_minimal_operation_ids
from repairflow.model import RepairFlowProblem
from repairflow.planner import kernel_hard_violations, plan, recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize
from repairflow.witnesses import domain_hard_witnesses, kernel_hard_witnesses, same_hard_decision


def _kernel_compatible(problem: RepairFlowProblem) -> RepairFlowProblem:
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def test_rotable_reuse_is_a_domain_hard_decision_when_the_kernel_is_silent() -> None:
    problem = _kernel_compatible(synthesize("tiny", seed=1))
    clean = plan(problem, solver_config="CPSAT-10")
    users = [op.id for op in problem.operations if "SP-BEARING" in op.required_spare_ids][:2]
    assert len(users) == 2
    spares = [
        row.model_copy(
            update={"quantity": 1, "domain_attributes": {"kind": "rotable", "return_lag_min": 10_000}}
        )
        if row.id == "SP-BEARING"
        else row
        for row in problem.spares
    ]
    operations = [
        op.model_copy(update={"required_spare_ids": ["SP-BEARING"]}) if op.id in users else op
        for op in problem.operations
    ]
    loaded = problem.model_copy(update={"spares": spares, "operations": operations})
    outcome = recheck(
        loaded,
        assignments=list(clean.result.assignments),
        kernel_status="feasible",
        solver_config="parity-rotable",
    )
    domain = domain_hard_witnesses(outcome.result.violations)
    kernel = kernel_hard_witnesses(kernel_hard_violations(outcome.schedule_problem, outcome.schedule))

    assert outcome.result.verified_feasible is False
    assert outcome.result.exit_code == 2
    assert outcome.result.claim_status == "rejected"
    assert any(row.code == ReasonCode.SPARE_UNAVAILABLE for row in domain)
    assert kernel == []
    assert same_hard_decision(domain, kernel) is False
    assert all(row.verifier == "domain" for row in domain)
    assert "explanation" not in outcome.result.metadata


def test_rotable_explanation_is_minimal_and_does_not_change_the_verdict() -> None:
    problem = _kernel_compatible(synthesize("tiny", seed=1))
    clean = plan(problem, solver_config="CPSAT-10")
    users = [op.id for op in problem.operations if "SP-BEARING" in op.required_spare_ids][:2]
    spares = [
        row.model_copy(
            update={"quantity": 1, "domain_attributes": {"kind": "rotable", "return_lag_min": 10_000}}
        )
        if row.id == "SP-BEARING"
        else row
        for row in problem.spares
    ]
    operations = [
        op.model_copy(update={"required_spare_ids": ["SP-BEARING"]}) if op.id in set(users) else op
        for op in problem.operations
    ]
    loaded = problem.model_copy(update={"spares": spares, "operations": operations})
    assignments = list(clean.result.assignments)
    before = recheck(
        loaded,
        assignments=assignments,
        kernel_status="feasible",
        solver_config="parity-rotable",
    )
    witness = deletion_minimal_operation_ids(loaded, assignments, ReasonCode.SPARE_UNAVAILABLE)
    after = recheck(
        loaded,
        assignments=assignments,
        kernel_status="feasible",
        solver_config="parity-rotable",
    )

    assert witness == sorted(users)
    reversed_witness = deletion_minimal_operation_ids(
        loaded,
        list(reversed(assignments)),
        ReasonCode.SPARE_UNAVAILABLE,
    )
    assert reversed_witness == witness
    assert before.result.verified_feasible == after.result.verified_feasible is False
    assert before.result.claim_status == after.result.claim_status == "rejected"
    assert before.result.exit_code == after.result.exit_code == 2
    assert [row.code for row in before.result.violations] == [row.code for row in after.result.violations]
    assert "MUS" not in witness
    assert "optimal" not in witness


def test_converged_dag_fixpoint_is_clean_for_both_verifiers_and_not_optimal() -> None:
    problem = _kernel_compatible(_diamond())
    compiled = compile_dag(problem)
    assert compiled.cross_edges
    outcome = plan(problem, solver_config="CPSAT-10")
    domain = domain_hard_witnesses(outcome.result.violations)
    kernel = kernel_hard_witnesses(kernel_hard_violations(outcome.schedule_problem, outcome.schedule))
    fixpoint = outcome.result.metadata["fixpoint"]

    assert fixpoint["converged"] is True
    assert fixpoint["iterations"] > 1
    assert fixpoint["cross_edges"] > 0
    assert domain == []
    assert kernel == []
    assert same_hard_decision(domain, kernel) is True
    assert outcome.result.verified_feasible is True
    assert outcome.result.claim_status == "verified"
    assert outcome.result.claim_status != "optimal"


def test_verdict_path_does_not_import_the_explanation_helper() -> None:
    source = Path("src/repairflow/planner.py").read_text(encoding="utf-8")
    assert "deletion_minimal_operation_ids" not in source
    assert "repairflow.explanations" not in source
