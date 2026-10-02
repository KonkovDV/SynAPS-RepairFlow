"""Guaranteed-invalid mutations of one checked synthetic plan.

The slow test is the proof. docs/fault-campaign.json is the committed denominator.
Synthetic data only. Not a shop measurement.
"""

from __future__ import annotations

from datetime import timedelta

from repairflow.evidence import fingerprint_payload
from repairflow.model import PlannedAssignment
from repairflow.planner import plan, recheck
from repairflow.synthetic import synthesize
from repairflow.versions import SYNAPS_COMMIT

MUTATIONS = ("shift_out", "drop", "wrong_crew", "same_slot", "bad_duration")


def _mutate(
    rows: list[PlannedAssignment],
    index: int,
    kind: str,
    crew_ids: list[str],
) -> list[PlannedAssignment]:
    row = rows[index % len(rows)]
    if kind == "shift_out":
        shifted = row.model_copy(
            update={"start": row.start - timedelta(days=30), "end": row.end - timedelta(days=30)}
        )
        return [shifted if item.operation_id == row.operation_id else item for item in rows]
    if kind == "drop":
        return [item for item in rows if item.operation_id != row.operation_id]
    if kind == "wrong_crew":
        other = next(crew_id for crew_id in crew_ids if crew_id != row.crew_id)
        changed = row.model_copy(update={"crew_id": other})
        return [changed if item.operation_id == row.operation_id else item for item in rows]
    if kind == "same_slot":
        other = rows[(index + 1) % len(rows)]
        changed = row.model_copy(
            update={
                "start": other.start,
                "end": other.end,
                "work_center_id": other.work_center_id,
            }
        )
        return [changed if item.operation_id == row.operation_id else item for item in rows]
    changed = row.model_copy(update={"end": row.start + timedelta(minutes=1)})
    return [changed if item.operation_id == row.operation_id else item for item in rows]


def run_fault_campaign(*, checks: int = 10_000) -> dict[str, object]:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    if not outcome.result.verified_feasible:
        raise RuntimeError("campaign baseline is not verified")
    rows = list(outcome.result.assignments)
    if len(rows) < 2:
        raise RuntimeError("campaign baseline has fewer than two assignments")
    crew_ids = [crew.id for crew in problem.crews]
    false_accept = 0
    for index in range(checks):
        mutated = _mutate(rows, index, MUTATIONS[index % len(MUTATIONS)], crew_ids)
        result = recheck(
            problem,
            assignments=mutated,
            kernel_status="feasible",
            solver_config="recheck",
        )
        if result.result.verified_feasible:
            false_accept += 1
    return {
        "schema": "repairflow.fault_campaign.v1",
        "checked": checks,
        "false_accept": false_accept,
        "preset": "tiny",
        "seed": 1,
        "solver_config": "GREED",
        "mutations": list(MUTATIONS),
        "input_hash": fingerprint_payload(problem.model_dump(mode="json")),
        "synaps_commit": SYNAPS_COMMIT,
        "claim_level": "experiment",
        "data_provenance": "synthetic",
    }
