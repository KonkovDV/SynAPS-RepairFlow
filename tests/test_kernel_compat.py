"""Fail-closed compatibility tests for the pinned SynAPS kernel."""

from __future__ import annotations

import pytest

from repairflow.adapter import to_schedule_problem
from repairflow.kernel_compat import (
    KERNEL_CALENDAR_UNSUPPORTED,
    assert_kernel_calendar_compatibility,
    unsupported_auxiliary_calendars,
)
from repairflow.model import Calendar, CalendarWindow, RepairFlowProblem
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def _kernel_compatible_problem() -> RepairFlowProblem:
    problem = synthesize("tiny", seed=1)
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def _auxiliary_calendar_problem() -> RepairFlowProblem:
    problem = _kernel_compatible_problem()
    calendar = Calendar(
        id="CAL-AUX-FULL",
        code="CAL-AUX-FULL",
        windows=[
            CalendarWindow(
                start=problem.planning_horizon.start,
                end=problem.planning_horizon.end,
            )
        ],
    )
    aux = problem.aux_resources[0].model_copy(update={"calendar_id": calendar.id})
    return problem.model_copy(
        update={
            "calendars": [*problem.calendars, calendar],
            "aux_resources": [aux, *problem.aux_resources[1:]],
        }
    )


def test_plain_synthetic_problem_is_kernel_calendar_compatible() -> None:
    problem = _kernel_compatible_problem()
    assert unsupported_auxiliary_calendars(problem) == []
    assert_kernel_calendar_compatibility(problem)


def test_auxiliary_calendar_is_rejected_with_stable_reason() -> None:
    problem = _kernel_compatible_problem()
    aux = problem.aux_resources[0].model_copy(update={"calendar_id": "CAL-DAY"})
    loaded = problem.model_copy(update={"aux_resources": [aux, *problem.aux_resources[1:]]})
    assert unsupported_auxiliary_calendars(loaded) == [f"aux:{aux.id}:CAL-DAY"]
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        assert_kernel_calendar_compatibility(loaded)


def test_crew_calendar_is_rejected_with_stable_reason() -> None:
    problem = _kernel_compatible_problem()
    crew = problem.crews[0].model_copy(update={"calendar_id": "CAL-DAY"})
    loaded = problem.model_copy(update={"crews": [crew, *problem.crews[1:]]})
    assert unsupported_auxiliary_calendars(loaded) == [f"crew:{crew.id}:CAL-DAY"]
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        assert_kernel_calendar_compatibility(loaded)


def test_adapter_rejects_kernel_inexpressible_calendar_before_compilation() -> None:
    problem = _auxiliary_calendar_problem()
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        to_schedule_problem(problem)


def test_kernel_planning_fails_closed_but_domain_greed_remains_available() -> None:
    problem = _auxiliary_calendar_problem()
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        plan(problem, solver_config="CPSAT-10")

    greed = plan(problem, solver_config="GREED")
    assert greed.result.exit_code == 0
    assert greed.result.verified_feasible is True
