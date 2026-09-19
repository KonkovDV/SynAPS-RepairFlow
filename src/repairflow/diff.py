"""Plan-to-plan assignment diff, including frozen-change detection."""

from __future__ import annotations

from typing import Any

from repairflow.model import SCHEMA_DIFF, PlannedAssignment, RepairFlowProblem, RepairFlowResult


def diff_plans(
    problem: RepairFlowProblem,
    baseline: RepairFlowResult,
    candidate: RepairFlowResult,
) -> dict[str, Any]:
    base_map = {row.operation_id: row for row in baseline.assignments}
    new_map = {row.operation_id: row for row in candidate.assignments}
    added = [new_map[op] for op in new_map if op not in base_map]
    removed = [base_map[op] for op in base_map if op not in new_map]
    moved = []
    for op_id, after in new_map.items():
        before = base_map.get(op_id)
        if before is None:
            continue
        if _placement(before) != _placement(after):
            moved.append({"before": _row(before), "after": _row(after)})

    frozen_ok: list[dict[str, Any]] = []
    frozen_broken: list[dict[str, Any]] = []
    for frozen in problem.frozen_assignments:
        if not frozen.immutable:
            continue
        placed = new_map.get(frozen.operation_id)
        if (
            placed is not None
            and placed.work_center_id == frozen.work_center_id
            and placed.start == frozen.start
            and placed.end == frozen.end
            and (frozen.crew_id is None or placed.crew_id == frozen.crew_id)
        ):
            frozen_ok.append(_row(placed))
        else:
            frozen_broken.append(
                {
                    "operation_id": frozen.operation_id,
                    "expected": {
                        "work_center_id": frozen.work_center_id,
                        "start": frozen.start.isoformat(),
                        "end": frozen.end.isoformat(),
                        "crew_id": frozen.crew_id,
                    },
                    "actual": None if placed is None else _row(placed),
                }
            )

    return {
        "schema_version": SCHEMA_DIFF,
        "instance_id": problem.instance_id,
        "baseline_solver": baseline.solver_config,
        "candidate_solver": candidate.solver_config,
        "baseline_status": baseline.status.value,
        "candidate_status": candidate.status.value,
        "baseline_verified": baseline.verified_feasible,
        "candidate_verified": candidate.verified_feasible,
        "added_assignments": [_row(row) for row in added],
        "removed_assignments": [_row(row) for row in removed],
        "moved_assignments": moved,
        "unchanged_frozen_assignments": frozen_ok,
        "broken_frozen_assignments": frozen_broken,
        "metrics": {
            "baseline_violations": len(baseline.violations),
            "candidate_violations": len(candidate.violations),
            "baseline_makespan": baseline.objective.get("makespan_minutes"),
            "candidate_makespan": candidate.objective.get("makespan_minutes"),
            "baseline_tardiness": baseline.objective.get("total_tardiness_minutes"),
            "candidate_tardiness": candidate.objective.get("total_tardiness_minutes"),
            "baseline_coverage": baseline.objective.get("coverage"),
            "candidate_coverage": candidate.objective.get("coverage"),
        },
        "churn": {
            "added": len(added),
            "removed": len(removed),
            "moved": len(moved),
            "unchanged_frozen": len(frozen_ok),
            "broken_frozen": len(frozen_broken),
        },
    }


def _placement(row: PlannedAssignment) -> tuple[Any, ...]:
    return (row.work_center_id, row.crew_id, row.start, row.end, row.setup_minutes)


def _row(row: PlannedAssignment) -> dict[str, Any]:
    return {
        "operation_id": row.operation_id,
        "work_center_id": row.work_center_id,
        "crew_id": row.crew_id,
        "aux_ids": list(row.aux_ids),
        "start": row.start.isoformat(),
        "end": row.end.isoformat(),
        "setup_minutes": row.setup_minutes,
        "reason": row.reason,
    }
