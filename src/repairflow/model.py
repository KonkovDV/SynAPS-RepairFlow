"""RepairFlow domain contract (schema repairflow.problem.v1 / result.v1)."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from repairflow.capacity import Occupancy, excess_arrivals
from repairflow.limits import (
    MAX_AUX,
    MAX_CALENDAR_WINDOWS,
    MAX_CALENDARS,
    MAX_CREWS,
    MAX_FROZEN,
    MAX_JOBS,
    MAX_OPERATIONS,
    MAX_POOLS,
    MAX_PRED_PER_OP,
    MAX_SETUP,
    MAX_SPARES,
    MAX_WORK_CENTERS,
)
from repairflow.scheduling_contract import held_minutes, is_unattended, open_minutes, policy_of

SCHEMA_PROBLEM: Literal["repairflow.problem.v1"] = "repairflow.problem.v1"
SCHEMA_RESULT: Literal["repairflow.result.v1"] = "repairflow.result.v1"
SCHEMA_DIFF: Literal["repairflow.diff.v1"] = "repairflow.diff.v1"

DataProvenance = Literal[
    "synthetic",
    "open_data",
    "customer_data",
    "experiment",
    "production_verified",
]
ClaimLevel = Literal["experiment", "benchmark", "pilot_candidate", "production_verified"]

_CROSS_REFS_LIMIT = 20


def _as_utc(value: datetime) -> datetime:
    from datetime import UTC

    return value.astimezone(UTC)


def _reject_unix_timestamp(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("boolean is not an instant; use ISO-8601 with offset")
    if isinstance(value, int | float):
        raise ValueError("unix timestamps are not accepted; use ISO-8601 with offset")
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            raise ValueError("unix timestamps are not accepted; use ISO-8601 with offset")
    return value


UTCInstant = Annotated[
    AwareDatetime,
    BeforeValidator(_reject_unix_timestamp),
    AfterValidator(_as_utc),
]


class RepairFlowModel(BaseModel):
    """Public documents reject unknown fields; extensions go in domain_attributes."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ResultStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    HEURISTIC_FEASIBLE = "HEURISTIC_FEASIBLE"
    PARTIAL = "PARTIAL"
    INFEASIBLE = "INFEASIBLE"
    NOT_VERIFIED = "NOT_VERIFIED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    ERROR = "ERROR"


class Policy(RepairFlowModel):
    """Scheduling policy.

    `unsupported_dag` is kept so existing v1 documents still parse. Branching
    cards are compiled (ADR-0002); the flag no longer rejects a DAG.
    """

    unknown_fields: Literal["reject"] = "reject"
    missing_setup: Literal["reject", "zero"] = "reject"
    unsupported_dag: Literal["reject"] = "reject"
    allow_partial_plan: bool = False
    dag_strategy: Literal["split_release_fixpoint", "serialize"] = "split_release_fixpoint"
    max_fixpoint_iter: int = Field(default=8, ge=1, le=32)
    nervousness_warn_ratio: float = Field(default=0.10, ge=0.0, le=1.0)


class PlanningHorizon(RepairFlowModel):
    start: UTCInstant
    end: UTCInstant

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("planning_horizon.end must be after start")
        return self


class CalendarWindow(RepairFlowModel):
    start: UTCInstant
    end: UTCInstant

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("calendar window end must be after start")
        return self


class Calendar(RepairFlowModel):
    id: str
    code: str = ""
    windows: list[CalendarWindow] = Field(default_factory=list)
    domain_attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _quota(self) -> Self:
        if len(self.windows) > MAX_CALENDAR_WINDOWS:
            raise ValueError(f"calendar {self.id}: more than {MAX_CALENDAR_WINDOWS} windows")
        return self


class Job(RepairFlowModel):
    id: str
    external_ref: str = ""
    asset_code: str = ""
    unit_type: str = ""
    due_date: UTCInstant | None = None
    deadline: UTCInstant | None = None
    release_date: UTCInstant | None = None
    priority: int = Field(default=500, ge=1, le=999)
    domain_attributes: dict[str, Any] = Field(default_factory=dict)


