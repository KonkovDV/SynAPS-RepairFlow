"""Stable hashing, provenance and evidence bundle helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from repairflow.versions import CLAIM_LEVEL, ISO16290_TRL, REPAIRFLOW_VERSION, SYNAPS_COMMIT


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


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
