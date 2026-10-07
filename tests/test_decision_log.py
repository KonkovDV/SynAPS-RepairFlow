from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

import pytest

from repairflow.decision_log import (
    GENESIS_HASH,
    Decision,
    DecisionEvent,
    append_decision,
    format_decision_stats,
    log_version,
    read_decision_log,
    verify_decision_log,
)

_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _event(decision: Decision = Decision.ACCEPTED, **updates: object) -> DecisionEvent:
    payload: dict[str, object] = {
        "operator_code": "op-shadow-01",
        "instance_id": "instance-01",
        "input_hash": _HASH_A,
        "result_hash": _HASH_B,
        "decision": decision.value,
    }
    payload.update(updates)
    return DecisionEvent.model_validate(payload)


def test_all_decisions_have_explicit_requirements() -> None:
    assert _event(Decision.ACCEPTED).decision is Decision.ACCEPTED
    edited = _event(Decision.ACCEPTED_WITH_EDITS, edit_summary="Moved one operation")
    assert edited.edit_summary == "Moved one operation"
    rejected = _event(Decision.REJECTED, reason="Missing crew binding")
    assert rejected.reason == "Missing crew binding"
    fallback = _event(Decision.MANUAL_FALLBACK, reason="Calendar unavailable")
    assert fallback.reason == "Calendar unavailable"


def test_required_decision_context_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="reason is required"):
        _event(Decision.REJECTED)
    with pytest.raises(ValueError, match="edit_summary is required"):
        _event(Decision.ACCEPTED_WITH_EDITS)
    with pytest.raises(ValueError, match="hashes must be"):
        _event(input_hash="not-a-hash")
    with pytest.raises(ValueError, match="timezone"):
        _event(timestamp=datetime(2026, 10, 1, 12, 0))


def test_operator_code_rejects_direct_identity_shapes() -> None:
    for value in ("Dmitrij Konkov", "konkov.dmitrij@yandex.ru", "123456"):
        with pytest.raises(ValueError, match="pseudonym"):
            _event(operator_code=value)


def test_append_is_canonical_and_preserves_order(tmp_path: Path) -> None:
    path = tmp_path / "evidence" / "decisions.jsonl"
    first = _event()
    second = _event(Decision.REJECTED, reason="Hard notary is non-empty")

    append_decision(path, first)
    append_decision(path, second)

    loaded = read_decision_log(path)
    assert [row.event_id for row in loaded] == [first.event_id, second.event_id]
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.dumps(json.loads(line), sort_keys=True, separators=(",", ":")) == line for line in lines)