class Operation(RepairFlowModel):
    id: str
    job_id: str
    sequence: int = Field(ge=1)
    duration_min: int = Field(ge=1)
    predecessor_ids: list[str] = Field(default_factory=list)
    eligible_work_center_ids: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    required_aux_ids: list[str] = Field(default_factory=list)
    required_spare_ids: list[str] = Field(default_factory=list)
    setup_state: str = ""
    earliest_start: UTCInstant | None = None
    latest_finish: UTCInstant | None = None
    domain_attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _pred_quota(self) -> Self:
        if len(self.predecessor_ids) > MAX_PRED_PER_OP:
            raise ValueError(f"operation {self.id}: too many predecessors")
        if self.id in self.predecessor_ids:
            raise ValueError(f"operation {self.id} cannot precede itself")
        return self


class WorkCenter(RepairFlowModel):
    id: str
    code: str
    capability_group: str = "post"
    calendar_id: str | None = None
    max_parallel: int = Field(default=1, ge=1)
    eligible_unit_types: list[str] = Field(default_factory=list)
    domain_attributes: dict[str, Any] = Field(default_factory=dict)


class Crew(RepairFlowModel):
    id: str
    code: str
    skills: list[str] = Field(default_factory=list)
    calendar_id: str | None = None
    max_parallel: int = Field(default=1, ge=1)
    domain_attributes: dict[str, Any] = Field(default_factory=dict)


class AuxResource(RepairFlowModel):
    id: str
    code: str
    resource_type: str = "tool"
    capacity: int = Field(default=1, ge=1)
    calendar_id: str | None = None
    domain_attributes: dict[str, Any] = Field(default_factory=dict)


class SetupEntry(RepairFlowModel):
    from_state: str
    to_state: str
    duration_min: int = Field(ge=0)
    work_center_id: str | None = None
    domain_attributes: dict[str, Any] = Field(default_factory=dict)


class FrozenAssignment(RepairFlowModel):
    operation_id: str
    work_center_id: str
    start: UTCInstant
    end: UTCInstant
    crew_id: str | None = None
    setup_minutes: int = Field(default=0, ge=0)
    immutable: bool = True
    frozen_reason: str = ""
    domain_attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError(f"frozen assignment {self.operation_id}: end must be after start")
        return self


class Spare(RepairFlowModel):
    id: str
    code: str
    quantity: int = Field(default=1, ge=0)
    available_from: UTCInstant | None = None
    domain_attributes: dict[str, Any] = Field(default_factory=dict)


class PoolDemand(RepairFlowModel):
    at: UTCInstant
    qty: int = Field(ge=1)


class ExchangePool(RepairFlowModel):
    """Serviceable-unit ledger. This is stock over time, not a simultaneous pool."""

    unit_type: str
    initial_serviceable: int = Field(ge=0)
    demand: list[PoolDemand] = Field(default_factory=list)
    hard: bool = False


class PlannedAssignment(RepairFlowModel):
    operation_id: str
    work_center_id: str
    start: UTCInstant
    end: UTCInstant
    crew_id: str | None = None
    aux_ids: list[str] = Field(default_factory=list)
    setup_minutes: int = Field(default=0, ge=0)
    reason: str = ""


