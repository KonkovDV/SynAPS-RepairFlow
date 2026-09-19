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
    payload["operations"] = [broken if row.id == child.id else row for row in ops]
    with pytest.raises(ValueError, match="unsupported DAG"):
        RepairFlowProblem.model_validate(payload)


def test_predecessor_ids_must_match_linear_sequence() -> None:
    problem = synthesize("tiny", seed=1)
    ops = list(problem.operations)
    child = next(op for op in ops if op.predecessor_ids)
    other = next(op.id for op in ops if op.id not in {child.id, *child.predecessor_ids})
    wrong = child.model_copy(update={"predecessor_ids": [other]})
    payload = problem.model_dump(mode="python")
    payload["operations"] = [wrong if row.id == child.id else row for row in ops]
    with pytest.raises(ValueError, match="linear sequence"):
        RepairFlowProblem.model_validate(payload)


def test_first_operation_cannot_declare_a_predecessor() -> None:
    problem = synthesize("tiny", seed=1)
    ops = list(problem.operations)
    first = min(
        (op for op in ops if op.job_id == ops[0].job_id),
        key=lambda item: item.sequence,
    )
    extra = next(op.id for op in ops if op.id != first.id)
    broken = first.model_copy(update={"predecessor_ids": [extra]})
    payload = problem.model_dump(mode="python")
    payload["operations"] = [broken if row.id == first.id else row for row in ops]
    with pytest.raises(ValueError, match="linear sequence"):
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
