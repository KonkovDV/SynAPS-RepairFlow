"""Explicit compatibility checks for the pinned SynAPS kernel."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from repairflow.model import Operation, RepairFlowProblem
from repairflow.scheduling_contract import is_unattended, policy_of

KERNEL_CALENDAR_UNSUPPORTED = "KERNEL_CALENDAR_UNSUPPORTED"
Window = tuple[datetime, datetime]


def kernel_calendar_windows(
    problem: RepairFlowProblem,
    calendar_id: str | None,
    attributes: Mapping[str, Any],
) -> list[Window] | None:
    """Windows SynAPS can store on a resource.

    An empty list is the kernel's 24/7 calendar: the domain resource has no
    calendar, or it is unattended. A non-empty list is one published shift
    list. ``None`` means the attended calendar has no windows. That is closed
    in this domain and must not be compiled as an empty kernel list.
    """

    if is_unattended(attributes) or not calendar_id:
        return []
    calendar = next((row for row in problem.calendars if row.id == calendar_id), None)
    if calendar is None or not calendar.windows:
        return None
    return [(window.start, window.end) for window in calendar.windows]


def unsupported_auxiliary_calendars(problem: RepairFlowProblem) -> list[str]:
    """Return crew and aux calendars the kernel would otherwise drop or invert."""

    from repairflow.adapter import _bound_crew, _crews_for_skills

    resources: list[str] = []
    crews_by_id = {crew.id: crew for crew in problem.crews}
    for crew in problem.crews:
        if kernel_calendar_windows(problem, crew.calendar_id, crew.domain_attributes) is None:
            resources.append(f"crew:{crew.id}:{crew.calendar_id}")
    for aux in problem.aux_resources:
        if kernel_calendar_windows(problem, aux.calendar_id, aux.domain_attributes) is None:
            resources.append(f"aux:{aux.id}:{aux.calendar_id}")

    pools: dict[str, list[str]] = {}
    for operation in problem.operations:
        if _bound_crew(problem, operation) is not None or not operation.required_skills:
            continue
        key = "|".join(sorted(operation.required_skills))
        pools.setdefault(key, _crews_for_skills(problem, operation.required_skills))
    for key, crew_ids in pools.items():
        encoded: list[tuple[Window, ...]] = []
        blocked = False
        for crew_id in crew_ids:
            crew = crews_by_id[crew_id]
            windows = kernel_calendar_windows(problem, crew.calendar_id, crew.domain_attributes)
            if windows is None:
                resources.append(f"skillpool:{key}:crew:{crew.id}:{crew.calendar_id}")
                blocked = True
                break
            encoded.append(tuple(windows))
        if not blocked and len(set(encoded)) > 1:
            resources.append(f"skillpool:{key}:mixed")

    for operation in problem.operations:
        if _preemptive_published_calendar(problem, operation, crews_by_id):
            resources.append(f"op:{operation.id}:preemptive")
    return resources


def _preemptive_published_calendar(
    problem: RepairFlowProblem,
    operation: Operation,
    crews_by_id: dict[str, Any],
) -> bool:
    """True when CP-SAT's one-window rule is not the domain preemptive rule."""

    from repairflow.adapter import _bound_crew, _crews_for_skills

    if policy_of(operation.domain_attributes) != "preemptive":
        return False
    bound = _bound_crew(problem, operation)
    if bound is not None:
        crew = crews_by_id[bound]
        if kernel_calendar_windows(problem, crew.calendar_id, crew.domain_attributes):
            return True
    elif operation.required_skills:
        for crew_id in _crews_for_skills(problem, operation.required_skills):
            crew = crews_by_id[crew_id]
            if kernel_calendar_windows(problem, crew.calendar_id, crew.domain_attributes):
                return True
    aux_by_id = {aux.id: aux for aux in problem.aux_resources}
    for aux_id in operation.required_aux_ids:
        aux = aux_by_id.get(aux_id)
        if aux is not None and kernel_calendar_windows(
            problem, aux.calendar_id, aux.domain_attributes
        ):
            return True
    return False


def assert_kernel_calendar_compatibility(problem: RepairFlowProblem) -> None:
    """Fail closed instead of silently dropping auxiliary calendar constraints."""

    unsupported = unsupported_auxiliary_calendars(problem)
    if unsupported:
        joined = ", ".join(unsupported)
        raise ValueError(f"{KERNEL_CALENDAR_UNSUPPORTED}: {joined}")
