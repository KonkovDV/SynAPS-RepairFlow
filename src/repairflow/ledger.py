"""Exchange-pool ledger. Stock is cumulative, not a simultaneous resource pool."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Literal

from repairflow.model import PlannedAssignment, RepairFlowProblem, Violation
from repairflow.reasons import REASON_RU, SUGGESTIONS, ReasonCode


def exchange_pool_violations(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    if not problem.exchange_pools:
        return []
    completions = _completion_times(problem, assignments)
    out: list[Violation] = []
    for pool in problem.exchange_pools:
        deltas: dict[datetime, int] = defaultdict(int)
        for job in problem.jobs:
            if job.unit_type != pool.unit_type:
                continue
            finished = completions.get(job.id)
            if finished is not None:
                deltas[finished] += 1
        for demand in pool.demand:
            deltas[demand.at] -= demand.qty
        stock = pool.initial_serviceable
        worst = stock
        worst_at: datetime | None = None
        for moment in sorted(deltas):
            stock += deltas[moment]
            if stock < worst:
                worst = stock
                worst_at = moment
        if worst >= 0:
            continue
        level: Literal["hard", "kpi"] = "hard" if pool.hard else "kpi"
        out.append(
            Violation(
                code=ReasonCode.EXCHANGE_POOL_STOCKOUT,
                message=REASON_RU[ReasonCode.EXCHANGE_POOL_STOCKOUT],
                severity=level,
                resource_id=pool.unit_type,
                start=worst_at,
                suggested_relaxation=SUGGESTIONS[ReasonCode.EXCHANGE_POOL_STOCKOUT],
                details={
                    "unit_type": pool.unit_type,
                    "min_stock": worst,
                    "hard": pool.hard,
                },
            )
        )
    return out


def _completion_times(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> dict[str, datetime]:
    """A unit returns to the pool when every sink of its card has finished."""

    successors: dict[str, list[str]] = defaultdict(list)
    for operation in problem.operations:
        for pred in operation.predecessor_ids:
            successors[pred].append(operation.id)
    by_op = {row.operation_id: row for row in assignments}
    finished: dict[str, datetime] = {}
    for job in problem.jobs:
        job_ops = [op for op in problem.operations if op.job_id == job.id]
        if not job_ops:
            continue
        sinks = [op for op in job_ops if not successors[op.id]]
        ends: list[datetime] = []
        complete = True
        for sink in sinks:
            placed = by_op.get(sink.id)
            if placed is None:
                complete = False
                break
            ends.append(placed.end)
        if complete and ends:
            finished[job.id] = max(ends)
    return finished
