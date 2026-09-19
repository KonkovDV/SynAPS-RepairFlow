"""Pack a hashed laboratory evidence folder from the MVP fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from repairflow.diff import diff_plans
from repairflow.planner import plan
from repairflow.report import render_html, render_markdown
from repairflow.synthetic import synthesize
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT

ROOT = Path(__file__).resolve().parents[1]


def pack(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    problem = synthesize("repair-site-mvp", seed=42)
    fifo = plan(problem, solver_config="FIFO")
    greed = plan(problem, solver_config="GREED")
    compare = diff_plans(problem, fifo.result, greed.result)
    (out_dir / "repair-site-mvp.json").write_text(problem.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "fifo.json").write_text(fifo.result.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "greed.json").write_text(greed.result.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "compare.json").write_text(
        json.dumps(compare, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    (out_dir / "greed.md").write_text(render_markdown(problem, greed.result), encoding="utf-8")
    (out_dir / "greed.html").write_text(render_html(problem, greed.result), encoding="utf-8")
    (out_dir / "fifo.html").write_text(render_html(problem, fifo.result), encoding="utf-8")
    summary = {
        "repairflow_version": REPAIRFLOW_VERSION,
        "synaps_commit": SYNAPS_COMMIT,
        "instance_id": problem.instance_id,
        "operations": len(problem.operations),
        "fifo_exit_code": fifo.result.exit_code,
        "fifo_violations": len(fifo.result.violations),
        "greed_exit_code": greed.result.exit_code,
        "greed_verified": greed.result.verified_feasible,
        "input_hash": greed.result.input_hash,
        "config_hash": greed.result.config_hash,
        "result_hash": greed.result.result_hash,
        "claim_level": greed.result.claim_level,
        "data_provenance": greed.result.data_provenance,
    }
    (out_dir / "hashes.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "checker.json").write_text(
        json.dumps(
            {
                "fifo": [row.model_dump(mode="json") for row in fifo.result.violations],
                "greed": [row.model_dump(mode="json") for row in greed.result.violations],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    target = Path("out") / "evidence"
    if argv and len(argv) >= 2 and argv[0] == "--out":
        target = Path(argv[1])
    summary = pack(target)
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["greed_verified"] and summary["fifo_exit_code"] == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
