"""Duration, calendar span, frozen ingest, and the dependency lock."""

from __future__ import annotations

from datetime import timedelta

import pytest

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_plan
from repairflow.dependency_lock import build_dependency_lock
from repairflow.model import (
    Calendar,
    CalendarWindow,
    FrozenAssignment,
    PlannedAssignment,
    PredecessorLink,
    RepairFlowProblem,
)
from repairflow.planner import plan, recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def _check(problem: RepairFlowProblem, rows: list[PlannedAssignment]) -> list[str]:
    schedule, id_map = to_schedule_problem(problem)
    violations = check_plan(
        problem,
        schedule_problem=schedule,
        assignments=rows,
        id_map=id_map,
        kernel_status="feasible",
    )
    return [f"{row.code}:{row.resource_id or ''}:{row.message}" for row in violations]


def test_overlapping_calendar_windows_count_a_minute_once() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    calendar = Calendar(
        id="CAL-OVER",
        code="CAL-OVER",
        windows=[
            CalendarWindow(start=start + timedelta(hours=8), end=start + timedelta(hours=12)),
            CalendarWindow(start=start + timedelta(hours=10), end=start + timedelta(hours=14)),
        ],
    )
    operation = problem.operations[0].model_copy(
        update={
            "duration_min": 480,
            "required_aux_ids": [],
            "domain_attributes": {"duration_policy": "preemptive"},
        }
    )
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "operations": [operation, *problem.operations[1:]],
                "calendars": [calendar],
                "work_centers": [
                    row.model_copy(update={"calendar_id": "CAL-OVER"}) for row in problem.work_centers
                ],
                "crews": [row.model_copy(update={"calendar_id": None}) for row in problem.crews],
                "aux_resources": [
                    row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources
                ],
            }
        ).model_dump(mode="python")
    )
    visit = PlannedAssignment(
        operation_id=operation.id,
        work_center_id=operation.eligible_work_center_ids[0],
        start=start + timedelta(hours=8),
        end=start + timedelta(hours=14),
    )
    doubled = _check(loaded, [visit])
    assert any(message.startswith(f"{ReasonCode.INVALID_DURATION}:") for message in doubled)

    honest = operation.model_copy(update={"duration_min": 360})
    counted_once = RepairFlowProblem.model_validate(
        loaded.model_copy(update={"operations": [honest, *loaded.operations[1:]]}).model_dump(mode="python")
    )
    once = _check(counted_once, [visit])
    assert not any(message.startswith(f"{ReasonCode.INVALID_DURATION}:") for message in once)


def test_list_schedule_keeps_setup_inside_release_and_min_lag() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    release = start + timedelta(hours=10)
    jobs = [row.model_copy(update={"release_date": release}) for row in problem.jobs]
    setup = [
        row.model_copy(update={"duration_min": 30}) if row.from_state == "idle" else row
        for row in problem.setup_matrix
    ]
    successor = next(row for row in problem.operations if row.predecessor_ids)
    predecessor_id = successor.predecessor_ids[0]
    operations = []
    for row in problem.operations:
        if row.id != successor.id:
            operations.append(row)
            continue
        operations.append(
            row.model_copy(
                update={
                    "predecessors": [PredecessorLink(id=predecessor_id, min_lag_min=45)],
                    "predecessor_ids": [predecessor_id],
                }
            )
        )
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"jobs": jobs, "setup_matrix": setup, "operations": operations}).model_dump(
            mode="python"
        )
    )
    outcome = plan(loaded, solver_config="GREED")
    by_op = {row.operation_id: row for row in outcome.result.assignments}
    placed = by_op[successor.id]
    earlier = by_op[predecessor_id]
    assert placed.start >= earlier.end + timedelta(minutes=45)
    for row in outcome.result.assignments:
        assert row.start - timedelta(minutes=row.setup_minutes) >= release
    assert not any(row.code == ReasonCode.RELEASE_VIOLATION for row in outcome.result.violations)
    assert not any(row.code == ReasonCode.PRECEDENCE_BROKEN for row in outcome.result.violations)


