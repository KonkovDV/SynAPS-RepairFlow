"""CycloneDX 1.5 SBOM and installed-runtime binding for RepairFlow."""

from __future__ import annotations

import hashlib
from importlib import metadata
from typing import Any

from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT

COMPONENTS = ("synaps-repairflow", "synaps", "pydantic", "ortools")
PINNED_ORTOOLS = "9.15.6755"


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "absent"


def _file_manifest(name: str) -> tuple[str, list[dict[str, str]]]:
    """Hash every installed file advertised by a distribution's RECORD."""

    try:
        distribution = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return "absent", []

    files: list[dict[str, str]] = []
    for relative in sorted(distribution.files or [], key=str):
        relative_path = str(relative)
        path = distribution.locate_file(relative_path)
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": relative_path, "sha256": digest})
    if not files:
        return "empty", []
    manifest = "\n".join(f"{row['path']}\0{row['sha256']}" for row in files)
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest(), files


def runtime_binding() -> dict[str, Any]:
    """Return a deterministic binding of direct packages to installed files.

    This is offline evidence about the installed distribution trees. It is not
    a signed wheel hash, a supply-chain attestation, or a license report.
    """

    components: list[dict[str, Any]] = []
    for name in COMPONENTS:
        manifest_sha256, files = _file_manifest(name)
        components.append(
            {
                "name": name,
                "version": _version(name),
                "manifest_sha256": manifest_sha256,
                "file_count": len(files),
                "files": files,
            }
        )
    return {
        "schema": "repairflow.runtime_binding.v1",
        "repairflow_version": REPAIRFLOW_VERSION,
        "synaps_commit": SYNAPS_COMMIT,
        "components": components,
    }


def build_sbom() -> dict[str, Any]:
    binding = runtime_binding()
    components: list[dict[str, Any]] = []
    for row in binding["components"]:
        name = str(row["name"])
        version = str(row["version"])
        if name == "ortools" and version not in {PINNED_ORTOOLS, "absent"}:
            raise RuntimeError(f"ortools {version} is not the pinned {PINNED_ORTOOLS}")
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "properties": [
                    {
                        "name": "repairflow:installed_file_manifest_sha256",
                        "value": str(row["manifest_sha256"]),
                    },
                    {
                        "name": "repairflow:installed_file_count",
                        "value": str(row["file_count"]),
                    },
                ],
            }
        )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "synaps-repairflow",
                "version": binding["repairflow_version"],
            }
        },
        "components": components,
        "runtime_binding": binding,
    }
