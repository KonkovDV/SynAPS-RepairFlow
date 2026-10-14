"""Exact findings for survivors that 1587/1921 left open.

Each assertion is the observable the mutant changes: code, sentence,
identifier, or instant. These tests are not part of that score.
"""

from __future__ import annotations

from datetime import timedelta

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_domain_assignments, check_plan
from repairflow.model import (
    Calendar,
    CalendarWindow,
    FrozenAssignment,
    Operation,
    PlannedAssignment,
    PredecessorLink,
    RepairFlowProblem,
    SpareReceipt,
)
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_a_deadline_uses_the_later_finish() -> None:
    problem = synthesize("tiny", seed=1)
    job = problem.jobs[0]
    ops = [row for row in problem.operations if row.job_id == job.id][:2]
    late = problem.planning_horizon.start + timedelta(hours=10)
    early = problem.planning_horizon.start + timedelta(hours=8)
    deadline = early + timedelta(minutes=30)
    loaded = _jobs(problem, job.id, ops, due=None, deadline=deadline)
    rows = [
        _visit(ops[0], late - timedelta(minutes=20), end=late),
        _visit(ops[1], early - timedelta(minutes=20), end=early),
    ]
    hit = _one(check_domain_assignments(loaded, rows), ReasonCode.DEADLINE_MISSED)
    assert hit.message == f"job {job.id} finishes after deadline"
    assert hit.operation_id == ops[0].id
    assert hit.job_id == job.id
    assert hit.start == rows[0].start
    assert hit.end == late


def test_a_zero_spare_keeps_the_operation_that_needs_it() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    spare = problem.spares[0]
    loaded, edited = _demand(problem, op, spare.id, quantity=0, attributes={})
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(edited, start)
    found = [
        item
        for item in check_domain_assignments(loaded, [row])
        if item.message == f"spare {spare.code} has quantity 0" and item.operation_id == edited.id
    ]
    assert len(found) == 1
    hit = found[0]
    assert hit.code == ReasonCode.SPARE_UNAVAILABLE
    assert hit.job_id == edited.job_id
    assert hit.resource_id == spare.id
    assert hit.start == row.start
    assert hit.end == row.end


def test_a_rotable_with_no_stock_is_not_a_consumable_zero() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    spare = problem.spares[0]
    loaded, edited = _demand(
        problem,
        op,
        spare.id,
        quantity=0,
        attributes={"kind": "rotable"},
    )
    start = problem.planning_horizon.start + timedelta(hours=8)
    messages = [row.message for row in check_domain_assignments(loaded, [_visit(edited, start)])]
    assert f"spare {spare.code} has quantity 0" not in messages


