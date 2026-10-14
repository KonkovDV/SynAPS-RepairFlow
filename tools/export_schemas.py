"""Export Pydantic v1 contracts and reject documents the model forbids.

Hand-written schemas stay the short public sketch. The generated files are the
strict contract (`extra=forbid`) used by the negative-fixture check.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schemas" / "generated"
EXAMPLES = ROOT / "schemas" / "examples"
NEGATIVE = ROOT / "schemas" / "negative"


def _schema(model: type, schema_id: str) -> dict[str, Any]:
    document = model.model_json_schema()
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    document["$id"] = schema_id
    required = list(document.get("required") or [])
    if "schema_version" not in required:
        required.append("schema_version")
    document["required"] = required
    return document


def generated_schemas() -> dict[str, dict[str, Any]]:
    from repairflow.model import RepairFlowProblem, RepairFlowResult

    return {
        "repairflow.problem.v1": _schema(
            RepairFlowProblem,
            "https://github.com/KonkovDV/SynAPS-RepairFlow/schemas/generated/repairflow.problem.v1.json",
        ),
        "repairflow.result.v1": _schema(
            RepairFlowResult,
            "https://github.com/KonkovDV/SynAPS-RepairFlow/schemas/generated/repairflow.result.v1.json",
        ),
    }


def write_schemas() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, document in generated_schemas().items():
        path = OUT / f"{name}.json"
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be an object")
    return value


def check_documents() -> list[str]:
    failures: list[str] = []
    schemas = generated_schemas()
    committed = {path.name: _load(path) for path in OUT.glob("*.json")}
    for name, document in schemas.items():
        filename = f"{name}.json"
        if committed.get(filename) != document:
            failures.append(f"{filename} drifted from Pydantic; run tools/export_schemas.py --write")
    problem_validator = Draft202012Validator(schemas["repairflow.problem.v1"], format_checker=FormatChecker())
    for path in sorted(EXAMPLES.glob("*.problem.json")):
        errors = list(problem_validator.iter_errors(_load(path)))
        for error in errors:
            failures.append(f"{path.name}: {error.message}")
    if not list(NEGATIVE.glob("*.json")):
        failures.append("schemas/negative has no fixtures")
    for path in sorted(NEGATIVE.glob("*.json")):
        errors = list(problem_validator.iter_errors(_load(path)))
        if not errors:
            failures.append(f"{path.name} was accepted; a negative fixture must fail")
    return failures


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--write" in args:
        write_schemas()
        print(f"wrote {OUT}")
        return 0
    failures = check_documents()
    if failures:
        print("schema export check failed:", file=sys.stderr)
        for row in failures:
            print(f"  {row}", file=sys.stderr)
        return 1
    print("schema export check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