class Violation(RepairFlowModel):
    code: str
    message: str
    severity: Literal["hard", "kpi"] = "hard"
    job_id: str | None = None
    operation_id: str | None = None
    resource_id: str | None = None
    start: UTCInstant | None = None
    end: UTCInstant | None = None
    suggested_relaxation: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RepairFlowProblem(RepairFlowModel):
    schema_version: Literal["repairflow.problem.v1"] = SCHEMA_PROBLEM
    instance_id: str
    data_provenance: DataProvenance = "synthetic"
    planning_horizon: PlanningHorizon
    jobs: list[Job]
    operations: list[Operation]
    work_centers: list[WorkCenter]
    crews: list[Crew]
    aux_resources: list[AuxResource] = Field(default_factory=list)
    setup_matrix: list[SetupEntry] = Field(default_factory=list)
    calendars: list[Calendar] = Field(default_factory=list)
    frozen_assignments: list[FrozenAssignment] = Field(default_factory=list)
    spares: list[Spare] = Field(default_factory=list)
    exchange_pools: list[ExchangePool] = Field(default_factory=list)
    policy: Policy = Field(default_factory=Policy)
    domain_attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _cross_refs(self) -> Self:
        issues: list[str] = []
        for name, rows, limit in (
            ("jobs", self.jobs, MAX_JOBS),
            ("operations", self.operations, MAX_OPERATIONS),
            ("work_centers", self.work_centers, MAX_WORK_CENTERS),
            ("crews", self.crews, MAX_CREWS),
            ("aux_resources", self.aux_resources, MAX_AUX),
            ("setup_matrix", self.setup_matrix, MAX_SETUP),
            ("calendars", self.calendars, MAX_CALENDARS),
            ("frozen_assignments", self.frozen_assignments, MAX_FROZEN),
            ("spares", self.spares, MAX_SPARES),
            ("exchange_pools", self.exchange_pools, MAX_POOLS),
        ):
            if len(rows) > limit:
                issues.append(f"{name} count {len(rows)} exceeds lab limit {limit}")

        job_ids = [row.id for row in self.jobs]
        op_ids = [row.id for row in self.operations]
        wc_ids = [row.id for row in self.work_centers]
        crew_ids = [row.id for row in self.crews]
        aux_ids = [row.id for row in self.aux_resources]
        cal_ids = [row.id for row in self.calendars]
        spare_ids = [row.id for row in self.spares]

        for label, ids in (
            ("jobs", job_ids),
            ("operations", op_ids),
            ("work_centers", wc_ids),
            ("crews", crew_ids),
            ("aux_resources", aux_ids),
            ("calendars", cal_ids),
            ("spares", spare_ids),
        ):
            if len(set(ids)) != len(ids):
                issues.append(f"duplicate id in {label}")

        job_set = set(job_ids)
        op_set = set(op_ids)
        wc_set = set(wc_ids)
        crew_set = set(crew_ids)
        aux_set = set(aux_ids)
        cal_set = set(cal_ids)
        spare_set = set(spare_ids)

        seq_by_job: dict[str, list[int]] = defaultdict(list)
        for operation in self.operations:
            if operation.job_id not in job_set:
                issues.append(f"operation {operation.id} references unknown job {operation.job_id}")
            seq_by_job[operation.job_id].append(operation.sequence)
            for pred in operation.predecessor_ids:
                if pred not in op_set:
                    issues.append(f"operation {operation.id} references unknown predecessor {pred}")
            if not operation.eligible_work_center_ids:
                issues.append(
                    f"operation {operation.id} has empty eligible_work_center_ids "
                    "(empty does not mean every post)"
                )
            for wc_id in operation.eligible_work_center_ids:
                if wc_id not in wc_set:
                    issues.append(f"operation {operation.id} references unknown work center {wc_id}")
            for aux_id in operation.required_aux_ids:
                if aux_id not in aux_set:
                    issues.append(f"operation {operation.id} references unknown aux {aux_id}")
            for spare_id in operation.required_spare_ids:
                if spare_id not in spare_set:
                    issues.append(f"operation {operation.id} references unknown spare {spare_id}")
            if not operation.setup_state:
                issues.append(f"operation {operation.id} is missing setup_state")

        for job_id, sequences in seq_by_job.items():
            if len(set(sequences)) != len(sequences):
                issues.append(f"duplicate sequence in job {job_id}")

        for center in self.work_centers:
            if center.calendar_id is not None and center.calendar_id not in cal_set:
                issues.append(f"work center {center.id} references unknown calendar")
        for crew in self.crews:
            if crew.calendar_id is not None and crew.calendar_id not in cal_set:
                issues.append(f"crew {crew.id} references unknown calendar")
        for aux in self.aux_resources:
            if aux.calendar_id is not None and aux.calendar_id not in cal_set:
                issues.append(f"aux {aux.id} references unknown calendar")

        for entry in self.setup_matrix:
            if entry.work_center_id is not None and entry.work_center_id not in wc_set:
                issues.append("setup_matrix references unknown work center")

        frozen_ops = [row.operation_id for row in self.frozen_assignments]
        if len(set(frozen_ops)) != len(frozen_ops):
            issues.append("duplicate operation_id in frozen_assignments")
        ops_by_id = {op.id: op for op in self.operations}
        crews_by_id = {crew.id: crew for crew in self.crews}
        for frozen in self.frozen_assignments:
            if frozen.operation_id not in op_set:
                issues.append(f"frozen assignment references unknown operation {frozen.operation_id}")
            if frozen.work_center_id not in wc_set:
                issues.append(f"frozen assignment references unknown work center {frozen.work_center_id}")
            if frozen.crew_id is not None and frozen.crew_id not in crew_set:
                issues.append(f"frozen assignment references unknown crew {frozen.crew_id}")
            frozen_op = ops_by_id.get(frozen.operation_id)
            if frozen_op is None:
                continue
            if (
                frozen_op.eligible_work_center_ids
                and frozen.work_center_id not in frozen_op.eligible_work_center_ids
            ):
                issues.append(
                    f"frozen assignment {frozen.operation_id} work center {frozen.work_center_id} "
                    f"is not eligible"
                )
            if frozen.crew_id is not None and frozen_op.required_skills:
                frozen_crew = crews_by_id.get(frozen.crew_id)
                if frozen_crew is not None and not set(frozen_op.required_skills) <= set(frozen_crew.skills):
                    issues.append(
                        f"frozen assignment {frozen.operation_id}: crew {frozen.crew_id} "
                        f"lacks skills {sorted(frozen_op.required_skills)}"
                    )

        pool_types = [pool.unit_type for pool in self.exchange_pools]
        if len(set(pool_types)) != len(pool_types):
            issues.append("duplicate unit_type in exchange_pools")
        horizon = self.planning_horizon
        for pool in self.exchange_pools:
            if not pool.unit_type:
                issues.append("exchange pool is missing unit_type")
            for demand in pool.demand:
                if demand.at < horizon.start or demand.at > horizon.end:
                    issues.append(
                        f"exchange pool {pool.unit_type} demand at {demand.at.isoformat()} "
                        "is outside the planning horizon"
                    )

        issues.extend(_frozen_batch_issues(self))
        issues.extend(_dag_issues(self.operations))
        issues.extend(_setup_issues(self))

        if issues:
            msg = "; ".join(issues[:_CROSS_REFS_LIMIT])
            overflow = len(issues) - _CROSS_REFS_LIMIT
            if overflow > 0:
                msg += f"; … and {overflow} more validation error(s)"
            raise ValueError(msg)
        return self


