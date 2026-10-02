"""Domain notary for a plan that did not come from the kernel.

This module does not import solver search and does not read the SynAPS
feasibility checker. A clean result is `domain_verified`. It is not
`verified` and it is not `optimal`.
"""

from __future__ import annotations

from typing import Literal

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_plan
from repairflow.evidence import evidence_stamp, fingerprint_payload, runtime_manifest
from repairflow.metrics import compute_metrics
from repairflow.model import PlannedAssignment, RepairFlowProblem, RepairFlowResult, ResultStatus, Violation
from repairflow.versions import CLAIM_LEVEL, REPAIRFLOW_VERSION, SYNAPS_COMMIT


def verify_domain_plan(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    *,
    extra_violations: list[Violation] | None = None,
) -> RepairFlowResult:
    """Check a shop plan against the domain contract. The kernel is not called."""

    schedule_problem, id_map = to_schedule_problem(problem)
    violations = check_plan(
        problem,
        schedule_problem=schedule_problem,
        assignments=assignments,
        id_map=id_map,
        kernel_status="domain_only",
    )
    if extra_violations:
        violations.extend(extra_violations)
        violations.sort(
            key=lambda row: (row.code, row.operation_id or "", row.resource_id or "", row.message)
        )
    hard = [row for row in violations if row.severity != "kpi"]
    clean = not hard
    claim_status: Literal["domain_verified", "rejected"] = "domain_verified" if clean else "rejected"
    if clean:
        status = ResultStatus.DOMAIN_VERIFIED
        exit_code = 0
    elif any(row.code == "PARTIAL_COVERAGE" for row in hard):
        status = ResultStatus.PARTIAL
        exit_code = 2
    else:
        status = ResultStatus.NOT_VERIFIED
        exit_code = 2
    input_hash = fingerprint_payload(problem.model_dump(mode="json"))
    config_payload = {
        "solver_config": "verify-plan",
        "synaps_commit": SYNAPS_COMMIT,
        "kernel_consulted": False,
        "runtime": runtime_manifest(),
    }
    config_hash = fingerprint_payload(config_payload)
    stamp = evidence_stamp(
        input_hash=input_hash,
        config_hash=config_hash,
        data_provenance=problem.data_provenance,
        extra={
            "solver_config": "verify-plan",
            "kernel_status": "domain_only",
            "kernel_consulted": False,
            "verification_origin": "domain_only",
            "claim_status": claim_status,
            "claim_note": "domain notary only; the kernel was not called",
            "config_payload": config_payload,
        },
    )
    payload = RepairFlowResult(
        instance_id=problem.instance_id,
        status=status,
        verified_feasible=False,
        input_hash=input_hash,
        config_hash=config_hash,
        repairflow_version=REPAIRFLOW_VERSION,
        synaps_commit=SYNAPS_COMMIT,
        claim_level=CLAIM_LEVEL,
        data_provenance=problem.data_provenance,
        kernel_status="domain_only",
        solver_config="verify-plan",
        claim_status=claim_status,
        solver_class="domain",
        exit_code=exit_code,
        assignments=list(assignments),
        violations=violations,
        objective=compute_metrics(problem, assignments),
        metadata=stamp,
    )
    payload.result_hash = fingerprint_payload(payload.model_dump(mode="json", exclude={"result_hash"}))
    return payload
