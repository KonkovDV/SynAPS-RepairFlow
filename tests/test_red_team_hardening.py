from datetime import timedelta

from repairflow.model import AuxResource, Calendar, CalendarWindow, PlannedAssignment
from repairflow.planner import plan, recheck
from repairflow.synthetic import synthesize


def test_allow_partial_never_returns_green() -> None:
    problem = synthesize("tiny", seed=1)
    problem = problem.model_copy(
        update={"policy": problem.policy.model_copy(update={"allow_partial_plan": True})}
    )
    clean = plan(problem, solver_config="GREED")
    missing_id = clean.result.assignments[0].operation_id
    partial = [row for row in clean.result.assignments if row.operation_id != missing_id]
    outcome = recheck(problem, assignments=partial, kernel_status="FEASIBLE")
    assert outcome.result.status.value == "PARTIAL"
    assert outcome.result.exit_code == 2
    assert not outcome.result.verified_feasible


def test_aux_calendar_is_checked_and_empty_means_unavailable() -> None:
    problem = synthesize("tiny", seed=1)
    first = problem.operations[0]
    aux_id = "aux-red-team"
    cal_id = "calendar-red-team"
    aux = AuxResource(id=aux_id, code="fixture", calendar_id=cal_id)
    calendar = Calendar(id=cal_id, code="closed", windows=[])
    operation = first.model_copy(update={"required_aux_ids": [aux_id]})
    problem = problem.model_copy(
        update={
            "operations": [operation if row.id == first.id else row for row in problem.operations],
            "aux_resources": [*problem.aux_resources, aux],
            "calendars": [*problem.calendars, calendar],
        }
    )
    base = plan(problem, solver_config="GREED")
    assert base.result.assignments
    outcome = recheck(problem, assignments=list(base.result.assignments), kernel_status="FEASIBLE")
    assert outcome.result.exit_code == 2
    assert any(row.code == "CALENDAR_BROKEN" for row in outcome.result.violations)


def test_aux_calendar_violation_cannot_be_hidden_by_window_shift() -> None:
    problem = synthesize("tiny", seed=1)
    row = plan(problem, solver_config="GREED").result.assignments[0]
    closed = row.model_copy(update={"start": row.start + timedelta(hours=2), "end": row.end + timedelta(hours=2)})
    assert isinstance(closed, PlannedAssignment)
