"""Validated append-only operator decisions for evidence bundles."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from repairflow.evidence import verify_plan_hashes
from repairflow.model import RepairFlowProblem, RepairFlowResult

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_OPERATOR_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,79}$")
GENESIS_HASH = "0" * 64


class Decision(StrEnum):
    """The four decisions an operator may record."""

    ACCEPTED = "accepted"
    ACCEPTED_WITH_EDITS = "accepted_with_edits"
    REJECTED = "rejected"
    MANUAL_FALLBACK = "manual_fallback"


_ACCEPTING = frozenset({Decision.ACCEPTED, Decision.ACCEPTED_WITH_EDITS})


class DecisionEvent(BaseModel):
    """One privacy-safe, hash-bound operator decision."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    operator_code: str
    instance_id: str
    input_hash: str
    result_hash: str
    decision: Decision
    edit_summary: str = ""
    reason: str = ""
    rollback_reference: str = ""
    prev_hash: str = ""
    event_hash: str = ""

    @field_validator("operator_code")
    @classmethod
    def validate_operator_code(cls, value: str) -> str:
        if not _OPERATOR_CODE.fullmatch(value) or value.isdigit():
            raise ValueError("operator_code must be a non-personal pseudonym")
        return value

    @field_validator("instance_id")
    @classmethod
    def validate_instance_id(cls, value: str) -> str:
        if not value or "\n" in value or "\r" in value:
            raise ValueError("instance_id must be a non-empty single-line value")
        return value

    @field_validator("input_hash", "result_hash", "prev_hash", "event_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if value == "":
            return value
        if not _SHA256.fullmatch(value):
            raise ValueError("hashes must be 64 hexadecimal characters")
        return value.lower()

    @field_validator("edit_summary", "reason", "rollback_reference")
    @classmethod
    def validate_single_line_text(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("decision text fields must be single-line values")
        return value

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_decision_requirements(self) -> Self:
        if self.decision in {Decision.REJECTED, Decision.MANUAL_FALLBACK} and not self.reason:
            raise ValueError("reason is required for rejection or manual fallback")
        if self.decision is Decision.ACCEPTED_WITH_EDITS and not self.edit_summary:
            raise ValueError("edit_summary is required when a plan is accepted with edits")
        return self


def canonical_event_json(event: DecisionEvent, *, include_event_hash: bool) -> str:
    """Stable JSON. The chain hash covers every field except ``event_hash``."""

    payload = event.model_dump(mode="json")
    if not include_event_hash:
        payload.pop("event_hash", None)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_event_hash(event: DecisionEvent) -> str:
    body = canonical_event_json(event, include_event_hash=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def seal_event(event: DecisionEvent, prev_hash: str) -> DecisionEvent:
    """Bind the event to the previous tip. The caller's chain fields are replaced."""

    drafted = event.model_copy(update={"prev_hash": prev_hash, "event_hash": ""})
    return drafted.model_copy(update={"event_hash": compute_event_hash(drafted)})


def read_decision_log(path: str | Path) -> list[DecisionEvent]:
    """Read and validate every JSONL record; malformed history fails closed."""

    _version, events = _load(Path(path))
    return events


def log_version(path: str | Path) -> str:
    """Return ``empty``, ``legacy``, or ``v2``."""

    version, _events = _load(Path(path))
    return version


def verify_decision_log(path: str | Path, head: str | None = None) -> str:
    """Check the chain. A known head catches a truncated tail."""

    version, events = _load(Path(path))
    if version == "legacy":
        if head is not None:
            raise ValueError("legacy decision log has no chain head")
        return "legacy"
    if version == "empty":
        if head is not None:
            raise ValueError("decision log head does not match")
        return "empty"
    tip = events[-1].event_hash
    if head is not None and head.lower() != tip:
        raise ValueError("decision log head does not match")
    return "v2"


def decision_stats(events: list[DecisionEvent]) -> dict[str, float | list[tuple[str, int]]]:
    """Counters only. Operator codes are not part of the result."""

    total = len(events)
    accepted = sum(1 for row in events if row.decision in _ACCEPTING)
    edits = sum(1 for row in events if row.decision is Decision.ACCEPTED_WITH_EDITS)
    reasons: Counter[str] = Counter(
        row.reason
        for row in events
        if row.decision in {Decision.REJECTED, Decision.MANUAL_FALLBACK} and row.reason
    )
    top = sorted(reasons.items(), key=lambda item: (-item[1], item[0]))[:5]
    return {
        "acceptance_rate": (accepted / total) if total else 0.0,
        "edit_rate": (edits / total) if total else 0.0,
        "top_reasons": top,
    }


def format_decision_stats(events: list[DecisionEvent]) -> str:
    stats = decision_stats(events)
    lines = [
        f"acceptance_rate={stats['acceptance_rate']:.6f}",
        f"edit_rate={stats['edit_rate']:.6f}",
    ]
    reasons = stats["top_reasons"]
    assert isinstance(reasons, list)
    for reason, count in reasons:
        lines.append(f"reason\t{count}\t{reason}")
    return "\n".join(lines) + "\n"


def append_decision(
    path: str | Path,
    event: DecisionEvent,
    *,
    lock_timeout: float = 5.0,
) -> DecisionEvent:
    """Lock, validate history, then append one sealed JSONL record."""

    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = log_path.with_name(log_path.name + ".lock")
    fd = _acquire_lock(lock_path, lock_timeout)
    try:
        version, events = _load(log_path)
        if version == "legacy":
            raise ValueError("legacy decision log cannot be extended")
        prev_hash = events[-1].event_hash if events else GENESIS_HASH
        sealed = seal_event(event, prev_hash)
        _append_line(log_path, sealed)
        return sealed
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def record_checked_decision(
    *,
    problem_path: Path,
    result_path: Path,
    decision: Decision,
    operator_code: str,
    log_path: Path,
    reason: str = "",
    edit_summary: str = "",
    rollback_reference: str = "",
) -> DecisionEvent:
    """Append a decision only when the result file still matches the problem."""

    problem = RepairFlowProblem.model_validate_json(problem_path.read_text(encoding="utf-8"))
    result = RepairFlowResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    mismatches = verify_plan_hashes(problem, result)
    if mismatches:
        raise ValueError("; ".join(mismatches))
    if problem.instance_id != result.instance_id:
        raise ValueError("instance_id does not match the result")
    if result.exit_code != 0 and decision in _ACCEPTING:
        raise ValueError("a non-zero exit cannot be accepted")
    event = DecisionEvent(
        operator_code=operator_code,
        instance_id=problem.instance_id,
        input_hash=result.input_hash,
        result_hash=result.result_hash,
        decision=decision,
        reason=reason,
        edit_summary=edit_summary,
        rollback_reference=rollback_reference,
    )
    return append_decision(log_path, event)


def _kind(payload: dict[str, Any], line_number: int) -> str:
    has_prev = "prev_hash" in payload
    has_event = "event_hash" in payload
    if has_prev != has_event:
        raise ValueError(f"invalid decision log line {line_number}: incomplete chain fields")
    return "v2" if has_prev else "legacy"


def _validate(payload: dict[str, Any], line_number: int) -> DecisionEvent:
    try:
        return DecisionEvent.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid decision log line {line_number}: {exc}") from exc


def _verify_chain(events: list[DecisionEvent]) -> None:
    previous = GENESIS_HASH
    for line_number, event in enumerate(events, start=1):
        if event.prev_hash != previous:
            raise ValueError(f"invalid decision log line {line_number}: breaks the chain")
        if event.event_hash == "" or event.event_hash != compute_event_hash(event):
            raise ValueError(f"invalid decision log line {line_number}: event_hash does not match")
        previous = event.event_hash


def _load(path: Path) -> tuple[str, list[DecisionEvent]]:
    if not path.exists():
        return "empty", []
    text = path.read_text(encoding="utf-8")
    if text == "":
        return "empty", []
    kinds: list[str] = []
    payloads: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"decision log line {line_number} is empty")
        try:
            payload: Any = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid decision log line {line_number}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"invalid decision log line {line_number}: not an object")
        kinds.append(_kind(payload, line_number))
        payloads.append(payload)
    if not payloads:
        return "empty", []
    if set(kinds) == {"legacy"}:
        events = [_validate(payload, number) for number, payload in enumerate(payloads, start=1)]
        return "legacy", events
    if set(kinds) == {"v2"}:
        events = [_validate(payload, number) for number, payload in enumerate(payloads, start=1)]
        _verify_chain(events)
        return "v2", events
    raise ValueError("decision log mixes legacy and chained records")


def _append_line(path: Path, event: DecisionEvent) -> None:
    line = canonical_event_json(event, include_event_hash=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_dir(path.parent)


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        return
    finally:
        os.close(fd)


def _acquire_lock(path: Path, timeout: float) -> int:
    deadline = time.monotonic() + timeout
    while True:
        try:
            return os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            pass
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
        if time.monotonic() >= deadline:
            raise TimeoutError(f"decision log lock timed out: {path.name}")
        time.sleep(0.01)
