"""Compare FIFO vs GREED on the synthetic repair-site fixture."""

from __future__ import annotations

import json
from pathlib import Path

from repairflow.diff import diff_plans
from repairflow.planner import plan
from repairflow.synthetic import synthesize


def main() -> int:
    problem = synthesize("repair-site-mvp", seed=42)
    fifo = plan(problem, solver_config="FIFO")
    greed = plan(problem, solver_config="GREED")
    payload = diff_plans(problem, fifo.result, greed.result)
    out = Path("benchmark") / "results" / "compare_baselines.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"FIFO violations={len(fifo.result.violations)} "
        f"GREED violations={len(greed.result.violations)} "
        f"verified={greed.result.verified_feasible}"
    )
    return 0 if greed.result.verified_feasible else 2


if __name__ == "__main__":
    raise SystemExit(main())