class RepairFlowResult(RepairFlowModel):
    schema_version: Literal["repairflow.result.v1"] = SCHEMA_RESULT
    instance_id: str
    status: ResultStatus
    verified_feasible: bool
    input_hash: str
    config_hash: str
    result_hash: str = ""
    repairflow_version: str
    synaps_commit: str
    claim_level: ClaimLevel = "experiment"
    data_provenance: DataProvenance | str = "synthetic"
    kernel_status: str | None = None
    solver_config: str = ""
    claim_status: (
        Literal[
            "usage_error",
            "error",
            "rejected",
            "heuristic_feasible",
            "verified",
            "optimal",
        ]
        | None
    ) = None
    solver_class: Literal["heuristic", "exact", "baseline", "recheck"] | None = None
    exit_code: int = 2
    assignments: list[PlannedAssignment] = Field(default_factory=list)
    rejected: list[dict[str, Any]] = Field(default_factory=list)
    violations: list[Violation] = Field(default_factory=list)
    objective: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _frozen_batch_issues(problem: RepairFlowProblem) -> list[str]:
    """Immutable freezes must already be a feasible fragment. mutable rows are notes."""

    rows = [row for row in problem.frozen_assignments if row.immutable]
    if not rows:
        return []
    ops = {op.id: op for op in problem.operations}
    by_op = {row.operation_id: row for row in rows}
    centers = {wc.id: wc for wc in problem.work_centers}
    crews = {crew.id: crew for crew in problem.crews}
    calendars = {row.id: row for row in problem.calendars}
    issues: list[str] = []
    for row in rows:
        operation = ops.get(row.operation_id)
        if operation is None:
            continue
        for pred_id in operation.predecessor_ids:
            earlier = by_op.get(pred_id)
            if earlier is not None and row.start < earlier.end:
                issues.append(f"frozen {row.operation_id} starts before frozen predecessor {pred_id} ends")
        _frozen_calendar(problem, row, centers, crews, calendars, issues)
        _frozen_duration(problem, row, operation, centers, crews, calendars, issues)
    issues.extend(_frozen_lane_issues(rows, centers, crews))
    issues.extend(_frozen_aux_issues(rows, ops, {aux.id: aux for aux in problem.aux_resources}))
    issues.extend(_frozen_setup_issues(problem, rows))
    return issues


