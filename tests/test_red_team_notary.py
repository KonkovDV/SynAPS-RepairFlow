"""Adversarial notary cases from the 2026-10-02 red team."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from synaps.model import Assignment
from tests.fault_campaign import run_fault_campaign

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_plan
from repairflow.explanations import deletion_minimal_operation_ids
from repairflow.model import Calendar, CalendarWindow, PlannedAssignment, Policy, RepairFlowProblem
from repairflow.planner import plan, recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize
from repairflow.versions import SYNAPS_COMMIT


def _kernel_row(
    problem: RepairFlowProblem,
    *,
    aux: list[object],
) -> Assignment:
    _schedule, id_map = to_schedule_problem(problem)
    operation = next(key for key in id_map if key.startswith("op:"))
    center = next(key for key in id_map if key.startswith("wc:"))
    start = problem.planning_horizon.start + timedelta(hours=9)
    return Assignment(
        operation_id=id_map[operation],
        work_center_id=id_map[center],
        start_time=start,
        end_time=start + timedelta(minutes=30),
        aux_resource_ids=list(aux),  # type: ignore[arg-type]
    )


def test_two_crews_on_one_kernel_assignment_are_not_verified() -> None:
    problem = synthesize("tiny", seed=1)
    _schedule, id_map = to_schedule_problem(problem)
    crews = [id_map[key] for key in id_map if key.startswith("crew:")]
    assert len(crews) >= 2
    row = _kernel_row(problem, aux=crews[:2])
    outcome = recheck(problem, assignments=[row], kernel_status="feasible", solver_config="recheck")
    assert any(item.code == ReasonCode.AMBIGUOUS_CREW for item in outcome.result.violations)
    assert outcome.result.assignments[0].crew_id is None
    assert outcome.result.verified_feasible is False
    assert outcome.result.exit_code == 2


def test_unknown_aux_kind_is_not_dropped() -> None:
    problem = synthesize("tiny", seed=1)
    _schedule, id_map = to_schedule_problem(problem)
    state = next(id_map[key] for key in id_map if key.startswith("state:"))
    row = _kernel_row(problem, aux=[state])
    outcome = recheck(problem, assignments=[row], kernel_status="feasible", solver_config="recheck")
    assert any(item.code == ReasonCode.UNKNOWN_RESOURCE for item in outcome.result.violations)
    assert outcome.result.verified_feasible is False


def test_missing_required_aux_is_aux_missing() -> None:
    problem = synthesize("tiny", seed=1)
    aux_id = problem.aux_resources[0].id
    operations = [
        problem.operations[0].model_copy(update={"required_aux_ids": [aux_id]}),
        *problem.operations[1:],
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"operations": operations}).model_dump(mode="python")
    )
    outcome = plan(loaded, solver_config="GREED")
    rows = [
        row.model_copy(update={"aux_ids": []}) if row.operation_id == operations[0].id else row
        for row in outcome.result.assignments
    ]
    checked = recheck(loaded, assignments=rows, kernel_status="feasible", solver_config="recheck")
    assert any(item.code == ReasonCode.AUX_MISSING for item in checked.result.violations)
    assert checked.result.verified_feasible is False


@pytest.mark.parametrize(
    ("status", "exit_code"),
    [
        ("feasible", 0),
        ("optimal", 0),
        ("FEASIBLE", 0),
        ("OPTIMAL", 0),
        ("domain_only", 0),
        ("infeasible", 2),
        ("timeout", 2),
        ("error", 2),
        ("UNKNOWN", 2),
        ("MODEL_INVALID", 2),
        ("", 2),
    ],
)
def test_only_admissible_kernel_statuses_exit_zero(status: str, exit_code: int) -> None:
    problem = synthesize("tiny", seed=1)
    planned = plan(problem, solver_config="GREED")
    checked = recheck(
        problem,
        assignments=list(planned.result.assignments),
        kernel_status=status,
        solver_config="recheck",
    )
    assert checked.result.exit_code == exit_code
    assert checked.result.verified_feasible is (exit_code == 0)
    if status.lower() == "domain_only":
        assert checked.result.claim_status != "optimal"


def test_precedence_explanation_keeps_both_operations() -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    by_op = {row.operation_id: row for row in outcome.result.assignments}
    pair = next(
        (pred_id, op.id)
        for op in problem.operations
        for pred_id in op.predecessor_ids
        if pred_id in by_op and op.id in by_op
    )
    predecessor, successor_id = pair
    successor = by_op[successor_id]
    held = successor.end - successor.start
    moved = successor.model_copy(
        update={"start": by_op[predecessor].start, "end": by_op[predecessor].start + held}
    )
    rows = [moved if row.operation_id == successor_id else row for row in outcome.result.assignments]
    witness = deletion_minimal_operation_ids(problem, rows, ReasonCode.PRECEDENCE_BROKEN)
    assert witness == sorted((predecessor, successor_id))


def test_preemptive_open_minutes_use_the_intersection() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    post = Calendar(
        id="CAL-POST",
        code="CAL-POST",
        windows=[CalendarWindow(start=start + timedelta(hours=8), end=start + timedelta(hours=12))],
    )
    crew = Calendar(
        id="CAL-CREW",
        code="CAL-CREW",
        windows=[CalendarWindow(start=start + timedelta(hours=10), end=start + timedelta(hours=14))],
    )
    operation = problem.operations[0].model_copy(
        update={
            "duration_min": 240,
            "required_aux_ids": [],
            "domain_attributes": {"duration_policy": "preemptive"},
        }
    )
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "operations": [operation, *problem.operations[1:]],
                "calendars": [post, crew],
                "work_centers": [
                    row.model_copy(update={"calendar_id": "CAL-POST"}) for row in problem.work_centers
                ],
                "crews": [row.model_copy(update={"calendar_id": "CAL-CREW"}) for row in problem.crews],
                "aux_resources": [
                    row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources
                ],
            }
        ).model_dump(mode="python")
    )
    crew_id = loaded.crews[0].id
    row = PlannedAssignment(
        operation_id=operation.id,
        work_center_id=loaded.work_centers[0].id,
        crew_id=crew_id,
        aux_ids=[],
        start=start + timedelta(hours=8),
        end=start + timedelta(hours=14),
        setup_minutes=0,
    )
    schedule, id_map = to_schedule_problem(loaded)
    violations = check_plan(
        loaded,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert any(item.code == ReasonCode.INVALID_DURATION for item in violations)


def test_preemptive_setup_must_sit_inside_an_open_window() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    calendar = Calendar(
        id="CAL-LATE",
        code="CAL-LATE",
        windows=[CalendarWindow(start=start + timedelta(hours=8), end=start + timedelta(hours=12))],
    )
    operation = problem.operations[0].model_copy(
        update={"domain_attributes": {"duration_policy": "preemptive"}, "required_aux_ids": []}
    )
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "operations": [operation, *problem.operations[1:]],
                "calendars": [calendar],
                "work_centers": [
                    row.model_copy(update={"calendar_id": "CAL-LATE"}) for row in problem.work_centers
                ],
                "crews": [row.model_copy(update={"calendar_id": None}) for row in problem.crews],
                "aux_resources": [
                    row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources
                ],
            }
        ).model_dump(mode="python")
    )
    visit_start = start + timedelta(hours=8)
    row = PlannedAssignment(
        operation_id=operation.id,
        work_center_id=loaded.work_centers[0].id,
        crew_id=None,
        aux_ids=[],
        start=visit_start,
        end=visit_start + timedelta(minutes=operation.duration_min),
        setup_minutes=30,
    )
    schedule, id_map = to_schedule_problem(loaded)
    violations = check_plan(
        loaded,
        schedule_problem=schedule,
        assignments=[row],
        id_map=id_map,
        kernel_status="feasible",
    )
    assert any(item.code == ReasonCode.CALENDAR_BROKEN and "setup" in item.message for item in violations)


def test_unsupported_dag_is_marked_deprecated() -> None:
    schema = Policy.model_json_schema()
    assert schema["properties"]["unsupported_dag"]["deprecated"] is True
    problem = synthesize("tiny", seed=1)
    assert problem.policy.unsupported_dag == "reject"
    assert problem.policy.dag_strategy == "split_release_fixpoint"


@pytest.mark.slow
def test_bad_mutations_are_not_accepted() -> None:
    report = json.loads(Path("docs/fault-campaign.json").read_text(encoding="utf-8"))
    live = run_fault_campaign(checks=int(report["checked"]))
    assert live["checked"] >= 10_000
    assert live["false_accept"] == 0
    assert report["false_accept"] == 0
    assert report["checked"] == live["checked"]
    assert report["input_hash"] == live["input_hash"]
    assert report["synaps_commit"] == SYNAPS_COMMIT
    assert report["claim_level"] == "experiment"
    assert report["data_provenance"] == "synthetic"
