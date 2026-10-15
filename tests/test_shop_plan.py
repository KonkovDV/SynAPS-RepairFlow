"""Shop CSV plans are checked without calling the kernel."""

from __future__ import annotations

import ast
import csv
import hashlib
from datetime import timedelta
from pathlib import Path

from repairflow.cli import main
from repairflow.domain_verify import verify_domain_plan
from repairflow.model import RepairFlowProblem
from repairflow.planner import plan
from repairflow.reasons import REASON_RU, ReasonCode
from repairflow.shop_plan import format_shop_finding, load_shop_plan, write_shop_plan
from repairflow.synthetic import synthesize


def _problem_path(tmp_path, problem: RepairFlowProblem):
    path = tmp_path / "problem.json"
    path.write_text(problem.model_dump_json(), encoding="utf-8")
    return path


def test_domain_verify_does_not_import_solver_search() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "repairflow"
    banned = ("repairflow.planner", "synaps.solvers", "synaps.portfolio")
    for name in ("domain_verify.py", "shop_plan.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            for module in modules:
                assert not any(module == item or module.startswith(f"{item}.") for item in banned)


def test_clean_shop_plan_is_domain_verified_and_not_kernel_verified(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    assert outcome.result.verified_feasible
    shop = tmp_path / "plan.csv"
    write_shop_plan(shop, problem, list(outcome.result.assignments))
    problem_path = _problem_path(tmp_path, problem)
    out = tmp_path / "result.json"
    exit_code = main(["verify-plan", "--problem", str(problem_path), "--plan", str(shop), "--out", str(out)])
    result_text = out.read_text(encoding="utf-8")
    assert exit_code == 0
    assert '"claim_status": "domain_verified"' in result_text
    assert '"verified_feasible": false' in result_text
    assert '"kernel_consulted": false' in result_text
    assert '"solver_class": "domain"' in result_text


def test_committed_five_error_sheet_exits_2(capsys) -> None:
    root = Path("schemas/templates/five-errors")
    exit_code = main(
        ["verify-plan", "--problem", str(root / "problem.json"), "--plan", str(root / "shop-plan.csv")]
    )
    captured = capsys.readouterr().out
    expected = {
        ReasonCode.PARTIAL_COVERAGE,
        ReasonCode.PRECEDENCE_BROKEN,
        ReasonCode.UNKNOWN_RESOURCE,
        ReasonCode.AUX_MISSING,
        ReasonCode.CREW_OVERLAP,
    }
    for code in expected:
        assert code in captured
        assert REASON_RU[code] in captured
    assert exit_code == 2


def test_five_shop_errors_print_five_russian_reasons(tmp_path, capsys) -> None:
    problem = synthesize("tiny", seed=1)
    aux_id = problem.aux_resources[0].id
    successor = next(op for op in problem.operations if op.predecessor_ids)
    host = next(
        op for op in problem.operations if op.id != successor.id and successor.id not in op.predecessor_ids
    )
    operations = [
        host.model_copy(update={"required_aux_ids": [aux_id]}) if op.id == host.id else op
        for op in problem.operations
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"operations": operations}).model_dump(mode="python")
    )
    outcome = plan(loaded, solver_config="GREED")
    rows = list(outcome.result.assignments)
    by_op = {row.operation_id: row for row in rows}
    predecessor = by_op[successor.predecessor_ids[0]]
    current = by_op[successor.id]
    held = current.end - current.start
    by_op[successor.id] = current.model_copy(
        update={"start": predecessor.start, "end": predecessor.start + held}
    )
    by_op[host.id] = by_op[host.id].model_copy(update={"aux_ids": [], "work_center_id": "POST-MISSING"})
    protected = {successor.id, host.id, predecessor.operation_id}
    other = next(row for row in rows if row.operation_id not in protected)
    protected.add(other.operation_id)
    by_op[other.operation_id] = other.model_copy(
        update={"crew_id": predecessor.crew_id, "start": predecessor.start, "end": predecessor.end}
    )
    drop = next(row.operation_id for row in rows if row.operation_id not in protected)
    kept = [by_op[row.operation_id] for row in rows if row.operation_id != drop]
    shop = tmp_path / "broken.csv"
    write_shop_plan(shop, loaded, kept)
    exit_code = main(["verify-plan", "--problem", str(_problem_path(tmp_path, loaded)), "--plan", str(shop)])
    captured = capsys.readouterr().out
    expected = {
        ReasonCode.PARTIAL_COVERAGE,
        ReasonCode.PRECEDENCE_BROKEN,
        ReasonCode.UNKNOWN_RESOURCE,
        ReasonCode.AUX_MISSING,
        ReasonCode.CREW_OVERLAP,
    }
    for code in expected:
        assert code in captured
        assert REASON_RU[code] in captured
    assert exit_code == 2


