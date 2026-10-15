"""Behaviours the nightly mutmut run left alive.

Run 38698472141 on 7f6e9ae is the measurement. These tests are not in it.
"""

from __future__ import annotations

from datetime import timedelta

from repairflow.checker import _duration_violation, _setup, check_domain_assignments
from repairflow.lane_setup import lane_setup_evidence, stamp_canonical_lanes
from repairflow.model import CalendarWindow, Operation, PlannedAssignment, RepairFlowProblem, Violation
from repairflow.reasons import SUGGESTIONS, ReasonCode
from repairflow.synthetic import synthesize


def test_a_fractional_hold_names_the_whole_minute_sentence() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=1)
    visit = _visit(op, start, end=start + timedelta(minutes=op.duration_min, seconds=30))
    hit = _duration_violation(problem, op, visit)
    assert len(hit) == 1
    assert hit[0].message == "held interval is not a whole number of minutes"


def test_a_closed_window_keeps_the_window_suggestion() -> None:
    problem = synthesize("tiny", seed=1)
    center = next(row for row in problem.work_centers if row.calendar_id)
    calendar = next(row for row in problem.calendars if row.id == center.calendar_id)
    horizon = problem.planning_horizon
    short = calendar.model_copy(
        update={"windows": [CalendarWindow(start=horizon.start, end=horizon.start + timedelta(hours=1))]}
    )
    loaded = _reload(
        problem,
        calendars=[short if row.id == calendar.id else row for row in problem.calendars],
    )
    op = next(row for row in loaded.operations if center.id in row.eligible_work_center_ids)
    start = horizon.start + timedelta(hours=2)
    hit = _one(
        check_domain_assignments(loaded, [_visit(op, start, work_center_id=center.id)]),
        ReasonCode.CALENDAR_BROKEN,
    )
    assert hit.suggested_relaxation == SUGGESTIONS[ReasonCode.WINDOW_BROKEN]
    assert hit.operation_id == op.id
    assert hit.resource_id == center.id


def test_stamp_keeps_an_explicit_lane_and_a_single_lane_blank() -> None:
    problem = synthesize("tiny", seed=1)
    parallel = problem.work_centers[0]
    single = problem.work_centers[1]
    loaded = _parallel(problem, parallel.id, 2)
    start = loaded.planning_horizon.start + timedelta(hours=1)
    first, second = loaded.operations[0], loaded.operations[1]
    stamped = stamp_canonical_lanes(
        loaded,
        [
            _visit(first, start, work_center_id=parallel.id, lane=1, end=start + timedelta(minutes=10)),
            _visit(
                second,
                start + timedelta(minutes=10),
                work_center_id=parallel.id,
                lane=1,
                end=start + timedelta(minutes=20),
            ),
        ],
    )
    assert [row.lane for row in stamped] == [1, 1]

    third = loaded.operations[2]
    mixed = stamp_canonical_lanes(
        loaded,
        [
            _visit(first, start, work_center_id=parallel.id, end=start + timedelta(minutes=10)),
            _visit(third, start, work_center_id=single.id, end=start + timedelta(minutes=10)),
        ],
    )
    assert all(isinstance(row, PlannedAssignment) for row in mixed)
    assert mixed[1].lane is None
    assert mixed[0].lane == 0


def test_a_single_lane_ignores_a_declared_lane_index() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0]
    post = op.eligible_work_center_ids[0]
    start = problem.planning_horizon.start + timedelta(hours=1)
    placed = lane_setup_evidence(
        problem,
        [_visit(op, start, work_center_id=post, lane=3, end=start + timedelta(minutes=10))],
    )
    assert len(placed) == 1
    assert placed[0].lane_index == 0
    assert placed[0].ambiguous is False
    assert placed[0].work_center_id == post
    assert placed[0].end == start + timedelta(minutes=10)