def test_a_spare_before_its_release_keeps_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    spare = problem.spares[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    available = start + timedelta(hours=2)
    loaded, edited = _demand(
        problem,
        op,
        spare.id,
        quantity=1,
        attributes={},
        available_from=available,
    )
    row = _visit(edited, start)
    hit = _one(check_domain_assignments(loaded, [row]), ReasonCode.SPARE_UNAVAILABLE)
    assert hit.message == f"spare {spare.code} is not available until {available.isoformat()}"
    assert hit.operation_id == edited.id
    assert hit.job_id == edited.job_id
    assert hit.resource_id == spare.id
    assert hit.start == row.start
    assert hit.end == row.end


def test_a_missing_predecessor_keeps_its_fields() -> None:
    problem = synthesize("tiny", seed=1)
    first, second = problem.operations[0], problem.operations[1]
    edited = second.model_copy(
        update={
            "predecessor_ids": [first.id],
            "predecessors": [],
            "required_skills": [],
            "required_aux_ids": [],
        }
    )
    loaded = _swap(problem, edited)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(edited, start)
    hit = _one(check_domain_assignments(loaded, [row]), ReasonCode.PRECEDENCE_BROKEN)
    assert hit.message == f"{edited.id} is scheduled but predecessor {first.id} is not"
    assert hit.operation_id == edited.id
    assert hit.job_id == edited.job_id
    assert hit.resource_id == first.id
    assert hit.start == row.start
    assert hit.end == row.end


def test_an_early_successor_keeps_its_fields() -> None:
    problem = synthesize("tiny", seed=1)
    first, second = problem.operations[0], problem.operations[1]
    edited = second.model_copy(
        update={
            "predecessor_ids": [first.id],
            "predecessors": [],
            "required_skills": [],
            "required_aux_ids": [],
        }
    )
    first_clear = first.model_copy(update={"predecessor_ids": [], "predecessors": [], "required_skills": []})
    loaded = _swap(problem, edited, also=first_clear)
    start = problem.planning_horizon.start + timedelta(hours=8)
    pred = _visit(first_clear, start + timedelta(hours=2))
    current = _visit(edited, start)
    hit = _one(check_domain_assignments(loaded, [pred, current]), ReasonCode.PRECEDENCE_BROKEN)
    assert hit.message == f"{edited.id} starts before predecessor {first.id} plus lag 0 min"
    assert hit.operation_id == edited.id
    assert hit.job_id == edited.job_id
    assert hit.resource_id == first.id
    assert hit.start == current.start
    assert hit.end == current.end


def test_a_late_successor_keeps_its_fields() -> None:
    problem = synthesize("tiny", seed=1)
    first, second = problem.operations[0], problem.operations[1]
    link = PredecessorLink(id=first.id, min_lag_min=0, max_lag_min=10)
    edited = second.model_copy(
        update={
            "predecessor_ids": [first.id],
            "predecessors": [link],
            "required_skills": [],
            "required_aux_ids": [],
        }
    )
    first_clear = first.model_copy(update={"predecessor_ids": [], "predecessors": [], "required_skills": []})
    loaded = _swap(problem, edited, also=first_clear)
    start = problem.planning_horizon.start + timedelta(hours=8)
    pred = _visit(first_clear, start)
    current = _visit(edited, start + timedelta(hours=2))
    hit = _one(check_domain_assignments(loaded, [pred, current]), ReasonCode.PRECEDENCE_BROKEN)
    assert hit.message == f"{edited.id} starts after the max lag from predecessor {first.id}"
    assert hit.operation_id == edited.id
    assert hit.job_id == edited.job_id
    assert hit.resource_id == first.id
    assert hit.start == current.start
    assert hit.end == current.end


def test_occupancy_outside_one_window_keeps_its_fields() -> None:
    problem, op, center_id, start = _window(covers=False, preemptive=False, setup=0)
    row = _visit(op, start, work_center_id=center_id)
    hit = _one(check_domain_assignments(problem, [row]), ReasonCode.CALENDAR_BROKEN)
    assert hit.message == "occupancy is not contained in a single calendar window"
    assert hit.operation_id == op.id
    assert hit.resource_id == center_id
    assert hit.start == row.start
    assert hit.end == row.end


def test_setup_outside_one_window_keeps_its_fields() -> None:
    problem, op, center_id, start = _window(covers=False, preemptive=True, setup=30, at_visit=True)
    row = _visit(op, start, work_center_id=center_id, setup_minutes=30)
    hit = _one(check_domain_assignments(problem, [row]), ReasonCode.CALENDAR_BROKEN)
    assert hit.message == "setup is not contained in a single calendar window"
    assert hit.operation_id == op.id
    assert hit.resource_id == center_id
    assert hit.start == start - timedelta(minutes=30)
    assert hit.end == start


def test_a_moved_frozen_visit_keeps_the_placed_interval() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    center_id = op.eligible_work_center_ids[0]
    edited = op.model_copy(update={"required_skills": [], "required_aux_ids": [], "predecessor_ids": []})
    start = problem.planning_horizon.start + timedelta(hours=8)
    frozen_start = start + timedelta(hours=1)
    frozen = FrozenAssignment(
        operation_id=edited.id,
        work_center_id=center_id,
        start=frozen_start,
        end=frozen_start + timedelta(minutes=edited.duration_min),
    )
    loaded = _swap(problem, edited, frozen_assignments=[frozen])
    row = _visit(edited, start, work_center_id=center_id)
    hit = _one(check_domain_assignments(loaded, [row]), ReasonCode.FROZEN_MOVED)
    assert hit.message == f"frozen operation {edited.id} was moved"
    assert hit.operation_id == edited.id
    assert hit.resource_id == center_id
    assert hit.start == row.start
    assert hit.end == row.end


def test_a_post_that_rejects_the_unit_keeps_its_code() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    job = next(row for row in problem.jobs if row.id == op.job_id)
    center = next(row for row in problem.work_centers if row.id == op.eligible_work_center_ids[0])
    unit = "PUMP" if job.unit_type == "OTHER" else (job.unit_type or "PUMP")
    centers = [
        row.model_copy(update={"eligible_unit_types": ["OTHER"]}) if row.id == center.id else row
        for row in problem.work_centers
    ]
    jobs = [row.model_copy(update={"unit_type": unit}) if row.id == job.id else row for row in problem.jobs]
    edited = op.model_copy(update={"required_skills": [], "required_aux_ids": []})
    loaded = _swap(problem, edited, work_centers=centers, jobs=jobs)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(edited, start, work_center_id=center.id)
    expected = f"post {center.code} does not accept unit type {unit}"
    found = [item for item in check_domain_assignments(loaded, [row]) if item.message == expected]
    assert len(found) == 1
    hit = found[0]
    assert hit.code == ReasonCode.ELIGIBLE_CENTER_MISMATCH
    assert hit.operation_id == edited.id
    assert hit.job_id == edited.job_id
    assert hit.resource_id == center.id
    assert hit.start == row.start
    assert hit.end == row.end


def test_an_ineligible_post_keeps_its_code() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    center_id = op.eligible_work_center_ids[0]
    other = next(row.id for row in problem.work_centers if row.id != center_id)
    edited = op.model_copy(
        update={
            "required_skills": [],
            "required_aux_ids": [],
            "eligible_work_center_ids": [center_id],
        }
    )
    loaded = _swap(problem, edited)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(edited, start, work_center_id=other)
    hit = _one(check_domain_assignments(loaded, [row]), ReasonCode.ELIGIBLE_CENTER_MISMATCH)
    assert hit.message == f"operation {edited.id} is not eligible on {other}"
    assert hit.operation_id == edited.id
    assert hit.job_id == edited.job_id
    assert hit.resource_id == other
    assert hit.start == row.start
    assert hit.end == row.end


def test_unknown_operations_sort_by_the_empty_id_first() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start + timedelta(hours=8)
    center = problem.work_centers[0].id
    rows = [
        PlannedAssignment(
            operation_id="OP-A",
            work_center_id=center,
            start=start,
            end=start + timedelta(minutes=10),
        ),
        PlannedAssignment(
            operation_id="",
            work_center_id=center,
            start=start,
            end=start + timedelta(minutes=10),
        ),
    ]
    found = [
        row
        for row in check_domain_assignments(problem, rows)
        if row.message == "assignment references an unknown operation"
    ]
    assert [row.operation_id for row in found] == ["", "OP-A"]


def test_unknown_aux_ids_sort_by_the_empty_id_first() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    edited = op.model_copy(update={"required_aux_ids": [], "required_skills": []})
    loaded = _swap(problem, edited)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(edited, start, aux_ids=["AUX-Z", ""])
    found = [
        item
        for item in check_domain_assignments(loaded, [row])
        if item.message == "assignment references an unknown auxiliary resource"
    ]
    assert [item.resource_id for item in found] == ["", "AUX-Z"]
    assert all(item.code == ReasonCode.UNKNOWN_RESOURCE for item in found)


def test_a_shorter_kernel_problem_keeps_its_sentence() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, id_map = to_schedule_problem(problem)
    shorter = schedule.model_copy(update={"operations": list(schedule.operations)[:-1]})
    found = check_plan(
        problem,
        schedule_problem=shorter,
        assignments=[],
        id_map=id_map,
        kernel_status="feasible",
    )
    hit = _one(found, ReasonCode.INVALID_ID_MAP)
    assert hit.message == "compiled kernel operations do not match the RepairFlow instance"


def test_one_stockout_of_an_operation_is_reported_once() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    start = problem.planning_horizon.start + timedelta(hours=8)
    edited_spare = spare.model_copy(
        update={
            "quantity": 0,
            "receipts": [SpareReceipt(at=start + timedelta(hours=3), qty=1)],
            "domain_attributes": {},
        }
    )
    edited = op.model_copy(
        update={"required_spare_ids": [spare.id], "required_spares": [], "required_skills": []}
    )
    loaded = _swap(
        problem,
        edited,
        spares=[edited_spare if row.id == spare.id else row for row in problem.spares],
    )
    rows = [
        _visit(edited, start),
        _visit(edited, start + timedelta(minutes=5)),
    ]
    shorts = [
        row.message for row in check_domain_assignments(loaded, rows) if "stock is short" in row.message
    ]
    assert len(shorts) == 1


def test_an_invalid_return_lag_keeps_its_details() -> None:
    problem = synthesize("tiny", seed=1)
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    edited = spare.model_copy(
        update={"quantity": 1, "domain_attributes": {"kind": "rotable", "return_lag_min": -1}}
    )
    loaded = _swap(problem, problem.operations[0], spares=_replace_spare(problem, edited))
    hit = _one(check_domain_assignments(loaded, []), ReasonCode.SPARE_UNAVAILABLE)
    assert hit.message == "rotable spare has invalid return_lag_min"
    assert hit.resource_id == spare.id
    assert hit.severity == "hard"
    assert hit.details == {"kind": "rotable", "return_lag_min": -1}


def test_a_rotable_clash_keeps_its_details() -> None:
    problem = synthesize("tiny", seed=1)
    users = [row for row in problem.operations if spare_on(row, "SP-BEARING")][:2]
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    edited = spare.model_copy(
        update={"quantity": 1, "domain_attributes": {"mode": "rotable", "return_lag_min": 0}}
    )
    loaded = _swap(problem, users[0], spares=_replace_spare(problem, edited))
    start = problem.planning_horizon.start + timedelta(hours=8)
    rows = [
        _visit(users[0], start, end=start + timedelta(minutes=20)),
        _visit(users[1], start, end=start + timedelta(minutes=20)),
    ]
    hit = _one(check_domain_assignments(loaded, rows), ReasonCode.SPARE_UNAVAILABLE)
    assert hit.message == f"rotable spare {spare.code} is reused before return"
    assert hit.resource_id == spare.id
    assert hit.details["kind"] == "rotable"
    assert hit.details["quantity"] == 1
    assert hit.details["active"] == 2


def test_a_rotable_used_before_release_keeps_its_details() -> None:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if spare_on(row, "SP-BEARING"))
    spare = next(row for row in problem.spares if row.id == "SP-BEARING")
    start = problem.planning_horizon.start + timedelta(hours=8)
    available = start + timedelta(hours=1)
    edited = spare.model_copy(
        update={
            "quantity": 1,
            "available_from": available,
            "domain_attributes": {"kind": "rotable", "return_lag_min": 0},
        }
    )
    loaded = _swap(problem, op, spares=_replace_spare(problem, edited))
    row = _visit(op, start, end=start + timedelta(minutes=20))
    hit = _one(check_domain_assignments(loaded, [row]), ReasonCode.SPARE_UNAVAILABLE)
    assert hit.message == f"rotable spare {spare.code} is not available at operation start"
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.resource_id == spare.id
    assert hit.start == row.start
    assert hit.end == row.end
    assert hit.details == {"available_from": available.isoformat()}