def test_job_mismatch_is_a_hard_russian_reason(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    shop = tmp_path / "plan.csv"
    write_shop_plan(shop, problem, list(outcome.result.assignments))
    text = shop.read_text(encoding="utf-8")
    shop.write_text(text.replace(problem.jobs[0].id, "JOB-OTHER", 1), encoding="utf-8")
    assignments, extra, sources, _digest = load_shop_plan(shop, problem)
    result = verify_domain_plan(problem, assignments, extra_violations=extra, source_rows=sources)
    assert any(row.code == ReasonCode.JOB_MISMATCH for row in result.violations)
    mismatch = next(row for row in result.violations if row.code == ReasonCode.JOB_MISMATCH)
    expected_line = next(
        number
        for number, line in enumerate(shop.read_text(encoding="utf-8").splitlines(), start=1)
        if "JOB-OTHER" in line
    )
    assert mismatch.details["source_name"] == "plan.csv"
    assert mismatch.details["source_line"] == expected_line
    assert result.claim_status == "rejected"
    assert result.verified_feasible is False
    assert REASON_RU[ReasonCode.JOB_MISMATCH]


def test_shop_csv_rejects_a_naive_timestamp(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    shop = tmp_path / "naive.csv"
    row = outcome.result.assignments[0]
    with shop.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["заказ", "операция", "пост", "бригада", "оснастка", "начало", "конец"])
        writer.writerow(
            [
                problem.jobs[0].id,
                row.operation_id,
                row.work_center_id,
                row.crew_id or "",
                "",
                "2026-10-02T08:00:00",
                "2026-10-02T09:00:00",
            ]
        )
    try:
        load_shop_plan(shop, problem)
    except ValueError as exc:
        assert "timezone" in str(exc)
    else:
        raise AssertionError("naive timestamp was accepted")


def test_semicolon_shop_csv_loads(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    shop = tmp_path / "excel.csv"
    write_shop_plan(shop, problem, list(outcome.result.assignments))
    comma = shop.read_text(encoding="utf-8")
    shop.write_text(comma.replace(",", ";"), encoding="utf-8")
    assignments, extra, _sources, _digest = load_shop_plan(shop, problem)
    assert extra == []
    assert len(assignments) == len(outcome.result.assignments)
    assert assignments[0].end - assignments[0].start >= timedelta(0)


def test_an_empty_crew_cell_is_left_for_the_notary(tmp_path: Path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    shop = tmp_path / "open-crew.csv"
    write_shop_plan(shop, problem, list(outcome.result.assignments))
    rows = list(csv.reader(shop.read_text(encoding="utf-8").splitlines()))
    rows[1][3] = ""
    with shop.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    assignments, extra, _sources, _digest = load_shop_plan(shop, problem)
    assert extra == []
    assert assignments[0].crew_id is None


def test_a_notary_finding_cites_the_shop_row(tmp_path: Path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    foreign = outcome.result.assignments[0].model_copy(update={"work_center_id": "POST-MISSING"})
    shop = tmp_path / "missing-post.csv"
    write_shop_plan(shop, problem, [foreign])
    assignments, extra, sources, digest = load_shop_plan(shop, problem)
    result = verify_domain_plan(
        problem,
        assignments,
        extra_violations=extra,
        source_rows=sources,
        shop_file=(shop.name, digest),
    )
    cited = [
        row for row in result.violations if row.operation_id == foreign.operation_id and row.severity != "kpi"
    ]
    assert cited
    assert digest == hashlib.sha256(shop.read_bytes()).hexdigest()
    assert result.metadata["shop_plan_name"] == "missing-post.csv"
    assert result.metadata["shop_plan_sha256"] == digest
    assert {row.details["source_name"] for row in cited} == {"missing-post.csv"}
    assert {row.details["source_line"] for row in cited} == {2}
    assert all("missing-post.csv:2" in format_shop_finding(row) for row in cited)
    omitted = [row for row in result.violations if row.operation_id not in sources]
    assert all("source_line" not in row.details for row in omitted)


def test_a_repeated_operation_row_is_rejected(tmp_path: Path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    shop = tmp_path / "twice.csv"
    write_shop_plan(shop, problem, list(outcome.result.assignments[:1]))
    lines = shop.read_text(encoding="utf-8").splitlines()
    shop.write_text("\n".join((lines[0], lines[1], lines[1])) + "\n", encoding="utf-8")
    try:
        load_shop_plan(shop, problem)
    except ValueError as exc:
        assert "repeats operation" in str(exc)
    else:
        raise AssertionError("a repeated operation row was accepted")
