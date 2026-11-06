"""Independent minute oracle for small repair plans.

The only RepairFlow import is ``repairflow.model``. A horizon longer than
eight days, or a timestamp off the minute, raises ``OracleLimit``. That
refusal is not an acceptance. Eight days covers the committed presets:
``tiny`` is two days and ``repair-site-mvp`` is seven.

Aligned minutes are judged by a half-open sweep, which is the same count as
walking each minute. When ``native/interval_kernel`` has been compiled, the
peak of that sweep runs there. The notary does not call it.

A hard exchange-pool stockout is judged with the same cumulative ledger.
A soft pool stays a kpi and is not a hard code. Consumable stock and rotable
reuse are judged too.
"""

from __future__ import annotations

import ctypes
import os
from datetime import datetime, timedelta
from pathlib import Path

from repairflow.model import (
    Calendar,
    Operation,
    PlannedAssignment,
    RepairFlowProblem,
    Spare,
)

_MAX_HORIZON = timedelta(days=8)
_POLICIES = frozenset({"exact", "min", "preemptive"})


class OracleLimit(RuntimeError):
    """The minute oracle refuses to label this input."""


def hard_codes(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> frozenset[str]:
    """Hard violation codes. An empty set means the oracle accepts the plan."""

    _require_judgable(problem, assignments)
    codes: set[str] = set()
    codes |= _identity(problem, assignments)
    codes |= _coverage(problem, assignments)
    codes |= _duration_and_windows(problem, assignments)
    codes |= _skills(problem, assignments)
    codes |= _precedence(problem, assignments)
    codes |= _calendars(problem, assignments)
    codes |= _capacity(problem, assignments)
    codes |= _setup(problem, assignments)
    codes |= _frozen(problem, assignments)
    codes |= _spares_and_dates(problem, assignments)
    codes |= _exchange_pools(problem, assignments)
    return frozenset(codes)


def _require_judgable(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> None:
    horizon = problem.planning_horizon
    if horizon.end - horizon.start > _MAX_HORIZON:
        raise OracleLimit("horizon is longer than eight days")
    moments = [horizon.start, horizon.end]
    for assignment in assignments:
        moments.extend((assignment.start, assignment.end))
    for calendar in problem.calendars:
        for window in calendar.windows:
            moments.extend((window.start, window.end))
    for crew in problem.crews:
        moments.extend(crew.skill_valid_until.values())
    for operation in problem.operations:
        if operation.earliest_start is not None:
            moments.append(operation.earliest_start)
        if operation.latest_finish is not None:
            moments.append(operation.latest_finish)
    for job in problem.jobs:
        if job.deadline is not None:
            moments.append(job.deadline)
        if job.release_date is not None:
            moments.append(job.release_date)
        if job.due_date is not None:
            moments.append(job.due_date)
    for spare in problem.spares:
        if spare.available_from is not None:
            moments.append(spare.available_from)
        moments.extend(receipt.at for receipt in spare.receipts)
    for frozen in problem.frozen_assignments:
        moments.extend((frozen.start, frozen.end))
    for moment in moments:
        if moment.utcoffset() is None or moment.second or moment.microsecond:
            raise OracleLimit("timestamp is not an aligned UTC minute")


def _duration_rejected(policy: str, held: int, duration_min: int) -> bool:
    if policy == "invalid":
        return True
    if policy == "min":
        return held < duration_min
    if policy == "exact":
        return held != duration_min
    return False


def _policy(attributes: dict[str, object]) -> str:
    raw = attributes.get("duration_policy", "exact")
    if isinstance(raw, str) and raw in _POLICIES:
        return raw
    return "invalid"


def _unattended(attributes: dict[str, object]) -> bool:
    return str(attributes.get("attendance", "attended")).lower() == "unattended"


def _always_open(attributes: dict[str, object]) -> bool:
    return str(attributes.get("availability", "")).lower() == "always_open"


def _occupancy_start(assignment: PlannedAssignment) -> datetime:
    return assignment.start - timedelta(minutes=int(assignment.setup_minutes))


def _held(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def _identity(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    operations = {operation.id for operation in problem.operations}
    centers = {center.id for center in problem.work_centers}
    crews = {crew.id for crew in problem.crews}
    aux_ids = {aux.id for aux in problem.aux_resources}
    seen: set[str] = set()
    codes: set[str] = set()
    for assignment in assignments:
        if assignment.operation_id not in operations:
            codes.add("UNKNOWN_OPERATION")
        elif assignment.operation_id in seen:
            codes.add("DUPLICATE_ASSIGNMENT")
        seen.add(assignment.operation_id)
        if assignment.work_center_id not in centers:
            codes.add("UNKNOWN_RESOURCE")
        if assignment.crew_id is not None and assignment.crew_id not in crews:
            codes.add("UNKNOWN_RESOURCE")
        if any(aux_id not in aux_ids for aux_id in assignment.aux_ids):
            codes.add("UNKNOWN_RESOURCE")
        if assignment.end <= assignment.start:
            codes.add("INVALID_DURATION")
    return codes


def _coverage(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    assigned = {assignment.operation_id for assignment in assignments}
    if any(operation.id not in assigned for operation in problem.operations):
        return {"PARTIAL_COVERAGE"}
    return set()


def _duration_and_windows(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> set[str]:
    operations = {operation.id: operation for operation in problem.operations}
    codes: set[str] = set()
    for assignment in assignments:
        operation = operations.get(assignment.operation_id)
        if operation is None or assignment.end <= assignment.start:
            continue
        policy = _policy(operation.domain_attributes)
        held = _held(assignment.start, assignment.end)
        if policy == "preemptive":
            masks = _masks(problem, operation, assignment)
            if _open_minutes(assignment.start, assignment.end, masks) != operation.duration_min:
                codes.add("INVALID_DURATION")
        elif _duration_rejected(policy, held, operation.duration_min):
            codes.add("INVALID_DURATION")
        if operation.latest_finish is not None and assignment.end > operation.latest_finish:
            codes.add("WINDOW_BROKEN")
        if operation.earliest_start is not None and _occupancy_start(assignment) < operation.earliest_start:
            codes.add("WINDOW_BROKEN")
        start = _occupancy_start(assignment)
        horizon = problem.planning_horizon
        if start < horizon.start or assignment.end > horizon.end:
            codes.add("HORIZON_VIOLATION")
    return codes


def _skills(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    operations = {operation.id: operation for operation in problem.operations}
    crews = {crew.id: crew for crew in problem.crews}
    centers = {center.id: center for center in problem.work_centers}
    jobs = {job.id: job for job in problem.jobs}
    codes: set[str] = set()
    for assignment in assignments:
        operation = operations.get(assignment.operation_id)
        if operation is None:
            continue
        if assignment.work_center_id not in operation.eligible_work_center_ids:
            codes.add("ELIGIBLE_CENTER_MISMATCH")
        center = centers.get(assignment.work_center_id)
        job = jobs.get(operation.job_id)
        if (
            center is not None
            and job is not None
            and center.eligible_unit_types
            and job.unit_type
            and job.unit_type not in center.eligible_unit_types
        ):
            codes.add("ELIGIBLE_CENTER_MISMATCH")
        if operation.required_skills and assignment.crew_id is None:
            codes.add("CREW_UNBOUND")
        crew = crews.get(assignment.crew_id or "")
        if operation.required_skills and crew is not None:
            if not set(operation.required_skills) <= set(crew.skills):
                codes.add("SKILL_MISMATCH")
            for skill in operation.required_skills:
                until = crew.skill_valid_until.get(skill)
                if until is not None and assignment.end > until:
                    codes.add("SKILL_EXPIRED")
        required = set(operation.required_aux_ids)
        if required and not required <= set(assignment.aux_ids):
            codes.add("AUX_MISSING")
    return codes


def _precedence(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    by_op: dict[str, list[PlannedAssignment]] = {}
    for assignment in assignments:
        by_op.setdefault(assignment.operation_id, []).append(assignment)
    codes: set[str] = set()
    for operation in problem.operations:
        placed = by_op.get(operation.id)
        if not placed:
            continue
        current = placed[0]
        for pred_id, min_lag, max_lag in operation.predecessor_links():
            earlier = by_op.get(pred_id)
            if not earlier:
                codes.add("PRECEDENCE_BROKEN")
                continue
            ready = earlier[0].end + timedelta(minutes=min_lag)
            latest = None if max_lag is None else earlier[0].end + timedelta(minutes=max_lag)
            if current.start < ready or (latest is not None and current.start > latest):
                codes.add("PRECEDENCE_BROKEN")
    return codes


def _calendars(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    operations = {operation.id: operation for operation in problem.operations}
    calendars = {calendar.id: calendar for calendar in problem.calendars}
    centers = {center.id: center for center in problem.work_centers}
    crews = {crew.id: crew for crew in problem.crews}
    auxes = {aux.id: aux for aux in problem.aux_resources}
    codes: set[str] = set()
    for assignment in assignments:
        if assignment.end <= assignment.start:
            continue
        operation = operations.get(assignment.operation_id)
        preemptive = operation is not None and _policy(operation.domain_attributes) == "preemptive"
        resources: list[tuple[str | None, dict[str, object]]] = []
        center = centers.get(assignment.work_center_id)
        if center is not None:
            resources.append((center.calendar_id, center.domain_attributes))
        crew = crews.get(assignment.crew_id or "")
        if crew is not None:
            resources.append((crew.calendar_id, crew.domain_attributes))
        needed = set(assignment.aux_ids)
        if operation is not None:
            needed.update(operation.required_aux_ids)
        for aux_id in needed:
            aux = auxes.get(aux_id)
            if aux is not None:
                resources.append((aux.calendar_id, aux.domain_attributes))
        for calendar_id, attributes in resources:
            codes |= _calendar_fit(
                calendars.get(calendar_id) if calendar_id else None,
                calendar_id,
                assignment,
                preemptive=preemptive,
                attributes=attributes,
                provenance=problem.data_provenance,
            )
    return codes


def _calendar_fit(
    calendar: Calendar | None,
    calendar_id: str | None,
    assignment: PlannedAssignment,
    *,
    preemptive: bool,
    attributes: dict[str, object],
    provenance: str,
) -> set[str]:
    if _unattended(attributes):
        return set()
    if not calendar_id:
        if provenance != "synthetic" and not _always_open(attributes):
            return {"CALENDAR_BROKEN"}
        return set()
    if calendar is None or not calendar.windows:
        return {"CALENDAR_BROKEN"}
    occ_start = _occupancy_start(assignment)
    # Minute semantics: every aligned minute of the half-open occupancy must be open.
    # Touching windows [a, b) and [b, c) cover [a, c). The sweep is that union.
    end = assignment.start if preemptive else assignment.end
    if end <= occ_start:
        return set()
    windows = [(window.start, window.end) for window in calendar.windows]
    if not _span_covered(occ_start, end, windows):
        return {"CALENDAR_BROKEN"}
    return set()


def _masks(
    problem: RepairFlowProblem,
    operation: Operation,
    assignment: PlannedAssignment,
) -> list[list[tuple[datetime, datetime]]]:
    calendars = {calendar.id: calendar for calendar in problem.calendars}
    masks: list[list[tuple[datetime, datetime]]] = []

    def add(calendar_id: str | None, attributes: dict[str, object]) -> None:
        if _unattended(attributes) or not calendar_id:
            return
        calendar = calendars.get(calendar_id)
        if calendar is None:
            return
        masks.append([(window.start, window.end) for window in calendar.windows])

    center = next((row for row in problem.work_centers if row.id == assignment.work_center_id), None)
    if center is not None:
        add(center.calendar_id, center.domain_attributes)
    crew = next((row for row in problem.crews if row.id == assignment.crew_id), None)
    if crew is not None:
        add(crew.calendar_id, crew.domain_attributes)
    aux_ids = set(assignment.aux_ids) | set(operation.required_aux_ids)
    for aux in problem.aux_resources:
        if aux.id in aux_ids:
            add(aux.calendar_id, aux.domain_attributes)
    return masks


def _open_minutes(
    start: datetime,
    end: datetime,
    masks: list[list[tuple[datetime, datetime]]],
) -> int:
    if end <= start:
        return 0
    if not masks:
        return _held(start, end)
    pieces: list[tuple[datetime, datetime]] = [(start, end)]
    for windows in masks:
        pieces = _intersect_spans(pieces, _merge_spans(windows))
        if not pieces:
            return 0
    return sum(_held(left, right) for left, right in pieces)


def _capacity(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    posts: dict[str, list[tuple[datetime, datetime]]] = {}
    crews: dict[str, list[tuple[datetime, datetime]]] = {}
    auxes: dict[str, list[tuple[datetime, datetime]]] = {}
    known_crews = {crew.id for crew in problem.crews}
    known_aux = {aux.id for aux in problem.aux_resources}
    for assignment in assignments:
        if assignment.end <= assignment.start:
            continue
        interval = (_occupancy_start(assignment), assignment.end)
        posts.setdefault(assignment.work_center_id, []).append(interval)
        if assignment.crew_id in known_crews:
            crews.setdefault(assignment.crew_id or "", []).append(interval)
        for aux_id in assignment.aux_ids:
            if aux_id in known_aux:
                auxes.setdefault(aux_id, []).append(interval)
    post_cap = {center.id: center.max_parallel for center in problem.work_centers}
    crew_cap = {crew.id: crew.max_parallel for crew in problem.crews}
    aux_cap = {aux.id: aux.capacity for aux in problem.aux_resources}
    codes: set[str] = set()
    if any(_minute_exceeds(rows, post_cap.get(key, 1)) for key, rows in posts.items()):
        codes.add("POST_OVERLAP")
    if any(_minute_exceeds(rows, crew_cap.get(key, 1)) for key, rows in crews.items()):
        codes.add("CREW_OVERLAP")
    if any(_minute_exceeds(rows, aux_cap.get(key, 1)) for key, rows in auxes.items()):
        codes.add("AUX_OVERLAP")
    return codes


def _minute_exceeds(intervals: list[tuple[datetime, datetime]], cap: int) -> bool:
    """True when more than ``cap`` half-open intervals cover one minute."""

    native = _native_kernel()
    if native is not None:
        return native.exceeds(intervals, cap)
    return _sweep_exceeds(intervals, cap)


def _sweep_exceeds(intervals: list[tuple[datetime, datetime]], cap: int) -> bool:
    """Ends sort before starts at one timestamp, so a shared endpoint is one lane."""

    if cap < 0:
        return True
    events: list[tuple[datetime, int]] = []
    for start, end in intervals:
        if start >= end:
            continue
        events.append((end, 0))
        events.append((start, 1))
    events.sort()
    active = 0
    for _moment, kind in events:
        if kind == 0:
            active -= 1
        else:
            active += 1
            if active > cap:
                return True
    return False


def _merge_spans(windows: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(windows):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _span_covered(start: datetime, end: datetime, windows: list[tuple[datetime, datetime]]) -> bool:
    if end <= start:
        return True
    cursor = start
    for left, right in _merge_spans(windows):
        if right <= cursor:
            continue
        if left > cursor:
            return False
        if right >= end:
            return True
        cursor = right
    return False


def _intersect_spans(
    pieces: list[tuple[datetime, datetime]],
    windows: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for left, right in pieces:
        for win_start, win_end in windows:
            lo = left if left >= win_start else win_start
            hi = right if right <= win_end else win_end
            if hi > lo:
                out.append((lo, hi))
    return out


def _setup(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    operations: dict[str, Operation] = {operation.id: operation for operation in problem.operations}
    centers = {center.id: center.max_parallel for center in problem.work_centers}
    grouped: dict[str, list[PlannedAssignment]] = {}
    for assignment in assignments:
        if assignment.operation_id in operations and assignment.end > assignment.start:
            grouped.setdefault(assignment.work_center_id, []).append(assignment)
    codes: set[str] = set()
    for center_id, rows in grouped.items():
        codes |= _lane_setup(problem, center_id, rows, centers.get(center_id, 1), operations)
    return codes


def _lane_setup(
    problem: RepairFlowProblem,
    center_id: str,
    rows: list[PlannedAssignment],
    capacity: int,
    operations: dict[str, Operation],
) -> set[str]:
    lanes: list[tuple[datetime, str]] = []
    ordered = sorted(rows, key=lambda row: (_occupancy_start(row), row.end, row.operation_id))
    codes: set[str] = set()
    given = [row.lane for row in rows]
    if capacity > 1 and any(lane is not None for lane in given):
        if any(lane is None for lane in given):
            return {"SETUP_MISMATCH"}
        return _explicit_lane_setup(problem, center_id, ordered, capacity, operations)
    for row in ordered:
        occ_start = _occupancy_start(row)
        reusable = [(index, lane) for index, lane in enumerate(lanes) if lane[0] <= occ_start]
        states = {lane[1] for _index, lane in reusable}
        if reusable and len(lanes) < capacity:
            states.add("idle")
        if len(states) > 1:
            codes.add("SETUP_MISMATCH")
        if reusable:
            lane_index, (_free, previous_state) = min(reusable, key=lambda item: (item[1][0], item[0]))
        elif len(lanes) < capacity:
            lane_index = len(lanes)
            previous_state = "idle"
            lanes.append((row.end, ""))
        else:
            continue
        operation = operations[row.operation_id]
        state = operation.setup_state
        expected = _setup_cell(problem, center_id, previous_state, state)
        lanes[lane_index] = (row.end, state)
        written = int(row.setup_minutes)
        if expected is None:
            if not (problem.policy.missing_setup == "zero" and written == 0 and previous_state != "idle"):
                codes.add("MISSING_SETUP")
        elif written != expected:
            codes.add("SETUP_MISMATCH")
    return codes


def _explicit_lane_setup(
    problem: RepairFlowProblem,
    center_id: str,
    ordered: list[PlannedAssignment],
    capacity: int,
    operations: dict[str, Operation],
) -> set[str]:
    codes: set[str] = set()
    state: dict[int, tuple[datetime | None, str]] = {}
    for row in ordered:
        lane = int(row.lane or 0)
        free, previous_state = state.get(lane, (None, "idle"))
        if lane >= capacity or (free is not None and free > _occupancy_start(row)):
            codes.add("CENTER_OVERLAP")
            continue
        expected = _setup_cell(problem, center_id, previous_state, operations[row.operation_id].setup_state)
        written = int(row.setup_minutes)
        if expected is None:
            if not (problem.policy.missing_setup == "zero" and written == 0 and previous_state != "idle"):
                codes.add("MISSING_SETUP")
        elif written != expected:
            codes.add("SETUP_MISMATCH")
        state[lane] = (row.end, operations[row.operation_id].setup_state)
    return codes


def _setup_cell(
    problem: RepairFlowProblem,
    work_center_id: str,
    from_state: str,
    to_state: str,
) -> int | None:
    specific: int | None = None
    generic: int | None = None
    for entry in problem.setup_matrix:
        if entry.from_state != from_state or entry.to_state != to_state:
            continue
        if entry.work_center_id == work_center_id:
            specific = entry.duration_min
        elif entry.work_center_id is None:
            generic = entry.duration_min
    return specific if specific is not None else generic


def _frozen(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    by_op = {assignment.operation_id: assignment for assignment in assignments}
    codes: set[str] = set()
    for frozen in problem.frozen_assignments:
        if not frozen.immutable:
            continue
        placed = by_op.get(frozen.operation_id)
        if placed is None:
            codes.add("FROZEN_MOVED")
            continue
        crew_ok = frozen.crew_id is None or placed.crew_id == frozen.crew_id
        moved = (
            placed.work_center_id != frozen.work_center_id
            or placed.start != frozen.start
            or placed.end != frozen.end
            or not crew_ok
        )
        if moved:
            codes.add("FROZEN_MOVED")
    return codes


def _spares_and_dates(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> set[str]:
    operations: dict[str, Operation] = {operation.id: operation for operation in problem.operations}
    jobs = {job.id: job for job in problem.jobs}
    spares = {spare.id: spare for spare in problem.spares}
    codes: set[str] = set()
    latest: dict[str, datetime] = {}
    for assignment in assignments:
        operation = operations.get(assignment.operation_id)
        if operation is None:
            continue
        job = jobs[operation.job_id]
        if job.release_date is not None and _occupancy_start(assignment) < job.release_date:
            codes.add("RELEASE_VIOLATION")
        previous = latest.get(job.id)
        if previous is None or assignment.end > previous:
            latest[job.id] = assignment.end
    for job in problem.jobs:
        end = latest.get(job.id)
        if end is not None and job.deadline is not None and end > job.deadline:
            codes.add("DEADLINE_MISSED")
    codes |= _consumables(problem, assignments, operations, spares)
    codes |= _rotables(assignments, operations, spares)
    return codes


def _consumables(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    operations: dict[str, Operation],
    spares: dict[str, Spare],
) -> set[str]:
    used: dict[str, int] = {}
    timed: dict[str, list[tuple[datetime, str, int]]] = {}
    for assignment in assignments:
        operation = operations.get(assignment.operation_id)
        if operation is None:
            continue
        for spare_id, qty in operation.spare_demand().items():
            spare = spares.get(spare_id)
            if spare is None or _rotable(spare):
                if spare is None:
                    return {"SPARE_UNAVAILABLE"}
                continue
            if spare.receipts:
                timed.setdefault(spare_id, []).append((assignment.start, operation.id, qty))
            else:
                if spare.quantity <= 0 or (
                    spare.available_from is not None and assignment.start < spare.available_from
                ):
                    return {"SPARE_UNAVAILABLE"}
                used[spare_id] = used.get(spare_id, 0) + qty
    codes: set[str] = set()
    for spare_id, count in used.items():
        if count > spares[spare_id].quantity:
            codes.add("SPARE_UNAVAILABLE")
    for spare_id, uses in timed.items():
        if _receipt_short(problem, spares[spare_id], uses):
            codes.add("SPARE_UNAVAILABLE")
    return codes


def _receipt_short(
    problem: RepairFlowProblem,
    spare: Spare,
    uses: list[tuple[datetime, str, int]],
) -> bool:
    initial_at = spare.available_from or problem.planning_horizon.start
    events: list[tuple[datetime, int, int]] = [(initial_at, 0, spare.quantity)]
    events.extend((receipt.at, 0, receipt.qty) for receipt in spare.receipts)
    events.extend((start, 1, -qty) for start, _op_id, qty in uses)
    stock = 0
    for _moment, _order, delta in sorted(events):
        stock += delta
        if stock < 0:
            return True
    return False


def _rotables(
    assignments: list[PlannedAssignment],
    operations: dict[str, Operation],
    spares: dict[str, Spare],
) -> set[str]:
    busy: dict[str, list[tuple[datetime, datetime]]] = {}
    caps = {spare_id: spare.quantity for spare_id, spare in spares.items() if _rotable(spare)}
    for assignment in assignments:
        operation = operations.get(assignment.operation_id)
        if operation is None or assignment.end <= assignment.start:
            continue
        for spare_id, qty in operation.spare_demand().items():
            spare = spares.get(spare_id)
            if spare is None or not _rotable(spare) or qty < 1:
                continue
            lag = spare.domain_attributes.get("return_lag_min", 0)
            if not isinstance(lag, int) or isinstance(lag, bool) or lag < 0:
                return {"SPARE_UNAVAILABLE"}
            if spare.available_from is not None and assignment.start < spare.available_from:
                return {"SPARE_UNAVAILABLE"}
            held = (assignment.start, assignment.end + timedelta(minutes=lag))
            busy.setdefault(spare_id, []).extend([held] * qty)
    if any(_minute_exceeds(intervals, caps.get(spare_id, 0)) for spare_id, intervals in busy.items()):
        return {"SPARE_UNAVAILABLE"}
    return set()


def _exchange_pools(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> set[str]:
    """Hard stockout only. ``stock(t) = initial + completions at or before t − demand at or before t``."""

    if not problem.exchange_pools:
        return set()
    by_job_ops: dict[str, set[str]] = {}
    for operation in problem.operations:
        by_job_ops.setdefault(operation.job_id, set()).add(operation.id)
    successors: dict[str, list[str]] = {}
    for operation in problem.operations:
        for pred in operation.predecessor_ids:
            if pred in by_job_ops.get(operation.job_id, set()):
                successors.setdefault(pred, []).append(operation.id)
    by_op = {row.operation_id: row for row in assignments}
    finished: dict[str, datetime] = {}
    for job in problem.jobs:
        job_ops = by_job_ops.get(job.id, set())
        sinks = sorted(op_id for op_id in job_ops if not successors.get(op_id))
        ends: list[datetime] = []
        complete = True
        for op_id in sinks:
            placed = by_op.get(op_id)
            if placed is None:
                complete = False
                break
            ends.append(placed.end)
        if complete and ends:
            finished[job.id] = max(ends)
    codes: set[str] = set()
    for pool in problem.exchange_pools:
        if not pool.hard:
            continue
        deltas: dict[datetime, int] = {}
        for job in problem.jobs:
            if job.unit_type != pool.unit_type:
                continue
            moment = finished.get(job.id)
            if moment is not None:
                deltas[moment] = deltas.get(moment, 0) + 1
        for demand in pool.demand:
            deltas[demand.at] = deltas.get(demand.at, 0) - demand.qty
        stock = pool.initial_serviceable
        worst = stock
        for moment in sorted(deltas):
            stock += deltas[moment]
            if stock < worst:
                worst = stock
        if worst < 0:
            codes.add("EXCHANGE_POOL_STOCKOUT")
    return codes


def _rotable(spare: Spare) -> bool:
    attrs = spare.domain_attributes
    mode = attrs.get("mode", attrs.get("kind", "consumable"))
    return str(mode).lower() == "rotable"


class _IntervalKernel:
    def __init__(self, library: ctypes.CDLL) -> None:
        self._peak = library.rf_peak_exceeds
        self._peak.argtypes = [
            ctypes.POINTER(ctypes.c_int64),
            ctypes.POINTER(ctypes.c_int64),
            ctypes.c_size_t,
            ctypes.c_int64,
        ]
        self._peak.restype = ctypes.c_int32

    def exceeds(self, intervals: list[tuple[datetime, datetime]], cap: int) -> bool:
        count = len(intervals)
        if count == 0:
            return cap < 0
        starts = (ctypes.c_int64 * count)(*(_minute_number(start) for start, _end in intervals))
        ends = (ctypes.c_int64 * count)(*(_minute_number(end) for _start, end in intervals))
        return bool(self._peak(starts, ends, count, cap))


_KERNEL: _IntervalKernel | None | bool = None


def reset_native_interval_kernel() -> None:
    """Drop a cached load so a freshly built library can be opened."""

    global _KERNEL
    _KERNEL = None


def _minute_number(moment: datetime) -> int:
    return int(moment.timestamp() // 60)


def _native_kernel() -> _IntervalKernel | None:
    global _KERNEL
    if isinstance(_KERNEL, _IntervalKernel):
        return _KERNEL
    if _KERNEL is False:
        return None
    root = Path(__file__).resolve().parents[1] / "native"
    opened: _IntervalKernel | None = None
    for name in ("interval_kernel.dll", "libinterval_kernel.so", "libinterval_kernel.dylib"):
        path = root / name
        if path.is_file():
            opened = _IntervalKernel(ctypes.CDLL(str(path)))
            break
    if opened is None and os.environ.get("REPAIRFLOW_REQUIRE_INTERVAL_RS") == "1":
        raise RuntimeError("the Rust interval kernel was required but has not been built")
    _KERNEL = opened if opened is not None else False
    return opened
