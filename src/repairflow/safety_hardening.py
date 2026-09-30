"""Runtime hardening for independent, fail-closed verification.

This module is deliberately small and dependency-free beyond the domain models. It
is installed from ``repairflow.__init__`` so every public import receives the same
safety gates, including direct checker use in tests and downstream integrations.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from repairflow.model import Calendar, Operation, PlannedAssignment, RepairFlowProblem
from repairflow.reasons import ReasonCode, SUGGESTIONS

_INSTALLED = False


def reverse_ids(id_map: dict[str, UUID]) -> dict[UUID, tuple[str, str]]:
    """Reverse a domain UUID map without importing the planner adapter."""
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
    """Independent setup lookup used by the checker and planner fallback."""
    specific: int | None = None
    generic: int | None = None
    for entry in problem.setup_matrix:
        if entry.from_state != from_state or entry.to_state != to_state:
            continue
        if entry.work_center_id == work_center_id:
            specific = entry.duration_min
        elif entry.work_center_id is None:
            generic = entry.duration_min
    if specific is not None:
        return specific
    if generic is not None:
        return generic
    return 0 if from_state == to_state else None


def bind_concrete_crews(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[PlannedAssignment]:
    """Bind skill-pool assignments using checker-owned deterministic logic."""
    operations = {op.id: op for op in problem.operations}
    occupied: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    bound: list[PlannedAssignment] = []
    for assignment in sorted(assignments, key=lambda row: (row.start, row.operation_id)):
        crew_id = assignment.crew_id
        operation = operations.get(assignment.operation_id)
        if crew_id is None and operation is not None and operation.required_skills:
            crew_id = _pick_crew(problem, operation, assignment, occupied)
        if crew_id is not None:
            occupied[crew_id].append(
                (assignment.start - timedelta(minutes=assignment.setup_minutes), assignment.end)
            )
        reason = assignment.reason
        if crew_id and crew_id != assignment.crew_id:
            reason = f"{reason} bound_crew={crew_id}".strip()
        bound.append(assignment.model_copy(update={"crew_id": crew_id, "reason": reason}))
    by_id = {row.operation_id: row for row in bound}
    return [by_id.get(row.operation_id, row) for row in assignments]


def _pick_crew(
    problem: RepairFlowProblem,
    operation: Operation,
    assignment: PlannedAssignment,
    occupied: dict[str, list[tuple[datetime, datetime]]],
) -> str | None:
    required = set(operation.required_skills)
    eligible = [crew for crew in problem.crews if required <= set(crew.skills)]
    for crew in sorted(eligible, key=lambda row: row.id):
        start = assignment.start - timedelta(minutes=assignment.setup_minutes)
        overlaps = sum(start < end and other_start < assignment.end for other_start, end in occupied[crew.id])
        if overlaps < crew.max_parallel:
            return crew.id
    return None


def _strict_coverage(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> list[Any]:
    """Coverage is a safety property, never an opt-out policy."""
    import repairflow.checker as checker

    assigned = {row.operation_id for row in assignments}
    return [
        checker._violation(
            ReasonCode.PARTIAL_COVERAGE,
            f"operation {op.id} has no assignment",
            operation_id=op.id,
            job_id=op.job_id,
            suggested_relaxation=SUGGESTIONS[ReasonCode.PARTIAL_COVERAGE],
        )
        for op in problem.operations
        if op.id not in assigned
    ]


def _strict_calendar_fit(
    calendar: Calendar | None,
    assignment: PlannedAssignment,
    occ_start: datetime,
    *,
    resource_id: str,
) -> list[Any]:
    import repairflow.checker as checker

    if calendar is None:
        return []
    if any(occ_start >= window.start and assignment.end <= window.end for window in calendar.windows):
        return []
    return [
        checker._violation(
            ReasonCode.CALENDAR_BROKEN,
            "occupancy is not contained in a single calendar window",
            operation_id=assignment.operation_id,
            resource_id=resource_id,
            start=assignment.start,
            end=assignment.end,
            suggested_relaxation=SUGGESTIONS[ReasonCode.WINDOW_BROKEN],
        )
    ]


def _with_aux_calendars(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> list[Any]:
    import repairflow.checker as checker

    violations = _ORIGINAL_CALENDAR_CHECK(problem, assignments)
    calendars = {row.id: row for row in problem.calendars}
    aux = {row.id: row for row in problem.aux_resources}
    for assignment in assignments:
        occ_start = assignment.start - timedelta(minutes=assignment.setup_minutes)
        for aux_id in assignment.aux_ids:
            resource = aux.get(aux_id)
            if resource is not None and resource.calendar_id is not None:
                violations.extend(
                    _strict_calendar_fit(
                        calendars.get(resource.calendar_id),
                        assignment,
                        occ_start,
                        resource_id=resource.id,
                    )
                )
    return violations


def install() -> None:
    global _INSTALLED, _ORIGINAL_CALENDAR_CHECK
    if _INSTALLED:
        return
    import repairflow.checker as checker
    import repairflow.planner as planner

    _ORIGINAL_CALENDAR_CHECK = checker._calendars_windows_horizon
    checker.reverse_ids = reverse_ids
    checker.lookup_setup_minutes = lookup_setup_minutes
    checker.bind_concrete_crews = bind_concrete_crews
    checker._coverage = _strict_coverage
    checker._calendar_fit = _strict_calendar_fit
    checker._calendars_windows_horizon = _with_aux_calendars
    planner.reverse_ids = reverse_ids
    planner.lookup_setup_minutes = lookup_setup_minutes
    planner.bind_concrete_crews = bind_concrete_crews
    original_classify = planner.classify_result

    def classify_fail_closed(*args: Any, **kwargs: Any) -> Any:
        kwargs["allow_partial"] = False
        return original_classify(*args, **kwargs)

    planner.classify_result = classify_fail_closed
    _INSTALLED = True


_ORIGINAL_CALENDAR_CHECK: Any = None
