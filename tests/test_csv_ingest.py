import pytest

from repairflow.model import ExchangePool, PoolDemand, RepairFlowProblem
from repairflow.normalize import load_problem, write_csv_bundle
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_csv_bundle_roundtrip(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    bundle = tmp_path / "tiny-csv"
    write_csv_bundle(bundle, problem)
    loaded = load_problem(bundle)
    assert [op.id for op in loaded.operations] == [op.id for op in problem.operations]
    assert [job.id for job in loaded.jobs] == [job.id for job in problem.jobs]
    greed = plan(loaded, solver_config="GREED")
    assert greed.result.verified_feasible
    assert greed.result.exit_code == 0
    assert loaded.exchange_pools == []


def test_exchange_pool_csv_roundtrip(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    pools = [
        ExchangePool(
            unit_type=problem.jobs[0].unit_type,
            initial_serviceable=2,
            hard=True,
            demand=[
                PoolDemand(at=start, qty=1),
                PoolDemand(at=problem.planning_horizon.end, qty=3),
            ],
        ),
        ExchangePool(unit_type="POOL-EMPTY", initial_serviceable=0, hard=False),
    ]
    sourced = RepairFlowProblem.model_validate(
        problem.model_copy(update={"exchange_pools": pools}).model_dump(mode="python")
    )
    bundle = tmp_path / "pools"
    write_csv_bundle(bundle, sourced)
    loaded = load_problem(bundle)
    assert loaded.exchange_pools == sourced.exchange_pools


def test_exchange_pool_csv_rejects_a_half_specified_demand(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    pool = ExchangePool(
        unit_type=problem.jobs[0].unit_type,
        initial_serviceable=1,
        hard=True,
        demand=[PoolDemand(at=problem.planning_horizon.start, qty=1)],
    )
    sourced = RepairFlowProblem.model_validate(
        problem.model_copy(update={"exchange_pools": [pool]}).model_dump(mode="python")
    )
    bundle = tmp_path / "half"
    write_csv_bundle(bundle, sourced)
    text = (bundle / "exchange_pools.csv").read_text(encoding="utf-8")
    (bundle / "exchange_pools.csv").write_text(
        text.replace(",1\n", ",\n"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="demand_at and demand_qty"):
        load_problem(bundle)
