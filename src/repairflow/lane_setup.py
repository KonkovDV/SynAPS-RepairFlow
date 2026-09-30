"""Reference semantics for setup on fungible parallel work-centre lanes.

A parallel work centre has independent lane state. Setup on one lane must not
silently change the state of another lane. The checker and the domain list
scheduler both call this oracle. It does not import solver search code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from repairflow.checker_primitives import lookup_setup_minutes
from repairflow.model import PlannedAssignment, RepairFlowProblem


@dataclass(frozen=True, slots=True)
class LanePlacement:
    operation_id: str
    work_center_id: str
    lane_index: int
    occupancy_start: datetime
    end: datetime
    previous_operation_id: str | None
    previous_state: str
    expected_setup_minutes: int | None


def lane_local_setup_placements(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[LanePlacement]:
    """Colour half-open assignments and resolve setup transitions per lane.

    Intervals are ordered deterministically by occupancy start, end and ID.
    An existing lane is reusable when its previous occupancy ends at or before
    the next occupancy start. Among reusable lanes, the one that became free
    earliest wins, and the lower index breaks a tie. A missing setup cell
    remains ``None``. Overflow raises instead of serialising the extra visit.
    """

    placements, overflows = _colour_lanes(problem, assignments)
    if overflows:
        centre_id, capacity = overflows[0]
        raise ValueError(f"assignments exceed capacity {capacity} on work center {centre_id}")
    return placements


def lane_setup_evidence(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[LanePlacement]:
    """Lane setup for visits that fit. Overflow visits stay a capacity finding."""

    placements, _overflows = _colour_lanes(problem, assignments)
    return placements


def _colour_lanes(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> tuple[list[LanePlacement], list[tuple[str, int]]]:
    operations = {row.id: row for row in problem.operations}
    centres = {row.id: row for row in problem.work_centers}
    grouped: dict[str, list[PlannedAssignment]] = {}
    for assignment in assignments:
        grouped.setdefault(assignment.work_center_id, []).append(assignment)

    result: list[LanePlacement] = []
    overflows: list[tuple[str, int]] = []
    for centre_id, rows in grouped.items():
        centre = centres.get(centre_id)
        capacity = centre.max_parallel if centre is not None else 1
        lanes: list[tuple[datetime, str | None, str]] = []
        ordered = sorted(
            rows,
            key=lambda row: (
                row.start - timedelta(minutes=row.setup_minutes),
                row.end,
                row.operation_id,
            ),
        )
        for row in ordered:
            occupancy_start = row.start - timedelta(minutes=row.setup_minutes)
            reusable = [(index, lane) for index, lane in enumerate(lanes) if lane[0] <= occupancy_start]
            if reusable:
                lane_index, (_end, previous_id, previous_state) = min(
                    reusable,
                    key=lambda item: (item[1][0], item[0]),
                )
            elif len(lanes) < capacity:
                lane_index = len(lanes)
                previous_id = None
                previous_state = "idle"
                lanes.append((row.end, None, ""))
            else:
                overflows.append((centre_id, capacity))
                continue
            operation = operations.get(row.operation_id)
            state = operation.setup_state if operation is not None else ""
            expected = lookup_setup_minutes(
                problem,
                work_center_id=centre_id,
                from_state=previous_state,
                to_state=state,
            )
            lanes[lane_index] = (row.end, row.operation_id, state)
            result.append(
                LanePlacement(
                    operation_id=row.operation_id,
                    work_center_id=centre_id,
                    lane_index=lane_index,
                    occupancy_start=occupancy_start,
                    end=row.end,
                    previous_operation_id=previous_id,
                    previous_state=previous_state,
                    expected_setup_minutes=expected,
                )
            )
    ordered_result = sorted(result, key=lambda row: (row.occupancy_start, row.operation_id))
    return ordered_result, overflows
