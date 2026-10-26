"""The id map must be injective, not only a matching set of keys."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from synaps.model import OperationMode
from synaps.precedence import PrecedenceEdge

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


def test_a_changed_post_capacity_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.work_centers)
        assert rows
        rows[0] = rows[0].model_copy(update={"max_parallel": rows[0].max_parallel + 1})
        return schedule.model_copy(update={"work_centers": rows})

    _assert_image_mismatch(mutate)


def test_a_changed_pool_size_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.auxiliary_resources)
        assert rows
        rows[0] = rows[0].model_copy(update={"pool_size": rows[0].pool_size + 1})
        return schedule.model_copy(update={"auxiliary_resources": rows})

    _assert_image_mismatch(mutate)


def test_a_dropped_compiled_shift_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.work_centers)
        chosen = next((index for index, row in enumerate(rows) if row.calendar), None)
        assert chosen is not None
        center = rows[chosen]
        rows[chosen] = center.model_copy(update={"calendar": list(center.calendar)[:-1]})
        return schedule.model_copy(update={"work_centers": rows})

    _assert_image_mismatch(mutate)


def test_a_changed_order_priority_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.orders)
        assert rows
        rows[0] = rows[0].model_copy(update={"priority": rows[0].priority + 1})
        return schedule.model_copy(update={"orders": rows})

    _assert_image_mismatch(mutate)


def test_a_post_speed_factor_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.work_centers)
        assert rows
        rows[0] = rows[0].model_copy(update={"speed_factor": 2})
        return schedule.model_copy(update={"work_centers": rows})

    _assert_image_mismatch(mutate)


def test_a_machine_duration_override_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        operation = rows[0]
        assert operation.eligible_wc_ids
        rows[0] = operation.model_copy(
            update={"machine_duration_overrides": {operation.eligible_wc_ids[0]: operation.base_duration_min}}
        )
        return schedule.model_copy(update={"operations": rows})

    _assert_image_mismatch(mutate)


def test_a_setup_energy_term_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.setup_matrix)
        assert rows
        rows[0] = rows[0].model_copy(update={"energy_kwh": 1})
        return schedule.model_copy(update={"setup_matrix": rows})

    _assert_image_mismatch(mutate)


def test_a_changed_state_code_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.states)
        assert rows
        rows[0] = rows[0].model_copy(update={"code": f"{rows[0].code}-other"})
        return schedule.model_copy(update={"states": rows})

    _assert_image_mismatch(mutate)


def test_a_shifted_kernel_horizon_is_rejected() -> None:
    def mutate(schedule):
        return schedule.model_copy(
            update={"planning_horizon_end": schedule.planning_horizon_end + timedelta(minutes=1)}
        )

    _assert_image_mismatch(mutate)


def test_a_reordered_eligible_post_list_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        chosen = next(index for index, row in enumerate(rows) if len(row.eligible_wc_ids) > 1)
        operation = rows[chosen]
        rows[chosen] = operation.model_copy(
            update={"eligible_wc_ids": list(reversed(operation.eligible_wc_ids))}
        )
        return schedule.model_copy(update={"operations": rows})

    _assert_image_mismatch(mutate)


def test_execution_modes_on_a_kernel_operation_are_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        operation = rows[0]
        rows[0] = operation.model_copy(
            update={"modes": [OperationMode(code="fast", duration_min=operation.base_duration_min)]}
        )
        return schedule.model_copy(update={"operations": rows})

    _assert_image_mismatch(mutate)


def test_kernel_precedence_edges_are_rejected() -> None:
    def mutate(schedule):
        source, target = schedule.operations[0], schedule.operations[1]
        edge = PrecedenceEdge(src_op_id=source.id, dst_op_id=target.id, min_lag=5)
        return schedule.model_copy(update={"precedence_edges": [edge]})

    _assert_image_mismatch(mutate)


def test_a_changed_operation_skill_label_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.operations)
        operation = rows[0]
        attrs = dict(operation.domain_attributes)
        attrs["required_skills"] = []
        rows[0] = operation.model_copy(update={"domain_attributes": attrs})
        return schedule.model_copy(update={"operations": rows})

    _assert_image_mismatch(mutate)


def test_a_changed_asset_code_is_rejected() -> None:
    def mutate(schedule):
        rows = list(schedule.orders)
        order = rows[0]
        attrs = dict(order.domain_attributes)
        attrs["asset_code"] = f"{attrs['asset_code']}-other"
        rows[0] = order.model_copy(update={"domain_attributes": attrs})
        return schedule.model_copy(update={"orders": rows})

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
