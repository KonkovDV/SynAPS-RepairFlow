"""Independent fail-closed RepairFlow checker. Does not import solver search code."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from synaps.model import Assignment, ScheduleProblem, ScheduleResult

from repairflow.adapter import bind_concrete_crews, lookup_setup_minutes, reverse_ids
from repairflow.model import (
    Calendar,
    Operation,
    PlannedAssignment,
    RepairFlowProblem,
    Violation,
)
from repairflow.reasons import REASON_RU, SUGGESTIONS, ReasonCode


def check_plan(
    problem: RepairFlowProblem,
    *,
    schedule_problem: ScheduleProblem,
    assignments: list[Assignment] | list[PlannedAssignment],
    id_map: dict[str, UUID],
    kernel_status: str | None,
) -> list[Violation]:
    try:
        problem = RepairFlowProblem.model_validate(problem.model_dump(mode="python"))
    except (ValueError, TypeError) as exc:
        return [
            _violation(
                ReasonCode.INVALID_PROBLEM,
                f"problem failed domain validation: {exc}",
            )
        ]

    mapped = bind_concrete_crews(problem, _normalize_assignments(assignments, id_map))
    issues = _id_map_issues(problem, schedule_problem, id_map)
    if issues:
        return issues

    violations: list[Violation] = []
    if not kernel_status:
        violations.append(
            _violation(
                ReasonCode.KERNEL_STATUS_MISSING,
                "result has no kernel_status; refusing to treat the plan as verified",
            )
        )

    violations.extend(_ref_and_duration(problem, mapped))
    violations.extend(_coverage(problem, mapped))
    violations.extend(_skills_and_eligibility(problem, mapped))
    violations.extend(_precedence(problem, mapped))
    violations.extend(_resource_overlaps(problem, mapped))
    violations.extend(_calendars_windows_horizon(problem, mapped))
    violations.extend(_due_release_spares(problem, mapped))
    violations.extend(_setup(problem, mapped))
    violations.extend(_frozen(problem, mapped))
    return _sorted(violations)


def _normalize_assignments(
    assignments: list[Assignment] | list[PlannedAssignment],
    id_map: dict[str, UUID],
) -> list[PlannedAssignment]:
    reversed_map = reverse_ids(id_map)
    out: list[PlannedAssignment] = []
    for row in assignments:
        if isinstance(row, PlannedAssignment):
            out.append(row)
            continue
        wc_kind, wc_id = reversed_map.get(row.work_center_id, ("wc", str(row.work_center_id)))
        op_kind, op_id = reversed_map.get(row.operation_id, ("op", str(row.operation_id)))
        crew_id = None
        aux_ids: list[str] = []
        for aux in row.aux_resource_ids:
            kind, ident = reversed_map.get(aux, ("aux", str(aux)))
            if kind == "crew":
                crew_id = ident
            elif kind == "aux":
                aux_ids.append(ident)
        out.append(
            PlannedAssignment(
                operation_id=op_id if op_kind == "op" else str(row.operation_id),
                work_center_id=wc_id if wc_kind == "wc" else str(row.work_center_id),
                crew_id=crew_id,
                aux_ids=aux_ids,
                start=row.start_time,
                end=row.end_time,
                setup_minutes=int(row.setup_minutes or 0),
            )
        )
    return out


def _id_map_issues(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
) -> list[Violation]:
    op_keys = {f"op:{op.id}" for op in problem.operations}
    wc_keys = {f"wc:{wc.id}" for wc in problem.work_centers}
    supplied_ops = {key for key in id_map if key.startswith("op:")}
    supplied_wcs = {key for key in id_map if key.startswith("wc:")}
    if op_keys != supplied_ops or wc_keys != supplied_wcs:
        return [
            _violation(
                ReasonCode.INVALID_ID_MAP,
                "operation/work-center mapping must be complete and injective",
            )
        ]
    if len(schedule_problem.operations) != len(problem.operations):
        return [
            _violation(
                ReasonCode.INVALID_ID_MAP,
                "compiled kernel operations do not match the RepairFlow instance",
            )
        ]
    return []


def _ref_and_duration(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    op_ids = {op.id for op in problem.operations}
    wc_ids = {wc.id for wc in problem.work_centers}
    crew_ids = {crew.id for crew in problem.crews}
    aux_ids = {aux.id for aux in problem.aux_resources}
    seen: set[str] = set()
    out: list[Violation] = []
    for asn in assignments:
        if asn.operation_id not in op_ids:
            out.append(
                _violation(
                    ReasonCode.UNKNOWN_OPERATION,
                    "assignment references an unknown operation",
                    operation_id=asn.operation_id,
                    start=asn.start,
                    end=asn.end,
                )
            )
            continue
        if asn.operation_id in seen:
            out.append(
                _violation(
                    ReasonCode.DUPLICATE_ASSIGNMENT,
                    "operation scheduled more than once",
                    operation_id=asn.operation_id,
                    job_id=_job_of(problem, asn.operation_id),
                    start=asn.start,
                    end=asn.end,
                )
            )
        seen.add(asn.operation_id)
        if asn.work_center_id not in wc_ids:
            out.append(
                _violation(
                    ReasonCode.UNKNOWN_RESOURCE,
                    "assignment references an unknown work center",
                    operation_id=asn.operation_id,
                    resource_id=asn.work_center_id,
                    start=asn.start,
                    end=asn.end,
                )
            )
        if asn.crew_id is not None and asn.crew_id not in crew_ids:
            out.append(
                _violation(
                    ReasonCode.UNKNOWN_RESOURCE,
                    "assignment references an unknown crew",
                    operation_id=asn.operation_id,
                    resource_id=asn.crew_id,
                    start=asn.start,
                    end=asn.end,
                )
            )
        for aux_id in asn.aux_ids:
            if aux_id not in aux_ids:
                out.append(
                    _violation(
                        ReasonCode.UNKNOWN_RESOURCE,
                        "assignment references an unknown auxiliary resource",
                        operation_id=asn.operation_id,
                        resource_id=aux_id,
                        start=asn.start,
                        end=asn.end,
                    )
                )
        if asn.end <= asn.start:
            out.append(
                _violation(
                    ReasonCode.INVALID_DURATION,
                    "assignment end must be after start",
                    operation_id=asn.operation_id,
                    job_id=_job_of(problem, asn.operation_id),
                    start=asn.start,
                    end=asn.end,
                )
            )
        else:
            op = _op(problem, asn.operation_id)
            held = int((asn.end - asn.start).total_seconds() // 60)
            if op is not None and held < op.duration_min:
                out.append(
                    _violation(
                        ReasonCode.INVALID_DURATION,
                        f"scheduled {held} min is shorter than duration_min={op.duration_min}",
                        operation_id=asn.operation_id,
                        job_id=op.job_id,
                        start=asn.start,
                        end=asn.end,
                    )
                )
    return out


def _coverage(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> list[Violation]:
    assigned = {asn.operation_id for asn in assignments}
    out: list[Violation] = []
    if problem.policy.allow_partial_plan:
        return out
    for operation in problem.operations:
        if operation.id not in assigned:
            out.append(
                _violation(
                    ReasonCode.PARTIAL_COVERAGE,
                    f"operation {operation.id} has no assignment",
                    operation_id=operation.id,
                    job_id=operation.job_id,
                    suggested_relaxation=SUGGESTIONS[ReasonCode.PARTIAL_COVERAGE],
                )
            )
    return out


def _skills_and_eligibility(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    ops = {op.id: op for op in problem.operations}
    crews = {crew.id: crew for crew in problem.crews}
    centers = {wc.id: wc for wc in problem.work_centers}
    jobs = {job.id: job for job in problem.jobs}
    out: list[Violation] = []
    for asn in assignments:
        op = ops.get(asn.operation_id)
        if op is None:
            continue
        if op.eligible_work_center_ids and asn.work_center_id not in op.eligible_work_center_ids:
            out.append(
                _violation(
                    ReasonCode.ELIGIBLE_CENTER_MISMATCH,
                    f"operation {op.id} is not eligible on {asn.work_center_id}",
                    operation_id=op.id,
                    job_id=op.job_id,
                    resource_id=asn.work_center_id,
                    start=asn.start,
                    end=asn.end,
                )
            )
        center = centers.get(asn.work_center_id)
        job = jobs.get(op.job_id)
        if (
            center is not None
            and job is not None
            and center.eligible_unit_types
            and job.unit_type
            and job.unit_type not in center.eligible_unit_types
        ):
            out.append(
                _violation(
                    ReasonCode.ELIGIBLE_CENTER_MISMATCH,
                    f"post {center.code} does not accept unit type {job.unit_type}",
                    operation_id=op.id,
                    job_id=op.job_id,
                    resource_id=center.id,
                    start=asn.start,
                    end=asn.end,
                )
            )
        if op.required_skills:
            if asn.crew_id is None:
                out.append(
                    _violation(
                        ReasonCode.SKILL_MISMATCH,
                        f"operation {op.id} requires skills {op.required_skills} but has no crew",
                        operation_id=op.id,
                        job_id=op.job_id,
                        start=asn.start,
                        end=asn.end,
                    )
                )
            else:
                crew = crews.get(asn.crew_id)
                if crew is not None and not set(op.required_skills) <= set(crew.skills):
                    out.append(
                        _violation(
                            ReasonCode.SKILL_MISMATCH,
                            (
                                f"operation {op.id} needs {sorted(op.required_skills)} "
                                f"but crew {crew.code} has {sorted(crew.skills)}"
                            ),
                            operation_id=op.id,
                            job_id=op.job_id,
                            resource_id=crew.id,
                            start=asn.start,
                            end=asn.end,
                            suggested_relaxation=SUGGESTIONS[ReasonCode.SKILL_MISMATCH],
                        )
                    )
        required_aux = set(op.required_aux_ids)
        if required_aux and not required_aux <= set(asn.aux_ids):
            out.append(
                _violation(
                    ReasonCode.UNKNOWN_RESOURCE,
                    f"operation {op.id} is missing required aux {sorted(required_aux - set(asn.aux_ids))}",
                    operation_id=op.id,
                    job_id=op.job_id,
                    start=asn.start,
                    end=asn.end,
                )
            )
    return out


def _precedence(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> list[Violation]:
    by_op = {asn.operation_id: asn for asn in assignments}
    out: list[Violation] = []
    for op in problem.operations:
        current = by_op.get(op.id)
        if current is None:
            continue
        preds = list(op.predecessor_ids)
        if not preds:
            same_job = [row for row in problem.operations if row.job_id == op.job_id]
            previous = [row for row in same_job if row.sequence < op.sequence]
            if previous:
                preds = [max(previous, key=lambda row: row.sequence).id]
        for pred_id in preds:
            pred = by_op.get(pred_id)
            if pred is None:
                out.append(
                    _violation(
                        ReasonCode.PRECEDENCE_BROKEN,
                        f"{op.id} is scheduled but predecessor {pred_id} is not",
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=pred_id,
                        start=current.start,
                        end=current.end,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.PRECEDENCE_BROKEN],
                        details={"missing_predecessor": pred_id},
                    )
                )
                continue
            if current.start < pred.end:
                out.append(
                    _violation(
                        ReasonCode.PRECEDENCE_BROKEN,
                        f"{op.id} starts before predecessor {pred_id} finishes",
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=pred_id,
                        start=current.start,
                        end=current.end,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.PRECEDENCE_BROKEN],
                        details={"predecessor_end": pred.end.isoformat()},
                    )
                )
    return out


def _resource_overlaps(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    out: list[Violation] = []
    by_center: dict[str, list[PlannedAssignment]] = defaultdict(list)
    by_crew: dict[str, list[PlannedAssignment]] = defaultdict(list)
    by_aux: dict[str, list[PlannedAssignment]] = defaultdict(list)
    for asn in assignments:
        by_center[asn.work_center_id].append(asn)
        if asn.crew_id:
            by_crew[asn.crew_id].append(asn)
        for aux_id in asn.aux_ids:
            by_aux[aux_id].append(asn)

    center_cap = {wc.id: wc.max_parallel for wc in problem.work_centers}
    crew_cap = {crew.id: crew.max_parallel for crew in problem.crews}
    aux_cap = {aux.id: aux.capacity for aux in problem.aux_resources}

    out.extend(
        _capacity_overlaps(
            by_center,
            center_cap,
            ReasonCode.CENTER_OVERLAP,
            include_setup=True,
        )
    )
    out.extend(
        _capacity_overlaps(
            by_crew,
            crew_cap,
            ReasonCode.CREW_OVERLAP,
            include_setup=True,
        )
    )
    out.extend(
        _capacity_overlaps(
            by_aux,
            aux_cap,
            ReasonCode.AUX_OVERLAP,
            include_setup=True,
        )
    )
    return out


def _capacity_overlaps(
    grouped: dict[str, list[PlannedAssignment]],
    capacity: dict[str, int],
    code: ReasonCode,
    *,
    include_setup: bool,
) -> list[Violation]:
    out: list[Violation] = []
    for resource_id, rows in grouped.items():
        cap = capacity.get(resource_id, 1)
        intervals = []
        for asn in rows:
            start = asn.start
            if include_setup:
                start = asn.start - timedelta(minutes=int(asn.setup_minutes or 0))
            intervals.append((start, asn.end, asn))
        intervals.sort(key=lambda item: item[0])
        for i, (start_a, end_a, asn_a) in enumerate(intervals):
            overlap_count = 1
            for start_b, end_b, asn_b in intervals[i + 1 :]:
                if start_b >= end_a:
                    break
                if start_a < end_b and start_b < end_a:
                    overlap_count += 1
                    if overlap_count > cap:
                        out.append(
                            _violation(
                                code,
                                f"resource {resource_id} exceeds capacity {cap}",
                                operation_id=asn_a.operation_id,
                                resource_id=resource_id,
                                start=max(start_a, start_b),
                                end=min(end_a, end_b),
                                details={"other_operation_id": asn_b.operation_id},
                                suggested_relaxation=SUGGESTIONS.get(code),
                            )
                        )
                        break
    return out


def _calendars_windows_horizon(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    calendars = {row.id: row for row in problem.calendars}
    centers = {wc.id: wc for wc in problem.work_centers}
    crews = {crew.id: crew for crew in problem.crews}
    ops = {op.id: op for op in problem.operations}
    out: list[Violation] = []
    horizon = problem.planning_horizon
    for asn in assignments:
        occ_start = asn.start - timedelta(minutes=int(asn.setup_minutes or 0))
        if occ_start < horizon.start or asn.end > horizon.end:
            out.append(
                _violation(
                    ReasonCode.HORIZON_VIOLATION,
                    "assignment occupancy is outside the planning horizon",
                    operation_id=asn.operation_id,
                    job_id=_job_of(problem, asn.operation_id),
                    start=asn.start,
                    end=asn.end,
                )
            )
        op = ops.get(asn.operation_id)
        if op is not None and op.latest_finish is not None and asn.end > op.latest_finish:
            out.append(
                _violation(
                    ReasonCode.WINDOW_BROKEN,
                    "operation finishes after latest_finish",
                    operation_id=op.id,
                    job_id=op.job_id,
                    start=asn.start,
                    end=asn.end,
                )
            )
        if op is not None and op.earliest_start is not None and asn.start < op.earliest_start:
            out.append(
                _violation(
                    ReasonCode.WINDOW_BROKEN,
                    "operation starts before earliest_start",
                    operation_id=op.id,
                    job_id=op.job_id,
                    start=asn.start,
                    end=asn.end,
                )
            )
        center = centers.get(asn.work_center_id)
        if center is not None:
            out.extend(
                _calendar_fit(
                    calendars.get(center.calendar_id or ""),
                    asn,
                    occ_start,
                    resource_id=center.id,
                )
            )
        if asn.crew_id:
            crew = crews.get(asn.crew_id)
            if crew is not None:
                out.extend(
                    _calendar_fit(
                        calendars.get(crew.calendar_id or ""),
                        asn,
                        occ_start,
                        resource_id=crew.id,
                    )
                )
    return out


def _calendar_fit(
    calendar: Calendar | None,
    assignment: PlannedAssignment,
    occ_start: datetime,
    *,
    resource_id: str,
) -> list[Violation]:
    if calendar is None or not calendar.windows:
        return []
    for window in calendar.windows:
        if occ_start >= window.start and assignment.end <= window.end:
            return []
    return [
        _violation(
            ReasonCode.CALENDAR_BROKEN,
            "occupancy is not contained in a single calendar window",
            operation_id=assignment.operation_id,
            resource_id=resource_id,
            start=assignment.start,
            end=assignment.end,
            suggested_relaxation=SUGGESTIONS[ReasonCode.WINDOW_BROKEN],
        )
    ]


def _due_release_spares(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    ops = {op.id: op for op in problem.operations}
    jobs = {job.id: job for job in problem.jobs}
    spares = {spare.id: spare for spare in problem.spares}
    by_job_end: dict[str, PlannedAssignment] = {}
    out: list[Violation] = []
    for asn in assignments:
        op = ops.get(asn.operation_id)
        if op is None:
            continue
        job = jobs[op.job_id]
        if job.release_date is not None and asn.start < job.release_date:
            out.append(
                _violation(
                    ReasonCode.RELEASE_VIOLATION,
                    f"operation {op.id} starts before job release_date",
                    operation_id=op.id,
                    job_id=job.id,
                    start=asn.start,
                    end=asn.end,
                )
            )
        current = by_job_end.get(job.id)
        if current is None or asn.end > current.end:
            by_job_end[job.id] = asn
        for spare_id in op.required_spare_ids:
            spare = spares.get(spare_id)
            if spare is None:
                continue
            if spare.quantity <= 0:
                out.append(
                    _violation(
                        ReasonCode.SPARE_UNAVAILABLE,
                        f"spare {spare.code} has quantity {spare.quantity}",
                        operation_id=op.id,
                        job_id=job.id,
                        resource_id=spare.id,
                        start=asn.start,
                        end=asn.end,
                    )
                )
            if spare.available_from is not None and asn.start < spare.available_from:
                out.append(
                    _violation(
                        ReasonCode.SPARE_UNAVAILABLE,
                        f"spare {spare.code} is not available until {spare.available_from.isoformat()}",
                        operation_id=op.id,
                        job_id=job.id,
                        resource_id=spare.id,
                        start=asn.start,
                        end=asn.end,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.SPARE_UNAVAILABLE],
                    )
                )
    used: dict[str, int] = defaultdict(int)
    for asn in assignments:
        op = ops.get(asn.operation_id)
        if op is None:
            continue
        for spare_id in op.required_spare_ids:
            used[spare_id] += 1
    for spare_id, count in used.items():
        spare = spares.get(spare_id)
        if spare is not None and count > spare.quantity:
            out.append(
                _violation(
                    ReasonCode.SPARE_UNAVAILABLE,
                    f"spare {spare.code} used {count} times with quantity {spare.quantity}",
                    resource_id=spare.id,
                )
            )
    for job in problem.jobs:
        last = by_job_end.get(job.id)
        if job.due_date is not None and last is not None and last.end > job.due_date:
            out.append(
                _violation(
                    ReasonCode.DUE_MISSED,
                    f"job {job.id} finishes after due_date",
                    job_id=job.id,
                    operation_id=last.operation_id,
                    start=last.start,
                    end=last.end,
                    suggested_relaxation=SUGGESTIONS[ReasonCode.DUE_MISSED],
                )
            )
    return out


def _setup(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> list[Violation]:
    ops = {op.id: op for op in problem.operations}
    by_center: dict[str, list[PlannedAssignment]] = defaultdict(list)
    for asn in assignments:
        by_center[asn.work_center_id].append(asn)
    out: list[Violation] = []
    for center_id, rows in by_center.items():
        ordered = sorted(rows, key=lambda item: (item.start, item.operation_id))
        previous_state = "idle"
        for asn in ordered:
            op = ops.get(asn.operation_id)
            if op is None:
                continue
            expected = lookup_setup_minutes(
                problem,
                work_center_id=center_id,
                from_state=previous_state,
                to_state=op.setup_state,
            )
            if expected is None:
                out.append(
                    _violation(
                        ReasonCode.MISSING_SETUP,
                        f"no setup cell {previous_state}->{op.setup_state} on {center_id}",
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=center_id,
                        start=asn.start,
                        end=asn.end,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.MISSING_SETUP],
                        details={"from_state": previous_state, "to_state": op.setup_state},
                    )
                )
            elif int(asn.setup_minutes or 0) != int(expected):
                out.append(
                    _violation(
                        ReasonCode.SETUP_MISMATCH,
                        (
                            f"setup {asn.setup_minutes} min, matrix has {expected} "
                            f"for {previous_state}->{op.setup_state}"
                        ),
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=center_id,
                        start=asn.start,
                        end=asn.end,
                    )
                )
            previous_state = op.setup_state
    return out


def _frozen(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> list[Violation]:
    by_op = {asn.operation_id: asn for asn in assignments}
    out: list[Violation] = []
    for frozen in problem.frozen_assignments:
        if not frozen.immutable:
            continue
        placed = by_op.get(frozen.operation_id)
        if placed is None:
            out.append(
                _violation(
                    ReasonCode.FROZEN_MOVED,
                    f"frozen operation {frozen.operation_id} is missing from the plan",
                    operation_id=frozen.operation_id,
                    resource_id=frozen.work_center_id,
                    start=frozen.start,
                    end=frozen.end,
                    suggested_relaxation=SUGGESTIONS[ReasonCode.FROZEN_MOVED],
                )
            )
            continue
        crew_ok = frozen.crew_id is None or placed.crew_id == frozen.crew_id
        if (
            placed.work_center_id != frozen.work_center_id
            or placed.start != frozen.start
            or placed.end != frozen.end
            or not crew_ok
        ):
            out.append(
                _violation(
                    ReasonCode.FROZEN_MOVED,
                    f"frozen operation {frozen.operation_id} was moved",
                    operation_id=frozen.operation_id,
                    resource_id=frozen.work_center_id,
                    start=placed.start,
                    end=placed.end,
                    suggested_relaxation=SUGGESTIONS[ReasonCode.FROZEN_MOVED],
                    details={
                        "expected_start": frozen.start.isoformat(),
                        "expected_end": frozen.end.isoformat(),
                        "expected_work_center_id": frozen.work_center_id,
                    },
                )
            )
    return out


def _job_of(problem: RepairFlowProblem, operation_id: str) -> str | None:
    op = _op(problem, operation_id)
    return None if op is None else op.job_id


def _op(problem: RepairFlowProblem, operation_id: str) -> Operation | None:
    return next((row for row in problem.operations if row.id == operation_id), None)


def _sorted(violations: list[Violation]) -> list[Violation]:
    return sorted(
        violations,
        key=lambda row: (row.code, row.operation_id or "", row.resource_id or "", row.message),
    )


def _violation(
    code: ReasonCode | str,
    message: str,
    *,
    job_id: str | None = None,
    operation_id: str | None = None,
    resource_id: str | None = None,
    start: Any = None,
    end: Any = None,
    suggested_relaxation: str | None = None,
    details: dict[str, Any] | None = None,
) -> Violation:
    text = code.value if isinstance(code, ReasonCode) else str(code)
    return Violation(
        code=text,
        message=message or REASON_RU.get(text, text),
        job_id=job_id,
        operation_id=operation_id,
        resource_id=resource_id,
        start=start,
        end=end,
        suggested_relaxation=suggested_relaxation or SUGGESTIONS.get(text),
        details=details or {},
    )


def kernel_hard_violations(schedule_problem: ScheduleProblem, result: ScheduleResult) -> list[dict[str, Any]]:
    from synaps.solvers.feasibility_checker import FeasibilityChecker, proven_hard_violations

    raw = FeasibilityChecker().check(schedule_problem, list(result.assignments))
    hard = proven_hard_violations(raw)
    out: list[dict[str, Any]] = []
    for item in hard:
        if hasattr(item, "model_dump"):
            out.append(item.model_dump(mode="json"))
        else:
            out.append({"kind": getattr(item, "kind", "KERNEL"), "message": str(item)})
    return out
