"""Planner façade: FIFO baseline, SynAPS portfolio, fail-closed wrap, local replan."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from synaps.model import Assignment, ObjectiveValues, ScheduleProblem, ScheduleResult, SolverStatus
from synaps.portfolio import PortfolioValidationError, repair_schedule, solve_schedule
from synaps.solvers.coverage_outcome import CoverageClass, classify_coverage
from synaps.solvers.registry import available_solver_configs
from synaps.solvers.router import SolveRegime

import repairflow.adapter as core_adapter
from repairflow.adapter import (
    bind_concrete_crews,
    compile_frozen_assignments,
    extract_frozen_from_planned,
    reverse_ids,
    to_schedule_problem,
)
from repairflow.checker import check_plan, kernel_hard_violations
from repairflow.dag_compiler import CompiledDag, compile_dag, propagate_windows
from repairflow.events import InspectionEvent, apply_inspection
from repairflow.evidence import evidence_stamp, fingerprint_payload, runtime_manifest, to_canonical
from repairflow.kernel_compat import (
    KERNEL_CALENDAR_UNSUPPORTED,
    assert_kernel_calendar_compatibility,
    unsupported_auxiliary_calendars,
)
from repairflow.lane_setup import LanePlacement, lane_local_setup_placements
from repairflow.limits import CPSAT_OPS_CAP
from repairflow.metrics import compute_metrics
from repairflow.model import (
    Crew,
    FrozenAssignment,
    Operation,
    PlannedAssignment,
    RepairFlowProblem,
    RepairFlowResult,
    ResultStatus,
    Violation,
    WorkCenter,
)
from repairflow.nervousness import compare as compare_nervousness
from repairflow.reasons import REASON_RU, SUGGESTIONS, ReasonCode
from repairflow.scheduling_contract import end_covering_open_minutes, is_unattended, policy_of
from repairflow.versions import CLAIM_LEVEL, REPAIRFLOW_VERSION, SYNAPS_COMMIT

ClaimStatus = Literal[
    "usage_error",
    "error",
    "rejected",
    "heuristic_feasible",
    "verified",
    "optimal",
]

HEURISTIC_PREFIXES = ("FIFO", "EDD", "ATC", "GREED", "BEAM", "ALNS", "RHC", "repair:")
DEFAULT_SOLVER = "GREED"
# RepairFlow list-dispatch bound. Not a SynAPS solver parameter.
ATC_LOOKAHEAD_K = 2.0
_DOMAIN_LIST_ORDERS = frozenset({"GREED", "EDD", "ATC"})


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
    compiled = compile_dag(problem)
    schedule_problem, id_map = to_schedule_problem(problem, compiled)
    kwargs = dict(solve_kwargs or {})
    if "random_seed" not in kwargs:
        kwargs["random_seed"] = int(problem.domain_attributes.get("seed", 42))

    usage_error = False
    fixpoint = _fixpoint_meta(compiled, iterations=0, converged=True)
    if solver_config.upper() == "FIFO":
        if apply_frozen:
            frozen = compile_frozen_assignments(problem, id_map)
            if frozen:
                kwargs["frozen_assignments"] = frozen
        result = plan_fifo(problem, schedule_problem, id_map, apply_frozen=apply_frozen)
    elif solver_config.upper() in _DOMAIN_LIST_ORDERS:
        result = plan_domain_greed(problem, schedule_problem, id_map, order=solver_config.upper())
    else:
        configs = set(available_solver_configs())
        if solver_config not in configs:
            raise ValueError(
                f"unknown solver_config {solver_config!r}; expected FIFO, EDD, ATC, GREED, "
                f"or one of {sorted(configs)}"
            )
        if solver_config.upper().startswith("CPSAT"):
            refused_cap = _cpsat_cap_refusal(problem, solver_config=solver_config, compiled=compiled)
            if refused_cap is not None:
                return refused_cap
        refused = _kernel_calendar_refusal(problem, solver_config=solver_config, compiled=compiled)
        if refused is not None:
            return refused
        if solver_config.upper().startswith("CPSAT") and "warm_start_assignments" not in kwargs:
            kwargs["warm_start_assignments"] = _as_kernel_assignments(domain_greed(problem), id_map)
            kwargs["auto_greedy_warm_start"] = False
        result, schedule_problem, id_map, compiled, converged, iterations = _kernel_fixpoint(
            problem,
            compiled,
            solver_config=solver_config,
            solve_kwargs=kwargs,
        )
        fixpoint = _fixpoint_meta(compiled, iterations=iterations, converged=converged)
    return wrap(
        problem,
        schedule_problem,
        id_map,
        result,
        solver_config=solver_config,
        usage_error=usage_error,
        kwargs_for_hash={"apply_frozen": apply_frozen, **kwargs},
        fixpoint=fixpoint,
        bind_crews=True,
    )


def replan_after_disruption(
    problem: RepairFlowProblem,
    *,
    base: PlanOutcome,
    disrupted_operation_ids: list[str],
    solver_config: str = "GREED",
) -> PlanOutcome:
    known = {op.id for op in problem.operations}
    unknown = [op_id for op_id in disrupted_operation_ids if op_id not in known]
    if unknown:
        raise ValueError("UNKNOWN_OPERATION: " + ", ".join(unknown))
    if solver_config.upper().startswith("CPSAT"):
        refused_cap = _cpsat_cap_refusal(problem, solver_config=f"repair:{solver_config}")
        if refused_cap is not None:
            return refused_cap
    if solver_config.upper() in _DOMAIN_LIST_ORDERS:
        return _replan_lane_local(
            problem,
            base=base,
            disrupted_operation_ids=list(disrupted_operation_ids),
            solver_config=solver_config.upper(),
        )
    refused = _kernel_calendar_refusal(problem, solver_config=f"repair:{solver_config}")
    if refused is not None:
        return refused
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
        bind_crews=True,
    )


def _replan_lane_local(
    problem: RepairFlowProblem,
    *,
    base: PlanOutcome,
    disrupted_operation_ids: list[str],
    solver_config: str,
) -> PlanOutcome:
    """Reschedule a broken visit without borrowing another lane's setup state.

    The broken slot is consumed: the visit may restart only at or after its old
    end. The tail of that lane and the direct precedence successors are free,
    because their previous state may have changed. Every other issued visit
    stays frozen, including the other lanes of the same work centre.
    """

    disrupted = set(disrupted_operation_ids)
    release = _lane_disruption_release(problem, base.result.assignments, disrupted)
    locked = extract_frozen_from_planned(
        assignments=list(base.result.assignments),
        skip_operation_ids=release,
        reason="disruption_freeze_rest",
    )
    existing = {
        row.operation_id: row
        for row in problem.frozen_assignments
        if row.immutable and row.operation_id not in release
    }
    for row in locked:
        existing.setdefault(row.operation_id, row)
    patched = problem.model_copy(
        update={
            "operations": _restart_after_broken_slot(problem, base.result.assignments, disrupted),
            "frozen_assignments": list(existing.values()),
        }
    )
    schedule_problem, id_map = to_schedule_problem(patched)
    result = plan_domain_greed(patched, schedule_problem, id_map, order=solver_config)
    tagged = result.model_copy(
        update={
            "solver_name": f"repair:{solver_config}",
            "metadata": {**(result.metadata or {}), "repair_engine": "LANE_LOCAL_REPAIR"},
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
            "repair_engine": "LANE_LOCAL_REPAIR",
        },
        bind_crews=True,
    )


def _lane_disruption_release(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    disrupted: set[str],
) -> set[str]:
    release = set(disrupted)
    try:
        placements = lane_local_setup_placements(problem, assignments)
    except ValueError:
        placements = []
    by_lane: dict[tuple[str, int], list[LanePlacement]] = {}
    for item in placements:
        by_lane.setdefault((item.work_center_id, item.lane_index), []).append(item)
    for sequence in by_lane.values():
        ordered = sorted(sequence, key=lambda item: item.occupancy_start)
        opened = False
        for item in ordered:
            if item.operation_id in disrupted:
                opened = True
            if opened:
                release.add(item.operation_id)
    for operation in problem.operations:
        if any(pred_id in disrupted for pred_id in operation.predecessor_ids):
            release.add(operation.id)
    return release


def _restart_after_broken_slot(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    disrupted: set[str],
) -> list[Operation]:
    by_id = {row.operation_id: row for row in assignments}
    restarted: list[Operation] = []
    for operation in problem.operations:
        row = by_id.get(operation.id)
        if operation.id not in disrupted or row is None:
            restarted.append(operation)
            continue
        earliest = row.end
        if operation.earliest_start is not None and operation.earliest_start > earliest:
            earliest = operation.earliest_start
        restarted.append(operation.model_copy(update={"earliest_start": earliest}))
    return restarted


def replan_after_inspection(
    problem: RepairFlowProblem,
    *,
    base: RepairFlowResult,
    event: InspectionEvent,
    solver_config: str = "GREED",
) -> PlanOutcome:
    """Insert the revealed branch. Already issued slots stay; the branch must fit."""

    revised = apply_inspection(problem, event)
    frozen = _freeze_issued(problem, base.assignments)
    revised = RepairFlowProblem.model_validate(
        revised.model_copy(update={"frozen_assignments": frozen}).model_dump(mode="python")
    )
    outcome = plan(revised, solver_config=solver_config)
    diff = compare_nervousness(
        base,
        outcome.result,
        frozen_operation_ids={row.operation_id for row in frozen},
    )
    notes: list[Violation] = []
    if diff.ratio > revised.policy.nervousness_warn_ratio:
        notes.append(
            Violation(
                code=ReasonCode.NERVOUSNESS_HIGH,
                message=REASON_RU[ReasonCode.NERVOUSNESS_HIGH],
                severity="kpi",
                suggested_relaxation=SUGGESTIONS[ReasonCode.NERVOUSNESS_HIGH],
                details={"ratio": diff.ratio, "moved": len(diff.moved)},
            )
        )
    return _attach_replan_notes(outcome, notes, diff.as_dict())


def _freeze_issued(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[FrozenAssignment]:
    """Keep every operation that already has a slot. Only the new branch is free.

    Setup on a post depends on the previous state. Moving an issued neighbour
    changes that setup, so issued slots stay put and the branch has to fit.
    """

    known = {op.id for op in problem.operations}
    locked: dict[str, FrozenAssignment] = {
        row.operation_id: row for row in problem.frozen_assignments if row.immutable
    }
    for row in assignments:
        if row.operation_id not in known or row.operation_id in locked:
            continue
        locked[row.operation_id] = FrozenAssignment(
            operation_id=row.operation_id,
            work_center_id=row.work_center_id,
            crew_id=row.crew_id,
            start=row.start,
            end=row.end,
            setup_minutes=row.setup_minutes,
            immutable=True,
            frozen_reason="inspection_freeze_issued",
        )
    return [locked[op_id] for op_id in sorted(locked)]


def _attach_replan_notes(
    outcome: PlanOutcome,
    notes: list[Violation],
    nervousness: dict[str, object],
) -> PlanOutcome:
    violations = list(outcome.result.violations)
    violations.extend(notes)
    violations.sort(key=lambda row: (row.code, row.operation_id or "", row.resource_id or "", row.message))
    metadata = dict(outcome.result.metadata)
    metadata["nervousness"] = nervousness
    updated = outcome.result.model_copy(update={"violations": violations, "metadata": metadata})
    updated.result_hash = fingerprint_payload(updated.model_dump(mode="json", exclude={"result_hash"}))
    outcome.result = updated
    return outcome


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
    submitted = [row for row in assignments if isinstance(row, PlannedAssignment)]
    outcome = wrap(
        problem,
        schedule_problem,
        live_map,
        result,
        solver_config=solver_config,
        kwargs_for_hash={"verification_origin": "independent_recheck"},
        kernel_status_override=kernel_status,
        domain_assignments=submitted if len(submitted) == len(assignments) else None,
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
    fixpoint: dict[str, Any] | None = None,
    extra_violations: list[Violation] | None = None,
    bind_crews: bool = False,
    domain_assignments: list[PlannedAssignment] | None = None,
) -> PlanOutcome:
    kernel_status = result.status.value if result.status is not None else None
    if kernel_status_override is not ...:
        kernel_status = kernel_status_override  # type: ignore[assignment]
    if domain_assignments is not None:
        planned = list(domain_assignments)
    else:
        planned = _planned_from_kernel(problem, result.assignments, id_map)
    if bind_crews:
        planned = bind_concrete_crews(problem, planned)
    domain_violations = check_plan(
        problem,
        schedule_problem=schedule_problem,
        assignments=planned,
        id_map=id_map,
        kernel_status=kernel_status,
    )
    if extra_violations:
        domain_violations.extend(extra_violations)
        domain_violations.sort(
            key=lambda row: (row.code, row.operation_id or "", row.resource_id or "", row.message)
        )
    fixpoint_info = fixpoint or _fixpoint_meta(compile_dag(problem), iterations=0, converged=True)
    if not fixpoint_info.get("converged", True):
        domain_violations.append(
            Violation(
                code=ReasonCode.DAG_FIXPOINT_NOT_CONVERGED,
                message=REASON_RU[ReasonCode.DAG_FIXPOINT_NOT_CONVERGED],
                severity="hard",
                suggested_relaxation=SUGGESTIONS[ReasonCode.DAG_FIXPOINT_NOT_CONVERGED],
                details=dict(fixpoint_info),
            )
        )
        domain_violations.sort(
            key=lambda row: (row.code, row.operation_id or "", row.resource_id or "", row.message)
        )
    engine_violations = kernel_hard_violations(schedule_problem, result)
    coverage = classify_coverage(
        n_operations=len(schedule_problem.operations),
        n_assigned=len({row.operation_id for row in result.assignments}),
    )
    status, verified, exit_code, claim_status = classify_result(
        solver_config=solver_config,
        kernel_status=result.status,
        coverage=coverage,
        violations=domain_violations,
        engine_violations=engine_violations,
        usage_error=usage_error,
        fixpoint_iterations=int(fixpoint_info.get("iterations", 0)),
        fixpoint_converged=bool(fixpoint_info.get("converged", True)),
    )
    input_hash = fingerprint_payload(problem.model_dump(mode="json"))
    config_payload = {
        "solver_config": solver_config,
        "synaps_commit": SYNAPS_COMMIT,
        "kwargs": to_canonical(kwargs_for_hash or {}),
        "runtime": runtime_manifest(),
    }
    config_hash = fingerprint_payload(config_payload)
    unified = compute_metrics(problem, planned)
    solver_objective = {
        "makespan_minutes": result.objective.makespan_minutes,
        "total_setup_minutes": result.objective.total_setup_minutes,
        "total_tardiness_minutes": result.objective.total_tardiness_minutes,
        "coverage": result.objective.coverage,
        "unscheduled_operations": result.objective.unscheduled_operations,
    }
    stamp = evidence_stamp(
        input_hash=input_hash,
        config_hash=config_hash,
        data_provenance=problem.data_provenance,
        extra={
            "solver_config": solver_config,
            "kernel_status": kernel_status,
            "coverage_class": coverage.value,
            "hard_violation_count": len([row for row in domain_violations if row.severity != "kpi"])
            + len(engine_violations),
            "engine_violations": engine_violations,
            "claim_status": claim_status,
            "fixpoint": fixpoint_info,
            "optimality_scope": fixpoint_info.get("optimality_scope"),
            "config_payload": config_payload,
            "solver_objective": solver_objective,
            "solver": _solver_record(solver_config, kwargs_for_hash or {}, result.metadata),
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
        claim_status=claim_status,
        solver_class=_solver_class(solver_config),
        exit_code=exit_code,
        assignments=planned,
        violations=domain_violations,
        objective=unified,
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
    fixpoint_iterations: int = 1,
    fixpoint_converged: bool = True,
) -> tuple[ResultStatus, bool, int, ClaimStatus]:
    """Return status, verified, exit code, and claim_status.

    `verified` means the notary is empty. `optimal` is only a clean CP-SAT
    OPTIMAL on a single compiled pass. `heuristic_feasible` is reserved for a
    heuristic candidate that has not been through this check.
    """

    if any(row.code == ReasonCode.KERNEL_STATUS_MISSING for row in violations):
        return ResultStatus.NOT_VERIFIED, False, 2, "rejected"
    if usage_error:
        return ResultStatus.ERROR, False, 1, "usage_error"
    if kernel_status is SolverStatus.ERROR:
        return ResultStatus.ERROR, False, 2, "error"
    hard = [row for row in violations if row.severity != "kpi"]
    dirty = bool(hard or engine_violations) or not fixpoint_converged
    incomplete = coverage is not CoverageClass.FULL
    if incomplete:
        dirty = True
    heuristic = any(solver_config.startswith(prefix) for prefix in HEURISTIC_PREFIXES)
    if kernel_status is SolverStatus.INFEASIBLE and not dirty:
        return ResultStatus.INFEASIBLE, False, 2, "rejected"
    if dirty:
        status = ResultStatus.PARTIAL if incomplete else ResultStatus.NOT_VERIFIED
        return status, False, 2, "rejected"
    exact_optimal = (
        kernel_status is SolverStatus.OPTIMAL
        and solver_config.upper().startswith("CPSAT")
        and fixpoint_converged
        and fixpoint_iterations <= 1
    )
    if exact_optimal:
        return ResultStatus.OPTIMAL, True, 0, "optimal"
    if heuristic or kernel_status in {SolverStatus.FEASIBLE, SolverStatus.OPTIMAL}:
        status = ResultStatus.HEURISTIC_FEASIBLE if heuristic else ResultStatus.FEASIBLE
        return status, True, 0, "verified"
    return ResultStatus.NOT_VERIFIED, False, 2, "rejected"


def _solver_class(solver_config: str) -> Literal["heuristic", "exact", "baseline", "recheck"]:
    upper = solver_config.upper()
    if upper.startswith("CPSAT"):
        return "exact"
    if upper.startswith("FIFO") or upper.startswith("EDD") or upper.startswith("ATC"):
        return "baseline"
    if solver_config in {"recheck", "broken"} or upper.startswith("RECHECK"):
        return "recheck"
    return "heuristic"


def _fixpoint_meta(compiled: CompiledDag, *, iterations: int, converged: bool) -> dict[str, Any]:
    scope = "original_chain" if not compiled.cross_edges else "compiled_windows"
    return {
        "strategy": compiled.strategy,
        "iterations": iterations,
        "converged": converged,
        "cross_edges": len(compiled.cross_edges),
        "optimality_scope": scope,
    }


def _cpsat_cap_refusal(
    problem: RepairFlowProblem,
    *,
    solver_config: str,
    compiled: CompiledDag | None = None,
) -> PlanOutcome | None:
    """Refuse CP-SAT before solve when the instance is above the lab cap.

    The recorded route is a capability refusal. Domain list solvers are not
    substituted, and the exact solver is not called.
    """

    count = len(problem.operations)
    if count <= CPSAT_OPS_CAP:
        return None
    current = compiled if compiled is not None else compile_dag(problem)
    schedule_problem, id_map = to_schedule_problem(problem, current)
    result = ScheduleResult(
        status=SolverStatus.ERROR,
        solver_name=solver_config,
        assignments=[],
        objective=ObjectiveValues(
            coverage=0.0,
            unscheduled_operations=count,
        ),
        metadata={
            "error": ReasonCode.CPSAT_OPS_CAP.value,
            "routing": "refused",
            "cpsat_invoked": False,
            "operation_count": count,
            "cpsat_ops_cap": CPSAT_OPS_CAP,
        },
    )
    violation = Violation(
        code=ReasonCode.CPSAT_OPS_CAP,
        message=REASON_RU[ReasonCode.CPSAT_OPS_CAP],
        severity="hard",
        suggested_relaxation=SUGGESTIONS[ReasonCode.CPSAT_OPS_CAP],
        details={
            "routing": "refused",
            "cpsat_invoked": False,
            "operation_count": count,
            "cpsat_ops_cap": CPSAT_OPS_CAP,
        },
    )
    return wrap(
        problem,
        schedule_problem,
        id_map,
        result,
        solver_config=solver_config,
        extra_violations=[violation],
        fixpoint=_fixpoint_meta(current, iterations=0, converged=True),
    )


def _kernel_calendar_refusal(
    problem: RepairFlowProblem,
    *,
    solver_config: str,
    compiled: CompiledDag | None = None,
) -> PlanOutcome | None:
    """Refuse a kernel solve that would drop crew or auxiliary calendars."""

    try:
        assert_kernel_calendar_compatibility(problem)
    except ValueError as exc:
        detail = str(exc)
    else:
        return None
    current = compiled if compiled is not None else compile_dag(problem)
    schedule_problem, id_map = to_schedule_problem(problem, current)
    result = ScheduleResult(
        status=SolverStatus.ERROR,
        solver_name=solver_config,
        assignments=[],
        objective=ObjectiveValues(
            coverage=0.0,
            unscheduled_operations=len(problem.operations),
        ),
        metadata={"error": KERNEL_CALENDAR_UNSUPPORTED, "detail": detail},
    )
    violation = Violation(
        code=ReasonCode.KERNEL_CALENDAR_UNSUPPORTED,
        message=detail,
        severity="hard",
        suggested_relaxation=SUGGESTIONS[ReasonCode.KERNEL_CALENDAR_UNSUPPORTED],
        details={"resources": unsupported_auxiliary_calendars(problem)},
    )
    return wrap(
        problem,
        schedule_problem,
        id_map,
        result,
        solver_config=solver_config,
        extra_violations=[violation],
        fixpoint=_fixpoint_meta(current, iterations=0, converged=True),
    )


def _kernel_fixpoint(
    problem: RepairFlowProblem,
    compiled: CompiledDag,
    *,
    solver_config: str,
    solve_kwargs: dict[str, Any],
) -> tuple[ScheduleResult, ScheduleProblem, dict[str, UUID], CompiledDag, bool, int]:
    """Solve, then lift cross-edge windows until they stop moving."""

    current = compiled
    last_result: ScheduleResult | None = None
    last_problem: ScheduleProblem | None = None
    last_map: dict[str, UUID] | None = None
    for index in range(problem.policy.max_fixpoint_iter):
        core, id_map = to_schedule_problem(problem, current)
        try:
            result = solve_schedule(
                core,
                solver_config=solver_config,
                solve_kwargs=solve_kwargs,
                verify_feasibility=True,
            )
        except PortfolioValidationError as exc:
            result = ScheduleResult(
                status=SolverStatus.ERROR,
                solver_name=solver_config,
                assignments=[],
                objective=ObjectiveValues(
                    coverage=0.0,
                    unscheduled_operations=len(core.operations),
                ),
                metadata={"error": "solve_rejected", "detail": str(exc)},
            )
            return result, core, id_map, current, False, index + 1
        starts, ends = _domain_times(result, id_map)
        current, changed = propagate_windows(current, starts=starts, ends=ends)
        last_result, last_problem, last_map = result, core, id_map
        if not changed:
            return result, core, id_map, current, True, index + 1
    assert last_result is not None and last_problem is not None and last_map is not None
    return last_result, last_problem, last_map, current, False, problem.policy.max_fixpoint_iter


def _domain_times(
    result: ScheduleResult,
    id_map: dict[str, UUID],
) -> tuple[dict[str, datetime], dict[str, datetime]]:
    reversed_map = reverse_ids(id_map)
    starts: dict[str, datetime] = {}
    ends: dict[str, datetime] = {}
    for row in result.assignments:
        kind, ident = reversed_map.get(row.operation_id, ("", ""))
        if kind != "op":
            continue
        starts[ident] = row.start_time
        ends[ident] = row.end_time
    return starts, ends


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
    *,
    order: str = "GREED",
) -> ScheduleResult:
    planned = domain_greed(problem, order=order)
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
    metadata: dict[str, Any] = {
        "constructive": "repairflow_list_schedule",
        "metric_tag": "synthetic_experiment",
    }
    if order == "ATC":
        metadata["dispatch_rule"] = "repairflow_atc"
        metadata["atc_k"] = ATC_LOOKAHEAD_K
    return ScheduleResult(
        solver_name=order,
        status=status,
        assignments=assignments,
        objective=ObjectiveValues(
            makespan_minutes=makespan,
            coverage=coverage,
            unscheduled_operations=unscheduled,
        ),
        metadata=metadata,
    )


def domain_greed(problem: RepairFlowProblem, *, order: str = "GREED") -> list[PlannedAssignment]:
    """Constraint-aware list scheduler used for reasons and as a fallback constructive path."""

    frozen = {row.operation_id: row for row in problem.frozen_assignments if row.immutable}
    pending = {op.id: op for op in problem.operations if op.id not in frozen}
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
    durations = [max(op.duration_min, 1) for op in problem.operations]
    mean_duration = (sum(durations) / len(durations)) if durations else 1.0
    while pending:
        ready = [op for op in pending.values() if all(pred_id in placed for pred_id in op.predecessor_ids)]
        ready.sort(key=lambda op: _list_key(problem, op, order, placed, mean_duration))
        placed_one = False
        for operation in ready:
            choice = _best_slot(problem, operation, list(placed.values()), deadlines.get(operation.id))
            if choice is None:
                continue
            placed[operation.id] = choice
            del pending[operation.id]
            placed_one = True
            break
        if not placed_one:
            break
    return [placed[op.id] for op in problem.operations if op.id in placed]


def _frozen_ancestor_deadlines(problem: RepairFlowProblem) -> dict[str, datetime]:
    by_id = {op.id: op for op in problem.operations}
    child_of: dict[str, list[str]] = {op.id: [] for op in problem.operations}
    for op in problem.operations:
        for pred in op.predecessor_ids:
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
            for pred in op.predecessor_ids:
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
    for pred_id in operation.predecessor_ids:
        current = next((row for row in placed if row.operation_id == pred_id), None)
        if current is None:
            return None
        pred_end = max(pred_end, current.end)
    if operation.earliest_start is not None:
        pred_end = max(pred_end, operation.earliest_start)
    for spare in problem.spares:
        if spare.id in operation.required_spare_ids and spare.available_from is not None:
            pred_end = max(pred_end, spare.available_from)

    eligible_centers = list(operation.eligible_work_center_ids)
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
    try:
        gaps = _lane_gaps(problem, placed, center)
    except ValueError:
        return None
    best: PlannedAssignment | None = None
    best_lane = 0
    for lane_index, prev_end, next_limit, prev_state, follower_id in gaps:
        if not _follower_setup_holds(problem, placed, operation, follower_id):
            continue
        candidate = _slot_from_lane(
            problem,
            operation,
            placed,
            center,
            crew,
            pred_end,
            deadline,
            lane_index=lane_index,
            prev_end=prev_end,
            next_limit=next_limit,
            prev_state=prev_state,
        )
        if candidate is None:
            continue
        if best is None or (candidate.start, lane_index) < (best.start, best_lane):
            best = candidate
            best_lane = lane_index
    return best


def _lane_gaps(
    problem: RepairFlowProblem,
    placed: list[PlannedAssignment],
    center: WorkCenter,
) -> list[tuple[int, datetime, datetime | None, str, str | None]]:
    """Open intervals on each lane: previous end, next occupancy, previous state, follower."""

    horizon = problem.planning_horizon.start
    rows = [row for row in placed if row.work_center_id == center.id]
    if not rows:
        return [(0, horizon, None, "idle", None)]
    operations = {op.id: op for op in problem.operations}
    by_lane: dict[int, list[LanePlacement]] = {}
    for item in lane_local_setup_placements(problem, rows):
        by_lane.setdefault(item.lane_index, []).append(item)
    gaps: list[tuple[int, datetime, datetime | None, str, str | None]] = []
    for lane_index in sorted(by_lane):
        sequence = sorted(by_lane[lane_index], key=lambda item: item.occupancy_start)
        gaps.append((lane_index, horizon, sequence[0].occupancy_start, "idle", sequence[0].operation_id))
        for previous, following in zip(sequence, sequence[1:], strict=False):
            operation = operations.get(previous.operation_id)
            state = operation.setup_state if operation is not None else ""
            gaps.append((lane_index, previous.end, following.occupancy_start, state, following.operation_id))
        last = sequence[-1]
        operation = operations.get(last.operation_id)
        state = operation.setup_state if operation is not None else ""
        gaps.append((lane_index, last.end, None, state, None))
    if len(by_lane) < center.max_parallel:
        gaps.append((len(by_lane), horizon, None, "idle", None))
    return gaps


def _follower_setup_holds(
    problem: RepairFlowProblem,
    placed: list[PlannedAssignment],
    operation: Operation,
    follower_id: str | None,
) -> bool:
    """Inserting here must leave the next visit's already written setup intact."""

    if follower_id is None:
        return True
    follower = next((row for row in problem.operations if row.id == follower_id), None)
    written = next((row for row in placed if row.operation_id == follower_id), None)
    if follower is None or written is None:
        return False
    expected = core_adapter.lookup_setup_minutes(
        problem,
        work_center_id=written.work_center_id,
        from_state=operation.setup_state,
        to_state=follower.setup_state,
    )
    if expected is None:
        return problem.policy.missing_setup == "zero" and int(written.setup_minutes) == 0
    return int(written.setup_minutes) == int(expected)


