"""Stable hashing, provenance and evidence bundle helpers."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime
from enum import Enum
from importlib import metadata
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from repairflow.model import RepairFlowProblem, RepairFlowResult
from repairflow.versions import CLAIM_LEVEL, ISO16290_TRL, REPAIRFLOW_VERSION, SYNAPS_COMMIT


def runtime_manifest() -> dict[str, str]:
    """Versions that must travel with a plan hash. Missing wheels stay explicit."""

    versions = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "repairflow": REPAIRFLOW_VERSION,
        "synaps_commit": SYNAPS_COMMIT,
    }
    for dist in ("ortools", "pydantic"):
        try:
            versions[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            versions[dist] = "absent"
    return versions


def to_canonical(data: Any) -> Any:
    """JSON-ready value. Refuses types that ``default=str`` would hide."""

    if isinstance(data, BaseModel):
        return to_canonical(data.model_dump(mode="json"))
    if isinstance(data, datetime):
        return data.isoformat()
    if isinstance(data, UUID):
        return str(data)
    if isinstance(data, Enum):
        return to_canonical(data.value)
    if isinstance(data, dict):
        return {str(key): to_canonical(value) for key, value in data.items()}
    if isinstance(data, list | tuple):
        return [to_canonical(value) for value in data]
    if data is None or isinstance(data, str | int | bool):
        return data
    if isinstance(data, float):
        if data != data or data in {float("inf"), float("-inf")}:
            raise TypeError("non-finite float is not canonical")
        return data
    raise TypeError(f"cannot canonicalize {type(data).__name__}")


def canonical_json(data: Any) -> str:
    return json.dumps(to_canonical(data), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint_payload(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def evidence_stamp(
    *,
    input_hash: str,
    config_hash: str,
    data_provenance: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "repairflow_version": REPAIRFLOW_VERSION,
        "synaps_commit": SYNAPS_COMMIT,
        "claim_level": CLAIM_LEVEL,
        "iso16290_trl": ISO16290_TRL,
        "data_provenance": data_provenance,
        "input_hash": input_hash,
        "config_hash": config_hash,
        "metric_tag": "synthetic_experiment" if data_provenance == "synthetic" else data_provenance,
    }
    if extra:
        payload.update(extra)
    return payload


def compute_schedule_hash(result: RepairFlowResult) -> str:
    """Fingerprint the schedule. The runtime manifest is not an input."""

    assignments = [
        row.model_dump(mode="json")
        for row in sorted(
            result.assignments,
            key=lambda row: (
                row.operation_id,
                row.start.isoformat(),
                row.end.isoformat(),
                row.work_center_id,
                row.crew_id or "",
            ),
        )
    ]
    payload = {
        "assignments": assignments,
        "claim_status": result.claim_status,
        "exit_code": result.exit_code,
        "input_hash": result.input_hash,
        "solver_config": result.solver_config,
        "synaps_commit": result.synaps_commit,
        "violation_codes": sorted(row.code for row in result.violations),
    }
    return fingerprint_payload(payload)


def seal_result_hashes(result: RepairFlowResult) -> None:
    """Set schedule_hash, then result_hash over the body that includes it."""

    result.schedule_hash = compute_schedule_hash(result)
    result.result_hash = fingerprint_payload(result.model_dump(mode="json", exclude={"result_hash"}))


def verify_plan_hashes(problem: RepairFlowProblem, result: RepairFlowResult) -> list[str]:
    """Return human-readable mismatches. Empty means the stored hashes still match."""

    errors: list[str] = []
    expected_input = fingerprint_payload(problem.model_dump(mode="json"))
    if result.input_hash != expected_input:
        errors.append("input_hash does not match the problem")
    expected_result = fingerprint_payload(result.model_dump(mode="json", exclude={"result_hash"}))
    if result.result_hash != expected_result:
        errors.append("result_hash does not match the plan body")
    stored = result.metadata.get("config_payload")
    if not isinstance(stored, dict):
        errors.append("config_payload is missing; config_hash cannot be checked")
    elif result.config_hash != fingerprint_payload(stored):
        errors.append("config_hash does not match config_payload")
    if result.schedule_hash != compute_schedule_hash(result):
        errors.append("schedule_hash does not match the schedule")
    return errors
