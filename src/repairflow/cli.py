"""CLI for the repair-flow experiment, including decide and the operator log."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from repairflow.benchmark import run_benchmark
from repairflow.decision_log import (
    Decision,
    decision_log_witness,
    format_decision_stats,
    read_decision_log,
    record_checked_decision,
    verify_decision_log,
)
from repairflow.diff import diff_plans
from repairflow.domain_verify import verify_domain_plan
from repairflow.events import InspectionEvent, PostDown, apply_disruption
from repairflow.evidence import verify_plan_hashes
from repairflow.explanations import deletion_minimal_operation_ids
from repairflow.io import read_text_limited
from repairflow.model import PlannedAssignment, RepairFlowResult
from repairflow.normalize import load_problem
from repairflow.planner import (
    plan,
    recheck,
    replan_after_disruption,
    replan_after_inspection,
    replan_disruption,
)
from repairflow.report import render_html, render_markdown
from repairflow.shop_plan import format_shop_finding, load_shop_plan, write_shop_plan
from repairflow.synthetic import PRESETS, corrupt_plan, synthesize
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repairflow")
    sub = parser.add_subparsers(dest="command")
    salted = argparse.ArgumentParser(add_help=False)
    salted.add_argument(
        "--crew-salt",
        default=None,
        help="HMAC salt for a personnel number. The salt is not stored.",
    )

    sub.add_parser("version", help="Print RepairFlow version and SynAPS pin")

    p_syn = sub.add_parser("synthesize", help="Write a synthetic repair-site JSON")
    p_syn.add_argument("--preset", default="repair-site-mvp", choices=list(PRESETS))
    p_syn.add_argument("--seed", type=int, default=42)
    p_syn.add_argument("--out", type=Path, required=True)

    p_solve = sub.add_parser("solve", parents=[salted], help="Build a candidate schedule")
    p_solve.add_argument("input", type=Path)
    p_solve.add_argument("--preset", default="GREED", dest="solver")
    p_solve.add_argument("--out", type=Path, required=True)

    p_check = sub.add_parser("check", parents=[salted], help="Independent checker only")
    p_check.add_argument("problem", type=Path)
    p_check.add_argument("plan", type=Path)
    p_check.add_argument("--report", type=Path, default=None)
    p_check.add_argument(
        "--verify-hashes",
        action="store_true",
        help="Refuse the plan when input, result, or config hashes do not match",
    )

    p_shop = sub.add_parser(
        "verify-plan",
        parents=[salted],
        help="Domain notary for a shop CSV plan; does not call the kernel",
    )
    p_shop.add_argument("--problem", type=Path, required=True)
    p_shop.add_argument("--plan", type=Path, required=True)
    p_shop.add_argument("--out", type=Path, default=None)

    p_cmp = sub.add_parser("compare", parents=[salted], help="Diff two plans")
    p_cmp.add_argument("problem", type=Path)
    p_cmp.add_argument("baseline", type=Path)
    p_cmp.add_argument("candidate", type=Path)
    p_cmp.add_argument("--out", type=Path, required=True)

    p_rep = sub.add_parser("report", parents=[salted], help="Markdown + optional HTML/Gantt")
    p_rep.add_argument("problem", type=Path)
    p_rep.add_argument("plan", type=Path)
    p_rep.add_argument("--html", type=Path, default=None)
    p_rep.add_argument("--md", type=Path, default=None)

    p_dis = sub.add_parser("disrupt", parents=[salted], help="Local replan; keep frozen assignments")
    p_dis.add_argument("problem", type=Path)
    p_dis.add_argument("base", type=Path)
    p_dis.add_argument("--operation-id", action="append", required=True)
    p_dis.add_argument("--out", type=Path, required=True)

    p_ins = sub.add_parser(
        "inspect",
        parents=[salted],
        help="Reveal a defect branch and replan other units frozen",
    )
    p_ins.add_argument("problem", type=Path)
    p_ins.add_argument("plan", type=Path)
    p_ins.add_argument("event", type=Path)
    p_ins.add_argument("--out", type=Path, required=True)

    p_demo = sub.add_parser("demo", help="One-command MVP readiness run")
    p_demo.add_argument("--preset", default="repair-site-mvp")
    p_demo.add_argument("--out", type=Path, default=Path("out"))
    p_demo.add_argument("--skip-cpsat", action="store_true")

    p_bench = sub.add_parser(
        "benchmark",
        help="FIFO vs GREED portfolio benchmark across preset/seed matrix",
    )
    p_bench.add_argument(
        "--out",
        type=Path,
        default=Path("bench"),
        help="Output directory for benchmark.json / .md / .html and per-instance reports",
    )
    p_bench.add_argument(
        "--solvers",
        nargs="+",
        default=["FIFO", "GREED"],
        metavar="SOLVER",
        help="Solver configs to compare (default: FIFO GREED)",
    )
    p_bench.add_argument(
        "--preset",
        nargs="+",
        default=None,
        metavar="PRESET",
        choices=list(PRESETS),
        help="Restrict to those presets (filters DEFAULT_MATRIX unless --seeds is also set)",
    )
    p_bench.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=None,
        metavar="SEED",
        help="Filter default matrix by seed. Combined with --preset, runs that cartesian product.",
    )

    p_decide = sub.add_parser("decide", help="Record an operator decision against a checked plan")
    p_decide.add_argument("--problem", type=Path, required=True)
    p_decide.add_argument("--result", type=Path, required=True)
    p_decide.add_argument("--operator-code", required=True)
    p_decide.add_argument("--log", type=Path, required=True)
    p_decide.add_argument("--reason", default="")
    choice = p_decide.add_mutually_exclusive_group(required=True)
    choice.add_argument("--accept", action="store_true")
    choice.add_argument("--accept-with-edits", dest="edit_summary")
    choice.add_argument("--reject", action="store_true")

    p_log = sub.add_parser("log", help="Verify or summarize an operator decision log")
    log_sub = p_log.add_subparsers(dest="log_command")
    p_verify = log_sub.add_parser("verify", help="Check the hash chain")
    p_verify.add_argument("log", type=Path)
    p_verify.add_argument("--head", default=None)
    p_verify.add_argument("--witness", default=None)
    p_verify.add_argument("--key-file", type=Path, default=None)
    p_witness = log_sub.add_parser("witness", help="HMAC the log tip with an operator key")
    p_witness.add_argument("log", type=Path)
    p_witness.add_argument("--key-file", type=Path, required=True)
    p_stats = log_sub.add_parser("stats", help="Print counters without operator codes")
    p_stats.add_argument("log", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            sys.stdout.write(f"repairflow {REPAIRFLOW_VERSION} \u00b7 synaps {SYNAPS_COMMIT}\n")
            return 0
        if args.command == "synthesize":
            problem = synthesize(args.preset, seed=args.seed)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(problem.model_dump_json(indent=2), encoding="utf-8")
            return 0
        if args.command == "solve":
            return _solve(args.input, args.out, args.solver, crew_salt=args.crew_salt)
        if args.command == "check":
            return _check(
                args.problem,
                args.plan,
                args.report,
                verify_hashes=args.verify_hashes,
                crew_salt=args.crew_salt,
            )
        if args.command == "verify-plan":
            return _verify_plan(args.problem, args.plan, args.out, crew_salt=args.crew_salt)
        if args.command == "compare":
            return _compare(
                args.problem,
                args.baseline,
                args.candidate,
                args.out,
                crew_salt=args.crew_salt,
            )
        if args.command == "report":
            return _report(args.problem, args.plan, args.html, args.md, crew_salt=args.crew_salt)
        if args.command == "disrupt":
            return _disrupt(
                args.problem,
                args.base,
                args.operation_id,
                args.out,
                crew_salt=args.crew_salt,
            )
        if args.command == "inspect":
            return _inspect(args.problem, args.plan, args.event, args.out, crew_salt=args.crew_salt)
        if args.command == "demo":
            return _demo(args.preset, args.out, skip_cpsat=args.skip_cpsat)
        if args.command == "benchmark":
            return _benchmark(
                out_dir=args.out,
                solvers=args.solvers,
                presets=args.preset,
                seeds=args.seeds,
            )
        if args.command == "decide":
            return _decide(args)
        if args.command == "log":
            return _log(args)
        parser.print_help()
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError, RecursionError) as exc:
        sys.stderr.write(f"repairflow: {exc}\n")
        return 1


def _decide(args: argparse.Namespace) -> int:
    if args.reject:
        decision = Decision.REJECTED
        edit_summary = ""
    elif args.edit_summary is not None:
        decision = Decision.ACCEPTED_WITH_EDITS
        edit_summary = str(args.edit_summary)
    else:
        decision = Decision.ACCEPTED
        edit_summary = ""
    event = record_checked_decision(
        problem_path=args.problem,
        result_path=args.result,
        decision=decision,
        operator_code=args.operator_code,
        log_path=args.log,
        reason=args.reason,
        edit_summary=edit_summary,
    )
    sys.stdout.write(event.event_hash + "\n")
    return 0


def _witness_key(path: Path | None) -> bytes | None:
    if path is None:
        return None
    key = path.read_bytes().strip()
    if not key:
        raise ValueError("decision log witness key is empty")
    return key


def _log(args: argparse.Namespace) -> int:
    if args.log_command == "verify":
        version = verify_decision_log(
            args.log,
            head=args.head,
            witness=args.witness,
            witness_key=_witness_key(args.key_file),
        )
        events = read_decision_log(args.log)
        tip = events[-1].event_hash if events and version == "v2" else ""
        sys.stdout.write(f"decision-log {version} events={len(events)} head={tip}\n")
        return 0
    if args.log_command == "witness":
        key = _witness_key(args.key_file)
        if key is None:
            raise ValueError("decision log witness key is empty")
        sys.stdout.write(decision_log_witness(args.log, key) + "\n")
        return 0
    if args.log_command == "stats":
        sys.stdout.write(format_decision_stats(read_decision_log(args.log)))
        return 0
    raise ValueError("log command must be verify, witness, or stats")


def _solve(input_path: Path, output: Path, solver: str, *, crew_salt: str | None) -> int:
    problem = load_problem(input_path, crew_salt=crew_salt)
    outcome = plan(problem, solver_config=solver)
    _write_json(output, outcome.result.model_dump(mode="json"))
    return int(outcome.result.exit_code)


def _check(
    problem_path: Path,
    plan_path: Path,
    report_path: Path | None,
    *,
    verify_hashes: bool = False,
    crew_salt: str | None = None,
) -> int:
    problem = load_problem(problem_path, crew_salt=crew_salt)
    payload = json.loads(read_text_limited(plan_path))
    result = RepairFlowResult.model_validate(payload)
    if verify_hashes:
        mismatches = verify_plan_hashes(problem, result)
        if mismatches:
            for row in mismatches:
                sys.stderr.write(f"repairflow: {row}\n")
            return 1
    outcome = recheck(
        problem,
        assignments=list(result.assignments),
        kernel_status=result.kernel_status,
        solver_config="recheck",
    )
    if report_path is not None:
        _write_json(report_path, outcome.result.model_dump(mode="json"))
    for violation in outcome.result.violations:
        sys.stdout.write(f"{violation.code}\t{violation.message}\n")
    return int(outcome.result.exit_code)


def _verify_plan(
    problem_path: Path,
    plan_path: Path,
    output: Path | None,
    *,
    crew_salt: str | None = None,
) -> int:
    problem = load_problem(problem_path, crew_salt=crew_salt)
    assignments, extra, sources, digest = load_shop_plan(plan_path, problem)
    result = verify_domain_plan(
        problem,
        assignments,
        extra_violations=extra,
        source_rows=sources,
        shop_file=(plan_path.name, digest),
    )
    if output is not None:
        _write_json(output, result.model_dump(mode="json"))
    if result.claim_status == "domain_verified":
        sys.stdout.write("domain_verified\tдоменный план проверен без ядра; это не вердикт ядра\n")
    for violation in result.violations:
        if violation.severity == "kpi":
            continue
        text = format_shop_finding(violation)
        sys.stdout.write(text + "\n")
    return int(result.exit_code)


def _compare(
    problem_path: Path,
    baseline_path: Path,
    candidate_path: Path,
    output: Path,
    *,
    crew_salt: str | None = None,
) -> int:
    problem = load_problem(problem_path, crew_salt=crew_salt)
    baseline = RepairFlowResult.model_validate_json(read_text_limited(baseline_path))
    candidate = RepairFlowResult.model_validate_json(read_text_limited(candidate_path))
    payload = diff_plans(problem, baseline, candidate)
    _write_json(output, payload)
    return 0 if not payload["broken_frozen_assignments"] else 2


def _report(
    problem_path: Path,
    plan_path: Path,
    html_path: Path | None,
    md_path: Path | None,
    *,
    crew_salt: str | None = None,
) -> int:
    problem = load_problem(problem_path, crew_salt=crew_salt)
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


def _inspect(
    problem_path: Path,
    plan_path: Path,
    event_path: Path,
    output: Path,
    *,
    crew_salt: str | None = None,
) -> int:
    problem = load_problem(problem_path, crew_salt=crew_salt)
    base = RepairFlowResult.model_validate_json(read_text_limited(plan_path))
    event = InspectionEvent.model_validate_json(read_text_limited(event_path))
    outcome = replan_after_inspection(problem, base=base, event=event)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output, outcome.result.model_dump(mode="json"))
    return int(outcome.result.exit_code)


def _disrupt(
    problem_path: Path,
    base_path: Path,
    operation_ids: list[str],
    output: Path,
    *,
    crew_salt: str | None = None,
) -> int:
    problem = load_problem(problem_path, crew_salt=crew_salt)
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
    greed_path = out_dir / "greed.json"
    _write_json(greed_path, greed.result.model_dump(mode="json"))
    compare = diff_plans(problem, fifo.result, greed.result)
    _write_json(out_dir / "compare.json", compare)
    (out_dir / "greed.md").write_text(render_markdown(problem, greed.result), encoding="utf-8")
    (out_dir / "greed.html").write_text(render_html(problem, greed.result), encoding="utf-8")
    (out_dir / "fifo.html").write_text(render_html(problem, fifo.result), encoding="utf-8")

    disrupted = (
        ["JOB-06-02"]
        if any(op.id == "JOB-06-02" for op in problem.operations)
        else [problem.operations[-1].id]
    )
    replanned = replan_after_disruption(problem, base=greed, disrupted_operation_ids=disrupted)
    _write_json(out_dir / "replan.json", replanned.result.model_dump(mode="json"))
    frozen_kept = diff_plans(problem, greed.result, replanned.result)
    _write_json(out_dir / "replan-diff.json", frozen_kept)
    issued_frozen = {row.operation_id for row in problem.frozen_assignments if row.immutable}
    # The latest visit keeps the released lane tail short. An early hole on a
    # packed post can leave the list repair with an uncovered chain.
    sample = max(
        (row for row in greed.result.assignments if row.operation_id not in issued_frozen),
        key=lambda row: row.start,
    )
    down = PostDown(work_center_id=sample.work_center_id, start=sample.start, end=sample.end)
    revised = apply_disruption(problem, down)
    old_down = recheck(
        revised,
        assignments=list(greed.result.assignments),
        kernel_status="feasible",
        solver_config="post-down-old",
    )
    post_replanned = replan_disruption(problem, base=greed, event=down)
    _write_json(out_dir / "post-down.json", post_replanned.result.model_dump(mode="json"))
    old_codes = sorted({row.code for row in old_down.result.violations})
    placed = {row.operation_id: row for row in post_replanned.result.assignments}
    issued = {row.operation_id: row for row in greed.result.assignments}
    frozen_moved = 0
    for op_id in issued_frozen:
        old = issued.get(op_id)
        new = placed.get(op_id)
        if old is None or new is None or old.start != new.start or old.work_center_id != new.work_center_id:
            frozen_moved += 1
    post_down_ok = (
        "CALENDAR_BROKEN" in old_codes
        and not old_down.result.verified_feasible
        and post_replanned.result.exit_code == 0
        and post_replanned.result.verified_feasible
        and frozen_moved == 0
    )

    broken_assignments = corrupt_plan([row.model_dump(mode="json") for row in greed.result.assignments])
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

    foreign = greed.result.assignments[0].model_copy(update={"work_center_id": "POST-MISSING"})
    shop_path = out_dir / "shop-plan.csv"
    write_shop_plan(shop_path, problem, [foreign])
    shop_assignments, extra, sources, digest = load_shop_plan(shop_path, problem)
    shop = verify_domain_plan(
        problem,
        shop_assignments,
        extra_violations=extra,
        source_rows=sources,
        shop_file=(shop_path.name, digest),
    )
    _write_json(out_dir / "shop-verify.json", shop.model_dump(mode="json"))
    shop_lines = [format_shop_finding(row) for row in shop.violations if row.severity != "kpi"]
    (out_dir / "shop-reasons.txt").write_text("\n".join(shop_lines) + "\n", encoding="utf-8")
    shop_ok = (
        shop.exit_code == 2
        and shop.claim_status == "rejected"
        and not shop.verified_feasible
        and bool(shop_lines)
    )
    witness_code = next(
        (row.code for row in broken_check.result.violations if row.severity != "kpi"),
        "",
    )
    witness_ids = (
        deletion_minimal_operation_ids(problem, list(broken_check.result.assignments), witness_code)
        if witness_code
        else []
    )
    _write_json(
        out_dir / "witness.json",
        {"code": witness_code, "operation_ids": witness_ids, "kind": "deletion-minimal"},
    )
    witness_ok = bool(witness_code) and bool(witness_ids)

    cpsat_ok = True
    cpsat_line = "  CPSAT skipped\n"
    if not skip_cpsat:
        tiny = synthesize("tiny", seed=1)
        tiny_path = out_dir / "tiny.json"
        tiny_path.write_text(tiny.model_dump_json(indent=2), encoding="utf-8")
        cpsat = plan(tiny, solver_config="CPSAT-10")
        _write_json(out_dir / "cpsat.json", cpsat.result.model_dump(mode="json"))
        dropped = any(row.code == "KERNEL_CALENDAR_UNSUPPORTED" for row in cpsat.result.violations)
        cpsat_ok = (
            not dropped
            and cpsat.result.exit_code == 0
            and cpsat.result.verified_feasible
            and cpsat.result.claim_status in {"verified", "optimal"}
        )
        cpsat_line = (
            f"  CPSAT status={cpsat.result.status.value} verified={cpsat.result.verified_feasible} "
            f"exit={cpsat.result.exit_code} claim={cpsat.result.claim_status}\n"
        )

    log_ok = False
    log_line = "  decision-log missing\n"
    if greed.result.exit_code == 0:
        log_path = out_dir / "decisions.jsonl"
        event = record_checked_decision(
            problem_path=problem_path,
            result_path=greed_path,
            decision=Decision.ACCEPTED,
            operator_code="op-demo",
            log_path=log_path,
            reason="demo candidate kept",
        )
        version = verify_decision_log(log_path, head=event.event_hash)
        logged = read_decision_log(log_path)
        log_ok = version == "v2" and len(logged) == 1 and logged[0].event_hash == event.event_hash
        log_line = f"  decision-log {version} head={event.event_hash}\n"

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
        f"  post_down old={old_codes} replan_verified={post_replanned.result.verified_feasible} "
        f"frozen_moved={frozen_moved}\n"
        f"  broken exit={broken_check.result.exit_code} codes="
        f"{sorted({row.code for row in broken_check.result.violations})}\n"
        f"  shop exit={shop.exit_code} claim={shop.claim_status}\n"
        f"  witness code={witness_code} ids={','.join(witness_ids)}\n"
        f"{log_line}"
    )
    clean_ok = greed.result.exit_code == 0 and greed.result.verified_feasible
    fifo_dirty = fifo.result.exit_code == 2 and len(fifo.result.violations) > 0
    broken_ok = broken_check.result.exit_code == 2
    frozen_ok = len(frozen_kept["broken_frozen_assignments"]) == 0
    if (
        clean_ok
        and fifo_dirty
        and broken_ok
        and frozen_ok
        and cpsat_ok
        and post_down_ok
        and log_ok
        and shop_ok
        and witness_ok
    ):
        sys.stdout.write("MVP readiness: PASS\n")
        return 0
    sys.stderr.write("MVP readiness: FAIL\n")
    return 1


def _benchmark(
    *,
    out_dir: Path,
    solvers: list[str],
    presets: list[str] | None,
    seeds: list[int] | None,
) -> int:
    """Run portfolio benchmark and write reports to out_dir."""
    from repairflow.benchmark import resolve_matrix

    matrix = resolve_matrix(presets, seeds)
    if not matrix:
        raise ValueError("benchmark matrix is empty; check --preset / --seeds against DEFAULT_MATRIX")

    summary = run_benchmark(matrix=matrix, solvers=solvers, out_dir=out_dir)
    verified = summary.verified_ratio()
    fifo_viol = summary.fifo_mean_violations()
    greed_mk = summary.greed_mean_makespan()
    delta = summary.fifo_minus_greed_makespan()
    sys.stdout.write(
        "RepairFlow benchmark\n"
        f"  instances={len(summary.rows)} solvers={solvers}\n"
        f"  GREED verified ratio: {verified:.1%}\n"
        f"  FIFO mean hard violations: {fifo_viol}\n"
        f"  GREED mean makespan: {greed_mk} min\n"
        f"  FIFO-GREED makespan: {delta} min (negative = GREED longer, expected)\n"
        f"  reports: {out_dir}/benchmark.{{json,md,html}}\n"
    )
    return 0 if summary.greed_all_verified() else 2


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
