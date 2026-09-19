import pytest

from repairflow.model import RepairFlowProblem
from repairflow.synthetic import synthesize


def test_linear_tech_card_is_accepted() -> None:
    problem = synthesize("tiny", seed=1)
    assert all(len(op.predecessor_ids) <= 1 for op in problem.operations)


def test_branching_dag_is_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    ops = list(problem.operations)
    child = ops[-1]
    extra = ops[0].id
    preds = list(child.predecessor_ids)
    preds = [extra, ops[1].id] if len(preds) < 1 else [preds[0], extra]
    broken = child.model_copy(update={"predecessor_ids": preds})
    payload = problem.model_dump(mode="python")
    payload["operations"] = [
        broken if row.id == child.id else row for row in ops
    ]
    with pytest.raises(ValueError, match="unsupported DAG"):
        RepairFlowProblem.model_validate(payload)


def test_setup_matrix_covers_all_states() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    states = {op.setup_state for op in problem.operations} | {"idle"}
    for center in problem.work_centers:
        for from_state in states:
            for to_state in states:
                match = [
                    row
                    for row in problem.setup_matrix
                    if row.work_center_id == center.id
                    and row.from_state == from_state
                    and row.to_state == to_state
                ]
                assert match, (center.id, from_state, to_state)
