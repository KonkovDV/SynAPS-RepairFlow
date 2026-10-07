"""Customer CSV manifest, local clocks, and crew pseudonyms.

The salt is an argument. Nothing in this module writes it into a bundle or a problem.
Eight hex characters is the published crew-code width. A collision is an error.
This is personnel-number hygiene. It is not a certification and not a legal opinion.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repairflow.io import read_text_encoded, read_text_limited

EncodingName = Literal["utf-8", "utf-8-sig", "cp1251"]
ProvenanceName = Literal[
    "synthetic",
    "open_data",
    "customer_data",
    "experiment",
    "production_verified",
]
_SCHEMA: Literal["repairflow.ingest_manifest.v1"] = "repairflow.ingest_manifest.v1"


class IngestManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["repairflow.ingest_manifest.v1"] = Field(alias="schema", default=_SCHEMA)
    encoding: EncodingName
    delimiter: str
    source_tz: str = "Europe/Moscow"
    data_provenance: ProvenanceName
    export_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _usable(self) -> IngestManifest:
        self.zone()
        self.separator()
        return self

    def zone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.source_tz)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"source_tz {self.source_tz!r} is not a known timezone") from exc

    def separator(self) -> str:
        if self.delimiter in {",", ";", "\t"}:
            return self.delimiter
        if self.delimiter == "tab":
            return "\t"
        raise ValueError("delimiter must be ',', ';', or a tab")


def load_manifest(path: Path) -> IngestManifest:
    payload = json.loads(read_text_limited(path))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a JSON object")
    return IngestManifest.model_validate(payload)


def read_csv_text(path: Path, manifest: IngestManifest) -> str:
    return read_text_encoded(path, manifest.encoding)


def pseudonymize_crew(personnel_number: str, salt: str) -> str:
    """HMAC-SHA256, published as ``crew-`` plus eight hex characters."""

    if salt.strip() == "" or "\n" in salt or "\r" in salt:
        raise ValueError("crew pseudonym salt is required")
    if personnel_number == "" or personnel_number.strip() != personnel_number:
        raise ValueError("personnel number must be a single line")
    if "\n" in personnel_number or "\r" in personnel_number:
        raise ValueError("personnel number must be a single line")
    digest = hmac.new(
        salt.encode("utf-8"),
        personnel_number.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return "crew-" + digest[:8]


def calendar_window(start: str, end: str, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """One shift. A local end that is not after its start rolls onto the next date."""

    start_local = _civil(start, zone)
    end_local = _civil(end, zone)
    if end_local <= start_local:
        end_local += timedelta(days=1)
    if end_local <= start_local:
        raise ValueError("calendar window end is not after start")
    return start_local, end_local


def to_utc(value: str, zone: ZoneInfo) -> datetime:
    parsed = _civil(value, zone)
    return parsed


def _civil(value: str, zone: ZoneInfo) -> datetime:
    text = value.strip()
    if text == "":
        raise ValueError("timestamp is empty")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{value!r} is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed
