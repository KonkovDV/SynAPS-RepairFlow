"""Domain notary for a plan that did not come from the kernel.

This module does not import solver search and does not read the SynAPS
feasibility checker. A clean result is `domain_verified`. It is not
`verified` and it is not `optimal`.
"""

from __future__ import annotations

from typing import Literal

from repairflow.checker import check_domain_assignments
from repairflow.evidence import evidence_stamp, fingerprint_payload, runtime_manifest, seal_result_hashes
from repairflow.metrics import compute_metrics
from repairflow.model import PlannedAssignment, RepairFlowProblem, RepairFlowResult, ResultStatus, Violation
from repairflow.versions import CLAIM_LEVEL, REPAIRFLOW_VERSION, SYNAPS_COMMIT


def verify_domain_plan(
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
    *,
    extra_violations: list[Violation] | None = None,
    source_rows: dict[str, tuple[str, int]] | None = None,
    shop_file: tuple[str, str] | None = None,
) -> RepairFlowResult:
    """Check a shop plan against the domain contract. The kernel is not called."""

    violations = check_domain_assignments(problem, assignments)
    if extra_violations:
        violations.extend(extra_violations)
    violations = _cite_source_rows(violations, source_rows)
    if extra_violations or source_rows:
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
    extra = {
        "solver_config": "verify-plan",
        "kernel_status": "domain_only",
        "kernel_consulted": False,
        "verification_origin": "domain_only",
        "claim_status": claim_status,
        "claim_note": "domain notary only; the kernel was not called",
        "config_payload": config_payload,
    }
    if shop_file is not None:
        extra["shop_plan_name"] = shop_file[0]
        extra["shop_plan_sha256"] = shop_file[1]
    stamp = evidence_stamp(
        input_hash=input_hash,
        config_hash=config_hash,
        data_provenance=problem.data_provenance,
        extra=extra,
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
    seal_result_hashes(payload)
    return payload


def _cite_source_rows(
    violations: list[Violation],
    source_rows: dict[str, tuple[str, int]] | None,
) -> list[Violation]:
    """Attach the shop file and line. The reason text stays the notary's."""

    if not source_rows:
        return violations
    cited: list[Violation] = []
    for row in violations:
        origin = None if row.operation_id is None else source_rows.get(row.operation_id)
        if origin is None or ("source_name" in row.details and "source_line" in row.details):
            cited.append(row)
            continue
        name, line = origin
        details = dict(row.details)
        details.setdefault("source_name", name)
        details.setdefault("source_line", line)
        cited.append(row.model_copy(update={"details": details}))
    return cited
