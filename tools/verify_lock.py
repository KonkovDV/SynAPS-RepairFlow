"""Fail CI when requirements-lock.txt drifts off the declared SynAPS SHA."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements-lock.txt"
VERSIONS = ROOT / "src" / "repairflow" / "versions.py"
PYPROJECT = ROOT / "pyproject.toml"
SHA_RE = re.compile(r'SYNAPS_COMMIT\s*=\s*"([0-9a-f]{40})"')


def main() -> int:
    failures: list[str] = []
    versions = VERSIONS.read_text(encoding="utf-8")
    match = SHA_RE.search(versions)
    if match is None:
        failures.append("versions.py: SYNAPS_COMMIT is not a full SHA")
        sha = ""
    else:
        sha = match.group(1)
    lock = LOCK.read_text(encoding="utf-8")
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    if sha and sha not in lock:
        failures.append(f"requirements-lock.txt: missing pin {sha}")
    if sha and sha not in pyproject:
        failures.append(f"pyproject.toml: missing pin {sha}")
    if "synaps @ git+" not in lock:
        failures.append("requirements-lock.txt: synaps is not a git pin")
    digest = hashlib.sha256(lock.encode("utf-8")).hexdigest()
    if failures:
        sys.stderr.write("lock-pin failed:\n")
        for row in failures:
            sys.stderr.write(f"  {row}\n")
        return 1
    sys.stdout.write(f"lock-pin ok synaps={sha} lock_sha256={digest}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
