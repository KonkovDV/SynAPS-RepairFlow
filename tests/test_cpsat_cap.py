"""CP-SAT above the lab cap is a recorded refusal, not a solve."""

from datetime import timedelta

from repairflow.limits import CPSAT_OPS_CAP
from repairflow.model import Calendar, RepairFlowProblem, Violation
from repairflow.planner import PlanOutcome, plan, replan_after_disruption
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def _sized(count: int) -> RepairFlowProblem:
    base = synthesize("tiny", seed=1)
    template = base.operations[0]
    jobs = []
    operations = []
    for index in range(count):
        job_id = f"JOB-{index:03d}"
        jobs.append(
            base.jobs[0].model_copy(
                update={
                    "id": job_id,
                    "external_ref": job_id,
                    "asset_code": f"A-{index:03d}",
                }
            )
        )
        operations.append(
            template.model_copy(
                update={"id": f"{job_id}-01", "job_id": job_id, "predecessor_ids": [], "sequence": 1}
            )
        )
    return RepairFlowProblem.model_validate(
        base.model_copy(
            update={"instance_id": f"cap-{count}", "jobs": jobs, "operations": operations}
        ).model_dump(mode="python")
    )


def _cap_row(outcome: PlanOutcome) -> Violation:
    return next(row for row in outcome.result.violations if row.code == ReasonCode.CPSAT_OPS_CAP)


def test_cpsat_above_cap_is_a_recorded_refusal() -> None:
    problem = _sized(CPSAT_OPS_CAP + 1)
    outcome = plan(problem, solver_config="CPSAT-10")
    row = _cap_row(outcome)
    kernel = outcome.result.metadata["solver"]["kernel"]
    assert outcome.result.assignments == []
    assert outcome.result.verified_feasible is False
    assert outcome.result.exit_code == 2
    assert outcome.result.claim_status == "error"
    assert outcome.result.status.value == "ERROR"
    assert row.details["routing"] == "refused"
    assert row.details["cpsat_invoked"] is False
    assert row.details["operation_count"] == CPSAT_OPS_CAP + 1
    assert row.details["cpsat_ops_cap"] == CPSAT_OPS_CAP
    assert kernel["routing"] == "refused"
    assert kernel["cpsat_invoked"] is False


def test_cpsat_at_cap_is_not_routed_to_the_size_refusal() -> None:
    problem = _sized(CPSAT_OPS_CAP)
    empty = Calendar(id="CAL-OFF", code="CAL-OFF", windows=[])
    loaded = problem.model_copy(
        update={
            "calendars": [*problem.calendars, empty],
            "crews": [row.model_copy(update={"calendar_id": "CAL-OFF"}) for row in problem.crews],
        }
    )
    outcome = plan(loaded, solver_config="CPSAT-10")
    assert outcome.result.assignments == []
    assert not any(row.code == ReasonCode.CPSAT_OPS_CAP for row in outcome.result.violations)
    assert any(row.code == ReasonCode.KERNEL_CALENDAR_UNSUPPORTED for row in outcome.result.violations)


def _with_room_for(problem: RepairFlowProblem, count: int) -> RepairFlowProblem:
    """Give the one-skill card enough open shifts to hold ``count`` visits."""

    days = max(4, (count * 30) // (16 * 60) + 2)
    start = problem.planning_horizon.start
    end = start + timedelta(days=days)
    horizon = problem.planning_horizon.model_copy(update={"end": end})
    calendars = []
    for calendar in problem.calendars:
        windows = []
        for day in range(days):
            day0 = start + timedelta(days=day)
            windows.append(
                calendar.windows[0].model_copy(
                    update={"start": day0 + timedelta(hours=6), "end": day0 + timedelta(hours=22)}
                )
            )
        calendars.append(calendar.model_copy(update={"windows": windows}))
    jobs = [job.model_copy(update={"due_date": end}) for job in problem.jobs]
    return problem.model_copy(
        update={"planning_horizon": horizon, "calendars": calendars, "jobs": jobs}
    )


def test_cpsat_checks_the_cap_on_a_card_that_fits_its_shifts() -> None:
    problem = _with_room_for(_sized(CPSAT_OPS_CAP), CPSAT_OPS_CAP)
    outcome = plan(problem, solver_config="CPSAT-30")
    assert not any(row.code == ReasonCode.CPSAT_OPS_CAP for row in outcome.result.violations)
    assert not any(
        row.code == ReasonCode.KERNEL_CALENDAR_UNSUPPORTED for row in outcome.result.violations
    )
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0
    assert outcome.result.claim_status in {"verified", "optimal"}
    assert len(outcome.result.assignments) == CPSAT_OPS_CAP


def test_domain_greed_is_not_subject_to_the_cpsat_cap() -> None:
    problem = _sized(CPSAT_OPS_CAP + 1)
    outcome = plan(problem, solver_config="GREED")
    assert not any(row.code == ReasonCode.CPSAT_OPS_CAP for row in outcome.result.violations)


def test_cpsat_repair_above_cap_does_not_call_the_solver() -> None:
    problem = _sized(CPSAT_OPS_CAP + 1)
    base = plan(problem, solver_config="GREED")
    outcome = replan_after_disruption(
        problem,
        base=base,
        disrupted_operation_ids=[problem.operations[0].id],
        solver_config="CPSAT-10",
    )
    row = _cap_row(outcome)
    assert outcome.result.assignments == []
    assert outcome.result.verified_feasible is False
    assert outcome.result.exit_code == 2
    assert row.details["cpsat_invoked"] is False
    assert outcome.result.metadata["solver"]["kernel"]["routing"] == "refused"