def test_a_partial_lane_colouring_is_ambiguous() -> None:
    problem = _parallel(synthesize("tiny", seed=1), None, 2)
    post = problem.work_centers[0].id
    start = problem.planning_horizon.start + timedelta(hours=1)
    first, second = problem.operations[0], problem.operations[1]
    placed = {
        row.operation_id: row
        for row in lane_setup_evidence(
            problem,
            [
                _visit(first, start, work_center_id=post, lane=0, end=start + timedelta(minutes=30)),
                _visit(second, start, work_center_id=post, end=start + timedelta(minutes=30)),
            ],
        )
    }
    assert placed[first.id].ambiguous is True
    assert placed[second.id].ambiguous is True


def test_an_explicit_lane_past_capacity_keeps_its_fields_and_the_next_visit() -> None:
    problem = _parallel(synthesize("tiny", seed=1), None, 2)
    post = problem.work_centers[0].id
    start = problem.planning_horizon.start + timedelta(hours=1)
    first, second = problem.operations[0], problem.operations[1]
    placed = {
        row.operation_id: row
        for row in lane_setup_evidence(
            problem,
            [
                _visit(first, start, work_center_id=post, lane=2, end=start + timedelta(minutes=10)),
                _visit(
                    second,
                    start + timedelta(minutes=10),
                    work_center_id=post,
                    lane=0,
                    end=start + timedelta(minutes=20),
                ),
            ],
        )
    }
    broken = placed[first.id]
    assert broken.ambiguous is True
    assert broken.work_center_id == post
    assert broken.lane_index == 2
    assert broken.end == start + timedelta(minutes=10)
    assert broken.previous_state == ""
    assert second.id in placed
    kept = placed[second.id]
    assert kept.work_center_id == post
    assert kept.previous_operation_id is None
    assert kept.previous_state == "idle"
    assert kept.end == start + timedelta(minutes=20)


def test_an_unknown_explicit_operation_does_not_invent_a_setup_state() -> None:
    problem = _parallel(synthesize("tiny", seed=1), None, 2)
    post = problem.work_centers[0].id
    known = problem.operations[0]
    start = problem.planning_horizon.start + timedelta(hours=1)
    placed = {
        row.operation_id: row
        for row in lane_setup_evidence(
            problem,
            [
                _visit(
                    known,
                    start,
                    operation_id="OP-MISSING",
                    work_center_id=post,
                    lane=0,
                    end=start + timedelta(minutes=10),
                ),
                _visit(
                    known,
                    start + timedelta(minutes=10),
                    work_center_id=post,
                    lane=0,
                    end=start + timedelta(minutes=20),
                ),
            ],
        )
    }
    assert placed["OP-MISSING"].work_center_id == post
    assert placed[known.id].previous_state == ""
    assert placed[known.id].previous_operation_id == "OP-MISSING"


def test_a_later_visit_still_fits_after_one_overflow() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    start = problem.planning_horizon.start + timedelta(hours=1)
    ops = problem.operations[:3]
    placed = lane_setup_evidence(
        problem,
        [
            _visit(ops[0], start, work_center_id=post, end=start + timedelta(minutes=10)),
            _visit(ops[1], start, work_center_id=post, end=start + timedelta(minutes=40)),
            _visit(
                ops[2], start + timedelta(minutes=40), work_center_id=post, end=start + timedelta(minutes=50)
            ),
        ],
    )
    assert ops[2].id in {row.operation_id for row in placed}


def test_an_idle_lane_and_a_free_slot_are_one_state() -> None:
    problem = synthesize("tiny", seed=1)
    op = problem.operations[0].model_copy(update={"setup_state": "idle"})
    other = problem.operations[1]
    loaded = _parallel(_with_op(problem, op), op.eligible_work_center_ids[0], 2)
    post = op.eligible_work_center_ids[0]
    start = loaded.planning_horizon.start + timedelta(hours=1)
    placed = {
        row.operation_id: row
        for row in lane_setup_evidence(
            loaded,
            [
                _visit(op, start, work_center_id=post, end=start + timedelta(minutes=10)),
                _visit(
                    other,
                    start + timedelta(minutes=10),
                    work_center_id=post,
                    end=start + timedelta(minutes=20),
                ),
            ],
        )
    }
    assert placed[other.id].ambiguous is False


