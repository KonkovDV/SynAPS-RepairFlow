"""Each typed disruption rejects the issued plan and replans without moving frozen work."""

from __future__ import annotations

from datetime import timedelta

import pytest

from repairflow.events import (
    CrewAbsent,
    DurationOverrun,
    PartDelay,
    PostDown,
    UrgentJob,
    apply_disruption,
)
from repairflow.model import FrozenAssignment, Job, Operation
from repairflow.planner import plan, protected_operation_ids, recheck, replan_disruption
from repairflow.synthetic import synthesize


def _issued(seed: int = 1):
    problem = synthesize("tiny", seed=seed)
    base = plan(problem, solver_config="GREED")
    assert base.ok
    return problem, base


def _reject_and_replan(event, code: str, seed: int = 1) -> None:
    problem, base = _issued(seed)
    revised = apply_disruption(problem, event(problem, base))
    old = recheck(
        revised,
        assignments=list(base.result.assignments),
        kernel_status="feasible",
        solver_config="disruption-old",
    )
    assert code in {row.code for row in old.result.violations}
    assert old.result.verified_feasible is False
    repaired = replan_disruption(problem, base=base, event=event(problem, base))
    assert repaired.result.exit_code == 0
    assert repaired.result.verified_feasible is True
    placed = {row.operation_id: row for row in repaired.result.assignments}
    for frozen in problem.frozen_assignments:
        if not frozen.immutable:
            continue
        current = placed[frozen.operation_id]
        assert current.start == frozen.start
        assert current.work_center_id == frozen.work_center_id


def _post_down(_problem, base):
    row = base.result.assignments[0]
    return PostDown(work_center_id=row.work_center_id, start=row.start, end=row.end)


def _crew_absent(_problem, base):
    row = next(item for item in base.result.assignments if item.crew_id)
    return CrewAbsent(crew_id=row.crew_id or "", start=row.start, end=row.end)


def _part_delay(problem, base):
    ops = {operation.id: operation for operation in problem.operations}
    row = next(item for item in base.result.assignments if ops[item.operation_id].spare_demand())
    spare_id = next(iter(ops[row.operation_id].spare_demand()))
    return PartDelay(spare_id=spare_id, available_at=row.end)


def _overrun(problem, base):
    row = base.result.assignments[0]
    operation = next(item for item in problem.operations if item.id == row.operation_id)
    return DurationOverrun(operation_id=operation.id, new_duration_min=operation.duration_min + 30)


def _urgent(problem, _base):
    start = problem.planning_horizon.start
    return UrgentJob(
        job=Job(
            id="JOB-URGENT",
            unit_type="engine",
            release_date=start,
            due_date=problem.planning_horizon.end,
            priority=1,
        ),
        operations=[
            Operation(
                id="JOB-URGENT-01",
                job_id="JOB-URGENT",
                sequence=1,
                duration_min=30,
                eligible_work_center_ids=["POST-U1", "POST-TEST"],
                required_skills=["mechanical"],
                setup_state="engine",
            )
        ],
    )


def test_post_down_rejects_the_old_plan_and_replans() -> None:
    _reject_and_replan(_post_down, "CALENDAR_BROKEN")


def test_crew_absent_rejects_the_old_plan_and_replans() -> None:
    _reject_and_replan(_crew_absent, "CALENDAR_BROKEN")


def test_part_delay_rejects_the_old_plan_and_replans() -> None:
    _reject_and_replan(_part_delay, "SPARE_UNAVAILABLE")


def test_duration_overrun_rejects_the_old_plan_and_replans() -> None:
    _reject_and_replan(_overrun, "INVALID_DURATION")


def test_urgent_job_rejects_the_old_plan_and_replans() -> None:
    _reject_and_replan(_urgent, "PARTIAL_COVERAGE")


def test_unknown_disruption_ids_are_errors() -> None:
    problem, base = _issued()
    start = problem.planning_horizon.start
    end = start + timedelta(hours=1)
    with pytest.raises(ValueError, match="unknown work center"):
        apply_disruption(problem, PostDown(work_center_id="NO-POST", start=start, end=end))
    with pytest.raises(ValueError, match="unknown crew"):
        apply_disruption(problem, CrewAbsent(crew_id="NO-CREW", start=start, end=end))
    with pytest.raises(ValueError, match="unknown spare"):
        apply_disruption(problem, PartDelay(spare_id="NO-SPARE", available_at=end))
    with pytest.raises(ValueError, match="unknown operation"):
        apply_disruption(problem, DurationOverrun(operation_id="NO-OP", new_duration_min=90))
    assert base.ok


def test_post_down_does_not_close_a_shared_calendar() -> None:
    problem, base = _issued()
    event = _post_down(problem, base)
    original = next(row for row in problem.calendars if row.id == "CAL-DAY")
    revised = apply_disruption(problem, event)
    kept = next(row for row in revised.calendars if row.id == "CAL-DAY")
    assert [(row.start, row.end) for row in kept.windows] == [
        (row.start, row.end) for row in original.windows
    ]
    hit = next(row for row in revised.work_centers if row.id == event.work_center_id)
    assert hit.calendar_id != "CAL-DAY"
    others = [
        row for row in revised.work_centers if row.id != event.work_center_id and row.calendar_id == "CAL-DAY"
    ]
    assert others


def test_rolling_window_keeps_early_visits() -> None:
    problem, base = _issued()
    ordered = sorted(base.result.assignments, key=lambda row: row.start)
    late = ordered[-1]
    now = late.start - timedelta(hours=9)
    event = PostDown(work_center_id=late.work_center_id, start=late.start, end=late.end)
    repaired = replan_disruption(problem, base=base, event=event, now=now)
    assert repaired.result.verified_feasible is True
    placed = {row.operation_id: row for row in repaired.result.assignments}
    early = [
        row
        for row in protected_operation_ids(list(base.result.assignments), now=now)
        if row != late.operation_id
    ]
    assert early
    for op_id in early:
        old = next(row for row in base.result.assignments if row.operation_id == op_id)
        assert placed[op_id].start == old.start
        assert placed[op_id].work_center_id == old.work_center_id
    assert "nervousness" in repaired.result.metadata


def test_an_unrelated_frozen_slot_stays() -> None:
    problem, base = _issued()
    keep = base.result.assignments[0]
    move = next(
        row
        for row in base.result.assignments
        if row.operation_id != keep.operation_id and row.work_center_id != keep.work_center_id
    )
    frozen = FrozenAssignment(
        operation_id=keep.operation_id,
        work_center_id=keep.work_center_id,
        crew_id=keep.crew_id,
        start=keep.start,
        end=keep.end,
        setup_minutes=keep.setup_minutes,
        immutable=True,
    )
    locked = problem.model_copy(update={"frozen_assignments": [frozen]})
    issued = plan(locked, solver_config="GREED")
    assert issued.ok
    event = PostDown(work_center_id=move.work_center_id, start=move.start, end=move.end)
    repaired = replan_disruption(locked, base=issued, event=event)
    placed = next(row for row in repaired.result.assignments if row.operation_id == keep.operation_id)
    assert placed.start == keep.start
    assert placed.work_center_id == keep.work_center_id