def test_frozen_pair_outside_max_lag_is_rejected_at_load() -> None:
    problem = synthesize("tiny", seed=1)
    earlier = problem.operations[0]
    later = next(row for row in problem.operations if earlier.id in row.predecessor_ids)
    start = problem.planning_horizon.start + timedelta(hours=8)
    first_end = start + timedelta(minutes=earlier.duration_min)
    second_start = first_end + timedelta(hours=3)
    operations = [
        row.model_copy(
            update={
                "predecessors": [PredecessorLink(id=earlier.id, min_lag_min=0, max_lag_min=30)],
                "predecessor_ids": [earlier.id],
            }
        )
        if row.id == later.id
        else row
        for row in problem.operations
    ]
    frozen = problem.model_copy(
        update={
            "operations": operations,
            "frozen_assignments": [
                FrozenAssignment(
                    operation_id=earlier.id,
                    work_center_id=earlier.eligible_work_center_ids[0],
                    start=start,
                    end=first_end,
                    immutable=True,
                ),
                FrozenAssignment(
                    operation_id=later.id,
                    work_center_id=later.eligible_work_center_ids[0],
                    start=second_start,
                    end=second_start + timedelta(minutes=later.duration_min),
                    immutable=True,
                ),
            ],
        }
    )
    with pytest.raises(ValueError, match="max lag"):
        RepairFlowProblem.model_validate(frozen.model_dump(mode="python"))


def test_exact_duration_rejects_a_stretched_visit() -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    assert outcome.result.verified_feasible
    rows = list(outcome.result.assignments)
    stretched = rows[0].model_copy(update={"end": rows[0].end + timedelta(minutes=15)})
    rows[0] = stretched
    checked = recheck(problem, assignments=rows, kernel_status="feasible", solver_config="recheck")
    assert any(row.code == ReasonCode.INVALID_DURATION for row in checked.result.violations)


def test_min_policy_allows_a_longer_visit() -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    target = outcome.result.assignments[0].operation_id
    operations = [
        row.model_copy(update={"domain_attributes": {"duration_policy": "min"}}) if row.id == target else row
        for row in problem.operations
    ]
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(update={"operations": operations}).model_dump(mode="python")
    )
    rows = list(outcome.result.assignments)
    rows[0] = rows[0].model_copy(update={"end": rows[0].end + timedelta(minutes=15)})
    messages = _check(loaded, rows)
    assert not any("is not duration_min" in message for message in messages)


def test_preemptive_visit_may_cross_a_closed_gap() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start
    windows = [
        CalendarWindow(start=start + timedelta(hours=8), end=start + timedelta(hours=9)),
        CalendarWindow(start=start + timedelta(hours=11), end=start + timedelta(hours=12)),
    ]
    calendar = Calendar(id="CAL-GAP", code="CAL-GAP", windows=windows)
    operation = problem.operations[0].model_copy(
        update={"duration_min": 60, "domain_attributes": {"duration_policy": "preemptive"}}
    )
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "operations": [operation, *problem.operations[1:]],
                "calendars": [calendar],
                "work_centers": [
                    row.model_copy(update={"calendar_id": "CAL-GAP"}) for row in problem.work_centers
                ],
                "crews": [row.model_copy(update={"calendar_id": None}) for row in problem.crews],
                "aux_resources": [
                    row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources
                ],
            }
        ).model_dump(mode="python")
    )
    visit = PlannedAssignment(
        operation_id=operation.id,
        work_center_id=operation.eligible_work_center_ids[0],
        start=start + timedelta(hours=8, minutes=30),
        end=start + timedelta(hours=11, minutes=30),
    )
    messages = _check(loaded, [visit])
    assert not any(message.startswith(f"{ReasonCode.CALENDAR_BROKEN}:") for message in messages)
    assert not any(message.startswith(f"{ReasonCode.INVALID_DURATION}:") for message in messages)

    exact = operation.model_copy(update={"domain_attributes": {}})
    non_preemptive = RepairFlowProblem.model_validate(
        loaded.model_copy(update={"operations": [exact, *loaded.operations[1:]]}).model_dump(mode="python")
    )
    blocked = _check(non_preemptive, [visit])
    assert any(message.startswith(f"{ReasonCode.CALENDAR_BROKEN}:") for message in blocked)
    assert any("is not duration_min" in message for message in blocked)