def _slot_from_lane(
    problem: RepairFlowProblem,
    operation: Operation,
    placed: list[PlannedAssignment],
    center: WorkCenter,
    crew: Crew,
    pred_end: datetime,
    deadline: datetime | None,
    *,
    lane_index: int,
    prev_end: datetime,
    next_limit: datetime | None,
    prev_state: str,
) -> PlannedAssignment | None:
    setup = core_adapter.lookup_setup_minutes(
        problem,
        work_center_id=center.id,
        from_state=prev_state,
        to_state=operation.setup_state,
    )
    if setup is None:
        if problem.policy.missing_setup == "zero":
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
        preemptive = policy_of(operation.domain_attributes) == "preemptive"
        start = _advance_calendar(
            problem,
            center.calendar_id,
            crew.calendar_id,
            cursor,
            setup,
            operation.duration_min,
            preemptive=preemptive,
        )
        if start is None:
            return None
        if preemptive:
            end = end_covering_open_minutes(
                start,
                operation.duration_min,
                _attended_window_masks(problem, center.calendar_id, crew.calendar_id),
                problem.planning_horizon.end,
            )
            if end is None:
                cursor = start + timedelta(minutes=30)
                continue
        else:
            end = start + timedelta(minutes=operation.duration_min)
        if end > problem.planning_horizon.end:
            return None
        if deadline is not None and end > deadline:
            return None
        if next_limit is not None and end > next_limit:
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
        if blocker is None and _lane_choice_matches(
            problem,
            placed,
            candidate,
            lane_index=lane_index,
            prev_state=prev_state,
        ):
            return candidate
        step = blocker if blocker is not None else start
        nxt = step + timedelta(minutes=1)
        cursor = nxt if nxt > cursor else cursor + timedelta(minutes=1)
    return None


