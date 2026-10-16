"""The id map must be injective, not only a matching set of keys."""

from __future__ import annotations

from uuid import uuid4

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


def test_a_foreign_kernel_operation_id_is_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    operations = list(schedule.operations)
    operations[0] = operations[0].model_copy(update={"id": uuid4()})
    swapped = schedule.model_copy(update={"operations": operations})
    violations = check_plan(
        problem,
        schedule_problem=swapped,
        assignments=[],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert [row.code for row in violations] == [ReasonCode.INVALID_ID_MAP]
    assert violations[0].message == "compiled kernel ids do not match the id map"


def test_a_foreign_kernel_work_center_id_is_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    centers = list(schedule.work_centers)
    centers[0] = centers[0].model_copy(update={"id": uuid4()})
    swapped = schedule.model_copy(update={"work_centers": centers})
    violations = check_plan(
        problem,
        schedule_problem=swapped,
        assignments=[],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert [row.code for row in violations] == [ReasonCode.INVALID_ID_MAP]
    assert violations[0].message == "compiled kernel ids do not match the id map"


def test_a_foreign_kernel_order_id_is_rejected() -> None:
    _assert_foreign_kernel_id("orders")


def test_a_foreign_kernel_state_id_is_rejected() -> None:
    _assert_foreign_kernel_id("states")


def test_a_foreign_kernel_auxiliary_id_is_rejected() -> None:
    _assert_foreign_kernel_id("auxiliary_resources")


def test_compiled_site_ids_match_the_map() -> None:
    problem = synthesize("repair-site-mvp", seed=42)
    schedule, id_map = to_schedule_problem(problem)
    violations = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert all(row.code != ReasonCode.INVALID_ID_MAP for row in violations)


def _assert_foreign_kernel_id(field: str) -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    rows = list(getattr(schedule, field))
    assert rows
    rows[0] = rows[0].model_copy(update={"id": uuid4()})
    swapped = schedule.model_copy(update={field: rows})
    violations = check_plan(
        problem,
        schedule_problem=swapped,
        assignments=[],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert [row.code for row in violations] == [ReasonCode.INVALID_ID_MAP]
    assert violations[0].message == "compiled kernel ids do not match the id map"
