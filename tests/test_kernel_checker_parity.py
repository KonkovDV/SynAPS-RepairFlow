"""Kernel/checker parity tests for supported kernel-compatible instances.

Parity here is the hard decision: both verifiers accept a clean plan, or both
reject a broken one and `verified` stays false. Kernel diagnostic text is not
required to match the domain reason code.
"""

from __future__ import annotations

from datetime import timedelta

from repairflow.kernel_compat import KERNEL_CALENDAR_UNSUPPORTED
from repairflow.model import PlannedAssignment, RepairFlowProblem
from repairflow.planner import PlanOutcome, kernel_hard_violations, plan, recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def _kernel_compatible_problem() -> RepairFlowProblem:
    problem = synthesize("tiny", seed=1)
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def _clean_kernel_outcome():
    return plan(_kernel_compatible_problem(), solver_config="CPSAT-10")


def _same_center_pair(rows: list[PlannedAssignment]) -> tuple[PlannedAssignment, PlannedAssignment]:
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            if left.work_center_id == right.work_center_id:
                return left, right
    raise AssertionError("kernel fixture did not produce two assignments on one center")


def _rejects(outcome: PlanOutcome, code: ReasonCode) -> None:
    """Both verifiers reject. Diagnostic wording is not compared."""

    assert outcome.result.verified_feasible is False
    assert outcome.result.claim_status not in {"verified", "optimal"}
    assert any(row.code == code and row.severity == "hard" for row in outcome.result.violations)
    assert kernel_hard_violations(outcome.schedule_problem, outcome.schedule)


def test_clean_kernel_result_has_no_independent_or_kernel_hard_violation() -> None:
    outcome = _clean_kernel_outcome()

    assert outcome.result.verified_feasible
    assert not [row for row in outcome.result.violations if row.severity == "hard"]
    assert kernel_hard_violations(outcome.schedule_problem, outcome.schedule) == []


def test_center_overlap_is_rejected_by_both_verifiers() -> None:
    problem = _kernel_compatible_problem()
    clean = plan(problem, solver_config="CPSAT-10")
    left, right = _same_center_pair(list(clean.result.assignments))
    rows = [
        row.model_copy(update={"start": left.start, "end": left.end})
        if row.operation_id == right.operation_id
        else row
        for row in clean.result.assignments
    ]

    outcome = recheck(
        problem,
        assignments=rows,
        kernel_status="FEASIBLE",
        solver_config="parity-center",
    )

    assert outcome.result.verified_feasible is False
    assert any(row.code == ReasonCode.CENTER_OVERLAP for row in outcome.result.violations)
    assert kernel_hard_violations(outcome.schedule_problem, outcome.schedule)


def test_setup_mismatch_is_rejected_by_both_verifiers() -> None:
    problem = _kernel_compatible_problem()
    clean = plan(problem, solver_config="CPSAT-10")
    row = clean.result.assignments[0]
    mutated = [
        item.model_copy(update={"setup_minutes": item.setup_minutes + 1})
        if item.operation_id == row.operation_id
        else item
        for item in clean.result.assignments
    ]

    outcome = recheck(
        problem,
        assignments=mutated,
        kernel_status="FEASIBLE",
        solver_config="parity-setup",
    )

    assert outcome.result.verified_feasible is False
    assert any(row.code == ReasonCode.SETUP_MISMATCH for row in outcome.result.violations)
    assert kernel_hard_violations(outcome.schedule_problem, outcome.schedule)


def test_unsupported_calendar_remains_a_boundary_refusal_not_a_parity_case() -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="CPSAT-10")

    assert outcome.result.verified_feasible is False
    assert any(row.code == KERNEL_CALENDAR_UNSUPPORTED for row in outcome.result.violations)
    assert outcome.result.assignments == []


def test_precedence_break_is_rejected_by_both_verifiers() -> None:
    problem = _kernel_compatible_problem()
    clean = plan(problem, solver_config="CPSAT-10")
    successor = next(op for op in problem.operations if op.predecessor_ids)
    predecessor = next(
        row for row in clean.result.assignments if row.operation_id == successor.predecessor_ids[0]
    )
    duration = next(
        row.end - row.start for row in clean.result.assignments if row.operation_id == successor.id
    )
    rows = [
        row.model_copy(update={"start": predecessor.start, "end": predecessor.start + duration})
        if row.operation_id == successor.id
        else row
        for row in clean.result.assignments
    ]
    outcome = recheck(problem, assignments=rows, kernel_status="FEASIBLE", solver_config="parity-precedence")
    _rejects(outcome, ReasonCode.PRECEDENCE_BROKEN)


def test_ineligible_center_is_rejected_by_both_verifiers() -> None:
    problem = _kernel_compatible_problem()
    clean = plan(problem, solver_config="CPSAT-10")
    operation = next(op for op in problem.operations if op.eligible_work_center_ids == ["POST-TEST"])
    rows = [
        row.model_copy(update={"work_center_id": "POST-U1"}) if row.operation_id == operation.id else row
        for row in clean.result.assignments
    ]
    outcome = recheck(problem, assignments=rows, kernel_status="FEASIBLE", solver_config="parity-eligibility")
    _rejects(outcome, ReasonCode.ELIGIBLE_CENTER_MISMATCH)


def test_work_center_calendar_window_is_rejected_by_both_verifiers() -> None:
    problem = _kernel_compatible_problem()
    clean = plan(problem, solver_config="CPSAT-10")
    operation_id = next(op.id for op in problem.operations if op.id == "JOB-01-03")
    current = next(row for row in clean.result.assignments if row.operation_id == operation_id)
    start = problem.planning_horizon.start + timedelta(hours=22)
    rows = [
        row.model_copy(update={"start": start, "end": start + (current.end - current.start)})
        if row.operation_id == operation_id
        else row
        for row in clean.result.assignments
    ]
    outcome = recheck(problem, assignments=rows, kernel_status="FEASIBLE", solver_config="parity-calendar")
    _rejects(outcome, ReasonCode.CALENDAR_BROKEN)


def test_auxiliary_capacity_is_rejected_by_both_verifiers() -> None:
    problem = _kernel_compatible_problem()
    clean = plan(problem, solver_config="CPSAT-10")
    target_ids = ["JOB-01-01", "JOB-02-01"]
    operations = [
        op.model_copy(update={"required_aux_ids": ["AUX-CRANE"]}) if op.id in target_ids else op
        for op in problem.operations
    ]
    aux_resources = [
        row.model_copy(update={"capacity": 1}) if row.id == "AUX-CRANE" else row
        for row in problem.aux_resources
    ]
    loaded = problem.model_copy(update={"operations": operations, "aux_resources": aux_resources})
    anchor = next(row for row in clean.result.assignments if row.operation_id == target_ids[0])
    rows = [
        row.model_copy(update={"start": anchor.start, "end": anchor.end, "aux_ids": ["AUX-CRANE"]})
        if row.operation_id in target_ids
        else row
        for row in clean.result.assignments
    ]
    outcome = recheck(loaded, assignments=rows, kernel_status="FEASIBLE", solver_config="parity-aux")
    _rejects(outcome, ReasonCode.AUX_OVERLAP)
