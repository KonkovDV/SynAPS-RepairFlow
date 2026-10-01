"""Bounded local ATC dispatch-order contract.

This module is an evaluation baseline, not a SynAPS API. It produces a
priority order for a supplied ready set; it does not assign resources, solve
the schedule, verify feasibility, or claim optimality.

The implementation uses the standard apparent-tardiness-cost shape with the
RepairFlow convention that a larger ``Job.priority`` is more urgent, matching
its existing EDD baseline. Missing due dates use the planning-horizon end.
The caller supplies ``now`` explicitly so the result is deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import exp, isfinite

from repairflow.model import RepairFlowProblem


@dataclass(frozen=True, slots=True)
class ATCConfig:
    """Explicit parameters for the bounded local ATC ordering contract."""

    k: float = 2.0

    def __post_init__(self) -> None:
        if not isfinite(self.k) or self.k <= 0:
            raise ValueError("ATC k must be finite and positive")


def atc_priority(
    problem: RepairFlowProblem,
    operation_id: str,
    *,
    now: datetime,
    average_processing_min: float,
    config: ATCConfig = ATCConfig(),
) -> float:
    """Return one deterministic ATC score for a known operation.

    The score is ``w / p * exp(-slack / (k * p_bar))`` where ``w`` is the
    RepairFlow job priority, ``p`` is the operation duration, and ``p_bar`` is
    the caller-provided mean processing time for the ready set. ``slack`` is
    ``max(due - now - p, 0)`` in minutes.
    """

    operations = {operation.id: operation for operation in problem.operations}
    operation = operations.get(operation_id)
    if operation is None:
        raise ValueError(f"unknown operation: {operation_id}")
    if not isfinite(average_processing_min) or average_processing_min <= 0:
        raise ValueError("average_processing_min must be finite and positive")

    jobs = {job.id: job for job in problem.jobs}
    job = jobs.get(operation.job_id)
    if job is None:
        raise ValueError(f"operation {operation_id} references unknown job {operation.job_id}")
    duration = float(operation.duration_min)
    due = job.due_date or problem.planning_horizon.end
    slack = max(0.0, (due - now).total_seconds() / 60.0 - duration)
    urgency = exp(-slack / (config.k * average_processing_min))
    return float(max(1, job.priority) / duration * urgency)


def atc_order(
    problem: RepairFlowProblem,
    operation_ids: Sequence[str],
    *,
    now: datetime,
    config: ATCConfig = ATCConfig(),
) -> list[str]:
    """Return a deterministic ATC order for a supplied ready-operation set.

    This function deliberately does not infer readiness, precedence, resource
    availability, or a schedule. Those remain the planner/checker contract.
    """

    ids = list(operation_ids)
    if len(set(ids)) != len(ids):
        raise ValueError("ATC operation_ids must be unique")
    operations = {operation.id: operation for operation in problem.operations}
    missing = sorted(operation_id for operation_id in ids if operation_id not in operations)
    if missing:
        raise ValueError("unknown operation(s): " + ", ".join(missing))
    if not ids:
        return []

    average = sum(operations[operation_id].duration_min for operation_id in ids) / len(ids)
    jobs = {job.id: job for job in problem.jobs}

    def key(operation_id: str) -> tuple[float, datetime, int, str]:
        operation = operations[operation_id]
        job = jobs[operation.job_id]
        due = job.due_date or problem.planning_horizon.end
        score = atc_priority(
            problem,
            operation_id,
            now=now,
            average_processing_min=average,
            config=config,
        )
        return (-score, due, operation.duration_min, operation_id)

    return sorted(ids, key=key)
