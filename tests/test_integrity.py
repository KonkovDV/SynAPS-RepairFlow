from repairflow.integrity import audit_predecessor_sequence
from repairflow.synthetic import synthesize


def test_predecessor_audit_passes_valid_dag() -> None:
    problem = synthesize("tiny", seed=1)

    report = audit_predecessor_sequence(problem)

    assert report["schema"] == "repairflow.predecessor_audit.v1"
    assert report["status"] == "pass"
    assert report["issue_count"] == 0
    assert report["edge_count"] > 0
    assert len(report["input_hash"]) == 64


def test_predecessor_audit_rejects_duplicate_and_forward_edges() -> None:
    problem = synthesize("tiny", seed=1)
    same_job = sorted(problem.operations, key=lambda row: (row.job_id, row.sequence, row.id))
    target = same_job[1]
    predecessor = same_job[0]
    forward_target = same_job[0]
    forward_predecessor = same_job[1]
    operations = [
        row.model_copy(
            update=(
                {"predecessor_ids": [predecessor.id, predecessor.id]}
                if row.id == target.id
                else {"predecessor_ids": [forward_predecessor.id]}
                if row.id == forward_target.id
                else {}
            )
        )
        for row in problem.operations
    ]
    malformed = problem.model_copy(update={"operations": operations})

    report = audit_predecessor_sequence(malformed)

    assert report["status"] == "fail"
    assert report["issue_count"] == 2
    assert {issue["code"] for issue in report["issues"]} == {
        "DUPLICATE_PREDECESSOR",
        "PREDECESSOR_SEQUENCE_INVALID",
    }