def _lane_choice_matches(
    problem: RepairFlowProblem,
    placed: list[PlannedAssignment],
    candidate: PlannedAssignment,
    *,
    lane_index: int,
    prev_state: str,
) -> bool:
    rows = [row for row in placed if row.work_center_id == candidate.work_center_id]
    try:
        placements = lane_local_setup_placements(problem, [*rows, candidate])
    except ValueError:
        return False
    found = next(row for row in placements if row.operation_id == candidate.operation_id)
    return found.lane_index == lane_index and found.previous_state == prev_state


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
    center_rows = [row for row in placed if row.work_center_id == candidate.work_center_id]
    try:
        lane_local_setup_placements(problem, [*center_rows, candidate])
    except ValueError:
        releases = [
            other.end
            for other in center_rows
            if occ_a < other.end and other.start - timedelta(minutes=other.setup_minutes) < candidate.end
        ]
        if not releases and center_rows:
            releases = [min(row.end for row in center_rows)]
        if releases:
            blocker = min(releases)
    for other in placed:
        occ_b = other.start - timedelta(minutes=other.setup_minutes)
        if not (occ_a < other.end and occ_b < candidate.end):
            continue
        shares_crew = candidate.crew_id is not None and other.crew_id == candidate.crew_id
        shares_aux = bool(set(candidate.aux_ids) & set(other.aux_ids))
        if shares_crew or shares_aux:
            blocker = other.end if blocker is None else max(blocker, other.end)
    return blocker


