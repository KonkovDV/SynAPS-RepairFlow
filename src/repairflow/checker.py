"""Independent fail-closed RepairFlow checker. Does not import solver search code."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from synaps.model import Assignment, ScheduleProblem

from repairflow.capacity import Occupancy, excess_arrivals
from repairflow.checker_primitives import lookup_setup_minutes, reverse_ids
from repairflow.kernel_compat import kernel_calendar_windows
from repairflow.lane_setup import lane_setup_evidence
from repairflow.ledger import exchange_pool_violations, spare_is_rotable
from repairflow.model import (
    Calendar,
    Job,
    Operation,
    PlannedAssignment,
    RepairFlowProblem,
    Spare,
    Violation,
)
from repairflow.reasons import REASON_RU, SUGGESTIONS, ReasonCode
from repairflow.scheduling_contract import (
    declares_open_horizon,
    held_minutes,
    is_unattended,
    is_whole_minutes,
    merge_windows,
    open_minutes,
    policy_of,
)

ADMISSIBLE_KERNEL_STATUSES = frozenset({"feasible", "optimal"})


def check_plan(
    problem: RepairFlowProblem,
    *,
    schedule_problem: ScheduleProblem,
    assignments: list[Assignment] | list[PlannedAssignment],
    id_map: dict[str, UUID],
    kernel_status: str | None,
    subset_mode: bool = False,
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

    mapped, binding_issues = _normalize_assignments(assignments, id_map)
    issues = _id_map_issues(problem, schedule_problem, id_map)
    if issues:
        return _sorted([*issues, *binding_issues])

    violations: list[Violation] = list(binding_issues)
    status_token = kernel_status.strip().lower() if kernel_status else ""
    if not status_token:
        violations.append(
            _violation(
                ReasonCode.KERNEL_STATUS_MISSING,
                "result has no kernel_status; refusing to treat the plan as verified",
            )
        )
    elif status_token not in ADMISSIBLE_KERNEL_STATUSES:
        violations.append(
            _violation(
                ReasonCode.KERNEL_STATUS_NOT_FEASIBLE,
                f"kernel_status {kernel_status!r} is not feasible or optimal",
            )
        )

    violations.extend(_constraint_violations(problem, mapped, subset_mode=subset_mode))
    return _sorted(violations)


def check_domain_assignments(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    """Check a shop plan without a kernel status or a compiled schedule."""
    try:
        problem = RepairFlowProblem.model_validate(problem.model_dump(mode="python"))
    except (ValueError, TypeError) as exc:
        return [
            _violation(
                ReasonCode.INVALID_PROBLEM,
                f"problem failed domain validation: {exc}",
            )
        ]
    return _sorted(_constraint_violations(problem, list(assignments), subset_mode=False))


def _constraint_violations(
    problem: RepairFlowProblem,
    mapped: list[PlannedAssignment],
    *,
    subset_mode: bool,
) -> list[Violation]:
    violations: list[Violation] = []
    violations.extend(_ref_and_duration(problem, mapped))
    if not subset_mode:
        violations.extend(_coverage(problem, mapped))
    violations.extend(_skills_and_eligibility(problem, mapped))
    violations.extend(_precedence(problem, mapped, ignore_absent=subset_mode))
    violations.extend(_resource_overlaps(problem, mapped))
    violations.extend(_calendars_windows_horizon(problem, mapped))
    violations.extend(_due_release_spares(problem, mapped))
    violations.extend(_setup(problem, mapped))
    violations.extend(_frozen(problem, mapped))
    violations.extend(exchange_pool_violations(problem, mapped))
    return violations


def binding_from_aux(
    aux_resource_ids: list[UUID],
    reversed_map: dict[UUID, tuple[str, str]],
    *,
    operation_id: str,
) -> tuple[str | None, list[str], list[Violation]]:
    """Read crew and tooling off a kernel assignment.

    More than one crew is a hard ambiguity. A kind other than crew or aux is a
    hard unknown resource. Neither case keeps a guessed binding.
    """

    crews: list[str] = []
    aux_ids: list[str] = []
    issues: list[Violation] = []
    for aux in aux_resource_ids:
        kind, ident = reversed_map.get(aux, ("unknown", str(aux)))
        if kind == "crew":
            crews.append(ident)
        elif kind == "aux":
            aux_ids.append(ident)
        else:
            issues.append(
                _violation(
                    ReasonCode.UNKNOWN_RESOURCE,
                    f"assignment aux {aux} has kind {kind}, expected crew or aux",
                    operation_id=operation_id,
                    resource_id=ident,
                    details={"kind": kind},
                )
            )
    crew_id: str | None = None
    if len(crews) > 1:
        issues.append(
            _violation(
                ReasonCode.AMBIGUOUS_CREW,
                f"operation {operation_id} lists crews {crews}",
                operation_id=operation_id,
                details={"crew_ids": crews},
            )
        )
    elif crews:
        crew_id = crews[0]
    return crew_id, aux_ids, issues


def _normalize_assignments(
    assignments: list[Assignment] | list[PlannedAssignment],
    id_map: dict[str, UUID],
) -> tuple[list[PlannedAssignment], list[Violation]]:
    reversed_map = reverse_ids(id_map)
    out: list[PlannedAssignment] = []
    issues: list[Violation] = []
    for row in assignments:
        if isinstance(row, PlannedAssignment):
            out.append(row)
            continue
        wc_kind, wc_id = reversed_map.get(row.work_center_id, ("wc", str(row.work_center_id)))
        op_kind, op_id = reversed_map.get(row.operation_id, ("op", str(row.operation_id)))
        operation_id = op_id if op_kind == "op" else str(row.operation_id)
        crew_id, aux_ids, binding_issues = binding_from_aux(
            list(row.aux_resource_ids),
            reversed_map,
            operation_id=operation_id,
        )
        issues.extend(binding_issues)
        out.append(
            PlannedAssignment(
                operation_id=operation_id,
                work_center_id=wc_id if wc_kind == "wc" else str(row.work_center_id),
                crew_id=crew_id,
                aux_ids=aux_ids,
                start=row.start_time,
                end=row.end_time,
                setup_minutes=int(row.setup_minutes or 0),
            )
        )
    return out, issues


def _id_map_issues(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
) -> list[Violation]:
    op_keys = {f"op:{op.id}" for op in problem.operations}
    wc_keys = {f"wc:{wc.id}" for wc in problem.work_centers}
    supplied_ops = {key for key in id_map if key.startswith("op:")}
    supplied_wcs = {key for key in id_map if key.startswith("wc:")}
    complete = op_keys == supplied_ops and wc_keys == supplied_wcs
    injective = len(set(id_map.values())) == len(id_map)
    if not complete or not injective:
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
    mapped_ops = {id_map[key] for key in op_keys}
    kernel_ops = {operation.id for operation in schedule_problem.operations}
    mapped_centers = {id_map[key] for key in wc_keys}
    kernel_centers = {center.id for center in schedule_problem.work_centers}
    mapped_orders = _mapped_ids(id_map, "job:")
    kernel_orders = {order.id for order in schedule_problem.orders}
    mapped_states = _mapped_ids(id_map, "state:")
    kernel_states = {state.id for state in schedule_problem.states}
    mapped_aux = (
        _mapped_ids(id_map, "crew:") | _mapped_ids(id_map, "aux:") | _mapped_ids(id_map, "skillpool:")
    )
    kernel_aux = {row.id for row in schedule_problem.auxiliary_resources}
    if (
        mapped_ops != kernel_ops
        or mapped_centers != kernel_centers
        or mapped_orders != kernel_orders
        or mapped_states != kernel_states
        or mapped_aux != kernel_aux
    ):
        return [
            _violation(
                ReasonCode.INVALID_ID_MAP,
                "compiled kernel ids do not match the id map",
            )
        ]
    if not _kernel_references_closed(
        schedule_problem,
        operations=kernel_ops,
        centers=kernel_centers,
        orders=kernel_orders,
        states=kernel_states,
        auxiliary=kernel_aux,
    ):
        return [
            _violation(
                ReasonCode.INVALID_ID_MAP,
                "compiled kernel references are not closed over the id map",
            )
        ]
    if not _kernel_image_matches(problem, schedule_problem, id_map):
        return [
            _violation(
                ReasonCode.INVALID_ID_MAP,
                "compiled kernel image does not match the RepairFlow instance",
            )
        ]
    return []


def _kernel_references_closed(
    schedule_problem: ScheduleProblem,
    *,
    operations: set[UUID],
    centers: set[UUID],
    orders: set[UUID],
    states: set[UUID],
    auxiliary: set[UUID],
) -> bool:
    for operation in schedule_problem.operations:
        if operation.order_id not in orders or operation.state_id not in states:
            return False
        if operation.predecessor_op_id is not None and operation.predecessor_op_id not in operations:
            return False
        if not operation.eligible_wc_ids or not set(operation.eligible_wc_ids) <= centers:
            return False
    for row in schedule_problem.setup_matrix:
        if (
            row.work_center_id not in centers
            or row.from_state_id not in states
            or row.to_state_id not in states
        ):
            return False
    for requirement in schedule_problem.aux_requirements:
        if requirement.operation_id not in operations or requirement.aux_resource_id not in auxiliary:
            return False
    return True


def _kernel_image_matches(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
) -> bool:
    reversed_map = reverse_ids(id_map)
    domain_ops = {operation.id: operation for operation in problem.operations}
    for operation in schedule_problem.operations:
        kind, ident = reversed_map[operation.id]
        if kind != "op" or ident not in domain_ops:
            return False
        domain = domain_ops[ident]
        if operation.base_duration_min != domain.duration_min:
            return False
        if operation.latest_finish != domain.latest_finish:
            return False
        if operation.state_id != id_map[f"state:{domain.setup_state}"]:
            return False
        eligible = [id_map[f"wc:{center_id}"] for center_id in domain.eligible_work_center_ids]
        if list(operation.eligible_wc_ids) != eligible:
            return False
        order_kind, order_key = reversed_map[operation.order_id]
        if order_kind != "job":
            return False
        if order_key != domain.job_id and not order_key.startswith(f"{domain.job_id}:"):
            return False
        if operation.machine_duration_overrides or operation.modes:
            return False
        if not _operation_attribute_image(operation, domain):
            return False
    return (
        _setup_image_matches(problem, schedule_problem, id_map)
        and _aux_image_matches(problem, schedule_problem, id_map)
        and _resource_image_matches(problem, schedule_problem, id_map)
        and _order_image_matches(problem, schedule_problem, id_map)
        and _state_image_matches(schedule_problem, id_map)
        and _horizon_image_matches(problem, schedule_problem)
    )


def _setup_image_matches(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
) -> bool:
    codes = [key.split(":", 1)[1] for key in id_map if key.startswith("state:")]
    expected: Counter[tuple[UUID, UUID, UUID, int]] = Counter()
    for center in problem.work_centers:
        work_center_id = id_map[f"wc:{center.id}"]
        for from_state in codes:
            for to_state in codes:
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
                expected[
                    (
                        work_center_id,
                        id_map[f"state:{from_state}"],
                        id_map[f"state:{to_state}"],
                        minutes,
                    )
                ] += 1
    actual: Counter[tuple[UUID, UUID, UUID, int]] = Counter(
        (row.work_center_id, row.from_state_id, row.to_state_id, int(row.setup_minutes))
        for row in schedule_problem.setup_matrix
    )
    if actual != expected:
        return False
    return all(row.material_loss == 0 and row.energy_kwh == 0 for row in schedule_problem.setup_matrix)


def _aux_image_matches(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
) -> bool:
    expected: Counter[tuple[UUID, UUID]] = Counter()
    for operation in problem.operations:
        operation_id = id_map[f"op:{operation.id}"]
        personnel = _personnel_resource(problem, operation, id_map)
        if personnel is False:
            return False
        if personnel is not None:
            expected[(operation_id, personnel)] += 1
        for aux_id in operation.required_aux_ids:
            mapped = id_map.get(f"aux:{aux_id}")
            if mapped is None:
                return False
            expected[(operation_id, mapped)] += 1
    actual: Counter[tuple[UUID, UUID]] = Counter()
    for requirement in schedule_problem.aux_requirements:
        if requirement.quantity_needed != 1:
            return False
        actual[(requirement.operation_id, requirement.aux_resource_id)] += 1
    return actual == expected


def _personnel_resource(
    problem: RepairFlowProblem,
    operation: Operation,
    id_map: dict[str, UUID],
) -> UUID | None | Literal[False]:
    """The crew or skill pool the compiler must attach, or False when the map cannot name it."""

    required = set(operation.required_skills)
    if required:
        matching = [crew.id for crew in problem.crews if required <= set(crew.skills)]
    else:
        matching = [crew.id for crew in problem.crews]
    chosen: str | None = matching[0] if len(matching) == 1 else None
    if chosen is None:
        frozen = next(
            (row for row in problem.frozen_assignments if row.operation_id == operation.id),
            None,
        )
        if frozen is not None and frozen.crew_id:
            chosen = frozen.crew_id
    if chosen is not None:
        return id_map.get(f"crew:{chosen}", False)
    if not operation.required_skills:
        return None
    pool_key = "|".join(sorted(operation.required_skills))
    return id_map.get(f"skillpool:{pool_key}", False)


def _resource_image_matches(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
) -> bool:
    reversed_map = reverse_ids(id_map)
    centers = {center.id: center for center in problem.work_centers}
    crews = {crew.id: crew for crew in problem.crews}
    auxiliaries = {aux.id: aux for aux in problem.aux_resources}
    for center in schedule_problem.work_centers:
        kind, ident = reversed_map[center.id]
        domain = centers.get(ident)
        if kind != "wc" or domain is None or center.max_parallel != domain.max_parallel:
            return False
        if center.speed_factor != 1 or center.code != domain.code:
            return False
        if center.capability_group != domain.capability_group:
            return False
        if center.domain_attributes != {"repairflow_id": domain.id}:
            return False
        actual = [(row.start, row.end) for row in center.calendar]
        if actual != _post_calendar(problem, domain.calendar_id):
            return False
    for resource in schedule_problem.auxiliary_resources:
        kind, ident = reversed_map[resource.id]
        actual = [(row.start, row.end) for row in resource.calendar]
        if kind == "crew":
            crew = crews.get(ident)
            if crew is None or resource.pool_size != crew.max_parallel:
                return False
            if resource.code != crew.code or resource.resource_type != "crew":
                return False
            if resource.domain_attributes != {"repairflow_id": crew.id, "skills": list(crew.skills)}:
                return False
            if actual != _shift_calendar(problem, crew.calendar_id, crew.domain_attributes):
                return False
        elif kind == "aux":
            aux = auxiliaries.get(ident)
            if aux is None or resource.pool_size != aux.capacity:
                return False
            if resource.code != aux.code or resource.resource_type != aux.resource_type:
                return False
            if resource.domain_attributes != {"repairflow_id": aux.id}:
                return False
            if actual != _shift_calendar(problem, aux.calendar_id, aux.domain_attributes):
                return False
        elif kind == "skillpool":
            if resource.pool_size != _skill_pool_size(problem, ident):
                return False
            skills = ident.split("|") if ident else []
            if resource.code != f"SKILL:{ident or 'any'}" or resource.resource_type != "crew-pool":
                return False
            if resource.domain_attributes != {"skills": skills}:
                return False
            if actual != _skill_pool_calendar(problem, ident):
                return False
        else:
            return False
    return True


def _post_calendar(problem: RepairFlowProblem, calendar_id: str | None) -> list[tuple[datetime, datetime]]:
    calendar = next((row for row in problem.calendars if row.id == (calendar_id or "")), None)
    if calendar is None:
        return []
    return [(window.start, window.end) for window in calendar.windows]


def _shift_calendar(
    problem: RepairFlowProblem,
    calendar_id: str | None,
    attributes: dict[str, Any],
) -> list[tuple[datetime, datetime]]:
    windows = kernel_calendar_windows(problem, calendar_id, attributes)
    if not windows:
        return []
    return list(windows)


def _skill_crews(problem: RepairFlowProblem, skill_key: str) -> list[str]:
    required = set(skill_key.split("|")) if skill_key else set()
    if not required:
        return [crew.id for crew in problem.crews]
    return [crew.id for crew in problem.crews if required <= set(crew.skills)]


def _skill_pool_size(problem: RepairFlowProblem, skill_key: str) -> int:
    return max(1, len(_skill_crews(problem, skill_key)))


def _skill_pool_calendar(problem: RepairFlowProblem, skill_key: str) -> list[tuple[datetime, datetime]]:
    crews = {crew.id: crew for crew in problem.crews}
    encoded: list[tuple[tuple[datetime, datetime], ...]] = []
    for crew_id in _skill_crews(problem, skill_key):
        crew = crews[crew_id]
        windows = kernel_calendar_windows(problem, crew.calendar_id, crew.domain_attributes)
        if windows is None:
            return []
        encoded.append(tuple(windows))
    if len(set(encoded)) != 1:
        return []
    return list(encoded[0])


def _order_image_matches(
    problem: RepairFlowProblem,
    schedule_problem: ScheduleProblem,
    id_map: dict[str, UUID],
) -> bool:
    reversed_map = reverse_ids(id_map)
    jobs = {job.id: job for job in problem.jobs}
    for order in schedule_problem.orders:
        kind, order_key = reversed_map[order.id]
        job = _job_for_order_key(jobs, order_key) if kind == "job" else None
        if job is None:
            return False
        due = job.due_date or problem.planning_horizon.end
        if order.release_date != job.release_date or order.due_date != due:
            return False
        if order.priority != job.priority or order.external_ref != (job.external_ref or job.id):
            return False
        if order.quantity != 1 or order.unit != "pcs":
            return False
        if not _order_attribute_image(order, job):
            return False
    return True


def _operation_attribute_image(operation: Any, domain: Operation) -> bool:
    """Copied operation labels. The compiler segment id is not derived again."""

    attrs = operation.domain_attributes
    if set(attrs) != {"repairflow_id", "job_id", "segment_id", "required_skills"}:
        return False
    segment_id = attrs["segment_id"]
    if not isinstance(segment_id, str) or not segment_id:
        return False
    return bool(
        attrs["repairflow_id"] == domain.id
        and attrs["job_id"] == domain.job_id
        and attrs["required_skills"] == list(domain.required_skills)
    )


def _order_attribute_image(order: Any, job: Job) -> bool:
    """Copied order labels. The compiler segment id is not derived again."""

    attrs = order.domain_attributes
    if set(attrs) != {"repairflow_id", "segment_id", "asset_code", "unit_type"}:
        return False
    segment_id = attrs["segment_id"]
    if not isinstance(segment_id, str) or not segment_id:
        return False
    return bool(
        attrs["repairflow_id"] == job.id
        and attrs["asset_code"] == job.asset_code
        and attrs["unit_type"] == job.unit_type
    )


def _horizon_image_matches(problem: RepairFlowProblem, schedule_problem: ScheduleProblem) -> bool:
    return (
        schedule_problem.planning_horizon_start == problem.planning_horizon.start
        and schedule_problem.planning_horizon_end == problem.planning_horizon.end
    )


def _job_for_order_key(jobs: dict[str, Job], order_key: str) -> Job | None:
    exact = jobs.get(order_key)
    if exact is not None:
        return exact
    matches = [job for job in jobs.values() if order_key.startswith(f"{job.id}:")]
    if len(matches) != 1:
        return None
    return matches[0]


def _state_image_matches(schedule_problem: ScheduleProblem, id_map: dict[str, UUID]) -> bool:
    reversed_map = reverse_ids(id_map)
    for state in schedule_problem.states:
        kind, ident = reversed_map[state.id]
        if kind != "state" or state.code != ident or state.label != ident or state.domain_attributes:
            return False
    return True


def _mapped_ids(id_map: dict[str, UUID], prefix: str) -> set[UUID]:
    return {value for key, value in id_map.items() if key.startswith(prefix)}


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
            if op is not None:
                out.extend(_duration_violation(problem, op, asn))
    return out


def _coverage(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> list[Violation]:
    assigned = {asn.operation_id for asn in assignments}
    out: list[Violation] = []
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
        if not op.eligible_work_center_ids or asn.work_center_id not in op.eligible_work_center_ids:
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
                        ReasonCode.CREW_UNBOUND,
                        f"operation {op.id} requires skills {op.required_skills} but has no crew",
                        operation_id=op.id,
                        job_id=op.job_id,
                        start=asn.start,
                        end=asn.end,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.CREW_UNBOUND],
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
                elif crew is not None:
                    for skill in op.required_skills:
                        until = crew.skill_valid_until.get(skill)
                        # The permit must cover the whole visit. A start one
                        # minute before expiry still fails when the visit ends later.
                        if until is not None and asn.end > until:
                            out.append(
                                _violation(
                                    ReasonCode.SKILL_EXPIRED,
                                    f"crew {crew.code} skill {skill} expires {until.isoformat()}",
                                    operation_id=op.id,
                                    job_id=op.job_id,
                                    resource_id=crew.id,
                                    start=asn.start,
                                    end=asn.end,
                                    suggested_relaxation=SUGGESTIONS[ReasonCode.SKILL_EXPIRED],
                                    details={"skill": skill},
                                )
                            )
        required_aux = set(op.required_aux_ids)
        if required_aux and not required_aux <= set(asn.aux_ids):
            out.append(
                _violation(
                    ReasonCode.AUX_MISSING,
                    f"operation {op.id} is missing required aux {sorted(required_aux - set(asn.aux_ids))}",
                    operation_id=op.id,
                    job_id=op.job_id,
                    start=asn.start,
                    end=asn.end,
                )
            )
    return out


def _precedence(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    *,
    ignore_absent: bool = False,
) -> list[Violation]:
    by_op = {asn.operation_id: asn for asn in assignments}
    out: list[Violation] = []
    for op in problem.operations:
        current = by_op.get(op.id)
        if current is None:
            continue
        for pred_id, min_lag, max_lag in op.predecessor_links():
            pred = by_op.get(pred_id)
            if pred is None:
                if ignore_absent:
                    continue
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
            ready = pred.end + timedelta(minutes=min_lag)
            if current.start < ready:
                out.append(
                    _violation(
                        ReasonCode.PRECEDENCE_BROKEN,
                        f"{op.id} starts before predecessor {pred_id} plus lag {min_lag} min",
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=pred_id,
                        start=current.start,
                        end=current.end,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.PRECEDENCE_BROKEN],
                        details={"predecessor_end": pred.end.isoformat(), "min_lag_min": min_lag},
                    )
                )
            elif max_lag is not None and current.start > pred.end + timedelta(minutes=max_lag):
                out.append(
                    _violation(
                        ReasonCode.PRECEDENCE_BROKEN,
                        f"{op.id} starts after the max lag from predecessor {pred_id}",
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=pred_id,
                        start=current.start,
                        end=current.end,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.PRECEDENCE_BROKEN],
                        details={"max_lag_min": max_lag},
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
        intervals: list[Occupancy] = []
        for asn in rows:
            start = asn.start
            if include_setup:
                start = asn.start - timedelta(minutes=int(asn.setup_minutes or 0))
            intervals.append(Occupancy(start, asn.end, asn.operation_id))
        for excess in excess_arrivals(intervals, cap):
            out.append(
                _violation(
                    code,
                    f"resource {resource_id} exceeds capacity {cap}",
                    operation_id=excess.operation_id,
                    resource_id=resource_id,
                    start=excess.start,
                    end=excess.end,
                    details={
                        "other_operation_id": excess.other_operation_id,
                        "active": excess.active,
                        "capacity": cap,
                    },
                    suggested_relaxation=SUGGESTIONS.get(code),
                )
            )
    return out


def _calendars_windows_horizon(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    calendars = {row.id: row for row in problem.calendars}
    centers = {wc.id: wc for wc in problem.work_centers}
    crews = {crew.id: crew for crew in problem.crews}
    auxes = {aux.id: aux for aux in problem.aux_resources}
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
        if op is not None and op.earliest_start is not None and occ_start < op.earliest_start:
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
        preemptive = op is not None and policy_of(op.domain_attributes) == "preemptive"
        center = centers.get(asn.work_center_id)
        if center is not None:
            out.extend(
                _named_calendar_fit(
                    calendars,
                    center.calendar_id,
                    asn,
                    occ_start,
                    resource_id=center.id,
                    preemptive=preemptive,
                    unattended=is_unattended(center.domain_attributes),
                    provenance=problem.data_provenance,
                    attributes=center.domain_attributes,
                )
            )
        if asn.crew_id:
            crew = crews.get(asn.crew_id)
            if crew is not None:
                out.extend(
                    _named_calendar_fit(
                        calendars,
                        crew.calendar_id,
                        asn,
                        occ_start,
                        resource_id=crew.id,
                        preemptive=preemptive,
                        unattended=is_unattended(crew.domain_attributes),
                        provenance=problem.data_provenance,
                        attributes=crew.domain_attributes,
                    )
                )
        needed = set(asn.aux_ids)
        if op is not None:
            needed.update(op.required_aux_ids)
        for aux_id in sorted(needed):
            aux = auxes.get(aux_id)
            if aux is None:
                continue
            out.extend(
                _named_calendar_fit(
                    calendars,
                    aux.calendar_id,
                    asn,
                    occ_start,
                    resource_id=aux.id,
                    preemptive=preemptive,
                    unattended=is_unattended(aux.domain_attributes),
                    provenance=problem.data_provenance,
                    attributes=aux.domain_attributes,
                )
            )
    return out


def _duration_violation(
    problem: RepairFlowProblem,
    op: Operation,
    asn: PlannedAssignment,
) -> list[Violation]:
    policy = policy_of(op.domain_attributes)
    held = held_minutes(asn.start, asn.end)
    if not is_whole_minutes(asn.start, asn.end):
        message = "held interval is not a whole number of minutes"
    elif policy == "invalid":
        message = "duration_policy must be exact, min, or preemptive"
    elif policy == "min" and held < op.duration_min:
        message = f"scheduled {held} min is shorter than duration_min={op.duration_min}"
    elif policy == "exact" and held != op.duration_min:
        message = f"scheduled {held} min is not duration_min={op.duration_min}"
    elif policy == "preemptive":
        masks = _attended_masks(problem, op, asn)
        open_held = open_minutes(asn.start, asn.end, masks) if masks else held
        message = (
            ""
            if open_held == op.duration_min
            else f"open minutes {open_held} are not duration_min={op.duration_min}"
        )
    else:
        message = ""
    if not message:
        return []
    return [
        _violation(
            ReasonCode.INVALID_DURATION,
            message,
            operation_id=asn.operation_id,
            job_id=op.job_id,
            start=asn.start,
            end=asn.end,
            details={"duration_policy": policy, "held_min": held},
        )
    ]


def _attended_masks(
    problem: RepairFlowProblem,
    op: Operation,
    asn: PlannedAssignment,
) -> list[list[tuple[datetime, datetime]]]:
    calendars = {row.id: row for row in problem.calendars}
    masks: list[list[tuple[datetime, datetime]]] = []

    def add(calendar_id: str | None, attributes: dict[str, object]) -> None:
        if is_unattended(attributes) or not calendar_id:
            return
        calendar = calendars.get(calendar_id)
        if calendar is None:
            return
        masks.append([(window.start, window.end) for window in calendar.windows])

    center = next((row for row in problem.work_centers if row.id == asn.work_center_id), None)
    if center is not None:
        add(center.calendar_id, center.domain_attributes)
    if asn.crew_id:
        crew = next((row for row in problem.crews if row.id == asn.crew_id), None)
        if crew is not None:
            add(crew.calendar_id, crew.domain_attributes)
    aux_ids = set(asn.aux_ids)
    aux_ids.update(op.required_aux_ids)
    for aux in problem.aux_resources:
        if aux.id in aux_ids:
            add(aux.calendar_id, aux.domain_attributes)
    return masks


def _named_calendar_fit(
    calendars: dict[str, Calendar],
    calendar_id: str | None,
    assignment: PlannedAssignment,
    occ_start: datetime,
    *,
    resource_id: str,
    preemptive: bool,
    unattended: bool,
    provenance: str,
    attributes: dict[str, object],
) -> list[Violation]:
    """Synthetic data may omit a calendar. Any other provenance must say always_open."""
    if not calendar_id:
        if provenance != "synthetic" and not declares_open_horizon(attributes):
            return [
                _violation(
                    ReasonCode.CALENDAR_BROKEN,
                    "calendar is not declared; set calendar_id or availability=always_open",
                    operation_id=assignment.operation_id,
                    resource_id=resource_id,
                    start=assignment.start,
                    end=assignment.end,
                )
            ]
        return []
    calendar = calendars.get(calendar_id)
    if calendar is None:
        return [
            _violation(
                ReasonCode.CALENDAR_BROKEN,
                f"calendar {calendar_id} is not in the instance",
                operation_id=assignment.operation_id,
                resource_id=resource_id,
                start=assignment.start,
                end=assignment.end,
            )
        ]
    return _calendar_fit(
        calendar,
        assignment,
        occ_start,
        resource_id=resource_id,
        preemptive=preemptive,
        unattended=unattended,
    )


def _calendar_fit(
    calendar: Calendar | None,
    assignment: PlannedAssignment,
    occ_start: datetime,
    *,
    resource_id: str,
    preemptive: bool,
    unattended: bool,
) -> list[Violation]:
    if calendar is None or unattended:
        return []
    if not calendar.windows:
        return [
            _violation(
                ReasonCode.CALENDAR_BROKEN,
                f"calendar {calendar.id} has no open windows",
                operation_id=assignment.operation_id,
                resource_id=resource_id,
                start=assignment.start,
                end=assignment.end,
            )
        ]
    if preemptive:
        if assignment.start <= occ_start:
            return []
        for left, right in merge_windows(calendar.windows):
            if occ_start >= left and assignment.start <= right:
                return []
        return [
            _violation(
                ReasonCode.CALENDAR_BROKEN,
                "setup is not contained in a single calendar window",
                operation_id=assignment.operation_id,
                resource_id=resource_id,
                start=occ_start,
                end=assignment.start,
            )
        ]
    for left, right in merge_windows(calendar.windows):
        if occ_start >= left and assignment.end <= right:
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


def _spare_receipts(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    spares: dict[str, Spare],
) -> list[Violation]:
    """Time-aware stock for a consumable that has a receipt schedule."""

    ops = {op.id: op for op in problem.operations}
    demand: dict[str, list[tuple[datetime, str, int]]] = defaultdict(list)
    for asn in assignments:
        op = ops.get(asn.operation_id)
        if op is None:
            continue
        for spare_id, qty in op.spare_demand().items():
            spare = spares.get(spare_id)
            if spare is None or spare_is_rotable(spare) or not spare.receipts:
                continue
            demand[spare_id].append((asn.start, op.id, qty))
    out: list[Violation] = []
    for spare_id, uses in demand.items():
        spare = spares[spare_id]
        initial_at = spare.available_from or problem.planning_horizon.start
        events: list[tuple[datetime, int, int, str]] = [(initial_at, 0, spare.quantity, "")]
        events.extend((receipt.at, 0, receipt.qty, "") for receipt in spare.receipts)
        events.extend((start, 1, -qty, op_id) for start, op_id, qty in uses)
        stock = 0
        reported: set[str] = set()
        for moment, _order, delta, op_id in sorted(events, key=lambda item: (item[0], item[1], item[3])):
            stock += delta
            if stock < 0 and op_id and op_id not in reported:
                reported.add(op_id)
                out.append(
                    _violation(
                        ReasonCode.SPARE_UNAVAILABLE,
                        f"spare {spare.code} stock is short at {moment.isoformat()}",
                        operation_id=op_id,
                        resource_id=spare.id,
                        start=moment,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.SPARE_UNAVAILABLE],
                    )
                )
    return out


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
        occ_start = asn.start - timedelta(minutes=int(asn.setup_minutes or 0))
        if job.release_date is not None and occ_start < job.release_date:
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
        for spare_id, _qty in op.spare_demand().items():
            spare = spares.get(spare_id)
            if spare is None:
                out.append(
                    _violation(
                        ReasonCode.UNKNOWN_RESOURCE,
                        f"operation {op.id} needs unknown spare {spare_id}",
                        operation_id=op.id,
                        job_id=job.id,
                        resource_id=spare_id,
                        start=asn.start,
                        end=asn.end,
                    )
                )
                continue
            if spare_is_rotable(spare) or spare.receipts:
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
        for spare_id, qty in op.spare_demand().items():
            spare = spares.get(spare_id)
            if spare is None:
                continue  # reported as UNKNOWN_RESOURCE above
            if spare_is_rotable(spare) or spare.receipts:
                continue
            used[spare_id] += qty
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
    out.extend(_spare_receipts(problem, assignments, spares))
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
                    severity="kpi",
                )
            )
        if job.deadline is not None and last is not None and last.end > job.deadline:
            out.append(
                _violation(
                    ReasonCode.DEADLINE_MISSED,
                    f"job {job.id} finishes after deadline",
                    job_id=job.id,
                    operation_id=last.operation_id,
                    start=last.start,
                    end=last.end,
                    suggested_relaxation=SUGGESTIONS[ReasonCode.DEADLINE_MISSED],
                )
            )
    return out


def _setup(problem: RepairFlowProblem, assignments: list[PlannedAssignment]) -> list[Violation]:
    ops = {op.id: op for op in problem.operations}
    by_id = {row.operation_id: row for row in assignments}
    by_center: dict[str, list[PlannedAssignment]] = defaultdict(list)
    for asn in assignments:
        by_center[asn.work_center_id].append(asn)
    out: list[Violation] = []
    for center_id, rows in by_center.items():
        placements = lane_setup_evidence(problem, rows)
        for item in placements:
            op = ops.get(item.operation_id)
            placed = by_id.get(item.operation_id)
            if op is None or placed is None:
                continue
            expected = item.expected_setup_minutes
            # policy.missing_setup="zero" fills absent cells with 0, except the first
            # transition out of "idle": that cell is the lane's initial state and stays
            # fail-closed (tests/test_setup_idle.py).
            if expected is None and problem.policy.missing_setup == "zero" and item.previous_state != "idle":
                expected = 0
            details = {
                "from_state": item.previous_state,
                "to_state": op.setup_state,
                "lane_index": item.lane_index,
                "previous_operation_id": item.previous_operation_id,
            }
            if item.ambiguous:
                out.append(
                    _violation(
                        ReasonCode.SETUP_MISMATCH,
                        (
                            f"lane assignment on {center_id} is ambiguous or inconsistent: "
                            "supply one valid, non-overlapping lane id for every visit"
                        ),
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=center_id,
                        start=placed.start,
                        end=placed.end,
                        details={**details, "ambiguous_lane": True},
                    )
                )
                continue
            if expected is None:
                out.append(
                    _violation(
                        ReasonCode.MISSING_SETUP,
                        (
                            f"no setup cell {item.previous_state}->{op.setup_state} "
                            f"on {center_id} lane {item.lane_index}"
                        ),
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=center_id,
                        start=placed.start,
                        end=placed.end,
                        suggested_relaxation=SUGGESTIONS[ReasonCode.MISSING_SETUP],
                        details=details,
                    )
                )
            elif int(placed.setup_minutes or 0) != int(expected):
                out.append(
                    _violation(
                        ReasonCode.SETUP_MISMATCH,
                        (
                            f"setup {placed.setup_minutes} min, matrix has {expected} "
                            f"for {item.previous_state}->{op.setup_state} "
                            f"on lane {item.lane_index}"
                        ),
                        operation_id=op.id,
                        job_id=op.job_id,
                        resource_id=center_id,
                        start=placed.start,
                        end=placed.end,
                        details=details,
                    )
                )
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
            or int(placed.setup_minutes or 0) != int(frozen.setup_minutes)
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
    severity: str = "hard",
    job_id: str | None = None,
    operation_id: str | None = None,
    resource_id: str | None = None,
    start: Any = None,
    end: Any = None,
    suggested_relaxation: str | None = None,
    details: dict[str, Any] | None = None,
) -> Violation:
    text = code.value if isinstance(code, ReasonCode) else str(code)
    level: Literal["hard", "kpi"] = "kpi" if severity == "kpi" else "hard"
    return Violation(
        code=text,
        message=message or REASON_RU.get(text, text),
        severity=level,
        job_id=job_id,
        operation_id=operation_id,
        resource_id=resource_id,
        start=start,
        end=end,
        suggested_relaxation=suggested_relaxation or SUGGESTIONS.get(text),
        details=details or {},
    )
