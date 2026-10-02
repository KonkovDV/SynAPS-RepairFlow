"""Compile RepairFlowProblem → SynAPS ScheduleProblem without mutating kernel types."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid5

from synaps.model import (
    Assignment,
    AuxiliaryResource,
    Operation,
    OperationAuxRequirement,
    Order,
    ScheduleProblem,
    SetupEntry,
    ShiftInterval,
    State,
    WorkCenter,
)

from repairflow.checker_primitives import (
    bind_concrete_crews as bind_concrete_crews,
)
from repairflow.checker_primitives import (
    lookup_setup_minutes,
)
from repairflow.checker_primitives import (
    reverse_ids as reverse_ids,
)

__all__ = [
    "bind_concrete_crews",
    "compile_frozen_assignments",
    "extract_frozen_from_planned",
    "lookup_setup_minutes",
    "reverse_ids",
    "to_schedule_problem",
]
from repairflow.dag_compiler import CompiledDag, compile_dag
from repairflow.kernel_compat import kernel_calendar_windows
from repairflow.model import (
    FrozenAssignment,
    PlannedAssignment,
    RepairFlowProblem,
)
from repairflow.model import (
    Operation as DomainOperation,
)

_NS = UUID("7e9a1c2b-4d5e-6f70-8192-a3b4c5d6e7f8")


def sid(*parts: str) -> UUID:
    return uuid5(_NS, "repairflow:" + ":".join(parts))


def _preserve_sequence(op_ids: tuple[str, ...], ops_by_id: dict[str, DomainOperation]) -> bool:
    """Keep original seq_in_order when the segment is already that chain."""

    rows = [ops_by_id[op_id] for op_id in op_ids]
    if len({row.sequence for row in rows}) != len(rows):
        return False
    ordered = sorted(rows, key=lambda row: (row.sequence, row.id))
    return [row.id for row in ordered] == list(op_ids)


def to_schedule_problem(
    problem: RepairFlowProblem,
    compiled: CompiledDag | None = None,
) -> tuple[ScheduleProblem, dict[str, UUID]]:
    id_map: dict[str, UUID] = {}
    states_by_code: dict[str, State] = {}

    def state_of(code: str) -> State:
        if code not in states_by_code:
            state = State(id=sid("state", code or "idle"), code=code or "idle", label=code or "idle")
            states_by_code[code] = state
            id_map[f"state:{code or 'idle'}"] = state.id
        return states_by_code[code]

    compiled_dag = compiled if compiled is not None else compile_dag(problem)
    state_of("idle")
    for operation in problem.operations:
        state_of(operation.setup_state)

    calendars = {row.id: row for row in problem.calendars}
    work_centers: list[WorkCenter] = []
    for center in problem.work_centers:
        wc_id = sid("wc", center.id)
        id_map[f"wc:{center.id}"] = wc_id
        calendar_rows = []
        calendar = calendars.get(center.calendar_id or "")
        if calendar is not None:
            calendar_rows = [ShiftInterval(start=window.start, end=window.end) for window in calendar.windows]
        work_centers.append(
            WorkCenter(
                id=wc_id,
                code=center.code,
                capability_group=center.capability_group,
                max_parallel=center.max_parallel,
                calendar=calendar_rows,
                domain_attributes={"repairflow_id": center.id},
            )
        )

    orders: list[Order] = []
    jobs_by_id = {job.id: job for job in problem.jobs}
    ops_by_id = {op.id: op for op in problem.operations}
    job_index = {job.id: index for index, job in enumerate(problem.jobs)}
    ordered_segments = sorted(
        compiled_dag.segments,
        key=lambda segment: (job_index.get(segment.job_id, 10**9), segment.op_ids[0]),
    )
    segments_by_job: dict[str, list[str]] = {}
    for segment in ordered_segments:
        segments_by_job.setdefault(segment.job_id, []).append(segment.id)
    kernel_order_of: dict[str, UUID] = {}
    for segment in ordered_segments:
        job = jobs_by_id[segment.job_id]
        sole = segments_by_job[segment.job_id] == [segment.id]
        order_key = job.id if sole else f"{job.id}:{segment.id}"
        order_id = sid("job", order_key)
        id_map[f"job:{order_key}"] = order_id
        kernel_order_of[segment.id] = order_id
        due = job.due_date or problem.planning_horizon.end
        orders.append(
            Order(
                id=order_id,
                external_ref=job.external_ref or job.id,
                release_date=job.release_date,
                due_date=due,
                priority=job.priority,
                domain_attributes={
                    "repairflow_id": job.id,
                    "segment_id": segment.id,
                    "asset_code": job.asset_code,
                    "unit_type": job.unit_type,
                },
            )
        )

    kernel_ops: list[Operation] = []
    for segment in ordered_segments:
        job = jobs_by_id[segment.job_id]
        previous: UUID | None = None
        preserve_sequence = _preserve_sequence(segment.op_ids, ops_by_id)
        for index, op_domain_id in enumerate(segment.op_ids, start=1):
            operation = ops_by_id[op_domain_id]
            op_id = sid("op", operation.id)
            id_map[f"op:{operation.id}"] = op_id
            if not operation.eligible_work_center_ids:
                raise ValueError(
                    f"operation {operation.id} has empty eligible_work_center_ids "
                    "(empty does not mean every post)"
                )
            eligible = [id_map[f"wc:{wc_id}"] for wc_id in operation.eligible_work_center_ids]
            earliest = operation.earliest_start or job.release_date
            for spare in problem.spares:
                if spare.id in operation.required_spare_ids and spare.available_from is not None:
                    if earliest is None:
                        earliest = spare.available_from
                    else:
                        earliest = max(earliest, spare.available_from)
            window = compiled_dag.window_lb.get(operation.id)
            if window is not None:
                earliest = window if earliest is None else max(earliest, window)
            kernel_ops.append(
                Operation(
                    id=op_id,
                    order_id=kernel_order_of[segment.id],
                    seq_in_order=operation.sequence if preserve_sequence else index,
                    state_id=state_of(operation.setup_state).id,
                    base_duration_min=operation.duration_min,
                    eligible_wc_ids=eligible,
                    predecessor_op_id=previous,
                    earliest_start=earliest,
                    latest_finish=operation.latest_finish,
                    domain_attributes={
                        "repairflow_id": operation.id,
                        "job_id": segment.job_id,
                        "segment_id": segment.id,
                        "required_skills": list(operation.required_skills),
                    },
                )
            )
            previous = op_id

    aux_resources: list[AuxiliaryResource] = []
    for crew in problem.crews:
        aux_id = sid("crew", crew.id)
        id_map[f"crew:{crew.id}"] = aux_id
        aux_resources.append(
            AuxiliaryResource(
                id=aux_id,
                code=crew.code,
                resource_type="crew",
                pool_size=crew.max_parallel,
                calendar=_shift_intervals(problem, crew.calendar_id, crew.domain_attributes),
                domain_attributes={"repairflow_id": crew.id, "skills": list(crew.skills)},
            )
        )
    for aux in problem.aux_resources:
        aux_id = sid("aux", aux.id)
        id_map[f"aux:{aux.id}"] = aux_id
        aux_resources.append(
            AuxiliaryResource(
                id=aux_id,
                code=aux.code,
                resource_type=aux.resource_type,
                pool_size=aux.capacity,
                calendar=_shift_intervals(problem, aux.calendar_id, aux.domain_attributes),
                domain_attributes={"repairflow_id": aux.id},
            )
        )

    skill_pools = _skill_pools(problem, id_map)
    for key, aux_id in skill_pools.items():
        id_map[f"skillpool:{key}"] = aux_id
        matching = _crews_for_skills(problem, key.split("|") if key else [])
        aux_resources.append(
            AuxiliaryResource(
                id=aux_id,
                code=f"SKILL:{key or 'any'}",
                resource_type="crew-pool",
                pool_size=max(1, len(matching)),
                calendar=_shared_pool_intervals(problem, matching),
                domain_attributes={"skills": key.split("|") if key else []},
            )
        )

    requirements: list[OperationAuxRequirement] = []
    for operation in problem.operations:
        op_id = id_map[f"op:{operation.id}"]
        bound_crew = _bound_crew(problem, operation)
        if bound_crew is not None:
            requirements.append(
                OperationAuxRequirement(
                    operation_id=op_id,
                    aux_resource_id=id_map[f"crew:{bound_crew}"],
                    quantity_needed=1,
                )
            )
        elif operation.required_skills:
            pool_key = "|".join(sorted(operation.required_skills))
            requirements.append(
                OperationAuxRequirement(
                    operation_id=op_id,
                    aux_resource_id=skill_pools[pool_key],
                    quantity_needed=1,
                )
            )
        for required_aux in operation.required_aux_ids:
            requirements.append(
                OperationAuxRequirement(
                    operation_id=op_id,
                    aux_resource_id=id_map[f"aux:{required_aux}"],
                    quantity_needed=1,
                )
            )

    setup_matrix = _compile_setup(problem, id_map, states_by_code)
    schedule = ScheduleProblem(
        states=list(states_by_code.values()),
        orders=orders,
        operations=kernel_ops,
        work_centers=work_centers,
        setup_matrix=setup_matrix,
        auxiliary_resources=aux_resources,
        aux_requirements=requirements,
        planning_horizon_start=problem.planning_horizon.start,
        planning_horizon_end=problem.planning_horizon.end,
    )
    return schedule, id_map


def compile_frozen_assignments(
    problem: RepairFlowProblem,
    id_map: dict[str, UUID],
) -> list[Assignment]:
    out: list[Assignment] = []
    for frozen in problem.frozen_assignments:
        if not frozen.immutable:
            continue
        aux_ids: list[UUID] = []
        if frozen.crew_id:
            aux_ids.append(id_map[f"crew:{frozen.crew_id}"])
        operation = next(op for op in problem.operations if op.id == frozen.operation_id)
        for aux_id in operation.required_aux_ids:
            aux_ids.append(id_map[f"aux:{aux_id}"])
        out.append(
            Assignment(
                operation_id=id_map[f"op:{frozen.operation_id}"],
                work_center_id=id_map[f"wc:{frozen.work_center_id}"],
                start_time=frozen.start,
                end_time=frozen.end,
                setup_minutes=frozen.setup_minutes,
                aux_resource_ids=aux_ids,
            )
        )
    return out


def extract_frozen_from_result(
    problem: RepairFlowProblem,
    *,
    assignments: list[Assignment],
    id_map: dict[str, UUID],
    skip_operation_ids: set[str] | None = None,
    reason: str = "base_plan",
) -> list[FrozenAssignment]:
    op_of = {id_map[f"op:{op.id}"]: op.id for op in problem.operations}
    wc_of = {id_map[f"wc:{wc.id}"]: wc.id for wc in problem.work_centers}
    crew_of = {id_map[f"crew:{crew.id}"]: crew.id for crew in problem.crews}
    skip = skip_operation_ids or set()
    out: list[FrozenAssignment] = []
    for assignment in assignments:
        op_id = op_of.get(assignment.operation_id)
        wc_id = wc_of.get(assignment.work_center_id)
        if op_id is None or wc_id is None or op_id in skip:
            continue
        crew_id = None
        for aux_id in assignment.aux_resource_ids:
            if aux_id in crew_of:
                crew_id = crew_of[aux_id]
                break
        out.append(
            FrozenAssignment(
                operation_id=op_id,
                work_center_id=wc_id,
                crew_id=crew_id,
                start=assignment.start_time,
                end=assignment.end_time,
                setup_minutes=assignment.setup_minutes,
                immutable=True,
                frozen_reason=reason,
            )
        )
    return out


def _compile_setup(
    problem: RepairFlowProblem,
    id_map: dict[str, UUID],
    states_by_code: dict[str, State],
) -> list[SetupEntry]:
    states = list(states_by_code.keys())
    out: list[SetupEntry] = []
    for center in problem.work_centers:
        wc_id = id_map[f"wc:{center.id}"]
        for from_state in states:
            for to_state in states:
                minutes = lookup_setup_minutes(
                    problem,
                    work_center_id=center.id,
                    from_state=from_state,
                    to_state=to_state,
                )
                if minutes is None:
                    if problem.policy.missing_setup == "zero":
                        minutes = 0
                    else:
                        continue
                out.append(
                    SetupEntry(
                        id=sid("setup", center.id, from_state, to_state),
                        work_center_id=wc_id,
                        from_state_id=states_by_code[from_state].id,
                        to_state_id=states_by_code[to_state].id,
                        setup_minutes=minutes,
                    )
                )
    return out


def _crews_for_skills(problem: RepairFlowProblem, skills: list[str]) -> list[str]:
    required = set(skills)
    if not required:
        return [crew.id for crew in problem.crews]
    return [crew.id for crew in problem.crews if required <= set(crew.skills)]


def extract_frozen_from_planned(
    *,
    assignments: list[PlannedAssignment],
    skip_operation_ids: set[str] | None = None,
    reason: str = "base_plan",
) -> list[FrozenAssignment]:
    skip = skip_operation_ids or set()
    out: list[FrozenAssignment] = []
    for assignment in assignments:
        if assignment.operation_id in skip:
            continue
        out.append(
            FrozenAssignment(
                operation_id=assignment.operation_id,
                work_center_id=assignment.work_center_id,
                crew_id=assignment.crew_id,
                start=assignment.start,
                end=assignment.end,
                setup_minutes=assignment.setup_minutes,
                immutable=True,
                frozen_reason=reason,
            )
        )
    return out


def _shift_intervals(
    problem: RepairFlowProblem,
    calendar_id: str | None,
    attributes: dict[str, Any],
) -> list[ShiftInterval]:
    """Kernel shifts. A closed domain calendar is not compiled as 24/7."""

    windows = kernel_calendar_windows(problem, calendar_id, attributes)
    if not windows:
        return []
    return [ShiftInterval(start=start, end=end) for start, end in windows]


def _shared_pool_intervals(problem: RepairFlowProblem, crew_ids: list[str]) -> list[ShiftInterval]:
    """One shift list when every crew in a fungible pool publishes the same one."""

    crews = {crew.id: crew for crew in problem.crews}
    encoded: list[tuple[tuple[datetime, datetime], ...]] = []
    for crew_id in crew_ids:
        crew = crews[crew_id]
        windows = kernel_calendar_windows(problem, crew.calendar_id, crew.domain_attributes)
        if windows is None:
            return []
        encoded.append(tuple(windows))
    if len(set(encoded)) != 1:
        return []
    return [ShiftInterval(start=start, end=end) for start, end in encoded[0]]


def _bound_crew(problem: RepairFlowProblem, operation: DomainOperation) -> str | None:
    matching = _crews_for_skills(problem, operation.required_skills)
    if len(matching) == 1:
        return matching[0]
    frozen = next(
        (row for row in problem.frozen_assignments if row.operation_id == operation.id),
        None,
    )
    if frozen is not None and frozen.crew_id:
        return frozen.crew_id
    return None


def _skill_pools(problem: RepairFlowProblem, id_map: dict[str, UUID]) -> dict[str, UUID]:
    pools: dict[str, UUID] = {}
    for operation in problem.operations:
        if _bound_crew(problem, operation) is not None:
            continue
        if not operation.required_skills:
            continue
        key = "|".join(sorted(operation.required_skills))
        pools.setdefault(key, sid("skillpool", key))
    return pools


def occupancy_start(assignment: Assignment) -> datetime:
    return assignment.start_time - timedelta(minutes=int(assignment.setup_minutes or 0))
