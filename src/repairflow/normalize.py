"""CSV/JSON ingest → canonical timezone-aware RepairFlowProblem."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any

from repairflow.io import read_text_limited
from repairflow.model import RepairFlowProblem


def load_problem(path: Path) -> RepairFlowProblem:
    suffix = path.suffix.lower()
    if path.is_dir() or suffix == ".csv":
        return problem_from_csv_bundle(path)
    if suffix == ".json":
        return RepairFlowProblem.model_validate(json.loads(read_text_limited(path)))
    raise ValueError(f"unsupported problem format: {path.suffix}")


def problem_from_csv_bundle(path: Path) -> RepairFlowProblem:
    """Load a directory of CSV tables or a single jobs-style CSV with JSON sidecar.

    Expected sibling files: jobs.csv, operations.csv, work_centers.csv, crews.csv.
    A JSON file with the same stem is preferred when present.
    """

    sidecar = path.with_suffix(".json")
    if sidecar.is_file():
        return RepairFlowProblem.model_validate_json(read_text_limited(sidecar))
    directory = path if path.is_dir() else path.parent
    payload: dict[str, Any] = {
        "schema_version": "repairflow.problem.v1",
        "instance_id": path.name if path.is_dir() else path.stem,
        "data_provenance": "synthetic",
        "planning_horizon": _require_horizon(directory),
        "jobs": _read_csv(directory / "jobs.csv"),
        "operations": _read_csv(directory / "operations.csv"),
        "work_centers": _read_csv(directory / "work_centers.csv"),
        "crews": _read_csv(directory / "crews.csv"),
        "aux_resources": _read_csv(directory / "aux_resources.csv", optional=True),
        "setup_matrix": _read_csv(directory / "setup_matrix.csv", optional=True),
        "calendars": _read_calendars(directory / "calendars.csv"),
        "frozen_assignments": _read_csv(directory / "frozen_assignments.csv", optional=True),
        "spares": _read_csv(directory / "spares.csv", optional=True),
        "policy": {"unknown_fields": "reject", "missing_setup": "reject", "unsupported_dag": "reject"},
    }
    payload = _split_list_fields(payload)
    return RepairFlowProblem.model_validate(payload)


def _read_csv(path: Path, *, optional: bool = False) -> list[dict[str, Any]]:
    if not path.is_file():
        if optional:
            return []
        raise ValueError(f"missing required CSV table {path}")
    text = read_text_limited(path)
    reader = csv.DictReader(StringIO(text))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        row = {key: _coerce(value) for key, value in raw.items() if key}
        rows.append(row)
    return rows


def _read_calendars(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    grouped: dict[str, dict[str, Any]] = {}
    for row in _read_csv(path, optional=True):
        cal_id = str(row.get("id") or row.get("calendar_id"))
        grouped.setdefault(cal_id, {"id": cal_id, "code": row.get("code", cal_id), "windows": []})
        grouped[cal_id]["windows"].append({"start": row["start"], "end": row["end"]})
    return list(grouped.values())


def _require_horizon(directory: Path) -> dict[str, str]:
    meta = directory / "horizon.json"
    if meta.is_file():
        payload = json.loads(read_text_limited(meta))
        if not isinstance(payload, dict):
            raise ValueError(f"{meta} must be a JSON object with start/end")
        return {str(key): str(value) for key, value in payload.items()}
    raise ValueError(f"{directory} CSV bundle needs horizon.json with start/end")


def _split_list_fields(payload: dict[str, Any]) -> dict[str, Any]:
    list_keys = {
        "predecessor_ids",
        "eligible_work_center_ids",
        "required_skills",
        "required_aux_ids",
        "required_spare_ids",
        "eligible_unit_types",
        "skills",
        "aux_ids",
    }
    for table in payload.values():
        if not isinstance(table, list):
            continue
        for row in table:
            if not isinstance(row, dict):
                continue
            for key, value in list(row.items()):
                if key in list_keys:
                    if value is None or value == "":
                        row[key] = []
                    elif isinstance(value, str):
                        row[key] = [item for item in value.split("|") if item]
    return payload


def write_csv_bundle(directory: Path, problem: RepairFlowProblem) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "horizon.json").write_text(
        json.dumps(
            {
                "start": problem.planning_horizon.start.isoformat(),
                "end": problem.planning_horizon.end.isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_table(
        directory / "jobs.csv",
        [
            {
                "id": job.id,
                "external_ref": job.external_ref,
                "asset_code": job.asset_code,
                "unit_type": job.unit_type,
                "release_date": _iso(job.release_date),
                "due_date": _iso(job.due_date),
                "priority": job.priority,
            }
            for job in problem.jobs
        ],
    )
    _write_table(
        directory / "operations.csv",
        [
            {
                "id": op.id,
                "job_id": op.job_id,
                "sequence": op.sequence,
                "duration_min": op.duration_min,
                "predecessor_ids": _join(op.predecessor_ids),
                "eligible_work_center_ids": _join(op.eligible_work_center_ids),
                "required_skills": _join(op.required_skills),
                "required_aux_ids": _join(op.required_aux_ids),
                "required_spare_ids": _join(op.required_spare_ids),
                "setup_state": op.setup_state,
                "earliest_start": _iso(op.earliest_start),
                "latest_finish": _iso(op.latest_finish),
            }
            for op in problem.operations
        ],
    )
    _write_table(
        directory / "work_centers.csv",
        [
            {
                "id": wc.id,
                "code": wc.code,
                "capability_group": wc.capability_group,
                "calendar_id": wc.calendar_id or "",
                "max_parallel": wc.max_parallel,
                "eligible_unit_types": _join(wc.eligible_unit_types),
            }
            for wc in problem.work_centers
        ],
    )
    _write_table(
        directory / "crews.csv",
        [
            {
                "id": crew.id,
                "code": crew.code,
                "skills": _join(crew.skills),
                "calendar_id": crew.calendar_id or "",
                "max_parallel": crew.max_parallel,
            }
            for crew in problem.crews
        ],
    )
    _write_table(
        directory / "aux_resources.csv",
        [
            {
                "id": aux.id,
                "code": aux.code,
                "resource_type": aux.resource_type,
                "capacity": aux.capacity,
                "calendar_id": aux.calendar_id or "",
            }
            for aux in problem.aux_resources
        ],
    )
    _write_table(
        directory / "setup_matrix.csv",
        [
            {
                "work_center_id": row.work_center_id or "",
                "from_state": row.from_state,
                "to_state": row.to_state,
                "duration_min": row.duration_min,
            }
            for row in problem.setup_matrix
        ],
    )
    calendar_rows: list[dict[str, Any]] = []
    for calendar in problem.calendars:
        for window in calendar.windows:
            calendar_rows.append(
                {
                    "id": calendar.id,
                    "code": calendar.code,
                    "start": window.start.isoformat(),
                    "end": window.end.isoformat(),
                }
            )
    _write_table(directory / "calendars.csv", calendar_rows)
    _write_table(
        directory / "frozen_assignments.csv",
        [
            {
                "operation_id": row.operation_id,
                "work_center_id": row.work_center_id,
                "start": row.start.isoformat(),
                "end": row.end.isoformat(),
                "crew_id": row.crew_id or "",
                "setup_minutes": row.setup_minutes,
                "immutable": row.immutable,
                "frozen_reason": row.frozen_reason,
            }
            for row in problem.frozen_assignments
        ],
    )
    _write_table(
        directory / "spares.csv",
        [
            {
                "id": spare.id,
                "code": spare.code,
                "quantity": spare.quantity,
                "available_from": _iso(spare.available_from),
            }
            for spare in problem.spares
        ],
    )


def _write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _join(values: list[str]) -> str:
    return "|".join(values)


def _iso(value: Any) -> str:
    if value is None:
        return ""
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return str(iso())
    return str(value)


def _coerce(value: str) -> Any:
    text = value.strip()
    if text == "":
        return None
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        if "." not in text:
            return int(text)
    except ValueError:
        pass
    return text