def test_a_setup_mismatch_keeps_the_matrix_sentence() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    center_id = op.eligible_work_center_ids[0]
    edited = op.model_copy(
        update={"required_skills": [], "required_aux_ids": [], "predecessor_ids": [], "predecessors": []}
    )
    matrix = [
        row.model_copy(update={"duration_min": 15})
        if row.from_state == "idle" and row.to_state == edited.setup_state
        else row
        for row in problem.setup_matrix
    ]
    loaded = _swap(problem, edited, setup_matrix=matrix)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(edited, start, work_center_id=center_id, setup_minutes=0)
    hit = _one(check_domain_assignments(loaded, [row]), ReasonCode.SETUP_MISMATCH)
    assert hit.message == (f"setup 0 min, matrix has 15 for idle->{edited.setup_state} on lane 0")
    assert hit.job_id == edited.job_id
    assert hit.resource_id == center_id
    assert hit.start == row.start
    assert hit.end == row.end
    assert hit.details["to_state"] == edited.setup_state


def test_a_synthetic_post_without_a_calendar_stays_quiet() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    center_id = op.eligible_work_center_ids[0]
    centers = [
        row.model_copy(update={"calendar_id": None}) if row.id == center_id else row
        for row in problem.work_centers
    ]
    edited = op.model_copy(update={"required_skills": [], "required_aux_ids": []})
    loaded = _swap(problem, edited, work_centers=centers)
    start = problem.planning_horizon.start + timedelta(hours=8)
    messages = [row.message for row in check_domain_assignments(loaded, [_visit(edited, start)])]
    assert "calendar is not declared" not in " ".join(messages)


