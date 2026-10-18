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


def test_a_dangling_setup_state_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.setup_matrix)
        assert rows
        rows[0] = rows[0].model_copy(update={"from_state_id": uuid4()})
        return schedule.model_copy(update={"setup_matrix": rows})

    _assert_open_reference(mutate)


def test_a_dangling_predecessor_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        rows[-1] = rows[-1].model_copy(update={"predecessor_op_id": uuid4()})
        return schedule.model_copy(update={"operations": rows})

    _assert_open_reference(mutate)


def test_a_dangling_operation_order_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        rows[0] = rows[0].model_copy(update={"order_id": uuid4()})
        return schedule.model_copy(update={"operations": rows})

    _assert_open_reference(mutate)


def test_an_empty_eligible_post_list_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        rows[0] = rows[0].model_copy(update={"eligible_wc_ids": []})
        return schedule.model_copy(update={"operations": rows})

    _assert_open_reference(mutate)


def test_a_dangling_aux_requirement_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.aux_requirements)
        assert rows
        rows[0] = rows[0].model_copy(update={"aux_resource_id": uuid4()})
        return schedule.model_copy(update={"aux_requirements": rows})

    _assert_open_reference(mutate)


def test_a_changed_kernel_duration_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        rows[0] = rows[0].model_copy(update={"base_duration_min": rows[0].base_duration_min + 1})
        return schedule.model_copy(update={"operations": rows})

    _assert_image_mismatch(mutate)


def test_a_narrowed_eligible_post_list_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        assert len(rows[0].eligible_wc_ids) > 1
        rows[0] = rows[0].model_copy(update={"eligible_wc_ids": list(rows[0].eligible_wc_ids[:-1])})
        return schedule.model_copy(update={"operations": rows})

    _assert_image_mismatch(mutate)


def test_a_changed_setup_minute_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.setup_matrix)
        assert rows
        rows[0] = rows[0].model_copy(update={"setup_minutes": rows[0].setup_minutes + 1})
        return schedule.model_copy(update={"setup_matrix": rows})

    _assert_image_mismatch(mutate)


def test_a_doubled_aux_quantity_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.aux_requirements)
        assert rows
        rows[0] = rows[0].model_copy(update={"quantity_needed": 2})
        return schedule.model_copy(update={"aux_requirements": rows})

    _assert_image_mismatch(mutate)


def test_a_dropped_aux_requirement_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.aux_requirements)
        assert rows
        return schedule.model_copy(update={"aux_requirements": rows[:-1]})

    _assert_image_mismatch(mutate)


def _assert_image_mismatch(mutate) -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    violations = check_plan(
        problem,
        schedule_problem=mutate(schedule),
        assignments=[],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert [row.code for row in violations] == [ReasonCode.INVALID_ID_MAP]
    assert violations[0].message == "compiled kernel image does not match the RepairFlow instance"


def _assert_open_reference(mutate) -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    violations = check_plan(
        problem,
        schedule_problem=mutate(schedule),
        assignments=[],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert [row.code for row in violations] == [ReasonCode.INVALID_ID_MAP]
    assert violations[0].message == "compiled kernel references are not closed over the id map"


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
