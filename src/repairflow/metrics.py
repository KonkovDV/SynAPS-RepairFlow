"""Independent schedule metrics. Every solver is scored with the same formulas.

Makespan is measured from the planning-horizon start, not from the first
assignment. Raw solver objectives stay in ``metadata['solver_objective']``.
Post utilization is setup-inclusive and normalized by parallel lane capacity.
"""

from __future__ import annotations

from repairflow.model import PlannedAssignment, RepairFlowProblem


def compute_metrics(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> dict[str, float | int | str]:
    horizon = problem.planning_horizon
    horizon_minutes = max(1, int((horizon.end - horizon.start).total_seconds() // 60))
    ops = {op.id: op for op in problem.operations}
    assigned = {row.operation_id for row in assignments}
    unscheduled = sum(1 for op in problem.operations if op.id not in assigned)
    total = len(problem.operations)
    coverage = 0.0 if total == 0 else (total - unscheduled) / total
    if assignments:
        makespan = (max(row.end for row in assignments) - horizon.start).total_seconds() / 60.0
    else:
        makespan = 0.0
    setup = sum(int(row.setup_minutes or 0) for row in assignments)
    by_job_end: dict[str, PlannedAssignment] = {}
    for row in assignments:
        operation = ops.get(row.operation_id)
        if operation is None:
            continue
        current = by_job_end.get(operation.job_id)
        if current is None or row.end > current.end:
            by_job_end[operation.job_id] = row
    tardiness = 0.0
    for job in problem.jobs:
        if job.due_date is None:
            continue
        last = by_job_end.get(job.id)
        if last is None:
            continue
        late = (last.end - job.due_date).total_seconds() / 60.0
        if late > 0:
            tardiness += late
    processing_minutes = sum((row.end - row.start).total_seconds() / 60.0 for row in assignments)
    post_capacity_lanes = max(1, sum(center.max_parallel for center in problem.work_centers))
    post_capacity_minutes = post_capacity_lanes * horizon_minutes
    setup_utilization = setup / post_capacity_minutes
    processing_utilization = processing_minutes / post_capacity_minutes
    return {
        "makespan_minutes": round(makespan, 3),
        "total_setup_minutes": int(setup),
        "total_tardiness_minutes": round(tardiness, 3),
        "coverage": round(coverage, 6),
        "unscheduled_operations": int(unscheduled),
        "post_capacity_lanes": int(post_capacity_lanes),
        "post_processing_utilization": round(processing_utilization, 6),
        "post_setup_utilization": round(setup_utilization, 6),
        "post_utilization": round(processing_utilization + setup_utilization, 6),
        "post_utilization_denominator": "sum_work_center_max_parallel * horizon_minutes",
        "origin": "horizon_start",
    }
