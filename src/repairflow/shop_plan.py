"""Shop CSV plan: the columns a 1C or Excel export can fill.

The file is not a solver result. Times must carry a timezone. An empty crew
or tooling cell stays empty; the domain checker decides whether that is legal.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

from repairflow.ingest import load_manifest
from repairflow.io import read_bytes_limited
from repairflow.model import PlannedAssignment, RepairFlowProblem, Violation
from repairflow.reasons import REASON_RU, SUGGESTIONS, ReasonCode

_COLUMNS = {
    "заказ": "job_id",
    "операция": "operation_id",
    "пост": "work_center_id",
    "бригада": "crew_id",
    "оснастка": "aux_ids",
    "начало": "start",
    "конец": "end",
    "переналадка": "setup_minutes",
    "setup_minutes": "setup_minutes",
    "job_id": "job_id",
    "operation_id": "operation_id",
    "work_center_id": "work_center_id",
    "crew_id": "crew_id",
    "aux_ids": "aux_ids",
    "start": "start",
    "end": "end",
}
_REQUIRED = frozenset({"job_id", "operation_id", "work_center_id", "crew_id", "aux_ids", "start", "end"})
SHOP_HEADER = ("заказ", "операция", "пост", "бригада", "оснастка", "начало", "конец", "переналадка")


def load_shop_plan(
    path: Path,
    problem: RepairFlowProblem,
) -> tuple[list[PlannedAssignment], list[Violation], dict[str, tuple[str, int]], str]:
    """Read a shop plan once. A repeated operation is an error, not a second visit."""

    raw = read_bytes_limited(path)
    file_sha256 = hashlib.sha256(raw).hexdigest()
    manifest_path = path.parent / "manifest.json"
    zone: ZoneInfo | None = None
    if manifest_path.is_file():
        manifest = load_manifest(manifest_path)
        text = _decode_shop(path, raw, manifest.encoding)
        delimiter = manifest.separator()
        zone = manifest.zone()
    else:
        text = _decode_shop(path, raw, None)
        if not text.strip():
            raise ValueError(f"{path} has no header")
        delimiter = ";" if text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    if reader.fieldnames is None:
        raise ValueError(f"{path} has no header")
    header = {_COLUMNS.get(name.strip(), ""): name for name in reader.fieldnames if name}
    missing = _REQUIRED - set(header)
    if missing:
        raise ValueError(f"{path} is missing columns {sorted(missing)}")
    jobs = {op.id: op.job_id for op in problem.operations}
    assignments: list[PlannedAssignment] = []
    issues: list[Violation] = []
    sources: dict[str, tuple[str, int]] = {}
    for index, record in enumerate(reader, start=2):
        row = {field: (record.get(source) or "").strip() for field, source in header.items() if field}
        operation_id = row["operation_id"]
        if not operation_id:
            raise ValueError(f"{path} line {index} has no operation")
        if operation_id in sources:
            raise ValueError(f"{path} line {index} repeats operation {operation_id}")
        sources[operation_id] = (path.name, index)
        start = _instant(row["start"], path=path, line=index, column="начало", zone=zone)
        end = _instant(row["end"], path=path, line=index, column="конец", zone=zone)
        if end <= start:
            raise ValueError(f"{path} line {index} ends at or before it starts")
        aux = [item for item in row["aux_ids"].split("|") if item]
        setup_text = row.get("setup_minutes", "")
        if setup_text == "":
            setup_minutes = 0
        elif not setup_text.isdigit():
            raise ValueError(f"{path} line {index} переналадка is not a whole number of minutes")
        else:
            setup_minutes = int(setup_text)
        assignments.append(
            PlannedAssignment(
                operation_id=operation_id,
                work_center_id=row["work_center_id"],
                crew_id=row["crew_id"] or None,
                aux_ids=aux,
                start=start,
                end=end,
                setup_minutes=setup_minutes,
                reason="shop csv",
            )
        )
        owner = jobs.get(operation_id)
        if owner is not None and row["job_id"] != owner:
            issues.append(
                Violation(
                    code=ReasonCode.JOB_MISMATCH,
                    message=REASON_RU[ReasonCode.JOB_MISMATCH],
                    operation_id=operation_id,
                    job_id=row["job_id"] or None,
                    suggested_relaxation=SUGGESTIONS[ReasonCode.JOB_MISMATCH],
                    details={
                        "operation_job_id": owner,
                        "source_name": path.name,
                        "source_line": index,
                    },
                )
            )
    return assignments, issues, sources, file_sha256


def format_shop_finding(violation: Violation) -> str:
    """One human-readable line. The notary sentence stays intact."""

    text = REASON_RU.get(violation.code, violation.message)
    place = violation.operation_id or violation.resource_id or ""
    parts = [violation.code, text]
    if place:
        parts.append(place)
    name = violation.details.get("source_name")
    line = violation.details.get("source_line")
    if isinstance(name, str) and isinstance(line, int):
        parts.append(f"{name}:{line}")
    return "\t".join(parts)


def _decode_shop(path: Path, raw: bytes, encoding: str | None) -> str:
    chosen = "utf-8" if encoding is None else encoding
    try:
        return raw.decode(chosen)
    except UnicodeDecodeError as exc:
        if encoding is None:
            raise
        raise ValueError(f"{path} is not encoded as {encoding}") from exc


def write_shop_plan(
    path: Path,
    problem: RepairFlowProblem,
    assignments: list[PlannedAssignment],
) -> None:
    """Write the shop template columns for a candidate that already exists."""

    jobs = {op.id: op.job_id for op in problem.operations}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SHOP_HEADER))
        writer.writeheader()
        for row in assignments:
            writer.writerow(
                {
                    "заказ": jobs.get(row.operation_id, ""),
                    "операция": row.operation_id,
                    "пост": row.work_center_id,
                    "бригада": row.crew_id or "",
                    "оснастка": "|".join(row.aux_ids),
                    "начало": row.start.isoformat(),
                    "конец": row.end.isoformat(),
                    "переналадка": row.setup_minutes,
                }
            )


def _instant(
    value: str,
    *,
    path: Path,
    line: int,
    column: str,
    zone: ZoneInfo | None,
) -> datetime:
    if not value:
        raise ValueError(f"{path} line {line} has no {column}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{path} line {line} {column} is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        if zone is None:
            raise ValueError(f"{path} line {line} {column} has no timezone")
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(UTC)
