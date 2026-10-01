"""Fail-closed compatibility tests for the pinned SynAPS kernel."""

from __future__ import annotations

import pytest

from repairflow.kernel_compat import (
    KERNEL_CALENDAR_UNSUPPORTED,
    assert_kernel_calendar_compatibility,
    unsupported_auxiliary_calendars,
)
from repairflow.model import RepairFlowProblem
from repairflow.planner import plan, replan_after_disruption
from repairflow.synthetic import synthesize


def _kernel_compatible_problem() -> RepairFlowProblem:
    problem = synthesize("tiny", seed=1)
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


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


def test_kernel_modes_refuse_synthetic_crew_calendars() -> None:
    problem = synthesize("tiny", seed=1)
    for solver_config in ("CPSAT-10", "RHC-GREEDY-COVER"):
        outcome = plan(problem, solver_config=solver_config)
        assert outcome.result.exit_code == 2
        assert outcome.result.verified_feasible is False
        assert outcome.result.claim_status != "optimal"
        assert outcome.result.assignments == []
        assert any(row.code == KERNEL_CALENDAR_UNSUPPORTED for row in outcome.result.violations)


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


def test_kernel_disruption_repair_refuses_before_repair_schedule() -> None:
    problem = synthesize("tiny", seed=1)
    base = plan(problem, solver_config="GREED")
    repaired = replan_after_disruption(
        problem,
        base=base,
        disrupted_operation_ids=[problem.operations[0].id],
        solver_config="CPSAT-10",
    )
    assert repaired.result.exit_code == 2
    assert repaired.result.verified_feasible is False
    assert repaired.result.assignments == []
    assert any(row.code == KERNEL_CALENDAR_UNSUPPORTED for row in repaired.result.violations)
    kept = plan(problem, solver_config="GREED")
    assert [(row.operation_id, row.start, row.end) for row in kept.result.assignments] == [
        (row.operation_id, row.start, row.end) for row in base.result.assignments
    ]
