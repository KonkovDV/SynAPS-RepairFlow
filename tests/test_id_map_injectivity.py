"""The id map must be injective, not only a matching set of keys."""

from __future__ import annotations

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_plan
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_duplicate_uuid_is_invalid_even_when_keys_match() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    keys = [key for key in id_map if key.startswith("op:")]
    collided = dict(id_map)
    collided[keys[1]] = collided[keys[0]]
    violations = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[],
        id_map=collided,
        kernel_status="feasible",
    )
    assert [row.code for row in violations] == [ReasonCode.INVALID_ID_MAP]
    assert "injective" in violations[0].message


def test_compiled_id_map_is_injective() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    violations = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert all(row.code != ReasonCode.INVALID_ID_MAP for row in violations)