def test_unattended_resource_ignores_a_closed_calendar() -> None:
    problem = synthesize("tiny", seed=1)
    empty = Calendar(id="CAL-OFF", code="CAL-OFF", windows=[])
    center_id = problem.work_centers[0].id
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "calendars": [*problem.calendars, empty],
                "work_centers": [
                    row.model_copy(
                        update={
                            "calendar_id": "CAL-OFF",
                            "domain_attributes": {"attendance": "unattended"},
                        }
                    )
                    if row.id == center_id
                    else row
                    for row in problem.work_centers
                ],
            }
        ).model_dump(mode="python")
    )
    outcome = plan(problem, solver_config="GREED")
    messages = _check(loaded, list(outcome.result.assignments))
    assert not any(f":{center_id}:" in message and "no open windows" in message for message in messages)


def test_empty_attended_calendar_is_closed_for_the_planner() -> None:
    problem = synthesize("tiny", seed=1)
    empty = Calendar(id="CAL-OFF", code="CAL-OFF", windows=[])
    loaded = RepairFlowProblem.model_validate(
        problem.model_copy(
            update={
                "calendars": [*problem.calendars, empty],
                "crews": [row.model_copy(update={"calendar_id": "CAL-OFF"}) for row in problem.crews],
            }
        ).model_dump(mode="python")
    )
    outcome = plan(loaded, solver_config="GREED")
    assert outcome.result.verified_feasible is False
    assert outcome.result.exit_code == 2


def test_frozen_ingest_checks_duration_aux_and_setup() -> None:
    problem = synthesize("tiny", seed=1)
    operation = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=8)
    frozen = problem.model_copy(
        update={
            "frozen_assignments": [
                {
                    "operation_id": operation.id,
                    "work_center_id": operation.eligible_work_center_ids[0],
                    "start": start,
                    "end": start + timedelta(minutes=operation.duration_min + 10),
                    "immutable": True,
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="holds"):
        RepairFlowProblem.model_validate(frozen.model_dump(mode="python"))

    aux_ops = [row.model_copy(update={"required_aux_ids": ["AUX-JIG"]}) for row in problem.operations[:2]]
    overlap = problem.model_copy(
        update={
            "operations": [*aux_ops, *problem.operations[2:]],
            "frozen_assignments": [
                {
                    "operation_id": aux_ops[0].id,
                    "work_center_id": aux_ops[0].eligible_work_center_ids[0],
                    "start": start,
                    "end": start + timedelta(minutes=aux_ops[0].duration_min),
                    "immutable": True,
                },
                {
                    "operation_id": aux_ops[1].id,
                    "work_center_id": aux_ops[1].eligible_work_center_ids[0],
                    "start": start,
                    "end": start + timedelta(minutes=aux_ops[1].duration_min),
                    "immutable": True,
                },
            ],
        }
    )
    with pytest.raises(ValueError, match="aux AUX-JIG"):
        RepairFlowProblem.model_validate(overlap.model_dump(mode="python"))

    wrong_setup = problem.model_copy(
        update={
            "frozen_assignments": [
                {
                    "operation_id": operation.id,
                    "work_center_id": operation.eligible_work_center_ids[0],
                    "start": start,
                    "end": start + timedelta(minutes=operation.duration_min),
                    "setup_minutes": 25,
                    "immutable": True,
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="setup"):
        RepairFlowProblem.model_validate(wrong_setup.model_dump(mode="python"))


def test_dependency_lock_requires_every_archive_hash() -> None:
    present = {
        "name": "demo",
        "version": "1",
        "scope": "direct",
        "archive": {"status": "present", "sha256": "ab" * 32},
    }
    missing = {
        "name": "other",
        "version": "1",
        "scope": "transitive",
        "archive": {"status": "editable", "sha256": None},
    }
    locked = build_dependency_lock({"components": [present]})
    assert locked["status"] == "locked"
    assert locked["signature"] == {"status": "absent", "sha256": None}
    incomplete = build_dependency_lock({"components": [present, missing]})
    assert incomplete["status"] == "incomplete"
