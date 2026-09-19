from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_result_carries_hashes_and_pin() -> None:
    outcome = plan(synthesize("tiny", seed=1), solver_config="FIFO")
    result = outcome.result
    assert len(result.input_hash) == 64
    assert len(result.config_hash) == 64
    assert len(result.result_hash) == 64
    assert len(result.synaps_commit) == 40
    assert result.data_provenance == "synthetic"
    assert result.claim_level == "experiment"
    assert result.metadata["iso16290_trl"] == 4
