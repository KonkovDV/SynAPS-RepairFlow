"""CLI: version / synthesize / solve / check / compare / report / demo / disrupt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from repairflow.diff import diff_plans
from repairflow.io import read_text_limited
from repairflow.model import PlannedAssignment, RepairFlowResult
from repairflow.normalize import load_problem
from repairflow.planner import plan, recheck, replan_after_disruption
from repairflow.report import render_html, render_markdown
from repairflow.synthetic import PRESETS, corrupt_plan, synthesize
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repairflow")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Print RepairFlow version and SynAPS pin")

    p_syn = sub.add_parser("synthesize", help="Write a synthetic repair-site JSON")
    p_syn.add_argument("--preset", default="repair-site-mvp", choices=list(PRESETS))
    p_syn.add_argument("--seed", type=int, default=42)
    p_syn.add_argument("--out", type=Path, required=True)

    p_solve = sub.add_parser("solve", help="Build a candidate schedule")
    p_solve.add_argument("input", type=Path)
    p_solve.add_argument("--preset", default="GREED", dest="solver")
    p_solve.add_argument("--out", type=Path, required=True)

    p_check = sub.add_parser("check", help="Independent checker only")
    p_check.add_argument("problem", type=Path)
    p_check.add_argument("plan", type=Path)
    p_check.add_argument("--report", type=Path, default=None)

    p_cmp = sub.add_parser("compare", help="Diff two plans")
    p_cmp.add_argument("problem", type=Path)
    p_cmp.add_argument("baseline", type=Path)
    p_cmp.add_argument("candidate", type=Path)
    p_cmp.add_argument("--out", type=Path, required=True)

    p_rep = sub.add_parser("report", help="Markdown + optional HTML/Gantt")
    p_rep.add_argument("problem", type=Path)
    p_rep.add_argument("plan", type=Path)
    p_rep.add_argument("--html", type=Path, default=None)
    p_rep.add_argument("--md", type=Path, default=None)

    p_dis = sub.add_parser("disrupt", help="Local replan; keep frozen assignments")
    p_dis.add_argument("problem", type=Path)
    p_dis.add_argument("base", type=Path)
    p_dis.add_argument("--operation-id", action="append", required=True)
    p_dis.add_argument("--out", type=Path, required=True)

    p_demo = sub.add_parser("demo", help="One-command MVP readiness run")
    p_demo.add_argument("--preset", default="repair-site-mvp")
    p_demo.add_argument("--out", type=Path, default=Path("out"))
    p_demo.add_argument("--skip-cpsat", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            sys.stdout.write(f"repairflow {REPAIRFLOW_VERSION} · synaps {SYNAPS_COMMIT}\n")
            return 0
        if args.command == "synthesize":
            problem = synthesize(args.preset, seed=args.seed)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(problem.model_dump_json(indent=2), encoding="utf-8")
            return 0
        if args.command == "solve":
            return _solve(args.input, args.out, args.solver)
        if args.command == "check":
            return _check(args.problem, args.plan, args.report)
        if args.command == "compare":
            return _compare(args.problem, args.baseline, args.candidate, args.out)
        if args.command == "report":
            return _report(args.problem, args.plan, args.html, args.md)
        if args.command == "disrupt":
            return _disrupt(args.problem, args.base, args.operation_id, args.out)
        if args.command == "demo":
            return _demo(args.preset, args.out, skip_cpsat=args.skip_cpsat)
        parser.print_help()
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError) as exc:
        sys.stderr.write(f"repairflow: {exc}\n")
        return 1


def _solve(input_path: Path, output: Path, solver: str) -> int:
    problem = load_problem(input_path)
    outcome = plan(problem, solver_config=solver)
    _write_json(output, outcome.result.model_dump(mode="json"))
    return int(outcome.result.exit_code)


def _check(problem_path: Path, plan_path: Path, report_path: Path | None) -> int:
    problem = load_problem(problem_path)
    payload = json.loads(read_text_limited(plan_path))
    result = RepairFlowResult.model_validate(payload)
    outcome = recheck(
        problem,
        assignments=list(result.assignments),
        kernel_status=result.kernel_status,
        solver_config="recheck",
    )
    if report_path is not None:
        _write_json(report_path, outcome.result.model_dump(mode="json"))
    for row in outcome.result.violations:
        sys.stdout.write(f"{row.code}\t{row.message}\n")
    return int(outcome.result.exit_code)


def _compare(problem_path: Path, baseline_path: Path, candidate_path: Path, output: Path) -> int:
    problem = load_problem(problem_path)
    baseline = RepairFlowResult.model_validate_json(read_text_limited(baseline_path))
    candidate = RepairFlowResult.model_validate_json(read_text_limited(candidate_path))
    payload = diff_plans(problem, baseline, candidate)
    _write_json(output, payload)
    return 0 if not payload["broken_frozen_assignments"] else 2


def _report(problem_path: Path, plan_path: Path, html_path: Path | None, md_path: Path | None) -> int:
    problem = load_problem(problem_path)
    result = RepairFlowResult.model_validate_json(read_text_limited(plan_path))
    markdown = render_markdown(problem, result)
    if md_path is not None:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown + "\n")
    if html_path is not None:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html(problem, result), encoding="utf-8")
    return 0 if result.verified_feasible else 2


def _disrupt(problem_path: Path, base_path: Path, operation_ids: list[str], output: Path) -> int:
    problem = load_problem(problem_path)
    base_result = RepairFlowResult.model_validate_json(read_text_limited(base_path))
    base = recheck(
        problem,
        assignments=list(base_result.assignments),
        kernel_status=base_result.kernel_status,
        solver_config=base_result.solver_config or "GREED",
    )
    outcome = replan_after_disruption(
        problem,
        base=base,
        disrupted_operation_ids=operation_ids,
    )
    _write_json(output, outcome.result.model_dump(mode="json"))
    return int(outcome.result.exit_code)


def _demo(preset: str, out_dir: Path, *, skip_cpsat: bool) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    problem = synthesize("repair-site-mvp" if preset == "broken-seed42" else preset, seed=42)
    problem_path = out_dir / "repair-site-mvp.json"
    problem_path.write_text(problem.model_dump_json(indent=2), encoding="utf-8")

    fifo = plan(problem, solver_config="FIFO")
    _write_json(out_dir / "fifo.json", fifo.result.model_dump(mode="json"))
    greed = plan(problem, solver_config="GREED")
    _write_json(out_dir / "greed.json", greed.result.model_dump(mode="json"))
    compare = diff_plans(problem, fifo.result, greed.result)
    _write_json(out_dir / "compare.json", compare)
    (out_dir / "greed.md").write_text(render_markdown(problem, greed.result), encoding="utf-8")
    (out_dir / "greed.html").write_text(render_html(problem, greed.result), encoding="utf-8")
    (out_dir / "fifo.html").write_text(render_html(problem, fifo.result), encoding="utf-8")

    disrupted = ["JOB-06-02"] if any(op.id == "JOB-06-02" for op in problem.operations) else [
        problem.operations[-1].id
    ]
    replanned = replan_after_disruption(problem, base=greed, disrupted_operation_ids=disrupted)
    _write_json(out_dir / "replan.json", replanned.result.model_dump(mode="json"))
    frozen_kept = diff_plans(problem, greed.result, replanned.result)
    _write_json(out_dir / "replan-diff.json", frozen_kept)

    broken_assignments = corrupt_plan(
        [row.model_dump(mode="json") for row in greed.result.assignments]
    )
    broken_result = greed.result.model_copy(
        update={
            "assignments": [PlannedAssignment.model_validate(row) for row in broken_assignments],
            "instance_id": "broken-seed42",
        }
    )
    broken_check = recheck(
        problem,
        assignments=list(broken_result.assignments),
        kernel_status=broken_result.kernel_status,
        solver_config="broken-demo",
    )
    _write_json(out_dir / "broken.json", broken_check.result.model_dump(mode="json"))
    (out_dir / "broken.html").write_text(render_html(problem, broken_check.result), encoding="utf-8")

    cpsat_ok = True
    cpsat_line = "  CPSAT skipped\n"
    if not skip_cpsat:
        tiny = synthesize("tiny", seed=1)
        tiny_path = out_dir / "tiny.json"
        tiny_path.write_text(tiny.model_dump_json(indent=2), encoding="utf-8")
        cpsat = plan(tiny, solver_config="CPSAT-10")
        _write_json(out_dir / "cpsat.json", cpsat.result.model_dump(mode="json"))
        cpsat_ok = cpsat.result.status.value == "OPTIMAL" and cpsat.result.verified_feasible
        cpsat_line = (
            f"  CPSAT status={cpsat.result.status.value} verified={cpsat.result.verified_feasible} "
            f"exit={cpsat.result.exit_code}\n"
        )

    sys.stdout.write(
        "RepairFlow demo\n"
        f"  FIFO violations={len(fifo.result.violations)} exit={fifo.result.exit_code}\n"
        f"  GREED violations={len(greed.result.violations)} verified={greed.result.verified_feasible} "
        f"exit={greed.result.exit_code}\n"
        f"{cpsat_line}"
        f"  input_hash={greed.result.input_hash}\n"
        f"  config_hash={greed.result.config_hash}\n"
        f"  synaps={SYNAPS_COMMIT}\n"
        f"  frozen_broken={len(frozen_kept['broken_frozen_assignments'])}\n"
        f"  broken exit={broken_check.result.exit_code} codes="
        f"{sorted({row.code for row in broken_check.result.violations})}\n"
    )
    clean_ok = greed.result.exit_code == 0 and greed.result.verified_feasible
    fifo_dirty = fifo.result.exit_code == 2 and len(fifo.result.violations) > 0
    broken_ok = broken_check.result.exit_code == 2
    frozen_ok = len(frozen_kept["broken_frozen_assignments"]) == 0
    if clean_ok and fifo_dirty and broken_ok and frozen_ok and cpsat_ok:
        sys.stdout.write("MVP readiness: PASS\n")
        return 0
    sys.stderr.write("MVP readiness: FAIL\n")
    return 1


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
