from pathlib import Path

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


def test_pack_evidence_writes_mvp_hashes(tmp_path) -> None:
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "tools" / "pack_evidence.py"
    spec = importlib.util.spec_from_file_location("repairflow_pack_evidence", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    summary = module.pack(tmp_path)
    assert summary["operations"] == 52
    assert summary["fifo_exit_code"] == 2
    assert summary["greed_verified"] is True
    assert (tmp_path / "greed.html").is_file()
    assert (tmp_path / "hashes.json").is_file()
    assert (tmp_path / "checker.json").is_file()
