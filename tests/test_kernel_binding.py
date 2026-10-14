"""Kernel-binding edges the 1587/1921 score did not kill.

`_normalize_assignments` returns a planned row unchanged, so a
`PlannedAssignment` never executes that loop. These tests pass kernel
`Assignment` rows. They are not part of 1587/1921.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from synaps.model import Assignment

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_domain_assignments, check_plan
from repairflow.model import PlannedAssignment, RepairFlowProblem
from repairflow.planner import recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_a_mapped_kernel_operation_keeps_its_domain_id() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    op_key = next(key for key in id_map if key.startswith("op:"))
    domain_id = op_key.split(":", 1)[1]
    row = _kernel(problem, id_map, operation_key=op_key)
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert any(item.operation_id == domain_id for item in found)


def test_a_work_center_uuid_is_not_rewritten_as_an_operation() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    center_key = next(key for key in id_map if key.startswith("wc:"))
    center_uuid = id_map[center_key]
    domain_center = center_key.split(":", 1)[1]
    row = _kernel(problem, id_map)
    row = row.model_copy(update={"operation_id": center_uuid})
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    unknown = [item for item in found if item.message == "assignment references an unknown operation"]
    assert unknown
    assert all(item.operation_id == str(center_uuid) for item in unknown)
    assert all(item.operation_id != domain_center for item in unknown)


def test_zero_setup_on_the_horizon_start_stays_inside() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    start = problem.planning_horizon.start
    op = problem.operations[0]
    row = _kernel(problem, id_map, start=start, minutes=op.duration_min, setup_minutes=0)
    messages = [
        item.message
        for item in check_plan(
            problem,
            schedule_problem=schedule,
            assignments=[row],
            id_map=id_map,
            kernel_status="feasible",
        )
    ]
    assert not any("outside the planning horizon" in message for message in messages)


def test_setup_minutes_extend_occupancy_into_the_previous_visit() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    start = problem.planning_horizon.start + timedelta(hours=8)
    first = _kernel(problem, id_map, start=start, minutes=30, setup_minutes=0)
    second_key = next(key for key in id_map if key.startswith("op:") and id_map[key] != first.operation_id)
    second = _kernel(
        problem,
        id_map,
        operation_key=second_key,
        start=start + timedelta(minutes=30),
        minutes=30,
        setup_minutes=10,
    )
    center_key = next(key for key in id_map if key.startswith("wc:"))
    domain_center = center_key.split(":", 1)[1]
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[first, second],
        id_map=id_map,
        kernel_status="feasible",
    )
    hit = _one(found, ReasonCode.CENTER_OVERLAP)
    assert hit.resource_id == domain_center
    assert hit.message == f"resource {domain_center} exceeds capacity {hit.details['capacity']}"


def test_the_later_finish_is_the_one_compared_with_the_due_date() -> None:
    problem = synthesize("tiny", seed=1)
    job = problem.jobs[0]
    ops = [row for row in problem.operations if row.job_id == job.id][:2]
    late = problem.planning_horizon.start + timedelta(hours=10)
    early = problem.planning_horizon.start + timedelta(hours=8)
    due = early + timedelta(minutes=30)
    loaded = _job(problem, job.id, ops, due=due, deadline=None)
    rows = [
        _planned(ops[0], late - timedelta(minutes=20), late),
        _planned(ops[1], early - timedelta(minutes=20), early),
    ]
    hit = _one(check_domain_assignments(loaded, rows), ReasonCode.DUE_MISSED)
    assert hit.code == ReasonCode.DUE_MISSED
    assert hit.message == f"job {job.id} finishes after due_date"
    assert hit.operation_id == ops[0].id
    assert hit.job_id == job.id
    assert hit.start == rows[0].start
    assert hit.end == late


def test_an_equal_finish_keeps_the_first_operation() -> None:
    problem = synthesize("tiny", seed=1)
    job = problem.jobs[0]
    ops = [row for row in problem.operations if row.job_id == job.id][:2]
    end = problem.planning_horizon.start + timedelta(hours=10)
    due = end - timedelta(minutes=30)
    loaded = _job(problem, job.id, ops, due=due, deadline=None)
    rows = [
        _planned(ops[0], end - timedelta(minutes=20), end),
        _planned(ops[1], end - timedelta(minutes=20), end),
    ]
    hit = _one(check_domain_assignments(loaded, rows), ReasonCode.DUE_MISSED)
    assert hit.operation_id == ops[0].id


def test_a_work_center_missing_from_the_id_map_is_incomplete() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    trimmed = dict(id_map)
    dropped = next(key for key in trimmed if key.startswith("wc:"))
    del trimmed[dropped]
    messages = [
        item.message
        for item in check_plan(
            problem,
            schedule_problem=schedule,
            assignments=[],
            id_map=trimmed,
            kernel_status="feasible",
        )
    ]
    assert "operation/work-center mapping must be complete and injective" in messages


def test_a_missing_kernel_status_keeps_its_sentence() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[],
        id_map=id_map,
        kernel_status=None,
    )
    hit = _one(found, ReasonCode.KERNEL_STATUS_MISSING)
    assert hit.message == "result has no kernel_status; refusing to treat the plan as verified"


def test_an_inadmissible_kernel_status_keeps_its_sentence() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[],
        id_map=id_map,
        kernel_status="timeout",
    )
    hit = _one(found, ReasonCode.KERNEL_STATUS_NOT_FEASIBLE)
    assert hit.message == "kernel_status 'timeout' is not feasible or optimal"


def test_an_unmapped_operation_keeps_the_uuid_text() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    unknown = uuid4()
    row = _kernel(problem, id_map).model_copy(update={"operation_id": unknown})
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    hit = next(item for item in found if item.message == "assignment references an unknown operation")
    assert hit.operation_id == str(unknown)


def test_an_unmapped_work_center_keeps_the_uuid_text() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    unknown = uuid4()
    row = _kernel(problem, id_map).model_copy(update={"work_center_id": unknown})
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    hit = next(item for item in found if item.message == "assignment references an unknown work center")
    assert hit.code == ReasonCode.UNKNOWN_RESOURCE
    assert hit.resource_id == str(unknown)


def test_an_operation_uuid_is_not_rewritten_as_a_work_center() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    op_key = next(key for key in id_map if key.startswith("op:"))
    row = _kernel(problem, id_map).model_copy(update={"work_center_id": id_map[op_key]})
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    hit = next(item for item in found if item.message == "assignment references an unknown work center")
    assert hit.resource_id == str(id_map[op_key])
    assert hit.resource_id != op_key.split(":", 1)[1]


def test_an_aux_missing_from_the_map_stays_unknown() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    op_key = next(key for key in id_map if key.startswith("op:"))
    unknown = uuid4()
    row = _kernel(problem, id_map, operation_key=op_key, aux=[unknown])
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    hit = _one(found, ReasonCode.UNKNOWN_RESOURCE)
    assert hit.operation_id == op_key.split(":", 1)[1]
    assert hit.resource_id == str(unknown)
    assert hit.details == {"kind": "unknown"}
    assert hit.message == f"assignment aux {unknown} has kind unknown, expected crew or aux"


def test_one_kernel_crew_is_kept_on_the_assignment() -> None:
    problem = synthesize("tiny", seed=1)
    _schedule, id_map = to_schedule_problem(problem)
    op_key = next(key for key in id_map if key.startswith("op:"))
    crew_key = next(key for key in id_map if key.startswith("crew:"))
    row = _kernel(problem, id_map, operation_key=op_key, aux=[id_map[crew_key]])
    outcome = recheck(problem, assignments=[row], kernel_status="feasible", solver_config="recheck")
    assert outcome.result.assignments[0].crew_id == crew_key.split(":", 1)[1]


def test_a_required_kernel_aux_stays_on_the_assignment() -> None:
    problem = synthesize("tiny", seed=1)
    _schedule, id_map = to_schedule_problem(problem)
    op_key = next(key for key in id_map if key.startswith("op:"))
    aux_key = next(key for key in id_map if key.startswith("aux:"))
    domain_op = op_key.split(":", 1)[1]
    domain_aux = aux_key.split(":", 1)[1]
    operations = [
        row.model_copy(update={"required_aux_ids": [domain_aux], "required_skills": []})
        if row.id == domain_op
        else row
        for row in problem.operations
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"operations": operations}).model_dump(mode="python")
    )
    row = _kernel(loaded, id_map, operation_key=op_key, aux=[id_map[aux_key]])
    outcome = recheck(loaded, assignments=[row], kernel_status="feasible", solver_config="recheck")
    assert domain_aux in outcome.result.assignments[0].aux_ids
    assert not any(item.code == ReasonCode.AUX_MISSING for item in outcome.result.violations)


def test_an_unknown_kernel_aux_keeps_its_kind() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    op_key = next(key for key in id_map if key.startswith("op:"))
    state_key = next(key for key in id_map if key.startswith("state:"))
    row = _kernel(problem, id_map, operation_key=op_key, aux=[id_map[state_key]])
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    hit = _one(found, ReasonCode.UNKNOWN_RESOURCE)
    assert hit.operation_id == op_key.split(":", 1)[1]
    assert hit.resource_id == state_key.split(":", 1)[1]
    assert hit.details == {"kind": "state"}
    assert "expected crew or aux" in hit.message


def test_two_kernel_crews_keep_their_ids() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    op_key = next(key for key in id_map if key.startswith("op:"))
    crews = [key for key in id_map if key.startswith("crew:")]
    row = _kernel(
        problem,
        id_map,
        operation_key=op_key,
        aux=[id_map[crews[0]], id_map[crews[1]]],
    )
    found = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    hit = _one(found, ReasonCode.AMBIGUOUS_CREW)
    names = [crews[0].split(":", 1)[1], crews[1].split(":", 1)[1]]
    assert hit.operation_id == op_key.split(":", 1)[1]
    assert hit.message == f"operation {hit.operation_id} lists crews {names}"
    assert hit.details == {"crew_ids": names}


def _kernel(
    problem: RepairFlowProblem,
    id_map: dict[str, object],
    *,
    operation_key: str | None = None,
    start: object | None = None,
    minutes: int = 30,
    setup_minutes: int = 0,
    aux: list[object] | None = None,
) -> Assignment:
    op_key = operation_key or next(key for key in id_map if key.startswith("op:"))
    center_key = next(key for key in id_map if key.startswith("wc:") and op_key)
    moment = start or (problem.planning_horizon.start + timedelta(hours=8))
    return Assignment(
        operation_id=id_map[op_key],  # type: ignore[index, arg-type]
        work_center_id=id_map[center_key],  # type: ignore[index, arg-type]
        start_time=moment,  # type: ignore[arg-type]
        end_time=moment + timedelta(minutes=minutes),  # type: ignore[operator]
        setup_minutes=setup_minutes,
        aux_resource_ids=list(aux or []),  # type: ignore[arg-type]
    )


def _job(
    problem: RepairFlowProblem,
    job_id: str,
    ops: list[object],
    *,
    due: object,
    deadline: object,
) -> RepairFlowProblem:
    jobs = [
        row.model_copy(update={"due_date": due, "deadline": deadline}) if row.id == job_id else row
        for row in problem.jobs
    ]
    edited = [
        row.model_copy(update={"predecessor_ids": [], "predecessors": []}) if row in ops else row
        for row in problem.operations
    ]
    return RepairFlowProblem.model_validate(
        problem.model_copy(update={"jobs": jobs, "operations": edited}).model_dump(mode="python")
    )


def _planned(op: object, start: object, end: object) -> PlannedAssignment:
    center = op.eligible_work_center_ids[0]  # type: ignore[attr-defined]
    return PlannedAssignment(
        operation_id=op.id,  # type: ignore[attr-defined]
        work_center_id=center,
        start=start,  # type: ignore[arg-type]
        end=end,  # type: ignore[arg-type]
    )


def _one(found: list[object], code: ReasonCode) -> object:
    rows = [item for item in found if item.code == code]  # type: ignore[attr-defined]
    assert len(rows) == 1, [item.message for item in found]  # type: ignore[attr-defined]
    return rows[0]