def test_an_unattended_crew_ignores_a_closed_calendar() -> None:
    problem, op, center_id, crew_id, start = _crew_calendar(unattended=True, preemptive=False)
    row = _visit(op, start, work_center_id=center_id, crew_id=crew_id)
    messages = [item.message for item in check_domain_assignments(problem, [row])]
    assert not any(crew_id in message or "no open windows" in message for message in messages)


def test_an_unattended_aux_ignores_a_closed_calendar() -> None:
    problem, op, center_id, aux_id, start = _aux_calendar(unattended=True, preemptive=False)
    row = _visit(op, start, work_center_id=center_id, aux_ids=[aux_id])
    messages = [item.message for item in check_domain_assignments(problem, [row])]
    assert "has no open windows" not in " ".join(messages)


def test_preemptive_crew_setup_does_not_need_the_whole_visit() -> None:
    problem, op, center_id, crew_id, start = _crew_calendar(unattended=False, preemptive=True)
    row = _visit(op, start, work_center_id=center_id, crew_id=crew_id, setup_minutes=0)
    messages = [item.message for item in check_domain_assignments(problem, [row])]
    assert "occupancy is not contained" not in " ".join(messages)


def test_preemptive_aux_setup_does_not_need_the_whole_visit() -> None:
    problem, op, center_id, aux_id, start = _aux_calendar(unattended=False, preemptive=True)
    row = _visit(op, start, work_center_id=center_id, aux_ids=[aux_id])
    messages = [item.message for item in check_domain_assignments(problem, [row])]
    assert "occupancy is not contained" not in " ".join(messages)


