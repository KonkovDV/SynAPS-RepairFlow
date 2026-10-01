"""Structural audits that preserve the domain checker as the final notary."""

from __future__ import annotations

from dataclasses import dataclass

from repairflow.evidence import fingerprint_payload
from repairflow.model import RepairFlowProblem
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT

AUDIT_SCHEMA = "repairflow.predecessor_audit.v1"


@dataclass(frozen=True)
class PredecessorIssue:
    code: str
    operation_id: str
    predecessor_id: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "operation_id": self.operation_id,
            "predecessor_id": self.predecessor_id,
            "message": self.message,
        }


def audit_predecessor_sequence(problem: RepairFlowProblem) -> dict[str, object]:
    """Audit edge identity and local sequence direction without changing a plan.

    Same-job predecessor edges must point strictly backwards in the published
    sequence. Cross-job edges are retained by the DAG compiler and therefore do
    not use the source job's sequence as a comparable ordering.
    """

    operations = sorted(problem.operations, key=lambda row: (row.job_id, row.sequence, row.id))
    by_id = {operation.id: operation for operation in operations}
    issues: list[PredecessorIssue] = []
    edge_count = 0
    for operation in operations:
        seen: set[str] = set()
        for predecessor_id in operation.predecessor_ids:
            edge_count += 1
            if predecessor_id in seen:
                issues.append(
                    PredecessorIssue(
                        code="DUPLICATE_PREDECESSOR",
                        operation_id=operation.id,
                        predecessor_id=predecessor_id,
                        message="predecessor_ids contains a duplicate edge",
                    )
                )
                continue
            seen.add(predecessor_id)
            predecessor = by_id.get(predecessor_id)
            if predecessor is None:
                issues.append(
                    PredecessorIssue(
                        code="UNKNOWN_PREDECESSOR",
                        operation_id=operation.id,
                        predecessor_id=predecessor_id,
                        message="predecessor_ids references an unknown operation",
                    )
                )
                continue
            if predecessor.job_id == operation.job_id and predecessor.sequence >= operation.sequence:
                issues.append(
                    PredecessorIssue(
                        code="PREDECESSOR_SEQUENCE_INVALID",
                        operation_id=operation.id,
                        predecessor_id=predecessor_id,
                        message="same-job predecessor must have a strictly lower sequence",
                    )
                )

    input_hash = fingerprint_payload(problem.model_dump(mode="json"))
    return {
        "schema": AUDIT_SCHEMA,
        "status": "pass" if not issues else "fail",
        "repairflow_version": REPAIRFLOW_VERSION,
        "synaps_commit": SYNAPS_COMMIT,
        "instance_id": problem.instance_id,
        "input_hash": input_hash,
        "operation_count": len(operations),
        "edge_count": edge_count,
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
