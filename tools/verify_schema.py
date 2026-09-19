"""Validate every committed JSON example against its public v1 schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {
    "problem": ROOT / "schemas" / "repairflow.problem.v1.json",
    "result": ROOT / "schemas" / "repairflow.result.v1.json",
    "diff": ROOT / "schemas" / "repairflow.diff.v1.json",
}
EXAMPLES = {
    "problem": sorted((ROOT / "schemas" / "examples").glob("*.problem.json")),
    "result": sorted((ROOT / "schemas" / "examples").glob("*.result.json")),
    "diff": sorted((ROOT / "schemas" / "examples").glob("*.diff.json")),
}


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def validate(kind: str, schema: dict[str, Any], paths: list[Path]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    failures: list[str] = []
    for path in paths:
        document = load(path)
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "$"
            failures.append(f"{path.relative_to(ROOT)} [{kind}] {location}: {error.message}")
        expected = f"repairflow.{kind}.v1"
        if document.get("schema_version") != expected:
            failures.append(
                f"{path.relative_to(ROOT)} [{kind}] $: "
                f"schema_version={document.get('schema_version')!r}, expected {expected!r}"
            )
    return failures


def main() -> int:
    failures: list[str] = []
    for kind, schema_path in SCHEMAS.items():
        schema = load(schema_path)
        paths = EXAMPLES[kind]
        if not paths:
            failures.append(f"no committed {kind} examples found")
            continue
        failures.extend(validate(kind, schema, paths))
    if failures:
        print("schema verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    counts = ", ".join(f"{kind}={len(EXAMPLES[kind])}" for kind in SCHEMAS)
    print(f"schema verification ok: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
