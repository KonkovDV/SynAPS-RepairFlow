"""CP-SAT above the lab cap is a recorded refusal, not a solve."""

from repairflow.limits import CPSAT_OPS_CAP
from repairflow.model import RepairFlowProblem, Violation
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
    outcome = plan(problem, solver_config="CPSAT-10")
    assert not any(row.code == ReasonCode.CPSAT_OPS_CAP for row in outcome.result.violations)
    assert any(row.code == ReasonCode.KERNEL_CALENDAR_UNSUPPORTED for row in outcome.result.violations)


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
