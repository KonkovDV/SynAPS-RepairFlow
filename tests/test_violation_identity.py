"""A violation keeps the visit, the ids, and the sentence that named it.

`suggested_relaxation=None` is not asserted. `_violation` fills a missing
suggestion from the same table the call site passes, so that edit is equivalent.
These tests are not part of mutation score 1227/1921.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from repairflow.checker import check_domain_assignments
from repairflow.model import FrozenAssignment, Operation, PlannedAssignment, RepairFlowProblem, Violation
from repairflow.planner import plan
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_unknown_operation_keeps_its_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, operation_id="OP-MISSING")
    hit = _one(
        check_domain_assignments(problem, [row]),
        "assignment references an unknown operation",
    )
    assert hit.code == ReasonCode.UNKNOWN_OPERATION
    assert hit.operation_id == "OP-MISSING"
    assert hit.job_id is None
    assert hit.resource_id is None
    assert hit.start == start
    assert hit.end == row.end


def test_duplicate_assignment_keeps_the_job_and_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start)
    hit = _one(
        check_domain_assignments(problem, [row, row]),
        "operation scheduled more than once",
    )
    assert hit.code == ReasonCode.DUPLICATE_ASSIGNMENT
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.start == start
    assert hit.end == row.end


def test_unknown_work_center_keeps_the_post_id() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, work_center_id="POST-NOPE")
    hit = _one(
        check_domain_assignments(problem, [row]),
        "assignment references an unknown work center",
    )
    assert hit.code == ReasonCode.UNKNOWN_RESOURCE
    assert hit.operation_id == op.id
    assert hit.resource_id == "POST-NOPE"
    assert hit.start == start
    assert hit.end == row.end


def test_unknown_crew_keeps_the_crew_id() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, crew_id="CREW-NOPE")
    hit = _one(
        check_domain_assignments(problem, [row]),
        "assignment references an unknown crew",
    )
    assert hit.operation_id == op.id
    assert hit.resource_id == "CREW-NOPE"
    assert hit.start == start
    assert hit.end == row.end


def test_unknown_aux_keeps_the_aux_id() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, aux_ids=["AUX-NOPE"])
    hit = _one(
        check_domain_assignments(problem, [row]),
        "assignment references an unknown auxiliary resource",
    )
    assert hit.operation_id == op.id
    assert hit.resource_id == "AUX-NOPE"
    assert hit.start == start
    assert hit.end == row.end


def test_zero_length_visit_keeps_the_job() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, end=start)
    hit = _one(
        check_domain_assignments(problem, [row]),
        "assignment end must be after start",
    )
    assert hit.code == ReasonCode.INVALID_DURATION
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.start == start
    assert hit.end == start


def test_ineligible_post_keeps_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if row.eligible_work_center_ids == ["POST-TEST"])
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, work_center_id="POST-U1")
    hit = _one(
        check_domain_assignments(problem, [row]),
        f"operation {op.id} is not eligible on POST-U1",
    )
    assert hit.code == ReasonCode.ELIGIBLE_CENTER_MISMATCH
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.resource_id == "POST-U1"
    assert hit.start == start
    assert hit.end == row.end


def test_rejected_unit_type_keeps_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    post = op.eligible_work_center_ids[0]
    job = next(row for row in problem.jobs if row.id == op.job_id)
    centers = [
        center.model_copy(update={"eligible_unit_types": ["not-a-unit"]}) if center.id == post else center
        for center in problem.work_centers
    ]
    loaded = _reload(problem, work_centers=centers)
    start = loaded.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start)
    hit = _one(
        check_domain_assignments(loaded, [row]),
        f"post {post} does not accept unit type {job.unit_type}",
    )
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.resource_id == post
    assert hit.start == start
    assert hit.end == row.end


def test_missing_crew_keeps_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if row.required_skills)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start)
    hit = _one(
        check_domain_assignments(problem, [row]),
        f"operation {op.id} requires skills {op.required_skills} but has no crew",
    )
    assert hit.code == ReasonCode.CREW_UNBOUND
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.resource_id is None
    assert hit.start == start
    assert hit.end == row.end


def test_wrong_skill_keeps_the_crew() -> None:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if row.required_skills)
    skill = op.required_skills[0]
    crew = next(row for row in problem.crews if skill not in row.skills)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, crew_id=crew.id)
    hit = _one(
        check_domain_assignments(problem, [row]),
        (
            f"operation {op.id} needs {sorted(op.required_skills)} "
            f"but crew {crew.code} has {sorted(crew.skills)}"
        ),
    )
    assert hit.code == ReasonCode.SKILL_MISMATCH
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.resource_id == crew.id
    assert hit.start == start
    assert hit.end == row.end


def test_expired_skill_keeps_the_permit() -> None:
    problem = synthesize("tiny", seed=1)
    op = next(row for row in problem.operations if row.required_skills)
    skill = op.required_skills[0]
    crew = next(row for row in problem.crews if skill in row.skills)
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, crew_id=crew.id)
    until = start
    crews = [
        item.model_copy(update={"skill_valid_until": {skill: until}}) if item.id == crew.id else item
        for item in problem.crews
    ]
    loaded = _reload(problem, crews=crews)
    hit = _one(
        check_domain_assignments(loaded, [row]),
        f"crew {crew.code} skill {skill} expires {until.isoformat()}",
    )
    assert hit.code == ReasonCode.SKILL_EXPIRED
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.resource_id == crew.id
    assert hit.start == start
    assert hit.end == row.end
    assert hit.details == {"skill": skill}


def test_missing_aux_keeps_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0].model_copy(update={"required_aux_ids": ["AUX-CRANE"]})
    operations = [op if item.id == op.id else item for item in problem.operations]
    loaded = _reload(problem, operations=operations)
    start = loaded.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start)
    missing = ["AUX-CRANE"]
    hit = _one(
        check_domain_assignments(loaded, [row]),
        f"operation {op.id} is missing required aux {missing}",
    )
    assert hit.code == ReasonCode.AUX_MISSING
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.start == start
    assert hit.end == row.end


def test_uncovered_operation_keeps_its_job() -> None:
    problem = synthesize("tiny", seed=1)
    covered = problem.operations[0]
    missing = problem.operations[1]
    start = problem.planning_horizon.start + timedelta(hours=8)
    hit = _one(
        check_domain_assignments(problem, [_visit(covered, start)]),
        f"operation {missing.id} has no assignment",
    )
    assert hit.code == ReasonCode.PARTIAL_COVERAGE
    assert hit.operation_id == missing.id
    assert hit.job_id == missing.job_id


def test_visit_past_the_horizon_keeps_its_end() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.end - timedelta(minutes=op.duration_min - 1)
    row = _visit(op, start)
    hit = _one(
        check_domain_assignments(problem, [row]),
        "assignment occupancy is outside the planning horizon",
    )
    assert hit.code == ReasonCode.HORIZON_VIOLATION
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.start == start
    assert hit.end == row.end


def test_latest_finish_keeps_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    latest = start + timedelta(minutes=1)
    operations = [
        item.model_copy(update={"latest_finish": latest}) if item.id == op.id else item
        for item in problem.operations
    ]
    loaded = _reload(problem, operations=operations)
    row = _visit(op, start)
    hit = _one(
        check_domain_assignments(loaded, [row]),
        "operation finishes after latest_finish",
    )
    assert hit.code == ReasonCode.WINDOW_BROKEN
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.start == start
    assert hit.end == row.end


def test_earliest_start_keeps_the_visit() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    earliest = start + timedelta(hours=1)
    operations = [
        item.model_copy(update={"earliest_start": earliest}) if item.id == op.id else item
        for item in problem.operations
    ]
    loaded = _reload(problem, operations=operations)
    row = _visit(op, start)
    hit = _one(
        check_domain_assignments(loaded, [row]),
        "operation starts before earliest_start",
    )
    assert hit.code == ReasonCode.WINDOW_BROKEN
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.start == start
    assert hit.end == row.end


def test_short_exact_visit_keeps_the_held_minutes() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    row = _visit(op, start, end=start + timedelta(minutes=1))
    held = 1
    hit = _one(
        check_domain_assignments(problem, [row]),
        f"scheduled {held} min is not duration_min={op.duration_min}",
    )
    assert hit.code == ReasonCode.INVALID_DURATION
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.start == start
    assert hit.end == row.end
    assert hit.details["held_min"] == held
    assert hit.details["duration_policy"] == "exact"


def test_missing_frozen_row_keeps_the_promised_slot() -> None:
    problem = synthesize("tiny", seed=1)
    issued = plan(problem, solver_config="GREED")
    assert issued.result.verified_feasible
    frozen_row = issued.result.assignments[0]
    frozen = FrozenAssignment(
        operation_id=frozen_row.operation_id,
        work_center_id=frozen_row.work_center_id,
        crew_id=frozen_row.crew_id,
        start=frozen_row.start,
        end=frozen_row.end,
        setup_minutes=frozen_row.setup_minutes,
        immutable=True,
    )
    loaded = _reload(problem, frozen_assignments=[frozen])
    others = [row for row in issued.result.assignments if row.operation_id != frozen.operation_id]
    hit = _one(
        check_domain_assignments(loaded, others),
        f"frozen operation {frozen.operation_id} is missing from the plan",
    )
    assert hit.code == ReasonCode.FROZEN_MOVED
    assert hit.operation_id == frozen.operation_id
    assert hit.resource_id == frozen.work_center_id
    assert hit.start == frozen.start
    assert hit.end == frozen.end


def test_lag_break_keeps_the_successor_visit() -> None:
    problem = synthesize("tiny", seed=1)
    successor = next(op for op in problem.operations if op.predecessor_ids)
    pred_id = successor.predecessor_ids[0]
    pred = next(op for op in problem.operations if op.id == pred_id)
    start = problem.planning_horizon.start + timedelta(hours=8)
    successor_row = _visit(successor, start)
    pred_row = _visit(pred, start + timedelta(hours=2))
    hit = _one(
        check_domain_assignments(problem, [successor_row, pred_row]),
        f"{successor.id} starts before predecessor {pred_id} plus lag 0 min",
    )
    assert hit.code == ReasonCode.PRECEDENCE_BROKEN
    assert hit.operation_id == successor.id
    assert hit.job_id == successor.job_id
    assert hit.resource_id == pred_id
    assert hit.start == start
    assert hit.end == successor_row.end
    assert hit.details["min_lag_min"] == 0
    assert hit.details["predecessor_end"] == pred_row.end.isoformat()


def _visit(op: Operation, start: datetime, **updates: object) -> PlannedAssignment:
    end = updates.pop("end", start + timedelta(minutes=op.duration_min))
    operation_id = updates.pop("operation_id", op.id)
    work_center_id = updates.pop("work_center_id", op.eligible_work_center_ids[0])
    crew_id = updates.pop("crew_id", None)
    aux_ids = updates.pop("aux_ids", [])
    return PlannedAssignment(
        operation_id=operation_id,
        work_center_id=work_center_id,
        start=start,
        end=end,
        crew_id=crew_id,
        aux_ids=aux_ids,
    )


def _reload(problem: RepairFlowProblem, **updates: object) -> RepairFlowProblem:
    return RepairFlowProblem.model_validate(problem.model_copy(update=updates).model_dump(mode="python"))


def _one(violations: list[Violation], message: str) -> Violation:
    found = [row for row in violations if row.message == message]
    assert len(found) == 1, [row.message for row in violations]
    return found[0]
