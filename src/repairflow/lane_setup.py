"""Reference semantics for setup on fungible parallel work-centre lanes.

A parallel work centre has independent lane state. Setup on one lane must not
silently change the state of another lane. This module is deliberately pure:
it is a small reference oracle that planner and checker integrations can share
without importing solver search code.
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
    the next occupancy start. The lowest reusable lane index wins. A missing
    setup cell remains ``None`` and is evidence for a fail-closed caller.
    """

    operations = {row.id: row for row in problem.operations}
    centres = {row.id: row for row in problem.work_centers}
    grouped: dict[str, list[PlannedAssignment]] = {}
    for assignment in assignments:
        grouped.setdefault(assignment.work_center_id, []).append(assignment)

    result: list[LanePlacement] = []
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
            reusable = [
                (index, lane)
                for index, lane in enumerate(lanes)
                if lane[0] <= occupancy_start
            ]
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
                raise ValueError(
                    f"assignments exceed capacity {capacity} on work center {centre_id}"
                )
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
    return sorted(result, key=lambda row: (row.occupancy_start, row.operation_id))
