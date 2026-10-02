"""Phase-1 verdict safety: partial plans, aux calendars, checker independence."""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

import pytest

from repairflow.checker_primitives import lookup_setup_minutes
from repairflow.cli import main
from repairflow.model import Calendar, CalendarWindow, FrozenAssignment, RepairFlowProblem, ResultStatus
from repairflow.planner import plan, recheck, replan_after_disruption
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_allow_partial_never_green() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    assert greed.result.verified_feasible
    partial = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={"policy": problem.policy.model_copy(update={"allow_partial_plan": True})}
        ).model_dump(mode="python")
    )
    outcome = recheck(
        partial,
        assignments=list(greed.result.assignments)[:-1],
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert outcome.result.exit_code != 0
    assert outcome.result.status is ResultStatus.PARTIAL
    assert outcome.result.verified_feasible is False
    assert any(row.code == ReasonCode.PARTIAL_COVERAGE for row in outcome.result.violations)


@pytest.mark.parametrize("solver", ["FIFO", "GREED", "CPSAT-10"])
def test_aux_calendar_rejects_work_outside_the_window(solver: str) -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    tool = Calendar(
        id="CAL-TOOL",
        code="CAL-TOOL",
        windows=[CalendarWindow(start=start + timedelta(hours=8), end=start + timedelta(hours=9))],
    )
    aux = [
        row.model_copy(update={"calendar_id": "CAL-TOOL"}) if row.id == "AUX-CRANE" else row
        for row in problem.aux_resources
    ]
    operations = []
    stamped = False
    for operation in problem.operations:
        if not stamped and operation.sequence == 1:
            operations.append(
                operation.model_copy(
                    update={
                        "required_aux_ids": ["AUX-CRANE"],
                        "earliest_start": start + timedelta(hours=10),
                    }
                )
            )
            stamped = True
        else:
            operations.append(operation)
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "calendars": [*problem.calendars, tool],
                "aux_resources": aux,
                "operations": operations,
            }
        ).model_dump(mode="python")
    )
    outcome = plan(loaded, solver_config=solver)
    assert outcome.result.exit_code == 2
    assert outcome.result.verified_feasible is False
    assert not any(
        row.code == ReasonCode.KERNEL_CALENDAR_UNSUPPORTED for row in outcome.result.violations
    )
    if solver != "CPSAT-10":
        assert any(
            row.code == ReasonCode.CALENDAR_BROKEN and row.resource_id == "AUX-CRANE"
            for row in outcome.result.violations
        )