def test_append_refuses_tampered_or_malformed_history(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    append_decision(path, _event())
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace(_HASH_A, "not-a-hash"), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid decision log line"):
        append_decision(path, _event())

    path.write_text(original + "not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid decision log line"):
        read_decision_log(path)


def test_new_log_is_a_hash_chain(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    first = append_decision(path, _event())
    second = append_decision(path, _event(Decision.REJECTED, reason="Hard notary is non-empty"))
    loaded = read_decision_log(path)
    assert loaded[0].prev_hash == GENESIS_HASH
    assert loaded[1].prev_hash == first.event_hash
    assert loaded[1].event_hash == second.event_hash
    assert verify_decision_log(path, head=second.event_hash) == "v2"


def test_a_changed_record_breaks_its_hash(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    append_decision(path, _event())
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("instance-01", "instance-02"), encoding="utf-8")
    with pytest.raises(ValueError, match="event_hash does not match"):
        read_decision_log(path)


def test_swapped_lines_break_the_chain(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    append_decision(path, _event())
    append_decision(path, _event(Decision.REJECTED, reason="Hard notary is non-empty"))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[1] + "\n" + lines[0] + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="breaks the chain"):
        read_decision_log(path)


def test_a_truncated_tail_needs_the_known_head(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    append_decision(path, _event())
    tip = append_decision(path, _event(Decision.REJECTED, reason="Hard notary is non-empty")).event_hash
    first = path.read_text(encoding="utf-8").splitlines()[0]
    path.write_text(first + "\n", encoding="utf-8")
    assert verify_decision_log(path) == "v2"
    with pytest.raises(ValueError, match="head does not match"):
        verify_decision_log(path, head=tip)


def test_legacy_log_is_not_a_chain_and_cannot_grow(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    legacy = {
        "decision": "accepted",
        "edit_summary": "",
        "event_id": "00000000-0000-0000-0000-000000000001",
        "input_hash": _HASH_A,
        "instance_id": "instance-01",
        "operator_code": "op-shadow-01",
        "reason": "",
        "result_hash": _HASH_B,
        "rollback_reference": "",
        "timestamp": "2026-10-01T12:00:00Z",
    }
    path.write_text(json.dumps(legacy, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    assert log_version(path) == "legacy"
    assert verify_decision_log(path) == "legacy"
    with pytest.raises(ValueError, match="no chain head"):
        verify_decision_log(path, head=GENESIS_HASH)
    with pytest.raises(ValueError, match="cannot be extended"):
        append_decision(path, _event())
    chained = append_decision(tmp_path / "new.jsonl", _event())
    mixed = path.read_text(encoding="utf-8") + path.with_name("new.jsonl").read_text(encoding="utf-8")
    path.write_text(mixed, encoding="utf-8")
    assert chained.event_hash
    with pytest.raises(ValueError, match="mixes legacy"):
        read_decision_log(path)


def test_a_held_lock_times_out(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    lock = path.with_name(path.name + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_RDWR)
    try:
        with pytest.raises(TimeoutError, match="lock timed out"):
            append_decision(path, _event(), lock_timeout=0.05)
    finally:
        os.close(fd)
        lock.unlink()


def test_parallel_appends_keep_whole_lines(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker(reason: str) -> None:
        try:
            barrier.wait(timeout=2)
            append_decision(path, _event(Decision.REJECTED, reason=reason))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(reason,)) for reason in ("first reason", "second reason")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    loaded = read_decision_log(path)
    assert {row.reason for row in loaded} == {"first reason", "second reason"}
    assert verify_decision_log(path) == "v2"


def test_stats_are_counters_without_the_operator_code(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    append_decision(path, _event())
    append_decision(path, _event(Decision.ACCEPTED_WITH_EDITS, edit_summary="Moved one operation"))
    append_decision(path, _event(Decision.REJECTED, reason="Hard notary is non-empty"))
    text = format_decision_stats(read_decision_log(path))
    assert "op-shadow-01" not in text
    assert "acceptance_rate=0.666667" in text
    assert "edit_rate=0.333333" in text
    assert "Hard notary is non-empty" in text


def test_decide_checks_hashes_and_refuses_a_failed_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from repairflow.cli import main
    from repairflow.evidence import fingerprint_payload
    from repairflow.planner import plan
    from repairflow.synthetic import synthesize

    problem = synthesize("tiny", seed=1)
    result = plan(problem, solver_config="GREED").result
    assert result.exit_code == 0
    problem_path = tmp_path / "problem.json"
    result_path = tmp_path / "result.json"
    log_path = tmp_path / "decisions.jsonl"
    problem_path.write_text(problem.model_dump_json(), encoding="utf-8")
    result_path.write_text(result.model_dump_json(), encoding="utf-8")
    code = main(
        [
            "decide",
            "--problem",
            str(problem_path),
            "--result",
            str(result_path),
            "--accept",
            "--operator-code",
            "op-shadow-01",
            "--log",
            str(log_path),
        ]
    )
    assert code == 0
    head = capsys.readouterr().out.strip()
    assert main(["log", "verify", str(log_path), "--head", head]) == 0
    other = synthesize("tiny", seed=2)
    problem_path.write_text(other.model_dump_json(), encoding="utf-8")
    assert (
        main(
            [
                "decide",
                "--problem",
                str(problem_path),
                "--result",
                str(result_path),
                "--accept",
                "--operator-code",
                "op-shadow-01",
                "--log",
                str(log_path),
            ]
        )
        == 1
    )
    problem_path.write_text(problem.model_dump_json(), encoding="utf-8")
    result.exit_code = 2
    result.result_hash = fingerprint_payload(result.model_dump(mode="json", exclude={"result_hash"}))
    bad = tmp_path / "bad.json"
    bad.write_text(result.model_dump_json(), encoding="utf-8")
    assert (
        main(
            [
                "decide",
                "--problem",
                str(problem_path),
                "--result",
                str(bad),
                "--accept",
                "--operator-code",
                "op-shadow-01",
                "--log",
                str(log_path),
            ]
        )
        == 1
    )