def _calendar_is_unattended(problem: RepairFlowProblem, calendar_id: str) -> bool:
    users = [row.domain_attributes for row in problem.work_centers if row.calendar_id == calendar_id]
    users.extend(row.domain_attributes for row in problem.crews if row.calendar_id == calendar_id)
    users.extend(row.domain_attributes for row in problem.aux_resources if row.calendar_id == calendar_id)
    return bool(users) and all(is_unattended(row) for row in users)


def _attended_window_masks(
    problem: RepairFlowProblem,
    center_cal: str | None,
    crew_cal: str | None,
) -> list[list[tuple[datetime, datetime]]]:
    calendars = {row.id: row for row in problem.calendars}
    masks: list[list[tuple[datetime, datetime]]] = []
    for cal_id in (center_cal, crew_cal):
        if not cal_id or _calendar_is_unattended(problem, cal_id):
            continue
        calendar = calendars.get(cal_id)
        if calendar is None or not calendar.windows:
            continue
        masks.append([(window.start, window.end) for window in calendar.windows])
    return masks


def _advance_calendar(
    problem: RepairFlowProblem,
    center_cal: str | None,
    crew_cal: str | None,
    start: datetime,
    setup: int,
    duration: int,
    *,
    preemptive: bool = False,
) -> datetime | None:
    occupancy = timedelta(minutes=setup + duration)
    calendars = {row.id: row for row in problem.calendars}
    windows = []
    for cal_id in (center_cal, crew_cal):
        if not cal_id:
            continue
        calendar = calendars.get(cal_id)
        if calendar is None:
            continue
        if not calendar.windows:
            if _calendar_is_unattended(problem, cal_id):
                continue
            return None
        windows.append(calendar.windows)
    if preemptive:
        occ_start = start
        if occ_start - timedelta(minutes=setup) < problem.planning_horizon.start:
            occ_start = problem.planning_horizon.start + timedelta(minutes=setup)
        if occ_start >= problem.planning_horizon.end:
            return None
        return occ_start
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


