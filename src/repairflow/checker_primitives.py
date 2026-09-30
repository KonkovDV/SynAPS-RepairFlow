"""Checker-owned copies of lookup and id mapping.

The notary must not call `repairflow.adapter` or `repairflow.planner`. A bug in
the planner's setup lookup must not hide the same bug from the checker.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from repairflow.model import Operation, PlannedAssignment, RepairFlowProblem


def reverse_ids(id_map: dict[str, UUID]) -> dict[UUID, tuple[str, str]]:
    out: dict[UUID, tuple[str, str]] = {}
    for key, value in id_map.items():
        kind, ident = key.split(":", 1)
        out[value] = (kind, ident)
    return out


def lookup_setup_minutes(
    problem: RepairFlowProblem,
    *,
    work_center_id: str,
    from_state: str,
    to_state: str,
) -> int | None:
    """Return the matrix cell, or None when it is absent."""

    return _setup_cell(problem, work_center_id, from_state, to_state)


def bind_concrete_crews(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[PlannedAssignment]:
    """Name a crew for a skill-pool assignment. Does not invent setup minutes."""

    ops = {op.id: op for op in problem.operations}
    occupied: dict[str, list[tuple[datetime, datetime]]] = {crew.id: [] for crew in problem.crews}
    bound: list[PlannedAssignment] = []
    for assignment in sorted(assignments, key=lambda row: (row.start, row.operation_id)):
        crew_id = assignment.crew_id
        operation = ops.get(assignment.operation_id)
        if crew_id is None and operation is not None and operation.required_skills:
            crew_id = _pick_free_crew(problem, assignment, occupied, operation)
        if crew_id:
            occ_start = assignment.start - timedelta(minutes=int(assignment.setup_minutes or 0))
            occupied.setdefault(crew_id, []).append((occ_start, assignment.end))
        if crew_id == assignment.crew_id:
            bound.append(assignment)
            continue
        reason = assignment.reason
        if crew_id:
            reason = f"{reason} bound_crew={crew_id}".strip()
        bound.append(assignment.model_copy(update={"crew_id": crew_id, "reason": reason}))
    by_op = {row.operation_id: row for row in bound}
    return [by_op.get(row.operation_id, row) for row in assignments]


def _setup_cell(
    problem: RepairFlowProblem,
    work_center_id: str,
    from_state: str,
    to_state: str,
) -> int | None:
    specific = None
    generic = None
    for entry in problem.setup_matrix:
        if entry.from_state != from_state or entry.to_state != to_state:
            continue
        if entry.work_center_id == work_center_id:
            specific = entry.duration_min
        elif entry.work_center_id is None:
            generic = entry.duration_min
    if specific is not None:
        return specific
    return generic


def _pick_free_crew(
    problem: RepairFlowProblem,
    assignment: PlannedAssignment,
    occupied: dict[str, list[tuple[datetime, datetime]]],
    operation: Operation,
) -> str | None:
    occ_start = assignment.start - timedelta(minutes=int(assignment.setup_minutes or 0))
    eligible = [crew for crew in problem.crews if set(operation.required_skills) <= set(crew.skills)]
    eligible.sort(key=lambda crew: crew.id)
    for crew in eligible:
        overlaps = sum(
            1 for start, end in occupied.get(crew.id, []) if occ_start < end and start < assignment.end
        )
        if overlaps < crew.max_parallel:
            return crew.id
    return None
