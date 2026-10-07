"""Independent minute oracle for small repair plans.

The only RepairFlow import is ``repairflow.model``. A horizon longer than
eight days, or a timestamp off the minute, raises ``OracleLimit``. That
refusal is not an acceptance. Eight days covers the committed presets:
``tiny`` is two days and ``repair-site-mvp`` is seven. The same minute loop
is used throughout.

The exchange-pool ledger is not judged. Consumable stock and rotable reuse are.
"""

from __future__ import annotations

from datetime import datetime, timedelta

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
        if operation.earliest_start is not None and assignment.start < operation.earliest_start:
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
    if preemptive:
        if assignment.start <= occ_start:
            return set()
        contained = any(
            occ_start >= window.start and assignment.start <= window.end for window in calendar.windows
        )
        return set() if contained else {"CALENDAR_BROKEN"}
    contained = any(occ_start >= window.start and assignment.end <= window.end for window in calendar.windows)
    return set() if contained else {"CALENDAR_BROKEN"}


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
    if not masks:
        return _held(start, end)
    count = 0
    moment = start
    while moment < end:
        if all(any(left <= moment < right for left, right in windows) for windows in masks):
            count += 1
        moment += timedelta(minutes=1)
    return count


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

    start = min(left for left, _right in intervals)
    end = max(right for _left, right in intervals)
    moment = start
    while moment < end:
        active = sum(1 for left, right in intervals if left <= moment < right)
        if active > cap:
            return True
        moment += timedelta(minutes=1)
    return False


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
    for row in ordered:
        occ_start = _occupancy_start(row)
        reusable = [(index, lane) for index, lane in enumerate(lanes) if lane[0] <= occ_start]
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
            if not (problem.policy.missing_setup == "zero" and written == 0):
                codes.add("MISSING_SETUP")
        elif written != expected:
            codes.add("SETUP_MISMATCH")
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
        if job.release_date is not None and assignment.start < job.release_date:
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
        for spare_id in operation.spare_demand():
            spare = spares.get(spare_id)
            if spare is None or not _rotable(spare):
                continue
            lag = spare.domain_attributes.get("return_lag_min", 0)
            if not isinstance(lag, int) or isinstance(lag, bool) or lag < 0:
                return {"SPARE_UNAVAILABLE"}
            busy.setdefault(spare_id, []).append((assignment.start, assignment.end + timedelta(minutes=lag)))
    if any(_minute_exceeds(intervals, caps.get(spare_id, 0)) for spare_id, intervals in busy.items()):
        return {"SPARE_UNAVAILABLE"}
    return set()


def _rotable(spare: Spare) -> bool:
    attrs = spare.domain_attributes
    mode = attrs.get("mode", attrs.get("kind", "consumable"))
    return str(mode).lower() == "rotable"
