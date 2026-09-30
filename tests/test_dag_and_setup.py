import pytest

from repairflow.model import RepairFlowProblem
from repairflow.synthetic import synthesize


def test_linear_tech_card_is_accepted() -> None:
    problem = synthesize("tiny", seed=1)
    assert all(len(op.predecessor_ids) <= 1 for op in problem.operations)


def test_branching_dag_is_accepted() -> None:
    problem = synthesize("tiny", seed=1)
    ops = list(problem.operations)
    child = next(op for op in ops if op.predecessor_ids)
    extra = next(op.id for op in ops if op.job_id != child.job_id)
    branched = child.model_copy(update={"predecessor_ids": [child.predecessor_ids[0], extra]})
    payload = problem.model_dump(mode="python")
    payload["operations"] = [branched if row.id == child.id else row for row in ops]
    loaded = RepairFlowProblem.model_validate(payload)
    assert any(len(op.predecessor_ids) > 1 for op in loaded.operations)


def test_acyclic_skip_edge_is_accepted() -> None:
    problem = synthesize("tiny", seed=1)
    ops = list(problem.operations)
    child = next(op for op in ops if op.predecessor_ids)
    other = next(op.id for op in ops if op.job_id != child.job_id)
    wrong = child.model_copy(update={"predecessor_ids": [other]})
    payload = problem.model_dump(mode="python")
    payload["operations"] = [wrong if row.id == child.id else row for row in ops]
    loaded = RepairFlowProblem.model_validate(payload)
    assert loaded.operations


def test_precedence_cycle_is_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    ops = list(problem.operations)
    first = min(
        (op for op in ops if op.job_id == ops[0].job_id),
        key=lambda item: item.sequence,
    )
    later = next(op for op in ops if op.job_id == first.job_id and first.id in op.predecessor_ids)
    broken = first.model_copy(update={"predecessor_ids": [later.id]})
    payload = problem.model_dump(mode="python")
    payload["operations"] = [broken if row.id == first.id else row for row in ops]
    with pytest.raises(ValueError, match="cycle"):
        RepairFlowProblem.model_validate(payload)


def test_empty_eligible_posts_are_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    ops = list(problem.operations)
    blank = ops[0].model_copy(update={"eligible_work_center_ids": []})
    payload = problem.model_dump(mode="python")
    payload["operations"] = [blank if row.id == blank.id else row for row in ops]
    with pytest.raises(ValueError, match="empty eligible_work_center_ids"):
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
