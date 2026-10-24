"""The report surface follows the file's claim and does not invent a clean exit."""

from __future__ import annotations

from repairflow.cli import main
from repairflow.model import PlannedAssignment, Violation
from repairflow.planner import plan
from repairflow.reasons import ReasonCode
from repairflow.report import render_html, render_markdown
from repairflow.shop_plan import write_shop_plan
from repairflow.synthetic import synthesize


def test_report_of_a_clean_shop_plan_exits_zero(tmp_path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    shop = tmp_path / "plan.csv"
    write_shop_plan(shop, problem, list(outcome.result.assignments))
    problem_path = tmp_path / "problem.json"
    problem_path.write_text(problem.model_dump_json(), encoding="utf-8")
    checked = tmp_path / "checked.json"
    assert (
        main(["verify-plan", "--problem", str(problem_path), "--plan", str(shop), "--out", str(checked)]) == 0
    )
    exit_code = main(
        [
            "report",
            str(problem_path),
            str(checked),
            "--md",
            str(tmp_path / "r.md"),
            "--html",
            str(tmp_path / "r.html"),
        ]
    )
    page = (tmp_path / "r.md").read_text(encoding="utf-8")
    html = (tmp_path / "r.html").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "домен проверен без ядра, exit 0" in page
    assert "banner ok" in html
    assert "banner fail" not in html


def test_a_forged_domain_claim_with_exit_two_is_not_called_clean() -> None:
    problem = synthesize("tiny", seed=1)
    result = plan(problem, solver_config="GREED").result.model_copy(
        update={"claim_status": "domain_verified", "verified_feasible": False, "exit_code": 2}
    )
    page = render_markdown(problem, result)
    html = render_html(problem, result)
    assert "exit 0" not in page.split("## Назначения", 1)[0]
    assert "не выпускать, exit 2" in page
    assert "banner fail" in html


def test_markdown_table_does_not_split_on_a_pipe_and_names_the_russian_hint() -> None:
    problem = synthesize("tiny", seed=1)
    base = plan(problem, solver_config="GREED").result
    poisoned = base.assignments[0].model_copy(update={"operation_id": "JOB|01", "reason": "a|b\nc"})
    result = base.model_copy(
        update={
            "assignments": [poisoned, *base.assignments[1:]],
            "verified_feasible": False,
            "exit_code": 2,
            "claim_status": "rejected",
            "violations": [
                Violation(
                    code=ReasonCode.CENTER_OVERLAP,
                    message="resource POST-U1 exceeds capacity 1",
                    operation_id="JOB-01-01",
                    resource_id="POST-U1",
                    suggested_relaxation="выбрать альтернативный пост или сдвинуть слот",
                )
            ],
        }
    )
    page = render_markdown(problem, result)
    assert "JOB/01" in page
    assert "a/b c" in page
    assert "пост занят другим назначением" in page
    assert "выбрать альтернативный пост" in page
    html = render_html(problem, result)
    assert "выбрать альтернативный пост" in html
    assert "<script>" not in html


def test_html_escapes_a_hostile_reason() -> None:
    problem = synthesize("tiny", seed=1)
    base = plan(problem, solver_config="GREED").result
    hostile = PlannedAssignment(
        operation_id="JOB<script>",
        work_center_id=base.assignments[0].work_center_id,
        start=base.assignments[0].start,
        end=base.assignments[0].end,
        reason='"><script>alert(1)</script>',
    )
    result = base.model_copy(update={"assignments": [hostile]})
    html = render_html(problem, result)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
