"""Exchange-pool ledger and inspection replan."""

from datetime import timedelta

from repairflow.events import InspectionEvent
from repairflow.ledger import exchange_pool_violations
from repairflow.model import ExchangePool, PoolDemand, RepairFlowProblem
from repairflow.planner import plan, recheck, replan_after_inspection
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def _with_pool(problem: RepairFlowProblem, *, hard: bool, initial: int, qty: int) -> RepairFlowProblem:
    pool = ExchangePool(
        unit_type=problem.jobs[0].unit_type,
        initial_serviceable=initial,
        demand=[PoolDemand(at=problem.planning_horizon.start, qty=qty)],
        hard=hard,
    )
    return RepairFlowProblem.model_validate(
        problem.model_copy(update={"exchange_pools": [pool]}).model_dump(mode="python")
    )


def test_hard_stockout_rejects_a_feasible_schedule() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    assert greed.result.verified_feasible
    tight = _with_pool(problem, hard=True, initial=0, qty=1)
    outcome = recheck(
        tight,
        assignments=list(greed.result.assignments),
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert any(
        row.code == ReasonCode.EXCHANGE_POOL_STOCKOUT and row.severity == "hard"
        for row in outcome.result.violations
    )
    assert outcome.result.exit_code == 2
    assert outcome.result.claim_status == "rejected"


def test_soft_stockout_stays_verified() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    soft = _with_pool(problem, hard=False, initial=0, qty=1)
    outcome = recheck(
        soft,
        assignments=list(greed.result.assignments),
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert any(
        row.code == ReasonCode.EXCHANGE_POOL_STOCKOUT and row.severity == "kpi"
        for row in outcome.result.violations
    )
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0


def test_demand_covered_by_opening_stock_is_silent() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    covered = _with_pool(problem, hard=True, initial=1, qty=1)
    outcome = recheck(
        covered,
        assignments=list(greed.result.assignments),
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert not any(row.code == ReasonCode.EXCHANGE_POOL_STOCKOUT for row in outcome.result.violations)
    assert outcome.result.verified_feasible


def test_other_unit_does_not_hide_a_later_return() -> None:
    problem = synthesize("tiny", seed=1)
    issued = plan(problem, solver_config="GREED")
    assert issued.result.verified_feasible
    covered = problem.jobs[1]
    jobs = [
        job.model_copy(update={"unit_type": "ZZ-OTHER"}) if job.id == problem.jobs[0].id else job
        for job in problem.jobs
    ]
    ends = [
        row.end
        for row in issued.result.assignments
        if any(op.id == row.operation_id and op.job_id == covered.id for op in problem.operations)
    ]
    demand_at = max(ends) + timedelta(minutes=1)
    pool = ExchangePool(
        unit_type=covered.unit_type,
        initial_serviceable=0,
        demand=[PoolDemand(at=demand_at, qty=1)],
        hard=True,
    )
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"jobs": jobs, "exchange_pools": [pool]}).model_dump(mode="python")
    )
    violations = exchange_pool_violations(loaded, list(issued.result.assignments))
    assert not any(row.code == ReasonCode.EXCHANGE_POOL_STOCKOUT for row in violations)


def test_healthy_pool_does_not_hide_the_next_pool() -> None:
    problem = synthesize("tiny", seed=1)
    moment = problem.planning_horizon.start
    pools = [
        ExchangePool(
            unit_type="ZZ-HEALTHY",
            initial_serviceable=1,
            demand=[PoolDemand(at=moment, qty=1)],
            hard=True,
        ),
        ExchangePool(
            unit_type="ZZ-SHORT",
            initial_serviceable=0,
            demand=[PoolDemand(at=moment, qty=1)],
            hard=True,
        ),
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"exchange_pools": pools}).model_dump(mode="python")
    )
    hits = [
        row for row in exchange_pool_violations(loaded, []) if row.code == ReasonCode.EXCHANGE_POOL_STOCKOUT
    ]
    assert len(hits) == 1
    assert hits[0].resource_id == "ZZ-SHORT"
    assert hits[0].severity == "hard"
    assert hits[0].start == moment
    assert hits[0].details["min_stock"] == -1
    assert hits[0].details["unit_type"] == "ZZ-SHORT"


def test_inspection_freezes_other_units_and_waits_for_the_new_branch() -> None:
    problem = synthesize("tiny", seed=1)
    base = plan(problem, solver_config="GREED")
    assert base.result.verified_feasible
    job_id = problem.jobs[0].id
    chain = sorted(
        (op for op in problem.operations if op.job_id == job_id),
        key=lambda op: op.sequence,
    )
    trunk, branch, sink = chain[0], chain[1], chain[2]
    parallel = branch.model_copy(
        update={
            "id": f"{branch.id}-B",
            "sequence": max(op.sequence for op in chain) + 1,
            "duration_min": 30,
            "predecessor_ids": [trunk.id],
            "eligible_work_center_ids": ["POST-U1"],
            "required_skills": ["electrical"],
            "required_spare_ids": [],
            "required_aux_ids": [],
            "setup_state": "compressor",
        }
    )
    event = InspectionEvent(
        job_id=job_id,
        defect_class="crack_block",
        added_operations=[parallel],
        rewire={sink.id: [branch.id, parallel.id]},
    )
    outcome = replan_after_inspection(problem, base=base.result, event=event)
    nervous = outcome.result.metadata["nervousness"]
    assert nervous["frozen_violations"] == 0
    assert parallel.id in nervous["added"]
    by_id = {row.operation_id: row for row in outcome.result.assignments}
    assert by_id[sink.id].start >= by_id[branch.id].end
    assert by_id[sink.id].start >= by_id[parallel.id].end
    base_map = {row.operation_id: row for row in base.result.assignments}
    for operation in problem.operations:
        assert by_id[operation.id].start == base_map[operation.id].start
        assert by_id[operation.id].work_center_id == base_map[operation.id].work_center_id
    assert outcome.result.exit_code == 0
    assert outcome.result.claim_status == "verified"
    assert nervous["ratio"] == 0
    assert not any(row.code == ReasonCode.NERVOUSNESS_HIGH for row in outcome.result.violations)
