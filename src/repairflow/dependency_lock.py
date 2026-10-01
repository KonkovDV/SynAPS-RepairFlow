"""Transitive archive lock. A signature is never invented.

The lock is ``locked`` only when every component already has a wheel or sdist
SHA-256. An editable install or a missing hash stays ``incomplete``. Signature
status stays ``absent``: this build has no release key.
"""

from __future__ import annotations

from typing import Any

from repairflow.evidence import fingerprint_payload

LOCK_SCHEMA = "repairflow.dependency_lock.v1"


def build_dependency_lock(artifact_record: dict[str, Any]) -> dict[str, Any]:
    components_in = artifact_record.get("components")
    if not isinstance(components_in, list):
        raise ValueError("artifact record has no components")
    published: list[dict[str, Any]] = []
    incomplete = not components_in
    for row in components_in:
        if not isinstance(row, dict):
            raise ValueError("lock component must be an object")
        archive = row.get("archive")
        if not isinstance(archive, dict):
            raise ValueError("lock component is missing an archive")
        digest = archive.get("sha256")
        present = archive.get("status") == "present" and isinstance(digest, str) and len(digest) == 64
        if not present:
            incomplete = True
        published.append(
            {
                "name": str(row.get("name", "")),
                "version": str(row.get("version", "")),
                "scope": row.get("scope") if row.get("scope") in {"direct", "transitive"} else "transitive",
                "sha256": digest if present else None,
                "status": "present" if present else "absent",
            }
        )
    body: dict[str, Any] = {
        "schema": LOCK_SCHEMA,
        "status": "incomplete" if incomplete else "locked",
        "signature": {"status": "absent", "sha256": None},
        "components": published,
    }
    body["lock_sha256"] = fingerprint_payload(
        {key: value for key, value in body.items() if key != "lock_sha256"}
    )
    return body
