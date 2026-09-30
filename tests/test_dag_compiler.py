"""DAG compilation: chains for the kernel, original edges for the notary."""

from datetime import timedelta

from repairflow.dag_compiler import compile_dag, propagate_windows
from repairflow.model import RepairFlowProblem
from repairflow.planner import plan, recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def _diamond(seed: int = 1) -> RepairFlowProblem:
    problem = synthesize("tiny", seed=seed)
    ops = list(problem.operations)
    job_id = ops[0].job_id
    chain = sorted((op for op in ops if op.job_id == job_id), key=lambda op: op.sequence)
    trunk, branch, sink = chain[0], chain[1], chain[2]
    parallel = branch.model_copy(
        update={
            "id": f"{branch.id}-B",
            "sequence": branch.sequence + 1,
            "predecessor_ids": [trunk.id],
            "required_spare_ids": [],
            "required_aux_ids": [],
        }
    )
    joined = sink.model_copy(
        update={
            "sequence": sink.sequence + 1,
            "predecessor_ids": [branch.id, parallel.id],
        }
    )
    payload = problem.model_dump(mode="python")
    payload["operations"] = [joined if row.id == sink.id else row for row in ops] + [parallel]
    return RepairFlowProblem.model_validate(payload)


def test_linear_job_is_one_segment_without_cross_edges() -> None:
    problem = synthesize("tiny", seed=1)
    compiled = compile_dag(problem)
    assert compiled.cross_edges == ()
    assert len(compiled.segments) == len(problem.jobs)
    for job in problem.jobs:
        rows = [segment for segment in compiled.segments if segment.job_id == job.id]
        assert len(rows) == 1
        assert len(rows[0].op_ids) == sum(1 for op in problem.operations if op.job_id == job.id)


def test_diamond_splits_into_segments() -> None:
    compiled = compile_dag(_diamond())
    assert len(compiled.segments) > len({segment.job_id for segment in compiled.segments})
    assert compiled.cross_edges
    assert compiled.strategy == "split_release_fixpoint"


def test_serialize_keeps_one_chain_per_job() -> None:
    problem = _diamond()
    problem = problem.model_copy(
        update={"policy": problem.policy.model_copy(update={"dag_strategy": "serialize"})}
    )
    compiled = compile_dag(problem)
    assert len(compiled.segments) == len(problem.jobs)
    assert compiled.cross_edges == ()
    join = next(op for op in problem.operations if len(op.predecessor_ids) > 1)
    assert join.job_id
    same_job = [segment for segment in compiled.segments if segment.job_id == join.job_id]
    assert len(same_job) == 1
    assert join.id in same_job[0].op_ids


def test_propagate_lifts_only_violated_edges() -> None:
    compiled = compile_dag(_diamond())
    edge = compiled.cross_edges[0]
    start = synthesize("tiny", seed=1).planning_horizon.start
    satisfied_starts = {row.dst: start + timedelta(hours=5) for row in compiled.cross_edges}
    satisfied_ends = {row.src: start + timedelta(hours=1) for row in compiled.cross_edges}
    same, changed = propagate_windows(compiled, starts=satisfied_starts, ends=satisfied_ends)
    assert changed is False
    assert same.window_lb == {}
    violated_starts = dict(satisfied_starts)
    violated_starts[edge.dst] = start
    lifted, changed = propagate_windows(
        compiled,
        starts=violated_starts,
        ends={**satisfied_ends, edge.src: start + timedelta(hours=2)},
    )
    assert changed is True
    assert lifted.window_lb[edge.dst] >= start + timedelta(hours=2)


def test_domain_greed_respects_join() -> None:
    problem = _diamond()
    outcome = plan(problem, solver_config="GREED")
    assert outcome.result.exit_code == 0
    assert outcome.result.verified_feasible
    assert outcome.result.claim_status == "verified"
    assert outcome.result.status.value == "HEURISTIC_FEASIBLE"
    by_id = {row.operation_id: row for row in outcome.result.assignments}
    join = next(op for op in problem.operations if len(op.predecessor_ids) > 1)
    for pred_id in join.predecessor_ids:
        assert by_id[join.id].start >= by_id[pred_id].end


def test_join_violation_is_caught_on_the_original_dag() -> None:
    problem = _diamond()
    greed = plan(problem, solver_config="GREED")
    by_id = {row.operation_id: row for row in greed.result.assignments}
    join = next(op for op in problem.operations if len(op.predecessor_ids) > 1)
    pred = by_id[join.predecessor_ids[0]]
    rows = []
    for row in greed.result.assignments:
        if row.operation_id == join.id:
            start = pred.start
            rows.append(row.model_copy(update={"start": start, "end": start + timedelta(minutes=20)}))
        else:
            rows.append(row.model_copy(deep=True))
    outcome = recheck(problem, assignments=rows, kernel_status="feasible", solver_config="recheck")
    assert any(row.code == ReasonCode.PRECEDENCE_BROKEN for row in outcome.result.violations)
    assert outcome.result.claim_status == "rejected"


def test_soft_due_date_does_not_reject_a_feasible_plan() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    assert greed.result.verified_feasible
    early = problem.planning_horizon.start
    jobs = [
        job.model_copy(update={"due_date": early}) if job.id == problem.jobs[0].id else job
        for job in problem.jobs
    ]
    tight = problem.model_copy(update={"jobs": jobs})
    outcome = recheck(
        tight,
        assignments=list(greed.result.assignments),
        kernel_status="feasible",
        solver_config="recheck",
    )
    missed = [
        row
        for row in outcome.result.violations
        if row.code == ReasonCode.DUE_MISSED and row.severity == "kpi"
    ]
    assert missed
    assert outcome.result.verified_feasible
    assert outcome.result.exit_code == 0
    assert outcome.result.claim_status == "verified"