def _frozen_duration(
    problem: RepairFlowProblem,
    row: FrozenAssignment,
    operation: Operation,
    centers: dict[str, WorkCenter],
    crews: dict[str, Crew],
    calendars: dict[str, Calendar],
    issues: list[str],
) -> None:
    policy = policy_of(operation.domain_attributes)
    held = held_minutes(row.start, row.end)
    if policy == "invalid":
        issues.append(f"frozen {row.operation_id} has an invalid duration_policy")
        return
    if policy == "min":
        if held < operation.duration_min:
            issues.append(
                f"frozen {row.operation_id} holds {held} min, shorter than {operation.duration_min}"
            )
        return
    if policy == "preemptive":
        masks = _frozen_masks(row, operation, centers, crews, calendars, problem)
        open_held = open_minutes(row.start, row.end, masks) if masks else held
        if open_held != operation.duration_min:
            issues.append(
                f"frozen {row.operation_id} open minutes {open_held} "
                f"are not duration_min {operation.duration_min}"
            )
        return
    if held != operation.duration_min:
        issues.append(f"frozen {row.operation_id} holds {held} min, duration_min is {operation.duration_min}")
    _ = problem


def _frozen_masks(
    row: FrozenAssignment,
    operation: Operation,
    centers: dict[str, WorkCenter],
    crews: dict[str, Crew],
    calendars: dict[str, Calendar],
    problem: RepairFlowProblem,
) -> list[list[tuple[datetime, datetime]]]:
    masks: list[list[tuple[datetime, datetime]]] = []

    def add(calendar_id: str | None, attributes: dict[str, Any]) -> None:
        if is_unattended(attributes) or not calendar_id:
            return
        calendar = calendars.get(calendar_id)
        if calendar is None:
            return
        masks.append([(window.start, window.end) for window in calendar.windows])

    center = centers.get(row.work_center_id)
    if center is not None:
        add(center.calendar_id, center.domain_attributes)
    if row.crew_id is not None:
        crew = crews.get(row.crew_id)
        if crew is not None:
            add(crew.calendar_id, crew.domain_attributes)
    auxes = {aux.id: aux for aux in problem.aux_resources}
    for aux_id in operation.required_aux_ids:
        aux = auxes.get(aux_id)
        if aux is not None:
            add(aux.calendar_id, aux.domain_attributes)
    return masks


def _frozen_aux_issues(
    rows: list[FrozenAssignment],
    ops: dict[str, Operation],
    auxes: dict[str, AuxResource],
) -> list[str]:
    grouped: dict[str, list[FrozenAssignment]] = defaultdict(list)
    for row in rows:
        operation = ops.get(row.operation_id)
        if operation is None:
            continue
        for aux_id in operation.required_aux_ids:
            grouped[aux_id].append(row)
    issues: list[str] = []
    for aux_id, group in grouped.items():
        aux = auxes.get(aux_id)
        lanes = aux.capacity if aux is not None else 1
        issues.extend(_lane_clause(group, lanes, f"aux {aux_id}"))
    return issues


def _frozen_setup_issues(problem: RepairFlowProblem, rows: list[FrozenAssignment]) -> list[str]:
    from repairflow.lane_setup import lane_setup_evidence

    planned = [
        PlannedAssignment(
            operation_id=row.operation_id,
            work_center_id=row.work_center_id,
            start=row.start,
            end=row.end,
            crew_id=row.crew_id,
            setup_minutes=row.setup_minutes,
        )
        for row in rows
    ]
    by_id = {item.operation_id: item for item in lane_setup_evidence(problem, planned)}
    issues: list[str] = []
    for row in rows:
        placed = by_id.get(row.operation_id)
        if placed is None:
            continue
        expected = placed.expected_setup_minutes
        if expected is None:
            if problem.policy.missing_setup == "zero" and row.setup_minutes == 0:
                continue
            issues.append(f"frozen {row.operation_id} has no setup cell")
            continue
        if int(row.setup_minutes) != int(expected):
            issues.append(f"frozen {row.operation_id} setup {row.setup_minutes} min, matrix has {expected}")
    return issues