def test_an_always_open_crew_and_aux_need_no_calendar() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    center_id = op.eligible_work_center_ids[0]
    crew = problem.crews[0]
    aux = problem.aux_resources[0]
    open_attrs = {"availability": "always_open"}
    centers = [
        row.model_copy(update={"calendar_id": None, "domain_attributes": open_attrs})
        if row.id == center_id
        else row
        for row in problem.work_centers
    ]
    crews = [
        row.model_copy(
            update={"calendar_id": None, "domain_attributes": {**row.domain_attributes, **open_attrs}}
        )
        if row.calendar_id is None or row.id == crew.id
        else row
        for row in problem.crews
    ]
    auxes = [
        row.model_copy(
            update={"calendar_id": None, "domain_attributes": {**row.domain_attributes, **open_attrs}}
        )
        if row.calendar_id is None or row.id == aux.id
        else row
        for row in problem.aux_resources
    ]
    edited = op.model_copy(
        update={"required_skills": [], "required_aux_ids": [aux.id], "predecessor_ids": []}
    )
    loaded = _swap(
        problem,
        edited,
        data_provenance="open_data",
        work_centers=centers,
        crews=crews,
        aux_resources=auxes,
    )
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(edited, start, crew_id=crew.id, aux_ids=[aux.id])
    messages = [item.message for item in check_domain_assignments(loaded, [row])]
    assert "calendar is not declared" not in " ".join(messages)


