from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from repairflow.decision_log import Decision, DecisionEvent, append_decision, read_decision_log

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