def test_empty_calendar_is_unavailable_and_missing_calendar_is_open() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    assert greed.result.verified_feasible
    empty = Calendar(id="CAL-OFF", code="CAL-OFF", windows=[])
    closed = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "calendars": [*problem.calendars, empty],
                "crews": [
                    row.model_copy(update={"calendar_id": "CAL-OFF"}) if row.id == "CREW-MECH" else row
                    for row in problem.crews
                ],
            }
        ).model_dump(mode="python")
    )
    rejected = recheck(
        closed,
        assignments=list(greed.result.assignments),
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert rejected.result.exit_code == 2
    assert any(
        row.code == ReasonCode.CALENDAR_BROKEN and row.resource_id == "CREW-MECH"
        for row in rejected.result.violations
    )

    open_crews = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "crews": [row.model_copy(update={"calendar_id": None}) for row in problem.crews],
            }
        ).model_dump(mode="python")
    )
    accepted = recheck(
        open_crews,
        assignments=list(greed.result.assignments),
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert accepted.result.verified_feasible
    assert not any(row.code == ReasonCode.CALENDAR_BROKEN for row in accepted.result.violations)


def test_deadline_is_hard_and_due_date_stays_soft() -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    early = problem.planning_horizon.start
    jobs = [
        job.model_copy(update={"deadline": early}) if job.id == problem.jobs[0].id else job
        for job in problem.jobs
    ]
    tight = RepairFlowProblem.model_validate(
        problem.model_copy(update={"jobs": jobs}).model_dump(mode="python")
    )
    outcome = recheck(
        tight,
        assignments=list(greed.result.assignments),
        kernel_status="feasible",
        solver_config="recheck",
    )
    assert any(
        row.code == ReasonCode.DEADLINE_MISSED and row.severity == "hard" for row in outcome.result.violations
    )
    assert outcome.result.exit_code == 2


def test_duplicate_setup_cells_are_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    payload = problem.model_dump(mode="python")
    payload["setup_matrix"] = [*problem.setup_matrix, problem.setup_matrix[0].model_copy()]
    with pytest.raises(ValueError, match="duplicate setup_matrix"):
        RepairFlowProblem.model_validate(payload)


def test_unknown_disruption_id_is_exit_1(tmp_path: Path) -> None:
    problem = synthesize("tiny", seed=1)
    greed = plan(problem, solver_config="GREED")
    with pytest.raises(ValueError, match="UNKNOWN_OPERATION"):
        replan_after_disruption(problem, base=greed, disrupted_operation_ids=["NO-SUCH"])
    problem_path = tmp_path / "problem.json"
    plan_path = tmp_path / "plan.json"
    problem_path.write_text(problem.model_dump_json(), encoding="utf-8")
    plan_path.write_text(greed.result.model_dump_json(), encoding="utf-8")
    code = main(
        [
            "disrupt",
            str(problem_path),
            str(plan_path),
            "--operation-id",
            "NO-SUCH",
            "--out",
            str(tmp_path / "out.json"),
        ]
    )
    assert code == 1


def test_immutable_frozen_overlap_rejected_and_mutable_rows_are_notes() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start + timedelta(hours=8)
    first, second = problem.operations[0], problem.operations[1]
    post = first.eligible_work_center_ids[0]

    def crew_for(operation_skills: list[str]) -> str:
        for crew in problem.crews:
            if set(operation_skills) <= set(crew.skills):
                return crew.id
        raise AssertionError(operation_skills)

    left = FrozenAssignment(
        operation_id=first.id,
        work_center_id=post,
        crew_id=crew_for(first.required_skills),
        start=start,
        end=start + timedelta(minutes=30),
    )
    right = FrozenAssignment(
        operation_id=second.id,
        work_center_id=post,
        crew_id=crew_for(second.required_skills),
        start=start + timedelta(minutes=10),
        end=start + timedelta(minutes=40),
    )
    payload = problem.model_dump(mode="python")
    payload["frozen_assignments"] = [left, right]
    with pytest.raises(ValueError, match="frozen overlap"):
        RepairFlowProblem.model_validate(payload)
    payload["frozen_assignments"] = [
        left.model_copy(update={"immutable": False}),
        right.model_copy(update={"immutable": False}),
    ]
    loaded = RepairFlowProblem.model_validate(payload)
    assert loaded.frozen_assignments[0].immutable is False


def test_checker_modules_do_not_import_search_or_solver() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "repairflow"
    banned = {"repairflow.adapter", "repairflow.planner", "synaps.solvers"}
    modules = (
        "checker.py",
        "checker_primitives.py",
        "capacity.py",
        "lane_setup.py",
        "ledger.py",
    )
    for name in modules:
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules_found: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules_found.append(node.module)
            if isinstance(node, ast.Import):
                modules_found.extend(alias.name for alias in node.names)
            for module in modules_found:
                assert not any(module == item or module.startswith(f"{item}.") for item in banned), (
                    f"{name} imports {module}"
                )


def test_adapter_setup_mutation_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = synthesize("tiny", seed=1)

    def plus_five(
        problem: RepairFlowProblem,
        *,
        work_center_id: str,
        from_state: str,
        to_state: str,
    ) -> int | None:
        found = lookup_setup_minutes(
            problem,
            work_center_id=work_center_id,
            from_state=from_state,
            to_state=to_state,
        )
        if found is None:
            return None
        return found + 5

    monkeypatch.setattr("repairflow.adapter.lookup_setup_minutes", plus_five)
    outcome = plan(problem, solver_config="GREED")
    assert outcome.result.exit_code == 2
    assert any(row.code == ReasonCode.SETUP_MISMATCH for row in outcome.result.violations)