def _jobs(
    problem: RepairFlowProblem,
    job_id: str,
    ops: list[Operation],
    *,
    due: object,
    deadline: object,
) -> RepairFlowProblem:
    jobs = [
        row.model_copy(update={"due_date": due, "deadline": deadline}) if row.id == job_id else row
        for row in problem.jobs
    ]
    wanted = {row.id for row in ops}
    operations = [
        row.model_copy(update={"predecessor_ids": [], "predecessors": []}) if row.id in wanted else row
        for row in problem.operations
    ]
    return _reload(problem, jobs=jobs, operations=operations)


def _demand(
    problem: RepairFlowProblem,
    op: Operation,
    spare_id: str,
    *,
    quantity: int,
    attributes: dict[str, object],
    available_from: object | None = None,
) -> tuple[RepairFlowProblem, Operation]:
    edited = op.model_copy(
        update={
            "required_spare_ids": [spare_id],
            "required_spares": [],
            "required_skills": [],
            "required_aux_ids": [],
            "predecessor_ids": [],
            "predecessors": [],
        }
    )
    spares = [
        row.model_copy(
            update={
                "quantity": quantity,
                "receipts": [],
                "domain_attributes": attributes,
                "available_from": available_from,
            }
        )
        if row.id == spare_id
        else row
        for row in problem.spares
    ]
    return _swap(problem, edited, spares=spares), edited


