"""Temporal ledgers for exchange pools and reusable/rotable spares.

The v1 schema keeps domain-specific spare semantics in ``Spare.domain_attributes``
so old documents remain valid. A spare is rotable when its attributes contain
``kind`` or ``mode`` equal to ``rotable``; ``return_lag_min`` models inspection,
cleaning or service time before the unit becomes serviceable again.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal

from repairflow.capacity import Occupancy, excess_arrivals
from repairflow.model import PlannedAssignment, RepairFlowProblem, Violation
from repairflow.reasons import REASON_RU, SUGGESTIONS, ReasonCode


def exchange_pool_violations(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    """Return exchange-pool and temporal-rotable-spare violations.

    Exchange-pool stock is cumulative over completion/demand events. Rotable
    spares are different: one physical unit may be reused only after the
    operation has finished and its declared return lag has elapsed. Both
    ledgers use deterministic half-open event semantics.
    """

    out: list[Violation] = []
    if problem.exchange_pools:
        out.extend(_exchange_pool_violations(problem, assignments))
    out.extend(_rotable_spare_violations(problem, assignments))
    return out


def _exchange_pool_violations(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
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


def _rotable_spare_violations(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> list[Violation]:
    ops = {op.id: op for op in problem.operations}
    by_op = {row.operation_id: row for row in assignments}
    out: list[Violation] = []
    for spare in problem.spares:
        attrs = spare.domain_attributes
        mode = str(attrs.get("mode", attrs.get("kind", "consumable"))).lower()
        if mode != "rotable":
            continue
        raw_lag = attrs.get("return_lag_min", 0)
        if isinstance(raw_lag, bool) or not isinstance(raw_lag, int) or raw_lag < 0:
            out.append(
                Violation(
                    code=ReasonCode.SPARE_UNAVAILABLE,
                    message="rotable spare has invalid return_lag_min",
                    resource_id=spare.id,
                    severity="hard",
                    suggested_relaxation=SUGGESTIONS[ReasonCode.SPARE_UNAVAILABLE],
                    details={"kind": "rotable", "return_lag_min": raw_lag},
                )
            )
            continue
        uses: list[Occupancy] = []
        for operation in ops.values():
            if spare.id not in operation.required_spare_ids:
                continue
            placed = by_op.get(operation.id)
            if placed is None:
                continue
            if spare.available_from is not None and placed.start < spare.available_from:
                out.append(
                    Violation(
                        code=ReasonCode.SPARE_UNAVAILABLE,
                        message=f"rotable spare {spare.code} is not available at operation start",
                        resource_id=spare.id,
                        operation_id=operation.id,
                        job_id=operation.job_id,
                        start=placed.start,
                        end=placed.end,
                        severity="hard",
                        suggested_relaxation=SUGGESTIONS[ReasonCode.SPARE_UNAVAILABLE],
                        details={"available_from": spare.available_from.isoformat()},
                    )
                )
            uses.append(
                Occupancy(
                    placed.start,
                    placed.end + timedelta(minutes=raw_lag),
                    operation.id,
                )
            )
        for excess in excess_arrivals(uses, spare.quantity):
            out.append(
                Violation(
                    code=ReasonCode.SPARE_UNAVAILABLE,
                    message=f"rotable spare {spare.code} is reused before return",
                    resource_id=spare.id,
                    operation_id=excess.operation_id,
                    start=excess.start,
                    end=excess.end,
                    severity="hard",
                    suggested_relaxation=SUGGESTIONS[ReasonCode.SPARE_UNAVAILABLE],
                    details={
                        "kind": "rotable",
                        "quantity": spare.quantity,
                        "return_lag_min": raw_lag,
                        "other_operation_id": excess.other_operation_id,
                        "active": excess.active,
                    },
                )
            )
    return out


def _completion_times(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> dict[str, datetime]:
    """A unit returns to the pool when every sink of its own card finishes."""

    by_job_ops: dict[str, set[str]] = defaultdict(set)
    for operation in problem.operations:
        by_job_ops[operation.job_id].add(operation.id)
    successors: dict[str, list[str]] = defaultdict(list)
    for operation in problem.operations:
        for pred in operation.predecessor_ids:
            if pred in by_job_ops[operation.job_id]:
                successors[pred].append(operation.id)
    by_op = {row.operation_id: row for row in assignments}
    finished: dict[str, datetime] = {}
    for job in problem.jobs:
        job_ops = by_job_ops.get(job.id, set())
        sinks = [op_id for op_id in job_ops if not successors[op_id]]
        ends: list[datetime] = []
        complete = True
        for op_id in sinks:
            placed = by_op.get(op_id)
            if placed is None:
                complete = False
                break
            ends.append(placed.end)
        if complete and ends:
            finished[job.id] = max(ends)
    return finished
