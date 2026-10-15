"""The decision wrapper checks the result file before it appends."""

from __future__ import annotations

import json
from pathlib import Path

from tools.append_decision import main

from repairflow.decision_log import verify_decision_log
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def _pair(tmp_path: Path, solver: str) -> tuple[Path, Path]:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config=solver)
    problem_path = tmp_path / f"{solver}-problem.json"
    result_path = tmp_path / f"{solver}-result.json"
    problem_path.write_text(problem.model_dump_json(), encoding="utf-8")
    result_path.write_text(outcome.result.model_dump_json(), encoding="utf-8")
    return problem_path, result_path


def test_wrapper_accepts_a_checked_plan_and_seals_the_log(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    problem_path, result_path = _pair(tmp_path, "GREED")
    log_path = tmp_path / "decisions.jsonl"
    code = main(
        [
            "--log",
            str(log_path),
            "--problem",
            str(problem_path),
            "--result",
            str(result_path),
            "--operator-code",
            "op-shadow-01",
            "--decision",
            "accepted",
            "--timestamp",
            "2026-10-15T09:00:00+00:00",
        ]
    )
    assert code == 0
    assert "event_hash" in capsys.readouterr().out
    assert verify_decision_log(log_path) == "v2"


def test_wrapper_refuses_to_accept_a_nonzero_exit(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    problem_path, result_path = _pair(tmp_path, "FIFO")
    log_path = tmp_path / "decisions.jsonl"
    code = main(
        [
            "--log",
            str(log_path),
            "--problem",
            str(problem_path),
            "--result",
            str(result_path),
            "--operator-code",
            "op-shadow-01",
            "--decision",
            "accepted",
        ]
    )
    assert code == 1
    assert "non-zero exit" in capsys.readouterr().err
    assert not log_path.exists()


def test_wrapper_refuses_a_result_whose_hash_was_edited(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    problem_path, result_path = _pair(tmp_path, "GREED")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["result_hash"] = "ab" + payload["result_hash"][2:]
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    log_path = tmp_path / "decisions.jsonl"
    code = main(
        [
            "--log",
            str(log_path),
            "--problem",
            str(problem_path),
            "--result",
            str(result_path),
            "--operator-code",
            "op-shadow-01",
            "--decision",
            "rejected",
            "--reason",
            "hash was edited",
        ]
    )
    assert code == 1
    assert "result_hash" in capsys.readouterr().err
    assert not log_path.exists()
