"""Explicit compatibility checks for the pinned SynAPS kernel."""

from __future__ import annotations

from repairflow.model import RepairFlowProblem

KERNEL_CALENDAR_UNSUPPORTED = "KERNEL_CALENDAR_UNSUPPORTED"


def unsupported_auxiliary_calendars(problem: RepairFlowProblem) -> list[str]:
    """Return auxiliary resources whose calendars the pinned kernel cannot model."""

    resources: list[str] = []
    for crew in problem.crews:
        if crew.calendar_id is not None:
            resources.append(f"crew:{crew.id}:{crew.calendar_id}")
    for aux in problem.aux_resources:
        if aux.calendar_id is not None:
            resources.append(f"aux:{aux.id}:{aux.calendar_id}")
    return resources


def assert_kernel_calendar_compatibility(problem: RepairFlowProblem) -> None:
    """Fail closed instead of silently dropping auxiliary calendar constraints."""

    unsupported = unsupported_auxiliary_calendars(problem)
    if unsupported:
        joined = ", ".join(unsupported)
        raise ValueError(f"{KERNEL_CALENDAR_UNSUPPORTED}: {joined}")
