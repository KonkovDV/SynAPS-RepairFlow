"""Unified, hash-bound evidence rows for solver comparisons."""

from __future__ import annotations

from typing import Any

from repairflow.evidence import evidence_stamp, fingerprint_payload
from repairflow.metrics import compute_metrics
from repairflow.model import RepairFlowProblem, RepairFlowResult
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT

TABLE_SCHEMA = "repairflow.evidence_table.v1"


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def build_evidence_table(
    problem: RepairFlowProblem,
    results: dict[str, RepairFlowResult],
) -> dict[str, Any]:
    """Build a comparable table without changing any solver verdicts.

    Every row is scored with the same independent metric function and must refer
    to the same input problem. The table records claims and provenance instead
    of inferring them from a solver name.
    """

    input_hashes = {result.input_hash for result in results.values()}
    if len(input_hashes) > 1:
        raise ValueError("evidence table cannot mix different input hashes")

    rows: list[dict[str, Any]] = []
    for solver_name, result in sorted(results.items()):
        scope = _optional_string(result.metadata.get("optimality_scope"))
        rows.append(
            {
                "solver": solver_name,
                "status": result.status.value,
                "claim_status": result.claim_status,
                "solver_class": result.solver_class,
                "kernel_status": result.kernel_status,
                "optimality_scope": scope,
                "verified_feasible": result.verified_feasible,
                "exit_code": result.exit_code,
                "input_hash": result.input_hash,
                "config_hash": result.config_hash,
                "result_hash": result.result_hash,
                "repairflow_version": result.repairflow_version,
                "synaps_commit": result.synaps_commit,
                "claim_level": result.claim_level,
                "data_provenance": result.data_provenance,
                "metrics": compute_metrics(problem, list(result.assignments)),
            }
        )

    input_hash = next(iter(input_hashes), fingerprint_payload(problem.model_dump(mode="json")))
    config_hash = fingerprint_payload([row["config_hash"] for row in rows])
    table: dict[str, Any] = {
        "schema": TABLE_SCHEMA,
        "repairflow_version": REPAIRFLOW_VERSION,
        "synaps_commit": SYNAPS_COMMIT,
        "claim_level": "experiment",
        "data_provenance": problem.data_provenance,
        "metric_contract": {
            "makespan_origin": "planning_horizon.start",
            "post_utilization_denominator": "sum_work_center_max_parallel * horizon_minutes",
            "coverage": "assigned_operations / total_operations",
            "verified": "independent_checker_exit_code == 0 and full coverage",
            "optimality": "recorded per row; never inferred from a heuristic solver name",
        },
        "rows": rows,
    }
    table["table_hash"] = fingerprint_payload(table["rows"])
    table["evidence"] = evidence_stamp(
        input_hash=input_hash,
        config_hash=config_hash,
        data_provenance=str(problem.data_provenance),
        extra={"table_hash": table["table_hash"]},
    )
    return table
