"""Planner façade: FIFO baseline, SynAPS portfolio, fail-closed wrap, local replan."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from synaps.model import Assignment, ObjectiveValues, ScheduleProblem, ScheduleResult, SolverStatus
from synaps.portfolio import PortfolioValidationError, repair_schedule, solve_schedule
from synaps.solvers.coverage_outcome import CoverageClass, classify_coverage
from synaps.solvers.registry import available_solver_configs
from synaps.solvers.router import SolveRegime

from repairflow.adapter import (
    bind_concrete_crews,
    compile_frozen_assignments,
    extract_frozen_from_planned,
    lookup_setup_minutes,
    reverse_ids,
    to_schedule_problem,
)
from repairflow.checker import check_plan, kernel_hard_violations
from repairflow.evidence import evidence_stamp, fingerprint_payload
from repairflow.limits import CPSAT_OPS_CAP
from repairflow.model import (
    Crew,
    Operation,
    PlannedAssignment,
    RepairFlowProblem,
    RepairFlowResult,
    ResultStatus,
    Violation,
    WorkCenter,
)
from repairflow.reasons import ReasonCode
from repairflow.versions import CLAIM_LEVEL, REPAIRFLOW_VERSION, SYNAPS_COMMIT

HEURISTIC_PREFIXES = ("FIFO", "GREED", "BEAM", "ALNS", "RHC", "repair:")
DEFAULT_SOLVER = "GREED"


@dataclass
class PlanOutcome:
    problem: RepairFlowProblem
    schedule_problem: ScheduleProblem
    id_map: dict[str, UUID]
    schedule: ScheduleResult
    result: RepairFlowResult
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.result.verified_feasible and self.result.exit_code == 0


def plan(
    problem: RepairFlowProblem,
    *,
    solver_config: str = DEFAULT_SOLVER,
    solve_kwargs: dict[str, Any] | None = None,
    apply_frozen: bool = True,
) -> PlanOutcome:
    schedule_problem, id_map = to_schedule_problem(problem)
    kwargs = dict(solve_kwargs or {})
    if apply_frozen:
        frozen = compile_frozen_assignments(problem, id_map)
        if frozen:
            kwargs["frozen_assignments"] = frozen
    if "random_seed" not in kwargs:
        kwargs["random_seed"] = int(problem.domain_attributes.get("seed", 42))

    usage_error = False
    if solver_config.upper() == "FIFO":
        result = plan_fifo(problem, schedule_problem, id_map, apply_frozen=apply_frozen)
    elif solver_config.upper() == "GREED":
        result = plan_domain_greed(problem, schedule_problem, id_map)
    else:
        configs = set(available_solver_configs())
        if solver_config not in configs:
            raise ValueError(
                f"unknown solver_config {solver_config!r}; expected FIFO, GREED, or one of {sorted(configs)}"
            )
        if solver_config.upper().startswith("CPSAT") and len(schedule_problem.operations) > CPSAT_OPS_CAP:
            raise ValueError(
                f"CP-SAT refused on {len(schedule_problem.operations)} ops (cap {CPSAT_OPS_CAP})"
            )
        try:
            result = solve_schedule(
                schedule_problem,
                solver_config=solver_config,
                solve_kwargs=kwargs,
                verify_feasibility=True,
            )
        except PortfolioValidationError as exc:
            usage_error = True
            result = ScheduleResult(
                status=SolverStatus.ERROR,
                solver_name=solver_config,
                assignments=[],
                objective=ObjectiveValues(
                    coverage=0.0,
                    unscheduled_operations=len(schedule_problem.operations),
                ),
                metadata={"error": "solve_rejected", "detail": str(exc)},
            )
    return wrap(
        problem,
        schedule_problem,
        id_map,
        result,
        solver_config=solver_config,
        usage_error=usage_error,
        kwargs_for_hash={"apply_frozen": apply_frozen, **kwargs},
    )


def replan_after_disruption(
    problem: RepairFlowProblem,
    *,
    base: PlanOutcome,
    disrupted_operation_ids: list[str],
    solver_config: str = "GREED",
) -> PlanOutcome:
    schedule_problem, id_map = to_schedule_problem(problem)
    skip = set(disrupted_operation_ids)
    locked = extract_frozen_from_planned(
        assignments=list(base.result.assignments),
        skip_operation_ids=skip,
        reason="disruption_freeze_rest",
    )
    existing = {row.operation_id: row for row in problem.frozen_assignments if row.immutable}
    for row in locked:
        existing.setdefault(row.operation_id, row)
    patched = problem.model_copy(update={"frozen_assignments": list(existing.values())})
    disrupted_ops = [id_map[f"op:{op_id}"] for op_id in disrupted_operation_ids if f"op:{op_id}" in id_map]
    frozen_asns = compile_frozen_assignments(patched, id_map)
    try:
        result = repair_schedule(
            schedule_problem,
            base_assignments=[row.model_copy(deep=True) for row in base.schedule.assignments],
            disrupted_op_ids=disrupted_ops,
            regime=SolveRegime.BREAKDOWN,
            solve_kwargs={"frozen_assignments": frozen_asns} if frozen_asns else {},
            verify_feasibility=True,
        )
    except PortfolioValidationError as exc:
        result = ScheduleResult(
            status=SolverStatus.ERROR,
            solver_name=f"repair:{solver_config}",
            assignments=list(base.schedule.assignments),
            metadata={"error": "repair_rejected", "detail": str(exc)},
        )
    tagged = result.model_copy(
        update={
            "solver_name": f"repair:{solver_config}",
            "metadata": {**(result.metadata or {}), "repair_engine": "INCREMENTAL_REPAIR"},
        }
    )
    return wrap(
        patched,
        schedule_problem,
        id_map,
        tagged,
        solver_config=f"repair:{solver_config}",
        kwargs_for_hash={
            "disrupted_operation_ids": list(disrupted_operation_ids),
            "repair_engine": "INCREMENTAL_REPAIR",
        },
    )


def recheck(
    problem: RepairFlowProblem,
    *,
    assignments: list[Assignment] | list[PlannedAssignment],
    solver_config: str = "recheck",
    kernel_status: str | None,
    id_map: dict[str, UUID] | None = None,
) -> PlanOutcome:
    schedule_problem, live_map = to_schedule_problem(problem)
    if id_map is not None and id_map != live_map:
        dummy = ScheduleResult(
            solver_name=solver_config,
            status=SolverStatus.ERROR,
            assignments=[],
            metadata={"error": "id_map_diverged_from_recompiled_problem"},
        )
        outcome = wrap(
            problem,
            schedule_problem,
            live_map,
            dummy,
            solver_config=solver_config,
            usage_error=True,
        )
        outcome.result.metadata["verification_origin"] = "independent_recheck"
        return outcome
    kernel_assignments = _as_kernel_assignments(assignments, live_map)
    result = ScheduleResult(
        solver_name=solver_config,
        status=_status_from_text(kernel_status),
        assignments=kernel_assignments,
        metadata={"verification_origin": "independent_recheck"},
    )
    outcome = wrap(
        problem,
        schedule_problem,
        live_map,
        result,
        solver_config=solver_config,
        kwargs_for_hash={"verification_origin": "independent_recheck"},
        kernel_status_override=kernel_status,
    )
    outcome.result.metadata["verification_origin"] = "independent_recheck"
    return outcome


def wrap(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
    result: ScheduleResult,
    *,
    solver_config: str,
    usage_error: bool = False,
    kwargs_for_hash: dict[str, Any] | None = None,
    kernel_status_override: str | None | object = ...,
) -> PlanOutcome:
    kernel_status = result.status.value if result.status is not None else None
    if kernel_status_override is not ...:
        kernel_status = kernel_status_override  # type: ignore[assignment]
    planned = bind_concrete_crews(problem, _planned_from_kernel(problem, result.assignments, id_map))
    domain_violations = check_plan(
        problem,
        schedule_problem=schedule_problem,
        assignments=planned,
        id_map=id_map,
        kernel_status=kernel_status,
    )
    engine_violations = kernel_hard_violations(schedule_problem, result)
    coverage = classify_coverage(
        n_operations=len(schedule_problem.operations),
        n_assigned=len({row.operation_id for row in result.assignments}),
    )
    status, verified, exit_code = classify_result(
        solver_config=solver_config,
        kernel_status=result.status,
        coverage=coverage,
        violations=domain_violations,
        engine_violations=engine_violations,
        usage_error=usage_error,
        allow_partial=problem.policy.allow_partial_plan,
    )
    input_hash = fingerprint_payload(problem.model_dump(mode="json"))
    config_hash = fingerprint_payload(
        {
            "solver_config": solver_config,
            "synaps_commit": SYNAPS_COMMIT,
            "kwargs": kwargs_for_hash or {},
        }
    )
    stamp = evidence_stamp(
        input_hash=input_hash,
        config_hash=config_hash,
        data_provenance=problem.data_provenance,
        extra={
            "solver_config": solver_config,
            "kernel_status": kernel_status,
            "coverage_class": coverage.value,
            "hard_violation_count": len(domain_violations) + len(engine_violations),
            "engine_violations": engine_violations,
        },
    )
    payload = RepairFlowResult(
        instance_id=problem.instance_id,
        status=status,
        verified_feasible=verified,
        input_hash=input_hash,
        config_hash=config_hash,
        repairflow_version=REPAIRFLOW_VERSION,
        synaps_commit=SYNAPS_COMMIT,
        claim_level=CLAIM_LEVEL,
        data_provenance=problem.data_provenance,
        kernel_status=kernel_status,
        solver_config=solver_config,
        exit_code=exit_code,
        assignments=planned,
        violations=domain_violations,
        objective={
            "makespan_minutes": result.objective.makespan_minutes,
            "total_setup_minutes": result.objective.total_setup_minutes,
            "total_tardiness_minutes": result.objective.total_tardiness_minutes,
            "coverage": result.objective.coverage,
            "unscheduled_operations": result.objective.unscheduled_operations,
        },
        metadata=stamp,
    )
    payload.result_hash = fingerprint_payload(payload.model_dump(mode="json", exclude={"result_hash"}))
    return PlanOutcome(
        problem=problem,
        schedule_problem=schedule_problem,
        id_map=id_map,
        schedule=result,
        result=payload,
        metadata=stamp,
    )


def classify_result(
    *,
    solver_config: str,
    kernel_status: SolverStatus,
    coverage: CoverageClass,
    violations: list[Violation],
    engine_violations: list[dict[str, Any]],
    usage_error: bool,
    allow_partial: bool,
) -> tuple[ResultStatus, bool, int]:
    if any(row.code == ReasonCode.KERNEL_STATUS_MISSING for row in violations):
        return ResultStatus.NOT_VERIFIED, False, 2
    if usage_error or kernel_status is SolverStatus.ERROR:
        return ResultStatus.ERROR, False, 1
    dirty = bool(violations or engine_violations)
    incomplete = coverage is not CoverageClass.FULL
    if incomplete and not allow_partial:
        dirty = True
    heuristic = any(solver_config.startswith(prefix) for prefix in HEURISTIC_PREFIXES)
    if kernel_status is SolverStatus.INFEASIBLE and not dirty:
        return ResultStatus.INFEASIBLE, False, 2
    if dirty:
        status = ResultStatus.PARTIAL if incomplete else ResultStatus.NOT_VERIFIED
        return status, False, 2
    if kernel_status is SolverStatus.OPTIMAL and solver_config.upper().startswith("CPSAT"):
        return ResultStatus.OPTIMAL, True, 0
    if heuristic:
        return ResultStatus.HEURISTIC_FEASIBLE, True, 0
    if kernel_status in {SolverStatus.FEASIBLE, SolverStatus.OPTIMAL}:
        return ResultStatus.FEASIBLE, True, 0
    return ResultStatus.NOT_VERIFIED, False, 2


def plan_fifo(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
    *,
    apply_frozen: bool,
) -> ScheduleResult:
    """Naive earliest-due packing. Intentionally ignores skills, eligibility and setup."""

    ops = {op.id: op for op in problem.operations}
    jobs = {job.id: job for job in problem.jobs}
    centers = list(problem.work_centers)
    crews = list(problem.crews)
    assignments: list[Assignment] = []
    frozen_ops: set[str] = set()
    if apply_frozen:
        for frozen in compile_frozen_assignments(problem, id_map):
            assignments.append(frozen)
            reversed_map = reverse_ids(id_map)
            frozen_ops.add(reversed_map[frozen.operation_id][1])

    ordered_jobs = sorted(
        problem.jobs,
        key=lambda job: (job.due_date or problem.planning_horizon.end, job.external_ref or job.id),
    )
    for job in ordered_jobs:
        job_ops = sorted(
            [op for op in problem.operations if op.job_id == job.id],
            key=lambda op: (op.sequence, op.id),
        )
        # Naive calendar queue: chain inside the job, ignore other jobs' occupancy.
        pred_end = job.release_date or problem.planning_horizon.start
        for operation in job_ops:
            if operation.id in frozen_ops:
                frozen_row = next(
                    row for row in assignments if row.operation_id == id_map[f"op:{operation.id}"]
                )
                pred_end = frozen_row.end_time
                continue
            center = centers[0] if centers else None
            crew = crews[0] if crews else None
            if center is None:
                continue
            start = max(pred_end, problem.planning_horizon.start)
            end = start + timedelta(minutes=operation.duration_min)
            aux_ids = []
            if crew is not None:
                aux_ids.append(id_map[f"crew:{crew.id}"])
            assignments.append(
                Assignment(
                    operation_id=id_map[f"op:{operation.id}"],
                    work_center_id=id_map[f"wc:{center.id}"],
                    start_time=start,
                    end_time=end,
                    setup_minutes=0,
                    aux_resource_ids=aux_ids,
                )
            )
            pred_end = end
            _ = ops, jobs

    unscheduled = len(schedule_problem.operations) - len(assignments)
    coverage = 1.0 if not schedule_problem.operations else len(assignments) / len(schedule_problem.operations)
    makespan = 0.0
    if assignments:
        makespan = (
            max(row.end_time for row in assignments) - min(row.start_time for row in assignments)
        ).total_seconds() / 60.0
    status = (
        SolverStatus.INFEASIBLE if schedule_problem.operations and not assignments else SolverStatus.FEASIBLE
    )
    return ScheduleResult(
        solver_name="FIFO",
        status=status,
        assignments=assignments,
        objective=ObjectiveValues(
            makespan_minutes=makespan,
            coverage=coverage,
            unscheduled_operations=unscheduled,
        ),
        metadata={"baseline": "fifo_due_date", "metric_tag": "synthetic_experiment"},
    )


def plan_domain_greed(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
) -> ScheduleResult:
    planned = domain_greed(problem)
    assignments = _as_kernel_assignments(planned, id_map)
    unscheduled = len(schedule_problem.operations) - len(assignments)
    coverage = 1.0 if not schedule_problem.operations else len(assignments) / len(schedule_problem.operations)
    makespan = 0.0
    if assignments:
        makespan = (
            max(row.end_time for row in assignments) - min(row.start_time for row in assignments)
        ).total_seconds() / 60.0
    status = (
        SolverStatus.INFEASIBLE if schedule_problem.operations and not assignments else SolverStatus.FEASIBLE
    )
    return ScheduleResult(
        solver_name="GREED",
        status=status,
        assignments=assignments,
        objective=ObjectiveValues(
            makespan_minutes=makespan,
            coverage=coverage,
            unscheduled_operations=unscheduled,
        ),
        metadata={"constructive": "repairflow_list_schedule", "metric_tag": "synthetic_experiment"},
    )


def domain_greed(problem: RepairFlowProblem) -> list[PlannedAssignment]:
    """Constraint-aware list scheduler used for reasons and as a fallback constructive path."""

    frozen = {row.operation_id: row for row in problem.frozen_assignments if row.immutable}
    remaining = [op for op in problem.operations if op.id not in frozen]
    remaining.sort(key=lambda op: (_job_due(problem, op.job_id), op.sequence, op.id))
    placed: dict[str, PlannedAssignment] = {}
    for row in problem.frozen_assignments:
        if not row.immutable:
            continue
        placed[row.operation_id] = PlannedAssignment(
            operation_id=row.operation_id,
            work_center_id=row.work_center_id,
            crew_id=row.crew_id,
            start=row.start,
            end=row.end,
            setup_minutes=row.setup_minutes,
            reason="frozen",
        )
    deadlines = _frozen_ancestor_deadlines(problem)
    for operation in remaining:
        choice = _best_slot(problem, operation, list(placed.values()), deadlines.get(operation.id))
        if choice is None:
            continue
        placed[operation.id] = choice
    return [placed[op.id] for op in problem.operations if op.id in placed]


def _frozen_ancestor_deadlines(problem: RepairFlowProblem) -> dict[str, datetime]:
    by_id = {op.id: op for op in problem.operations}
    child_of: dict[str, list[str]] = {op.id: [] for op in problem.operations}
    for op in problem.operations:
        for pred in op.predecessor_ids or _implied_pred(problem, op):
            child_of.setdefault(pred, []).append(op.id)
    deadlines: dict[str, datetime] = {}
    for frozen in problem.frozen_assignments:
        if not frozen.immutable or frozen.operation_id not in by_id:
            continue
        stack = [frozen.operation_id]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            op = by_id[current]
            for pred in op.predecessor_ids or _implied_pred(problem, op):
                previous = deadlines.get(pred)
                deadlines[pred] = frozen.start if previous is None else min(previous, frozen.start)
                stack.append(pred)
    return deadlines


def _best_slot(
    problem: RepairFlowProblem,
    operation: Operation,
    placed: list[PlannedAssignment],
    deadline: datetime | None,
) -> PlannedAssignment | None:
    job = next(job for job in problem.jobs if job.id == operation.job_id)
    pred_end = job.release_date or problem.planning_horizon.start
    for pred_id in operation.predecessor_ids or _implied_pred(problem, operation):
        current = next((row for row in placed if row.operation_id == pred_id), None)
        if current is None:
            return None
        pred_end = max(pred_end, current.end)
    if operation.earliest_start is not None:
        pred_end = max(pred_end, operation.earliest_start)
    for spare in problem.spares:
        if spare.id in operation.required_spare_ids and spare.available_from is not None:
            pred_end = max(pred_end, spare.available_from)

    eligible_centers = operation.eligible_work_center_ids or [wc.id for wc in problem.work_centers]
    eligible_crews = [
        crew
        for crew in problem.crews
        if not operation.required_skills or set(operation.required_skills) <= set(crew.skills)
    ]
    best: PlannedAssignment | None = None
    for center in problem.work_centers:
        if center.id not in eligible_centers:
            continue
        if center.eligible_unit_types and job.unit_type and job.unit_type not in center.eligible_unit_types:
            continue
        for crew in eligible_crews:
            candidate = _scan_slot(problem, operation, placed, center, crew, pred_end, deadline)
            if candidate is None:
                continue
            if best is None or (candidate.start, center.code, crew.code) < (
                best.start,
                next(wc.code for wc in problem.work_centers if wc.id == best.work_center_id),
                next(cr.code for cr in problem.crews if cr.id == best.crew_id),
            ):
                best = candidate
    return best


def _scan_slot(
    problem: RepairFlowProblem,
    operation: Operation,
    placed: list[PlannedAssignment],
    center: WorkCenter,
    crew: Crew,
    pred_end: datetime,
    deadline: datetime | None,
) -> PlannedAssignment | None:
    ops = {op.id: op for op in problem.operations}
    last_center = _last_on_center(center.id, placed, before=deadline)
    prev_state = "idle"
    prev_end = problem.planning_horizon.start
    if last_center is not None:
        prev_op = ops.get(last_center.operation_id)
        prev_state = prev_op.setup_state if prev_op is not None else "idle"
        prev_end = last_center.end
    setup = lookup_setup_minutes(
        problem,
        work_center_id=center.id,
        from_state=prev_state,
        to_state=operation.setup_state,
    )
    if setup is None:
        if problem.policy.missing_setup == "zero" or prev_state == operation.setup_state:
            setup = 0
        else:
            return None
    last_crew = _last_on_crew(crew.id, placed, before=deadline)
    crew_free = last_crew.end if last_crew is not None else problem.planning_horizon.start
    last_aux = problem.planning_horizon.start
    for aux_id in operation.required_aux_ids:
        last = _last_on_aux(aux_id, placed, before=deadline)
        if last is not None:
            last_aux = max(last_aux, last.end)
    cursor = max(
        pred_end,
        prev_end + timedelta(minutes=setup),
        crew_free + timedelta(minutes=setup),
        last_aux,
    )
    for _ in range(256):
        start = _advance_calendar(
            problem,
            center.calendar_id,
            crew.calendar_id,
            cursor,
            setup,
            operation.duration_min,
        )
        if start is None:
            return None
        end = start + timedelta(minutes=operation.duration_min)
        if end > problem.planning_horizon.end:
            return None
        if deadline is not None and end > deadline:
            return None
        candidate = PlannedAssignment(
            operation_id=operation.id,
            work_center_id=center.id,
            crew_id=crew.id,
            aux_ids=list(operation.required_aux_ids),
            start=start,
            end=end,
            setup_minutes=int(setup),
            reason=f"list-schedule post={center.code} crew={crew.code} setup={setup}",
        )
        blocker = _conflict_end(problem, candidate, placed)
        if blocker is None:
            return candidate
        nxt = blocker + timedelta(minutes=setup)
        cursor = nxt if nxt > cursor else cursor + timedelta(minutes=1)
    return None


def _last_on_center(
    center_id: str,
    placed: list[PlannedAssignment],
    *,
    before: datetime | None = None,
) -> PlannedAssignment | None:
    rows = [row for row in placed if row.work_center_id == center_id]
    if before is not None:
        rows = [row for row in rows if row.start < before]
    return max(rows, key=lambda row: row.end) if rows else None


def _last_on_crew(
    crew_id: str,
    placed: list[PlannedAssignment],
    *,
    before: datetime | None = None,
) -> PlannedAssignment | None:
    rows = [row for row in placed if row.crew_id == crew_id]
    if before is not None:
        rows = [row for row in rows if row.start < before]
    return max(rows, key=lambda row: row.end) if rows else None


def _last_on_aux(
    aux_id: str,
    placed: list[PlannedAssignment],
    *,
    before: datetime | None = None,
) -> PlannedAssignment | None:
    rows = [row for row in placed if aux_id in row.aux_ids]
    if before is not None:
        rows = [row for row in rows if row.start < before]
    return max(rows, key=lambda row: row.end) if rows else None


def _conflict_end(
    problem: RepairFlowProblem,
    candidate: PlannedAssignment,
    placed: list[PlannedAssignment],
) -> datetime | None:
    occ_a = candidate.start - timedelta(minutes=candidate.setup_minutes)
    blocker: datetime | None = None
    for other in placed:
        occ_b = other.start - timedelta(minutes=other.setup_minutes)
        if not (occ_a < other.end and occ_b < candidate.end):
            continue
        shares = other.work_center_id == candidate.work_center_id
        shares = shares or (candidate.crew_id is not None and other.crew_id == candidate.crew_id)
        shares = shares or bool(set(candidate.aux_ids) & set(other.aux_ids))
        if shares:
            blocker = other.end if blocker is None else max(blocker, other.end)
    _ = problem
    return blocker


def _advance_calendar(
    problem: RepairFlowProblem,
    center_cal: str | None,
    crew_cal: str | None,
    start: datetime,
    setup: int,
    duration: int,
) -> datetime | None:
    occupancy = timedelta(minutes=setup + duration)
    calendars = {row.id: row for row in problem.calendars}
    windows = []
    for cal_id in (center_cal, crew_cal):
        calendar = calendars.get(cal_id or "")
        if calendar is not None and calendar.windows:
            windows.append(calendar.windows)
    if not windows:
        occ_start = start
        end = start + timedelta(minutes=duration)
        if occ_start - timedelta(minutes=setup) < problem.planning_horizon.start:
            occ_start = problem.planning_horizon.start + timedelta(minutes=setup)
            end = occ_start + timedelta(minutes=duration)
        return occ_start if end <= problem.planning_horizon.end else None
    # Intersect: candidate must fit in one window of each calendar.
    cursor = start
    for _ in range(256):
        occ_start = cursor
        end = cursor + timedelta(minutes=duration)
        setup_start = occ_start - timedelta(minutes=setup)
        ok = True
        shifted = None
        for series in windows:
            fitted = None
            for window in series:
                if setup_start >= window.start and end <= window.end:
                    fitted = occ_start
                    break
                if window.end > setup_start and (window.end - window.start) >= occupancy:
                    trial = max(window.start + timedelta(minutes=setup), occ_start)
                    if trial + timedelta(minutes=duration) <= window.end:
                        fitted = trial
                        break
            if fitted is None:
                ok = False
                break
            if fitted > occ_start:
                shifted = fitted
                break
        if ok and shifted is None:
            return occ_start
        if shifted is not None:
            cursor = shifted
            continue
        cursor = cursor + timedelta(minutes=30)
        if cursor > problem.planning_horizon.end:
            return None
    return None


def _implied_pred(problem: RepairFlowProblem, operation: Operation) -> list[str]:
    previous = [
        row.id
        for row in problem.operations
        if row.job_id == operation.job_id and row.sequence < operation.sequence
    ]
    if not previous:
        return []
    current = [row for row in problem.operations if row.id in previous]
    return [max(current, key=lambda row: row.sequence).id]


def _job_due(problem: RepairFlowProblem, job_id: str) -> datetime:
    job = next(row for row in problem.jobs if row.id == job_id)
    return job.due_date or problem.planning_horizon.end


def _planned_from_kernel(
    problem: RepairFlowProblem,
    assignments: list[Assignment],
    id_map: dict[str, UUID],
) -> list[PlannedAssignment]:
    reversed_map = reverse_ids(id_map)
    ops = {op.id: op for op in problem.operations}
    out: list[PlannedAssignment] = []
    for row in sorted(assignments, key=lambda item: (item.start_time, str(item.operation_id))):
        op_id = reversed_map.get(row.operation_id, ("op", str(row.operation_id)))[1]
        wc_id = reversed_map.get(row.work_center_id, ("wc", str(row.work_center_id)))[1]
        crew_id = None
        aux_ids: list[str] = []
        for aux in row.aux_resource_ids:
            kind, ident = reversed_map.get(aux, ("aux", str(aux)))
            if kind == "crew":
                crew_id = ident
            elif kind == "aux":
                aux_ids.append(ident)
        operation = ops.get(op_id)
        reason = "kernel assignment"
        if operation is not None:
            reason = f"job={operation.job_id} post={wc_id} crew={crew_id or '—'} setup={row.setup_minutes}m"
        out.append(
            PlannedAssignment(
                operation_id=op_id,
                work_center_id=wc_id,
                crew_id=crew_id,
                aux_ids=aux_ids or list(operation.required_aux_ids if operation else []),
                start=row.start_time,
                end=row.end_time,
                setup_minutes=int(row.setup_minutes or 0),
                reason=reason,
            )
        )
    return out


def _as_kernel_assignments(
    assignments: list[Assignment] | list[PlannedAssignment],
    id_map: dict[str, UUID],
) -> list[Assignment]:
    out: list[Assignment] = []
    for row in assignments:
        if isinstance(row, Assignment):
            out.append(row)
            continue
        aux_ids = [id_map[f"aux:{aux_id}"] for aux_id in row.aux_ids if f"aux:{aux_id}" in id_map]
        if row.crew_id and f"crew:{row.crew_id}" in id_map:
            aux_ids.append(id_map[f"crew:{row.crew_id}"])
        out.append(
            Assignment(
                operation_id=id_map[f"op:{row.operation_id}"],
                work_center_id=id_map[f"wc:{row.work_center_id}"],
                start_time=row.start,
                end_time=row.end,
                setup_minutes=row.setup_minutes,
                aux_resource_ids=aux_ids,
            )
        )
    return out


def _status_from_text(value: str | None) -> SolverStatus:
    if not value:
        return SolverStatus.ERROR
    try:
        return SolverStatus(value)
    except ValueError:
        return SolverStatus.ERROR
