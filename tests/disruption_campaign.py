"""Five disruption types across thirty tiny seeds. A hit that still verifies is false_accept."""

from __future__ import annotations

import time
from typing import Any

from repairflow.events import (
    CrewAbsent,
    DisruptionEvent,
    DurationOverrun,
    PartDelay,
    PostDown,
    UrgentJob,
    apply_disruption,
)
from repairflow.model import Job, Operation, RepairFlowProblem
from repairflow.nervousness import compare
from repairflow.planner import PlanOutcome, plan, recheck, replan_disruption
from repairflow.synthetic import synthesize

EXPECTED = {
    "POST_DOWN": "CALENDAR_BROKEN",
    "CREW_ABSENT": "CALENDAR_BROKEN",
    "PART_DELAY": "SPARE_UNAVAILABLE",
    "DURATION_OVERRUN": "INVALID_DURATION",
    "URGENT_JOB": "PARTIAL_COVERAGE",
}


def _event(problem: RepairFlowProblem, base: PlanOutcome, kind: str) -> DisruptionEvent:
    assignments = list(base.result.assignments)
    ops = {operation.id: operation for operation in problem.operations}
    if kind == "POST_DOWN":
        row = assignments[0]
        return PostDown(work_center_id=row.work_center_id, start=row.start, end=row.end)
    if kind == "CREW_ABSENT":
        row = next(item for item in assignments if item.crew_id)
        return CrewAbsent(crew_id=row.crew_id or "", start=row.start, end=row.end)
    if kind == "PART_DELAY":
        row = next(item for item in assignments if ops[item.operation_id].spare_demand())
        spare_id = next(iter(ops[row.operation_id].spare_demand()))
        return PartDelay(spare_id=spare_id, available_at=row.end)
    if kind == "DURATION_OVERRUN":
        row = assignments[0]
        operation = ops[row.operation_id]
        return DurationOverrun(operation_id=operation.id, new_duration_min=operation.duration_min + 30)
    start = problem.planning_horizon.start
    return UrgentJob(
        job=Job(
            id="JOB-URGENT",
            unit_type="engine",
            release_date=start,
            due_date=problem.planning_horizon.end,
            priority=1,
        ),
        operations=[
            Operation(
                id="JOB-URGENT-01",
                job_id="JOB-URGENT",
                sequence=1,
                duration_min=30,
                eligible_work_center_ids=["POST-U1", "POST-TEST"],
                required_skills=["mechanical"],
                setup_state="engine",
            )
        ],
    )


def run_disruption_campaign(*, preset: str = "tiny", seeds: range = range(1, 31)) -> dict[str, Any]:
    """Replan every type. false_accept means the issued plan still verified."""

    checked = 0
    false_accept = 0
    replanned = 0
    churn_sum = 0.0
    seconds = 0.0
    by_kind: dict[str, dict[str, int]] = {}
    example: dict[str, str] | None = None
    for seed in seeds:
        problem = synthesize(preset, seed=seed)
        base = plan(problem, solver_config="GREED")
        if not base.ok:
            raise RuntimeError(f"{preset} seed {seed} GREED is not verified")
        for kind, code in EXPECTED.items():
            event = _event(problem, base, kind)
            revised = apply_disruption(problem, event)
            old = recheck(
                revised,
                assignments=list(base.result.assignments),
                kernel_status="feasible",
                solver_config="disruption-old",
            )
            codes = {row.code for row in old.result.violations}
            accepted = bool(old.result.verified_feasible)
            checked += 1
            bucket = by_kind.setdefault(kind, {"checked": 0, "false_accept": 0, "replanned": 0})
            bucket["checked"] += 1
            if accepted:
                false_accept += 1
                bucket["false_accept"] += 1
                if example is None:
                    example = {"preset": preset, "seed": str(seed), "kind": kind, "code": code}
                continue
            if code not in codes:
                raise RuntimeError(f"{preset} seed {seed} {kind} rejected without {code}: {sorted(codes)}")
            started = time.perf_counter()
            repaired = replan_disruption(problem, base=base, event=event)
            seconds += time.perf_counter() - started
            if not repaired.result.verified_feasible or repaired.result.exit_code != 0:
                raise RuntimeError(f"{preset} seed {seed} {kind} replan is not verified")
            moved = len(compare(base.result, repaired.result).moved)
            issued = len(base.result.assignments) or 1
            churn_sum += moved / issued
            replanned += 1
            bucket["replanned"] += 1
    return {
        "schema": "repairflow.disruption_campaign.v1",
        "preset": preset,
        "seeds": [seeds.start, seeds.stop - 1],
        "solvers": ["GREED"],
        "checked": checked,
        "false_accept": false_accept,
        "replanned": replanned,
        "mean_churn": (churn_sum / replanned) if replanned else 0.0,
        "replan_seconds": seconds,
        "by_kind": by_kind,
        "false_accept_example": example,
    }
