"""Validated append-only operator decisions for evidence bundles."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_OPERATOR_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,79}$")


class Decision(StrEnum):
    """The four decisions an operator may record."""

    ACCEPTED = "accepted"
    ACCEPTED_WITH_EDITS = "accepted_with_edits"
    REJECTED = "rejected"
    MANUAL_FALLBACK = "manual_fallback"


class DecisionEvent(BaseModel):
    """One privacy-safe, hash-bound operator decision."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operator_code: str
    instance_id: str
    input_hash: str
    result_hash: str
    decision: Decision
    edit_summary: str = ""
    reason: str = ""
    rollback_reference: str = ""

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

    @field_validator("input_hash", "result_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
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
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_decision_requirements(self) -> Self:
        if self.decision in {Decision.REJECTED, Decision.MANUAL_FALLBACK} and not self.reason:
            raise ValueError("reason is required for rejection or manual fallback")
        if self.decision is Decision.ACCEPTED_WITH_EDITS and not self.edit_summary:
            raise ValueError("edit_summary is required when a plan is accepted with edits")
        return self


def read_decision_log(path: str | Path) -> list[DecisionEvent]:
    """Read and validate every JSONL record; malformed history fails closed."""

    log_path = Path(path)
    if not log_path.exists():
        return []
    events: list[DecisionEvent] = []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ValueError(f"decision log line {line_number} is empty")
        try:
            payload: Any = json.loads(line)
            events.append(DecisionEvent.model_validate(payload))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid decision log line {line_number}: {exc}") from exc
    return events


def append_decision(path: str | Path, event: DecisionEvent) -> DecisionEvent:
    """Validate existing history, then append one canonical JSONL record."""

    log_path = Path(path)
    read_decision_log(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
    return event
