"""Domain events that change a repair card before a frozen replan."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import Field, model_validator

from repairflow.model import (
    Calendar,
    CalendarWindow,
    Crew,
    Job,
    Operation,
    PlannedAssignment,
    RepairFlowModel,
    RepairFlowProblem,
    Spare,
    UTCInstant,
    WorkCenter,
)


class InspectionEvent(RepairFlowModel):
    """Defect class revealed at inspection: insert branches and rewire the join."""

    job_id: str
    defect_class: str = Field(min_length=1)
    added_operations: list[Operation]
    rewire: dict[str, list[str]] = Field(default_factory=dict)


def apply_inspection(problem: RepairFlowProblem, event: InspectionEvent) -> RepairFlowProblem:
    jobs = {job.id: job for job in problem.jobs}
    if event.job_id not in jobs:
        raise ValueError(f"inspection references unknown job {event.job_id}")
    known = {op.id for op in problem.operations}
    added_ids = [op.id for op in event.added_operations]
    if len(set(added_ids)) != len(added_ids):
        raise ValueError("inspection added_operations contain duplicate ids")
    overlap = sorted(set(added_ids) & known)
    if overlap:
        raise ValueError(f"inspection reuses operation ids: {', '.join(overlap[:8])}")
    for operation in event.added_operations:
        if operation.job_id != event.job_id:
            raise ValueError(
                f"inspection operation {operation.id} belongs to {operation.job_id}, not {event.job_id}"
            )
    allowed = known | set(added_ids)
    for op_id, preds in event.rewire.items():
        if op_id not in allowed:
            raise ValueError(f"inspection rewires unknown operation {op_id}")
        missing = [pred for pred in preds if pred not in allowed]
        if missing:
            raise ValueError(f"inspection rewire {op_id} references unknown predecessors {missing}")

    by_id = {op.id: op for op in problem.operations}
    for op_id, preds in event.rewire.items():
        if op_id in by_id:
            by_id[op_id] = by_id[op_id].model_copy(update={"predecessor_ids": list(preds)})
    added: list[Operation] = []
    for operation in event.added_operations:
        preds = event.rewire.get(operation.id, list(operation.predecessor_ids))
        added.append(operation.model_copy(update={"predecessor_ids": list(preds)}))
    operations = [by_id[op.id] for op in problem.operations] + added
    job = jobs[event.job_id]
    attrs: dict[str, Any] = dict(job.domain_attributes)
    attrs["defect_class"] = event.defect_class
    jobs[event.job_id] = job.model_copy(update={"domain_attributes": attrs})
    payload = problem.model_dump(mode="python")
    payload["jobs"] = [jobs[row.id] for row in problem.jobs]
    payload["operations"] = operations
    return RepairFlowProblem.model_validate(payload)


class PostDown(RepairFlowModel):
    """One work centre is unavailable on a half-open interval."""

    kind: Literal["POST_DOWN"] = "POST_DOWN"
    work_center_id: str
    start: UTCInstant
    end: UTCInstant

    @model_validator(mode="after")
    def _ordered(self) -> PostDown:
        if self.end <= self.start:
            raise ValueError("POST_DOWN end must be after start")
        return self


class PartDelay(RepairFlowModel):
    """A consumable cannot be used before this instant."""

    kind: Literal["PART_DELAY"] = "PART_DELAY"
    spare_id: str
    available_at: UTCInstant


class CrewAbsent(RepairFlowModel):
    """One crew is unavailable on a half-open interval."""

    kind: Literal["CREW_ABSENT"] = "CREW_ABSENT"
    crew_id: str
    start: UTCInstant
    end: UTCInstant

    @model_validator(mode="after")
    def _ordered(self) -> CrewAbsent:
        if self.end <= self.start:
            raise ValueError("CREW_ABSENT end must be after start")
        return self


class DurationOverrun(RepairFlowModel):
    """The visit now takes longer than the card said."""

    kind: Literal["DURATION_OVERRUN"] = "DURATION_OVERRUN"
    operation_id: str
    new_duration_min: int = Field(ge=1)


class UrgentJob(RepairFlowModel):
    """A new job and its operations arrive after the plan was issued."""

    kind: Literal["URGENT_JOB"] = "URGENT_JOB"
    job: Job
    operations: list[Operation] = Field(min_length=1)


DisruptionEvent = PostDown | PartDelay | CrewAbsent | DurationOverrun | UrgentJob


def apply_disruption(problem: RepairFlowProblem, event: DisruptionEvent) -> RepairFlowProblem:
    """Return a new problem. An unknown id is an error."""

    if isinstance(event, PostDown):
        return _close_resource(problem, "work_center", event.work_center_id, event.start, event.end)
    if isinstance(event, CrewAbsent):
        return _close_resource(problem, "crew", event.crew_id, event.start, event.end)
    if isinstance(event, PartDelay):
        return _delay_spare(problem, event)
    if isinstance(event, DurationOverrun):
        return _lengthen(problem, event)
    return _insert_job(problem, event)


def affected_operation_ids(
    problem: RepairFlowProblem,
    event: DisruptionEvent,
    assignments: list[PlannedAssignment],
) -> list[str]:
    """Operations the issued plan can no longer keep. Unknown ids are an error."""

    if isinstance(event, UrgentJob):
        _insert_job(problem, event)
        return [operation.id for operation in event.operations]
    if isinstance(event, DurationOverrun):
        _require_operation(problem, event.operation_id)
        return [event.operation_id]
    if isinstance(event, PartDelay):
        _require_spare(problem, event.spare_id)
        hits: list[str] = []
        ops = {operation.id: operation for operation in problem.operations}
        for row in assignments:
            operation = ops.get(row.operation_id)
            if operation is None:
                continue
            if event.spare_id in operation.spare_demand() and row.start < event.available_at:
                hits.append(row.operation_id)
        return hits
    if isinstance(event, PostDown):
        _require_work_center(problem, event.work_center_id)
        return [
            row.operation_id
            for row in assignments
            if row.work_center_id == event.work_center_id and _occupancy_hits(row, event.start, event.end)
        ]
    _require_crew(problem, event.crew_id)
    return [
        row.operation_id
        for row in assignments
        if row.crew_id == event.crew_id and _occupancy_hits(row, event.start, event.end)
    ]


def _occupancy_hits(row: PlannedAssignment, start: datetime, end: datetime) -> bool:
    occ_start = row.start - timedelta(minutes=int(row.setup_minutes or 0))
    return occ_start < end and row.end > start


def _require_work_center(problem: RepairFlowProblem, work_center_id: str) -> WorkCenter:
    found = next((row for row in problem.work_centers if row.id == work_center_id), None)
    if found is None:
        raise ValueError(f"unknown work center {work_center_id}")
    return found


def _require_crew(problem: RepairFlowProblem, crew_id: str) -> Crew:
    found = next((row for row in problem.crews if row.id == crew_id), None)
    if found is None:
        raise ValueError(f"unknown crew {crew_id}")
    return found


def _require_spare(problem: RepairFlowProblem, spare_id: str) -> Spare:
    found = next((row for row in problem.spares if row.id == spare_id), None)
    if found is None:
        raise ValueError(f"unknown spare {spare_id}")
    return found


def _require_operation(problem: RepairFlowProblem, operation_id: str) -> Operation:
    found = next((row for row in problem.operations if row.id == operation_id), None)
    if found is None:
        raise ValueError(f"unknown operation {operation_id}")
    return found


def _private_calendar(
    problem: RepairFlowProblem,
    calendar_id: str | None,
    resource_id: str,
    start: datetime,
    end: datetime,
) -> Calendar:
    calendars = {row.id: row for row in problem.calendars}
    source = calendars.get(calendar_id) if calendar_id else None
    if source is None and calendar_id:
        raise ValueError(f"calendar {calendar_id} is not in the instance")
    windows = (
        list(source.windows)
        if source is not None
        else [CalendarWindow(start=problem.planning_horizon.start, end=problem.planning_horizon.end)]
    )
    return _fresh_calendar(problem, resource_id, _punch(windows, start, end))


def _close_resource(
    problem: RepairFlowProblem,
    kind: str,
    resource_id: str,
    start: datetime,
    end: datetime,
) -> RepairFlowProblem:
    if kind == "work_center":
        center = _require_work_center(problem, resource_id)
        private = _private_calendar(problem, center.calendar_id, resource_id, start, end)
        updated_center = center.model_copy(update={"calendar_id": private.id})
        centers = [updated_center if row.id == resource_id else row for row in problem.work_centers]
        return problem.model_copy(
            update={"work_centers": centers, "calendars": [*problem.calendars, private]}
        )
    crew = _require_crew(problem, resource_id)
    private = _private_calendar(problem, crew.calendar_id, resource_id, start, end)
    updated_crew = crew.model_copy(update={"calendar_id": private.id})
    crews = [updated_crew if row.id == resource_id else row for row in problem.crews]
    return problem.model_copy(update={"crews": crews, "calendars": [*problem.calendars, private]})


def _fresh_calendar(problem: RepairFlowProblem, resource_id: str, windows: list[CalendarWindow]) -> Calendar:
    taken = {row.id for row in problem.calendars}
    base = f"DISRUPT-{resource_id}"
    new_id = base
    suffix = 2
    while new_id in taken:
        new_id = f"{base}-{suffix}"
        suffix += 1
    return Calendar(id=new_id, code=new_id, windows=windows)


def _punch(windows: list[CalendarWindow], start: datetime, end: datetime) -> list[CalendarWindow]:
    punched: list[CalendarWindow] = []
    for window in windows:
        left_end = min(window.end, start)
        if window.start < left_end:
            punched.append(CalendarWindow(start=window.start, end=left_end))
        right_start = max(window.start, end)
        if right_start < window.end:
            punched.append(CalendarWindow(start=right_start, end=window.end))
    return punched


def _delay_spare(problem: RepairFlowProblem, event: PartDelay) -> RepairFlowProblem:
    spare = _require_spare(problem, event.spare_id)
    receipts = [row for row in spare.receipts if row.at >= event.available_at]
    updated = spare.model_copy(update={"available_from": event.available_at, "receipts": receipts})
    spares = [updated if row.id == spare.id else row for row in problem.spares]
    return problem.model_copy(update={"spares": spares})


def _lengthen(problem: RepairFlowProblem, event: DurationOverrun) -> RepairFlowProblem:
    operation = _require_operation(problem, event.operation_id)
    if event.new_duration_min == operation.duration_min:
        raise ValueError(f"duration overrun does not change {operation.id}")
    updated = operation.model_copy(update={"duration_min": event.new_duration_min})
    operations = [updated if row.id == operation.id else row for row in problem.operations]
    return problem.model_copy(update={"operations": operations})


def _insert_job(problem: RepairFlowProblem, event: UrgentJob) -> RepairFlowProblem:
    if any(job.id == event.job.id for job in problem.jobs):
        raise ValueError(f"job {event.job.id} already exists")
    known = {operation.id for operation in problem.operations}
    added = [operation.id for operation in event.operations]
    if len(set(added)) != len(added):
        raise ValueError("urgent job operations contain duplicate ids")
    overlap = sorted(set(added) & known)
    if overlap:
        raise ValueError(f"urgent job reuses operation ids: {', '.join(overlap[:8])}")
    allowed = known | set(added)
    for operation in event.operations:
        if operation.job_id != event.job.id:
            raise ValueError(
                f"urgent operation {operation.id} belongs to {operation.job_id}, not {event.job.id}"
            )
        missing = [pred for pred in operation.predecessor_ids if pred not in allowed]
        if missing:
            raise ValueError(f"urgent operation {operation.id} references unknown predecessors {missing}")
    return problem.model_copy(
        update={
            "jobs": [*problem.jobs, event.job],
            "operations": [*problem.operations, *event.operations],
        }
    )
