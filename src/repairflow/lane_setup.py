"""Reference semantics for setup on fungible parallel work-centre lanes.

A parallel work centre has independent lane state. Setup on one lane must not
silently change the state of another lane. The checker and the domain list
scheduler both call this oracle. It does not import solver search code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
    ambiguous: bool = False


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


def stamp_canonical_lanes(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[PlannedAssignment]:
    """Producer-side witness: write the canonical lane colouring into the plan.

    Only the planner calls this for its own candidates. A submitted plan is never
    stamped by the checker, so an ambiguous submission stays refused. A stamped plan
    is checked against the explicit lanes, which is a concrete witness of feasibility.
    """

    centres = {row.id: row for row in problem.work_centers}
    parallel = {cid for cid, centre in centres.items() if centre.max_parallel > 1}
    todo = [row for row in assignments if row.work_center_id in parallel and row.lane is None]
    if not todo:
        return list(assignments)
    bare = [
        row.model_copy(update={"lane": None}) if row.work_center_id in parallel else row
        for row in assignments
    ]
    placements, _overflows = _colour_lanes(problem, bare, ignore_explicit=True)
    lane_of = {(item.work_center_id, item.operation_id): item.lane_index for item in placements}
    out: list[PlannedAssignment] = []
    for row in assignments:
        if row.work_center_id in parallel and row.lane is None:
            lane = lane_of.get((row.work_center_id, row.operation_id))
            out.append(row.model_copy(update={"lane": lane}) if lane is not None else row)
        else:
            out.append(row)
    return out


def _colour_lanes(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    *,
    ignore_explicit: bool = False,
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
        explicit = not ignore_explicit and capacity > 1 and all(row.lane is not None for row in rows)
        mixed = (
            not ignore_explicit
            and capacity > 1
            and not explicit
            and any(row.lane is not None for row in rows)
        )
        if explicit:
            lanes = [(datetime.min.replace(tzinfo=UTC), None, "idle") for _ in range(capacity)]
        for row in ordered:
            occupancy_start = row.start - timedelta(minutes=row.setup_minutes)
            ambiguous = mixed
            if explicit:
                lane_index = int(row.lane or 0)
                if lane_index >= capacity or lanes[lane_index][0] > occupancy_start:
                    # Lane id out of range or two visits overlap on one lane: the
                    # declared colouring is inconsistent. Refuse, never drop the row.
                    result.append(
                        LanePlacement(
                            operation_id=row.operation_id,
                            work_center_id=centre_id,
                            lane_index=lane_index,
                            occupancy_start=occupancy_start,
                            end=row.end,
                            previous_operation_id=None,
                            previous_state="",
                            expected_setup_minutes=None,
                            ambiguous=True,
                        )
                    )
                    continue
                _end, previous_id, previous_state = lanes[lane_index]
                operation = operations.get(row.operation_id)
                state = operation.setup_state if operation is not None else ""
                expected = lookup_setup_minutes(
                    problem, work_center_id=centre_id, from_state=previous_state, to_state=state
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
                continue
            reusable = [(index, lane) for index, lane in enumerate(lanes) if lane[0] <= occupancy_start]
            # Without a lane id the plan is ambiguous when two admissible lanes (a free
            # existing lane or a fresh idle lane) would start this visit from different
            # setup states. Every free lane stays free for later visits (they are sorted by
            # occupancy start), so lanes with equal state are interchangeable; differing
            # states are not, and the checker refuses to guess.
            candidate_states = {lane[2] for _index, lane in reusable}
            if reusable and len(lanes) < capacity:
                candidate_states.add("idle")
            if not ignore_explicit and len(candidate_states) > 1:
                ambiguous = True
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
                    ambiguous=ambiguous,
                )
            )
    ordered_result = sorted(result, key=lambda row: (row.occupancy_start, row.operation_id))
    return ordered_result, overflows
