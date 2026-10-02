"""Fail-closed compatibility tests for the pinned SynAPS kernel."""

from __future__ import annotations

from datetime import timedelta

import pytest

from repairflow.adapter import to_schedule_problem
from repairflow.kernel_compat import (
    KERNEL_CALENDAR_UNSUPPORTED,
    assert_kernel_calendar_compatibility,
    unsupported_auxiliary_calendars,
)
from repairflow.model import Calendar, CalendarWindow, RepairFlowProblem
from repairflow.planner import plan, replan_after_disruption
from repairflow.synthetic import synthesize


def _kernel_compatible_problem() -> RepairFlowProblem:
    problem = synthesize("tiny", seed=1)
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def test_plain_synthetic_problem_is_kernel_calendar_compatible() -> None:
    problem = synthesize("tiny", seed=1)
    assert unsupported_auxiliary_calendars(problem) == []
    assert_kernel_calendar_compatibility(problem)


def test_published_crew_calendar_is_compiled_onto_the_kernel_resource() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, _id_map = to_schedule_problem(problem)
    crews = [row for row in schedule.auxiliary_resources if row.resource_type == "crew"]
    assert crews
    assert all(row.calendar for row in crews)


def test_empty_auxiliary_calendar_is_rejected_with_stable_reason() -> None:
    problem = _kernel_compatible_problem()
    empty = Calendar(id="CAL-OFF", code="CAL-OFF", windows=[])
    aux = problem.aux_resources[0].model_copy(update={"calendar_id": "CAL-OFF"})
    loaded = problem.model_copy(
        update={
            "aux_resources": [aux, *problem.aux_resources[1:]],
            "calendars": [*problem.calendars, empty],
        }
    )
    assert unsupported_auxiliary_calendars(loaded) == [f"aux:{aux.id}:CAL-OFF"]
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        assert_kernel_calendar_compatibility(loaded)


def test_empty_crew_calendar_is_rejected_with_stable_reason() -> None:
    problem = _kernel_compatible_problem()
    empty = Calendar(id="CAL-OFF", code="CAL-OFF", windows=[])
    crew = problem.crews[0].model_copy(update={"calendar_id": "CAL-OFF"})
    loaded = problem.model_copy(
        update={
            "crews": [crew, *problem.crews[1:]],
            "calendars": [*problem.calendars, empty],
        }
    )
    assert unsupported_auxiliary_calendars(loaded) == [f"crew:{crew.id}:CAL-OFF"]
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        assert_kernel_calendar_compatibility(loaded)


def test_unattended_crew_is_compiled_as_open() -> None:
    problem = synthesize("tiny", seed=1)
    crews = [
        row.model_copy(update={"domain_attributes": {"attendance": "unattended"}})
        if row.id == "CREW-MECH"
        else row
        for row in problem.crews
    ]
    loaded = problem.model_copy(update={"crews": crews})
    assert unsupported_auxiliary_calendars(loaded) == []
    schedule, id_map = to_schedule_problem(loaded)
    crew = next(row for row in schedule.auxiliary_resources if row.id == id_map["crew:CREW-MECH"])
    assert crew.calendar == []


def test_shared_skill_pool_calendar_is_compiled() -> None:
    problem = synthesize("tiny", seed=1)
    extra = next(row for row in problem.crews if row.id == "CREW-MECH").model_copy(
        update={"id": "CREW-MECH-2", "code": "CREW-MECH-2"}
    )
    loaded = problem.model_copy(update={"crews": [*problem.crews, extra]})
    assert unsupported_auxiliary_calendars(loaded) == []
    schedule, _id_map = to_schedule_problem(loaded)
    pool = next(
        row
        for row in schedule.auxiliary_resources
        if row.resource_type == "crew-pool" and "mechanical" in row.code
    )
    assert pool.calendar


def test_mixed_skill_pool_calendars_are_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    day = next(row for row in problem.calendars if row.id == "CAL-DAY")
    short = Calendar(
        id="CAL-SHORT",
        code="CAL-SHORT",
        windows=[
            CalendarWindow(start=window.start, end=window.start + timedelta(hours=4))
            for window in day.windows
        ],
    )
    extra = problem.crews[0].model_copy(
        update={
            "id": "CREW-MECH-2",
            "code": "CREW-MECH-2",
            "skills": ["mechanical"],
            "calendar_id": "CAL-SHORT",
        }
    )
    loaded = problem.model_copy(
        update={"crews": [*problem.crews, extra], "calendars": [*problem.calendars, short]}
    )
    unsupported = unsupported_auxiliary_calendars(loaded)
    assert "skillpool:mechanical:mixed" in unsupported
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        assert_kernel_calendar_compatibility(loaded)


def test_preemptive_published_calendar_is_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    operations = [
        problem.operations[0].model_copy(update={"domain_attributes": {"duration_policy": "preemptive"}}),
        *problem.operations[1:],
    ]
    loaded = problem.model_copy(update={"operations": operations})
    unsupported = unsupported_auxiliary_calendars(loaded)
    assert unsupported == [f"op:{problem.operations[0].id}:preemptive"]
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        assert_kernel_calendar_compatibility(loaded)


def test_kernel_modes_schedule_synthetic_crew_calendars() -> None:
    problem = synthesize("tiny", seed=1)
    for solver_config in ("CPSAT-10", "RHC-GREEDY-COVER"):
        outcome = plan(problem, solver_config=solver_config)
        assert not any(row.code == KERNEL_CALENDAR_UNSUPPORTED for row in outcome.result.violations)
        assert outcome.result.assignments
        assert outcome.result.verified_feasible
        assert outcome.result.exit_code == 0
        assert outcome.result.claim_status in {"verified", "optimal"}


def test_domain_greed_keeps_synthetic_crew_calendars() -> None:
    outcome = plan(synthesize("tiny", seed=1), solver_config="GREED")
    assert outcome.result.exit_code == 0
    assert outcome.result.verified_feasible
    assert outcome.result.claim_status == "verified"


def test_kernel_solve_still_runs_when_auxiliary_calendars_are_absent() -> None:
    outcome = plan(_kernel_compatible_problem(), solver_config="CPSAT-10")
    assert outcome.result.status.value == "OPTIMAL"
    assert outcome.result.claim_status == "optimal"
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0


def test_kernel_disruption_repair_keeps_crew_calendars() -> None:
    problem = synthesize("tiny", seed=1)
    base = plan(problem, solver_config="GREED")
    repaired = replan_after_disruption(
        problem,
        base=base,
        disrupted_operation_ids=[problem.operations[0].id],
        solver_config="CPSAT-10",
    )
    assert not any(row.code == KERNEL_CALENDAR_UNSUPPORTED for row in repaired.result.violations)
    assert repaired.result.assignments
    assert repaired.result.verified_feasible
    assert repaired.result.exit_code == 0
    kept = plan(problem, solver_config="GREED")
    assert [(row.operation_id, row.start, row.end) for row in kept.result.assignments] == [
        (row.operation_id, row.start, row.end) for row in base.result.assignments
    ]
