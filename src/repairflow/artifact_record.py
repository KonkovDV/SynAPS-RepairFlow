"""Offline wheel and source identity, distinct from the installed-file manifest.

The record hashes an archive the caller already has, or reads a PEP 610
``direct_url.json`` that pip wrote at install time. It does not download
packages, does not invent a missing digest, and does not claim a signature.
"""

from __future__ import annotations

import hashlib
import json
from importlib import metadata
from pathlib import Path
from typing import Any

from repairflow.evidence import fingerprint_payload
from repairflow.sbom import COMPONENTS
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT

ARTIFACT_SCHEMA = "repairflow.artifact_record.v1"
_DIRECT = frozenset(name.lower().replace("_", "-") for name in COMPONENTS)
_ARCHIVE_KEYS = ("status", "kind", "sha256", "filename", "source_url", "size_bytes")


def _canon(name: str) -> str:
    return name.lower().replace("_", "-")


def _kind(filename: str | None) -> str | None:
    if filename is None:
        return None
    if filename.endswith(".whl"):
        return "wheel"
    if filename.endswith(".tar.gz") or filename.endswith(".zip"):
        return "sdist"
    return None


def _sha256_token(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith("sha256="):
        return None
    digest = value.removeprefix("sha256=").lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        return None
    return digest


def _url(payload: dict[str, Any]) -> str | None:
    url = payload.get("url")
    if not isinstance(url, str) or not url:
        return None
    return url


def _filename(url: object) -> str | None:
    if not isinstance(url, str) or not url or url.endswith("/"):
        return None
    name = url.rsplit("/", 1)[-1]
    return name or None


def _archive(
    *,
    status: str,
    kind: str | None = None,
    sha256: str | None = None,
    filename: str | None = None,
    source_url: str | None = None,
    size_bytes: int | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "kind": kind,
        "sha256": sha256,
        "filename": filename,
        "source_url": source_url,
        "size_bytes": size_bytes,
    }


def hash_archive(path: Path) -> dict[str, Any]:
    """SHA-256 of one local wheel or sdist. The digest is of the archive bytes."""

    filename = path.name
    kind = _kind(filename)
    if kind is None:
        raise ValueError(f"unsupported artifact suffix: {filename}")
    data = path.read_bytes()
    return _archive(
        status="present",
        kind=kind,
        sha256=hashlib.sha256(data).hexdigest(),
        filename=filename,
        size_bytes=len(data),
    )


def archive_identity_from_direct_url(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Classify one PEP 610 record. A missing hash stays absent."""

    if payload is None:
        return _archive(status="absent")
    source_url = _url(payload)
    archive = payload.get("archive_info")
    if isinstance(archive, dict):
        filename = _filename(payload.get("url"))
        digest = _sha256_token(archive.get("hash"))
        if digest is None:
            status = "unsupported_hash" if archive.get("hash") else "absent"
            return _archive(status=status, filename=filename, source_url=source_url)
        return _archive(
            status="present",
            kind=_kind(filename),
            sha256=digest,
            filename=filename,
            source_url=source_url,
        )
    if isinstance(payload.get("dir_info"), dict):
        return _archive(status="editable", kind="source_tree", source_url=source_url)
    return _archive(status="absent", source_url=source_url)


def _require_archive(archive: dict[str, Any]) -> dict[str, Any]:
    status = archive.get("status")
    digest = archive.get("sha256")
    if status not in {"present", "absent", "editable", "unsupported_hash"}:
        raise ValueError(f"unsupported archive status: {status}")
    if status == "present":
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("present archive requires sha256")
    elif digest is not None:
        raise ValueError("sha256 requires status present")
    published = _archive(
        status=str(status),
        kind=archive.get("kind") if isinstance(archive.get("kind"), str) else None,
        sha256=digest if isinstance(digest, str) else None,
        filename=archive.get("filename") if isinstance(archive.get("filename"), str) else None,
        source_url=archive.get("source_url") if isinstance(archive.get("source_url"), str) else None,
        size_bytes=archive.get("size_bytes") if isinstance(archive.get("size_bytes"), int) else None,
    )
    return {key: published[key] for key in _ARCHIVE_KEYS}


def build_artifact_record(components: list[dict[str, Any]]) -> dict[str, Any]:
    """Publish one record. Signature status is always absent."""

    published: list[dict[str, Any]] = []
    ordered = sorted(
        components,
        key=lambda item: (
            0 if item.get("scope") == "direct" else 1,
            _canon(str(item.get("name", ""))),
            str(item.get("version", "")),
            str(item.get("archive", {}).get("filename") or ""),
        ),
    )
    for row in ordered:
        scope = row.get("scope")
        if scope not in {"direct", "transitive"}:
            raise ValueError("scope must be direct or transitive")
        archive = row.get("archive")
        if not isinstance(archive, dict):
            raise ValueError("component archive must be an object")
        published.append(
            {
                "name": str(row.get("name", "")),
                "version": str(row.get("version", "")),
                "scope": scope,
                "archive": _require_archive(archive),
                "signature": {"status": "absent", "sha256": None},
            }
        )
    body: dict[str, Any] = {
        "schema": ARTIFACT_SCHEMA,
        "repairflow_version": REPAIRFLOW_VERSION,
        "synaps_commit": SYNAPS_COMMIT,
        "claim_level": "experiment",
        "lockfile_status": "absent",
        "closure_status": "installed_environment_not_a_lock",
        "identities": {
            "runtime_file_manifest": {
                "schema": "repairflow.runtime_binding.v1",
                "role": "installed_file_digest",
                "is_wheel_hash": False,
                "is_signature": False,
            },
            "wheel_or_source": {
                "role": "archive_digest",
                "is_runtime_file_manifest": False,
                "is_signature": False,
            },
            "signature": {
                "role": "detached_signature",
                "status": "absent",
                "is_runtime_file_manifest": False,
                "is_wheel_hash": False,
            },
        },
        "components": published,
    }
    body["record_sha256"] = fingerprint_payload(
        {key: value for key, value in body.items() if key != "record_sha256"}
    )
    return body


def installed_artifact_record() -> dict[str, Any]:
    """Read installed distributions. This environment is not a lockfile."""

    components: list[dict[str, Any]] = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if not isinstance(name, str) or not name:
            continue
        raw = dist.read_text("direct_url.json")
        payload: dict[str, Any] | None
        if raw is None:
            payload = None
        else:
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                raise ValueError(f"{name} direct_url.json is not an object")
            payload = loaded
        components.append(
            {
                "name": name,
                "version": dist.version,
                "scope": "direct" if _canon(name) in _DIRECT else "transitive",
                "archive": archive_identity_from_direct_url(payload),
            }
        )
    return build_artifact_record(components)
