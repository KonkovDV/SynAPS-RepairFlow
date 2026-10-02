"""Deletion-minimal domain witnesses.

The result is a smallest-by-deletion set of operation ids that still produces
one hard reason code. It is an explanation beside the verdict. It is not a
CP-MUS, not an MCS, and not an IIS. `plan` and `recheck` do not call it, and
it does not change `verified`.
"""

from __future__ import annotations

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_plan
from repairflow.model import PlannedAssignment, RepairFlowProblem, Violation


def _witness(row: Violation) -> tuple[str, str, str, str]:
    missing = row.details.get("missing_predecessor")
    return (
        row.code,
        row.operation_id or "",
        row.resource_id or "",
        str(missing or ""),
    )


def deletion_minimal_operation_ids(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    code: str,
) -> list[str]:
    """Return a deletion-minimal set of operations that still raises `code`."""

    schedule_problem, id_map = to_schedule_problem(problem)
    operation_ids = {op.id for op in problem.operations}

    def has(kept: set[str], expected: set[tuple[str, str, str, str]]) -> bool:
        subset = [row for row in assignments if row.operation_id in kept]
        found = check_plan(
            problem,
            schedule_problem=schedule_problem,
            assignments=subset,
            id_map=id_map,
            kernel_status="feasible",
            subset_mode=True,
        )
        found_keys = {_witness(row) for row in found if row.severity == "hard"}
        return bool(expected & found_keys)

    full = check_plan(
        problem,
        schedule_problem=schedule_problem,
        assignments=list(assignments),
        id_map=id_map,
        kernel_status="feasible",
    )
    expected = {_witness(row) for row in full if row.code == code and row.severity == "hard"}
    involved: list[str] = []
    for row in full:
        if row.code != code or row.severity != "hard":
            continue
        if row.operation_id in operation_ids:
            involved.append(row.operation_id)
        if row.resource_id in operation_ids:
            involved.append(row.resource_id)
        other = row.details.get("other_operation_id")
        if isinstance(other, str) and other in operation_ids:
            involved.append(other)
    current = set(involved)
    if not current or not has(current, expected):
        raise ValueError(f"{code} is not a hard violation of these assignments")
    changed = True
    while changed:
        changed = False
        for operation_id in sorted(current):
            trial = current - {operation_id}
            if trial and has(trial, expected):
                current = trial
                changed = True
                break
    return sorted(current)
