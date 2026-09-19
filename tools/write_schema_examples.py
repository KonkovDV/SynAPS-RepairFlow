"""Write canonical schema examples from the tiny synthetic fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from repairflow.diff import diff_plans
from repairflow.planner import plan
from repairflow.synthetic import synthesize

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schemas" / "examples"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    problem = synthesize("tiny", seed=1)
    (OUT / "tiny.problem.json").write_text(problem.model_dump_json(indent=2), encoding="utf-8")
    fifo = plan(problem, solver_config="FIFO")
    greed = plan(problem, solver_config="GREED")
    (OUT / "tiny.greed.result.json").write_text(
        greed.result.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUT / "tiny.diff.json").write_text(
        json.dumps(diff_plans(problem, fifo.result, greed.result), indent=2, default=str),
        encoding="utf-8",
    )
    sys.stdout.write(f"wrote {OUT}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