def test_zero_policy_accepts_a_later_missing_cell_as_zero_minutes() -> None:
    problem = synthesize("tiny", seed=1)
    loaded = _reload(
        problem, policy=problem.policy.model_copy(update={"missing_setup": "zero"}), setup_matrix=[]
    )
    post = loaded.work_centers[0].id
    start = loaded.planning_horizon.start + timedelta(hours=1)
    first, second = loaded.operations[0], loaded.operations[1]
    rows = [
        _visit(first, start, work_center_id=post, end=start + timedelta(minutes=10)),
        _visit(second, start + timedelta(minutes=10), work_center_id=post, end=start + timedelta(minutes=20)),
    ]
    found = _setup(loaded, rows)
    later = [row for row in found if row.operation_id == second.id]
    assert not any(row.code == ReasonCode.SETUP_MISMATCH for row in later)
    assert not any(row.code == ReasonCode.MISSING_SETUP for row in later)


def test_two_ambiguous_lanes_keep_the_sentence_and_both_visits() -> None:
    problem = _parallel(synthesize("tiny", seed=1), None, 2)
    post = problem.work_centers[0].id
    start = problem.planning_horizon.start + timedelta(hours=1)
    first, second = problem.operations[0], problem.operations[1]
    rows = [
        _visit(first, start, work_center_id=post, lane=0, end=start + timedelta(minutes=30)),
        _visit(second, start, work_center_id=post, end=start + timedelta(minutes=30)),
    ]
    found = [row for row in _setup(problem, rows) if row.details.get("ambiguous_lane") is True]
    assert {row.operation_id for row in found} == {first.id, second.id}
    for row in found:
        assert row.code == ReasonCode.SETUP_MISMATCH
        assert row.message == (
            f"lane assignment on {post} is ambiguous or inconsistent: "
            "supply one valid, non-overlapping lane id for every visit"
        )
        assert row.job_id == problem.operations[0].job_id or row.job_id == problem.operations[1].job_id
        assert row.resource_id == post
        assert row.start == start
        assert row.end == start + timedelta(minutes=30)
        assert row.operation_id in {first.id, second.id}


def test_a_missing_setup_cell_keeps_the_operation() -> None:
    problem = synthesize("tiny", seed=1)
    loaded = _reload(
        problem,
        policy=problem.policy.model_copy(update={"missing_setup": "zero"}),
        setup_matrix=[],
    )
    op = loaded.operations[0]
    post = op.eligible_work_center_ids[0]
    start = loaded.planning_horizon.start + timedelta(hours=1)
    hit = _one(_setup(loaded, [_visit(op, start, work_center_id=post)]), ReasonCode.MISSING_SETUP)
    assert hit.operation_id == op.id
    assert hit.job_id == op.job_id
    assert hit.resource_id == post


def _parallel(problem: RepairFlowProblem, center_id: str | None, lanes: int) -> RepairFlowProblem:
    target = center_id or problem.work_centers[0].id
    centers = [
        row.model_copy(update={"max_parallel": lanes}) if row.id == target else row
        for row in problem.work_centers
    ]
    return _reload(problem, work_centers=centers)


def _with_op(problem: RepairFlowProblem, edited: Operation) -> RepairFlowProblem:
    operations = [edited if row.id == edited.id else row for row in problem.operations]
    return _reload(problem, operations=operations)


def _reload(problem: RepairFlowProblem, **updates: object) -> RepairFlowProblem:
    return RepairFlowProblem.model_validate(problem.model_copy(update=updates).model_dump(mode="python"))


def _visit(op: Operation, start: object, **updates: object) -> PlannedAssignment:
    end = updates.pop("end", start + timedelta(minutes=op.duration_min))  # type: ignore[operator]
    work_center_id = updates.pop("work_center_id", op.eligible_work_center_ids[0])
    return PlannedAssignment(
        operation_id=str(updates.pop("operation_id", op.id)),
        work_center_id=str(work_center_id),
        start=start,  # type: ignore[arg-type]
        end=end,  # type: ignore[arg-type]
        lane=updates.pop("lane", None),  # type: ignore[arg-type]
    )


def _one(violations: list[Violation], code: ReasonCode) -> Violation:
    found = [row for row in violations if row.code == code]
    assert len(found) == 1, [row.message for row in violations]
    return found[0]
