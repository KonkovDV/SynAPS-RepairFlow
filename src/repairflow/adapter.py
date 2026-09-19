"""Compile RepairFlowProblem → SynAPS ScheduleProblem without mutating kernel types."""

from __future__ import annotations

from datetime import datetime, timedelta
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


def to_schedule_problem(problem: RepairFlowProblem) -> tuple[ScheduleProblem, dict[str, UUID]]:
    id_map: dict[str, UUID] = {}
    states_by_code: dict[str, State] = {}

    def state_of(code: str) -> State:
        if code not in states_by_code:
            state = State(id=sid("state", code or "idle"), code=code or "idle", label=code or "idle")
            states_by_code[code] = state
            id_map[f"state:{code or 'idle'}"] = state.id
        return states_by_code[code]

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
    for job in problem.jobs:
        order_id = sid("job", job.id)
        id_map[f"job:{job.id}"] = order_id
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
                    "asset_code": job.asset_code,
                    "unit_type": job.unit_type,
                },
            )
        )

    ops_by_job: dict[str, list[DomainOperation]] = {}
    for operation in problem.operations:
        ops_by_job.setdefault(operation.job_id, []).append(operation)
    for rows in ops_by_job.values():
        rows.sort(key=lambda item: (item.sequence, item.id))

    kernel_ops: list[Operation] = []
    for job_id, rows in ops_by_job.items():
        job = jobs_by_id[job_id]
        for operation in rows:
            op_id = sid("op", operation.id)
            id_map[f"op:{operation.id}"] = op_id
            predecessor = None
            if operation.predecessor_ids:
                predecessor = sid("op", operation.predecessor_ids[0])
            eligible = [id_map[f"wc:{wc_id}"] for wc_id in operation.eligible_work_center_ids]
            if not eligible:
                eligible = [id_map[f"wc:{center.id}"] for center in problem.work_centers]
            earliest = operation.earliest_start or job.release_date
            for spare in problem.spares:
                if spare.id in operation.required_spare_ids and spare.available_from is not None:
                    if earliest is None:
                        earliest = spare.available_from
                    else:
                        earliest = max(earliest, spare.available_from)
            kernel_ops.append(
                Operation(
                    id=op_id,
                    order_id=id_map[f"job:{job_id}"],
                    seq_in_order=operation.sequence,
                    state_id=state_of(operation.setup_state).id,
                    base_duration_min=operation.duration_min,
                    eligible_wc_ids=eligible,
                    predecessor_op_id=predecessor,
                    earliest_start=earliest,
                    latest_finish=operation.latest_finish,
                    domain_attributes={
                        "repairflow_id": operation.id,
                        "job_id": job_id,
                        "required_skills": list(operation.required_skills),
                    },
                )
            )

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


def reverse_ids(id_map: dict[str, UUID]) -> dict[UUID, tuple[str, str]]:
    out: dict[UUID, tuple[str, str]] = {}
    for key, value in id_map.items():
        kind, ident = key.split(":", 1)
        out[value] = (kind, ident)
    return out


def lookup_setup_minutes(
    problem: RepairFlowProblem,
    *,
    work_center_id: str,
    from_state: str,
    to_state: str,
) -> int | None:
    if from_state == to_state:
        specific = _setup_cell(problem, work_center_id, from_state, to_state)
        return 0 if specific is None else specific
    return _setup_cell(problem, work_center_id, from_state, to_state)


def _setup_cell(
    problem: RepairFlowProblem,
    work_center_id: str,
    from_state: str,
    to_state: str,
) -> int | None:
    specific = None
    generic = None
    for entry in problem.setup_matrix:
        if entry.from_state != from_state or entry.to_state != to_state:
            continue
        if entry.work_center_id == work_center_id:
            specific = entry.duration_min
        elif entry.work_center_id is None:
            generic = entry.duration_min
    if specific is not None:
        return specific
    return generic


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
                    if from_state == to_state or problem.policy.missing_setup == "zero":
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


def bind_concrete_crews(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[PlannedAssignment]:
    """Resolve skill-pool kernel aux into a named crew. Jury contract: operation → crew."""

    ops = {op.id: op for op in problem.operations}
    occupied: dict[str, list[tuple[datetime, datetime]]] = {crew.id: [] for crew in problem.crews}
    bound: list[PlannedAssignment] = []
    for assignment in sorted(assignments, key=lambda row: (row.start, row.operation_id)):
        crew_id = assignment.crew_id
        operation = ops.get(assignment.operation_id)
        if crew_id is None and operation is not None and operation.required_skills:
            crew_id = _pick_free_crew(problem, assignment, occupied, operation)
        if crew_id:
            occ_start = assignment.start - timedelta(minutes=int(assignment.setup_minutes or 0))
            occupied.setdefault(crew_id, []).append((occ_start, assignment.end))
        if crew_id == assignment.crew_id:
            bound.append(assignment)
            continue
        reason = assignment.reason
        if crew_id:
            reason = f"{reason} bound_crew={crew_id}".strip()
        bound.append(assignment.model_copy(update={"crew_id": crew_id, "reason": reason}))
    by_op = {row.operation_id: row for row in bound}
    return [by_op.get(row.operation_id, row) for row in assignments]


def _pick_free_crew(
    problem: RepairFlowProblem,
    assignment: PlannedAssignment,
    occupied: dict[str, list[tuple[datetime, datetime]]],
    operation: DomainOperation,
) -> str | None:
    occ_start = assignment.start - timedelta(minutes=int(assignment.setup_minutes or 0))
    eligible = [crew for crew in problem.crews if set(operation.required_skills) <= set(crew.skills)]
    eligible.sort(key=lambda crew: crew.id)
    for crew in eligible:
        overlaps = sum(
            1 for start, end in occupied.get(crew.id, []) if occ_start < end and start < assignment.end
        )
        if overlaps < crew.max_parallel:
            return crew.id
    return None


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
