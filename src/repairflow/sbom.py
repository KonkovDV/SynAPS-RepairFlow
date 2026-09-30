"""CycloneDX 1.5 SBOM for the direct RepairFlow runtime pins."""

from __future__ import annotations

from importlib import metadata
from typing import Any

COMPONENTS = ("synaps-repairflow", "synaps", "pydantic", "ortools")
PINNED_ORTOOLS = "9.15.6755"


def build_sbom() -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    for name in COMPONENTS:
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            version = "absent"
        if name == "ortools" and version not in {PINNED_ORTOOLS, "absent"}:
            raise RuntimeError(f"ortools {version} is not the pinned {PINNED_ORTOOLS}")
        components.append({"type": "library", "name": name, "version": version})
    try:
        app_version = metadata.version("synaps-repairflow")
    except metadata.PackageNotFoundError:
        app_version = "absent"
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": "synaps-repairflow", "version": app_version}
        },
        "components": components,
    }