def _list_key(
    problem: RepairFlowProblem,
    operation: Operation,
    order: str,
    placed: dict[str, PlannedAssignment],
    mean_duration: float,
) -> tuple[object, ...]:
    due = _job_due(problem, operation.job_id)
    if order == "ATC":
        index = _atc_index(problem, operation, placed, mean_duration=mean_duration)
        return (-index, operation.id)
    if order == "EDD":
        job = next(row for row in problem.jobs if row.id == operation.job_id)
        return (due, -job.priority, operation.sequence, operation.id)
    return (due, operation.sequence, operation.id)


def _atc_index(
    problem: RepairFlowProblem,
    operation: Operation,
    placed: dict[str, PlannedAssignment],
    *,
    mean_duration: float,
) -> float:
    """Local apparent-tardiness index. Higher is dispatched first.

    ``weight / duration * exp(-max(slack, 0) / (k * mean_duration))``.
    ``k`` is ``ATC_LOOKAHEAD_K``. Weight is ``Job.priority``. Slack is the due
    date minus duration minus the earliest start already fixed by release and
    placed predecessors. This rule is not a SynAPS solver.
    """

    duration = max(operation.duration_min, 1)
    now = _dispatch_time(problem, operation, placed)
    slack = (_job_due(problem, operation.job_id) - now).total_seconds() / 60.0 - duration
    scale = ATC_LOOKAHEAD_K * max(mean_duration, 1.0)
    job = next(row for row in problem.jobs if row.id == operation.job_id)
    return (job.priority / duration) * math.exp(-max(slack, 0.0) / scale)


def _dispatch_time(
    problem: RepairFlowProblem,
    operation: Operation,
    placed: dict[str, PlannedAssignment],
) -> datetime:
    moments = [problem.planning_horizon.start]
    job = next(row for row in problem.jobs if row.id == operation.job_id)
    if job.release_date is not None:
        moments.append(job.release_date)
    if operation.earliest_start is not None:
        moments.append(operation.earliest_start)
    for pred_id in operation.predecessor_ids:
        placed_pred = placed.get(pred_id)
        if placed_pred is not None:
            moments.append(placed_pred.end)
    return max(moments)


def _solver_record(
    solver_config: str,
    kwargs: dict[str, Any],
    kernel_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    kernel: dict[str, Any] = {}
    for key, value in (kernel_metadata or {}).items():
        if value is None or isinstance(value, str | int | float | bool):
            kernel[str(key)] = value
    seed = kwargs.get("random_seed")
    limit = kwargs.get("time_limit_s")
    return {
        "solver_config": solver_config,
        "seed": seed if isinstance(seed, int) else None,
        "time_limit_s": limit if isinstance(limit, int | float) else None,
        "warm_start": "domain_greed" if kwargs.get("warm_start_assignments") else None,
        "kernel": kernel,
    }


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
