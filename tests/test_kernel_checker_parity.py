"""Kernel/checker parity tests for supported kernel-compatible instances."""

from __future__ import annotations

from repairflow.kernel_compat import KERNEL_CALENDAR_UNSUPPORTED
from repairflow.model import RepairFlowProblem, PlannedAssignment
from repairflow.planner import kernel_hard_violations, plan, recheck
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
