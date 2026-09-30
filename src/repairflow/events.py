"""Domain events that change a repair card before a frozen replan."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from repairflow.model import Operation, RepairFlowModel, RepairFlowProblem


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