def _frozen_lane_issues(
    rows: list[FrozenAssignment],
    centers: dict[str, WorkCenter],
    crews: dict[str, Crew],
) -> list[str]:
    """Same sweep as the checker: setup is inside the lane, and K lanes are fungible."""

    by_post: dict[str, list[FrozenAssignment]] = defaultdict(list)
    by_crew: dict[str, list[FrozenAssignment]] = defaultdict(list)
    for row in rows:
        by_post[row.work_center_id].append(row)
        if row.crew_id:
            by_crew[row.crew_id].append(row)
    issues: list[str] = []
    for post_id, group in by_post.items():
        center = centers.get(post_id)
        lanes = center.max_parallel if center is not None else 1
        issues.extend(_lane_clause(group, lanes, f"post {post_id}"))
    for crew_id, group in by_crew.items():
        crew = crews.get(crew_id)
        lanes = crew.max_parallel if crew is not None else 1
        issues.extend(_lane_clause(group, lanes, f"crew {crew_id}"))
    return issues


def _lane_clause(rows: list[FrozenAssignment], lanes: int, label: str) -> list[str]:
    intervals = [
        Occupancy(row.start - timedelta(minutes=row.setup_minutes), row.end, row.operation_id) for row in rows
    ]
    witnesses = excess_arrivals(intervals, lanes)
    if not witnesses:
        return []
    names = {item.operation_id for item in witnesses}
    names.update(item.other_operation_id for item in witnesses if item.other_operation_id is not None)
    return [f"frozen overlap on {label}: {', '.join(sorted(names))}"]


def _frozen_calendar(
    problem: RepairFlowProblem,
    row: FrozenAssignment,
    centers: dict[str, WorkCenter],
    crews: dict[str, Crew],
    calendars: dict[str, Calendar],
    issues: list[str],
) -> None:
    occ = row.start - timedelta(minutes=row.setup_minutes)
    targets: list[Calendar] = []
    center = centers.get(row.work_center_id)
    if center is not None and center.calendar_id is not None:
        calendar = calendars.get(center.calendar_id)
        if calendar is not None:
            targets.append(calendar)
    if row.crew_id is not None:
        crew = crews.get(row.crew_id)
        if crew is not None and crew.calendar_id is not None:
            calendar = calendars.get(crew.calendar_id)
            if calendar is not None:
                targets.append(calendar)
    for calendar in targets:
        fits = any(occ >= window.start and row.end <= window.end for window in calendar.windows)
        if not calendar.windows or not fits:
            issues.append(f"frozen {row.operation_id} is outside calendar {calendar.id}")
    _ = problem


def _dag_issues(operations: list[Operation]) -> list[str]:
    """Acyclic technology cards are accepted. The kernel still sees chains only."""

    by_id = {op.id: op for op in operations}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for op in operations:
        for pred in op.predecessor_ids:
            outgoing[pred].append(op.id)

    indegree = {op.id: len(op.predecessor_ids) for op in operations}
    queue = deque(sorted(op_id for op_id, deg in indegree.items() if deg == 0))
    seen = 0
    while queue:
        node = queue.popleft()
        seen += 1
        for nxt in sorted(outgoing.get(node, [])):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
        queue = deque(sorted(queue))
    if seen != len(by_id):
        return ["operation precedence graph contains a cycle"]
    return []


def _setup_issues(problem: RepairFlowProblem) -> list[str]:
    keys: set[tuple[str | None, str, str]] = set()
    duplicates: list[str] = []
    for entry in problem.setup_matrix:
        key = (entry.work_center_id, entry.from_state, entry.to_state)
        if key in keys:
            duplicates.append(f"{entry.work_center_id}:{entry.from_state}->{entry.to_state}")
            if len(duplicates) >= 8:
                break
        keys.add(key)
    if duplicates:
        return [f"duplicate setup_matrix cells: {', '.join(duplicates)}"]
    if problem.policy.missing_setup != "reject":
        return []
    states = {op.setup_state for op in problem.operations if op.setup_state} | {"idle"}
    if not states:
        return []
    missing: list[str] = []
    for center in problem.work_centers:
        for from_state in states:
            for to_state in states:
                if (center.id, from_state, to_state) in keys:
                    continue
                if (None, from_state, to_state) in keys:
                    continue
                missing.append(f"{center.id}:{from_state}->{to_state}")
                if len(missing) >= 8:
                    return [f"missing setup_matrix cells: {', '.join(missing)}"]
    if missing:
        return [f"missing setup_matrix cells: {', '.join(missing)}"]
    return []
