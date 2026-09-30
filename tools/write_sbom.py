"""Write a CycloneDX SBOM for the pinned runtime."""

from __future__ import annotations

import json

from repairflow.sbom import build_sbom


def main() -> int:
    print(json.dumps(build_sbom(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
