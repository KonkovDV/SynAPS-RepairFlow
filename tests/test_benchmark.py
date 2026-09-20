from pathlib import Path

from repairflow.benchmark import DEFAULT_MATRIX, run_benchmark
from repairflow.cli import main


def test_default_matrix_is_checker_clean_cells() -> None:
    assert DEFAULT_MATRIX == [
        ("tiny", 1),
        ("tiny", 42),
        ("tiny", 99),
        ("repair-site-mvp", 42),
        ("repair-site-mvp", 13),
    ]
    assert ("repair-site-mvp", 7) not in DEFAULT_MATRIX


def test_benchmark_tiny_fifo_dirty_greed_verified(tmp_path: Path) -> None:
    summary = run_benchmark(matrix=[("tiny", 42)], out_dir=tmp_path)
    fifo = next(row for row in summary.rows if row.solver == "FIFO")
    greed = next(row for row in summary.rows if row.solver == "GREED")
    assert fifo.verified is False
    assert fifo.exit_code == 2
    assert fifo.violations > 0
    assert greed.verified is True
    assert greed.exit_code == 0
    assert greed.violations == 0
    assert summary.verified_ratio() == 1.0
    assert summary.greed_all_verified() is True
    assert summary.fifo_minus_greed_makespan() is not None
    assert (summary.fifo_minus_greed_makespan() or 0) < 0
    payload = (tmp_path / "benchmark.json").read_text(encoding="utf-8")
    assert "synthetic" in payload
    assert "makespan_note" in payload
    assert (tmp_path / "benchmark.md").is_file()
    assert (tmp_path / "benchmark.html").is_file()
    assert (tmp_path / "tiny-seed42-greed.html").is_file()


def test_cli_benchmark_tiny(tmp_path: Path, capsys) -> None:
    assert main(["benchmark", "--out", str(tmp_path), "--preset", "tiny", "--seeds", "42"]) == 0
    out = capsys.readouterr().out
    assert "GREED verified ratio: 100.0%" in out
    assert "FIFO mean hard violations" in out
    assert (tmp_path / "benchmark.json").is_file()