def _window(
    *,
    covers: bool,
    preemptive: bool,
    setup: int,
    at_visit: bool = False,
) -> tuple[RepairFlowProblem, Operation, str, object]:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    center_id = op.eligible_work_center_ids[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    if at_visit:
        window_start = start
    elif covers:
        window_start = start - timedelta(minutes=setup)
    else:
        window_start = problem.planning_horizon.start
    calendar = Calendar(
        id="CAL-EDGE",
        code="CAL-EDGE",
        windows=[CalendarWindow(start=window_start, end=window_start + timedelta(hours=4))],
    )
    centers = [
        row.model_copy(update={"calendar_id": "CAL-EDGE", "domain_attributes": {}})
        if row.id == center_id
        else row
        for row in problem.work_centers
    ]
    attrs = {**op.domain_attributes}
    if preemptive:
        attrs["duration_policy"] = "preemptive"
    edited = op.model_copy(
        update={
            "domain_attributes": attrs,
            "required_aux_ids": [],
            "required_skills": [],
            "predecessor_ids": [],
            "predecessors": [],
            "duration_min": 30,
        }
    )
    loaded = _swap(
        problem,
        edited,
        calendars=[*problem.calendars, calendar],
        work_centers=centers,
    )
    return loaded, edited, center_id, start


def _crew_calendar(
    *,
    unattended: bool,
    preemptive: bool,
) -> tuple[RepairFlowProblem, Operation, str, str, object]:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    center_id = op.eligible_work_center_ids[0]
    crew = problem.crews[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    calendar = Calendar(
        id="CAL-CREW",
        code="CAL-CREW",
        windows=[] if unattended else [CalendarWindow(start=start, end=start + timedelta(minutes=30))],
    )
    centers = [
        row.model_copy(update={"domain_attributes": {"attendance": "unattended"}})
        if row.id == center_id
        else row
        for row in problem.work_centers
    ]
    attendance = {"attendance": "unattended"} if unattended else {}
    crews = [
        row.model_copy(update={"calendar_id": "CAL-CREW", "domain_attributes": attendance})
        if row.id == crew.id
        else row
        for row in problem.crews
    ]
    attrs = {"duration_policy": "preemptive"} if preemptive else {}
    edited = op.model_copy(
        update={
            "domain_attributes": {**op.domain_attributes, **attrs},
            "required_skills": [],
            "required_aux_ids": [],
            "predecessor_ids": [],
            "predecessors": [],
            "duration_min": 120,
        }
    )
    loaded = _swap(
        problem,
        edited,
        calendars=[*problem.calendars, calendar],
        work_centers=centers,
        crews=crews,
    )
    return loaded, edited, center_id, crew.id, start


def _aux_calendar(
    *,
    unattended: bool,
    preemptive: bool,
) -> tuple[RepairFlowProblem, Operation, str, str, object]:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    center_id = op.eligible_work_center_ids[0]
    aux = problem.aux_resources[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    calendar = Calendar(
        id="CAL-AUX",
        code="CAL-AUX",
        windows=[] if unattended else [CalendarWindow(start=start, end=start + timedelta(minutes=30))],
    )
    centers = [
        row.model_copy(update={"domain_attributes": {"attendance": "unattended"}})
        if row.id == center_id
        else row
        for row in problem.work_centers
    ]
    attendance = {"attendance": "unattended"} if unattended else {}
    auxes = [
        row.model_copy(update={"calendar_id": "CAL-AUX", "domain_attributes": attendance})
        if row.id == aux.id
        else row
        for row in problem.aux_resources
    ]
    attrs = {"duration_policy": "preemptive"} if preemptive else {}
    edited = op.model_copy(
        update={
            "domain_attributes": {**op.domain_attributes, **attrs},
            "required_skills": [],
            "required_aux_ids": [aux.id],
            "predecessor_ids": [],
            "predecessors": [],
            "duration_min": 120,
        }
    )
    loaded = _swap(
        problem,
        edited,
        calendars=[*problem.calendars, calendar],
        work_centers=centers,
        aux_resources=auxes,
    )
    return loaded, edited, center_id, aux.id, start


def _swap(
    problem: RepairFlowProblem, edited: Operation, also: Operation | None = None, **updates: object
) -> RepairFlowProblem:
    operations = []
    for row in problem.operations:
        if also is not None and row.id == also.id:
            operations.append(also)
        elif row.id == edited.id:
            operations.append(edited)
        else:
            operations.append(row)
    return _reload(problem, operations=operations, **updates)


def _replace_spare(problem: RepairFlowProblem, edited: object) -> list[object]:
    return [edited if row.id == edited.id else row for row in problem.spares]  # type: ignore[attr-defined]


def spare_on(op: Operation, spare_id: str) -> bool:
    return spare_id in op.required_spare_ids or any(row.spare_id == spare_id for row in op.required_spares)


def _visit(op: Operation, start: object, **updates: object) -> PlannedAssignment:
    end = updates.pop("end", start + timedelta(minutes=op.duration_min))  # type: ignore[operator]
    return PlannedAssignment(
        operation_id=op.id,
        work_center_id=str(updates.pop("work_center_id", op.eligible_work_center_ids[0])),
        start=start,  # type: ignore[arg-type]
        end=end,  # type: ignore[arg-type]
        crew_id=updates.pop("crew_id", None),  # type: ignore[arg-type]
        aux_ids=list(updates.pop("aux_ids", [])),  # type: ignore[arg-type]
        setup_minutes=int(updates.pop("setup_minutes", 0)),  # type: ignore[arg-type]
    )


def _reload(problem: RepairFlowProblem, **updates: object) -> RepairFlowProblem:
    return RepairFlowProblem.model_validate(problem.model_copy(update=updates).model_dump(mode="python"))


def _one(found: list[object], code: ReasonCode) -> object:
    rows = [item for item in found if item.code == code]  # type: ignore[attr-defined]
    assert len(rows) == 1, [item.message for item in found]  # type: ignore[attr-defined]
    return rows[0]
