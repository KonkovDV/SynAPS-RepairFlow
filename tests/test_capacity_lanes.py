"""Sweep-line lane oracle. The brute counter is independent of the sweep."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from synaps.model import SolverStatus
from synaps.solvers.coverage_outcome import CoverageClass

from repairflow.capacity import Excess, Occupancy, excess_arrivals, peak_concurrency
from repairflow.checker import _capacity_overlaps
from repairflow.model import FrozenAssignment, PlannedAssignment, RepairFlowProblem, Violation
from repairflow.planner import classify_result
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize

_BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _occ(start_min: int, end_min: int, name: str) -> Occupancy:
    return Occupancy(_BASE + timedelta(minutes=start_min), _BASE + timedelta(minutes=end_min), name)


def brute_peak(intervals: list[Occupancy]) -> int:
    """Count coverage at every start. Half-open peaks occur at a start event."""

    peak = 0
    for row in intervals:
        if row.start >= row.end:
            continue
        cover = sum(1 for other in intervals if other.start <= row.start < other.end)
        peak = max(peak, cover)
    return peak


def test_staggered_visits_peak_at_two_not_three() -> None:
    intervals = [_occ(0, 10, "a"), _occ(1, 3, "b"), _occ(5, 7, "c")]
    assert peak_concurrency(intervals) == 2
    assert excess_arrivals(intervals, 2) == []
    assert excess_arrivals(intervals, 1)


def test_touching_endpoints_share_no_lane() -> None:
    intervals = [_occ(0, 10, "a"), _occ(10, 20, "b")]
    assert peak_concurrency(intervals) == 1
    assert excess_arrivals(intervals, 1) == []


def test_zero_length_interval_is_not_occupancy() -> None:
    assert peak_concurrency([_occ(5, 5, "a"), _occ(0, 10, "b")]) == 1


def _planned(name: str, start_min: int, end_min: int, *, setup: int = 0) -> PlannedAssignment:
    window = _occ(start_min, end_min, name)
    return PlannedAssignment(
        operation_id=name,
        work_center_id="POST",
        start=window.start,
        end=window.end,
        setup_minutes=setup,
    )


def test_checker_counts_setup_and_ignores_staggered_false_overlap() -> None:
    post = "POST"
    rows = [_planned("a", 0, 30), _planned("b", 30, 50, setup=10)]
    hit = _capacity_overlaps({post: rows}, {post: 1}, ReasonCode.CENTER_OVERLAP, include_setup=True)
    assert len(hit) == 1
    assert hit[0].operation_id == "b"
    assert hit[0].details["active"] == 2

    staggered = [_planned("a", 0, 10), _planned("b", 1, 3), _planned("c", 5, 7)]
    quiet = _capacity_overlaps({post: staggered}, {post: 2}, ReasonCode.CENTER_OVERLAP, include_setup=True)
    assert quiet == []
    crowded = _capacity_overlaps({post: staggered}, {post: 1}, ReasonCode.CENTER_OVERLAP, include_setup=True)
    assert crowded
    assert all(row.code == ReasonCode.CENTER_OVERLAP for row in crowded)


def test_frozen_lanes_follow_the_same_peak() -> None:
    problem = synthesize("tiny", seed=1)
    start = problem.planning_horizon.start + timedelta(hours=8)
    post = problem.operations[0].eligible_work_center_ids[0]
    ops = []
    for operation in problem.operations[:3]:
        ops.append(operation.model_copy(update={"predecessor_ids": [], "eligible_work_center_ids": [post]}))
    others = [row for row in problem.operations if row.id not in {item.id for item in ops}]
    centers = [
        row.model_copy(update={"max_parallel": 2}) if row.id == post else row for row in problem.work_centers
    ]
    crews = [row.model_copy(update={"max_parallel": 3}) for row in problem.crews]

    def crew_for(skills: list[str]) -> str:
        for crew in crews:
            if set(skills) <= set(crew.skills):
                return crew.id
        raise AssertionError(skills)

    def freeze(index: int, begin: int, end: int) -> FrozenAssignment:
        return FrozenAssignment(
            operation_id=ops[index].id,
            work_center_id=post,
            crew_id=crew_for(ops[index].required_skills),
            start=start + timedelta(minutes=begin),
            end=start + timedelta(minutes=end),
        )

    staggered = problem.model_copy(
        update={
            "operations": [*ops, *others],
            "work_centers": centers,
            "crews": crews,
            "frozen_assignments": [freeze(0, 0, 10), freeze(1, 1, 3), freeze(2, 5, 7)],
        }
    )
    loaded = RepairFlowProblem.model_validate(staggered.model_dump(mode="python"))
    assert loaded.frozen_assignments

    simultaneous = problem.model_copy(
        update={
            "operations": [*ops, *others],
            "work_centers": centers,
            "crews": crews,
            "frozen_assignments": [freeze(0, 0, 10), freeze(1, 0, 10), freeze(2, 0, 10)],
        }
    )
    with pytest.raises(ValueError, match="frozen overlap"):
        RepairFlowProblem.model_validate(simultaneous.model_dump(mode="python"))


@given(
    st.lists(
        st.tuples(st.integers(min_value=0, max_value=400), st.integers(min_value=1, max_value=30)),
        max_size=12,
    )
)
@settings(max_examples=40, deadline=None)
def test_sweep_matches_critical_point_count(spans: list[tuple[int, int]]) -> None:
    intervals = [
        _occ(start, start + duration, f"op-{index}") for index, (start, duration) in enumerate(spans)
    ]
    assert peak_concurrency(intervals) == brute_peak(intervals)


def reference_excess(intervals: list[Occupancy], capacity: int) -> list[Excess]:
    """Arrivals that push coverage above K, ordered by start then list index.

    Coverage at an instant is half-open. Ends at that instant are already gone.
    Arrivals that share a timestamp are taken in list order, which is the sweep
    tie-break, without using the sweep itself.
    """

    positive = [(index, row) for index, row in enumerate(intervals) if row.start < row.end]
    witnesses: list[Excess] = []
    for instant in sorted({row.start for _, row in positive}):
        open_rows = [row for _, row in positive if row.start < instant < row.end]
        arrivals = [row for _, row in sorted(positive) if row.start == instant]
        for row in arrivals:
            open_rows.append(row)
            active = len(open_rows)
            if active <= capacity:
                continue
            others = sorted(item.operation_id for item in open_rows if item is not row)
            witnesses.append(
                Excess(
                    operation_id=row.operation_id,
                    other_operation_id=others[0] if others else None,
                    start=instant,
                    end=min(item.end for item in open_rows),
                    active=active,
                )
            )
    return witnesses


def test_simultaneous_starts_blame_only_the_arrivals_past_capacity() -> None:
    intervals = [_occ(0, 10, "a"), _occ(0, 10, "b"), _occ(0, 8, "c")]
    assert excess_arrivals(intervals, 1) == reference_excess(intervals, 1)
    assert [row.operation_id for row in excess_arrivals(intervals, 1)] == ["b", "c"]
    assert [row.active for row in excess_arrivals(intervals, 1)] == [2, 3]


def test_negative_capacity_is_rejected() -> None:
    with pytest.raises(ValueError, match="capacity must be non-negative"):
        excess_arrivals([_occ(0, 1, "a")], -1)


def test_unknown_resource_defaults_to_one_lane() -> None:
    rows = [_planned("a", 0, 10), _planned("b", 0, 10)]
    hit = _capacity_overlaps({"UNKNOWN": rows}, {}, ReasonCode.CENTER_OVERLAP, include_setup=True)
    assert [row.operation_id for row in hit] == ["b"]
    assert hit[0].details["capacity"] == 1


def test_capacity_violation_cannot_be_verified() -> None:
    violation = Violation(
        code=ReasonCode.CENTER_OVERLAP, message="resource exceeds capacity", severity="hard"
    )
    status, verified, exit_code, claim = classify_result(
        solver_config="GREED",
        kernel_status=SolverStatus.FEASIBLE,
        coverage=CoverageClass.FULL,
        violations=[violation],
        engine_violations=[],
        usage_error=False,
    )
    assert verified is False
    assert exit_code == 2
    assert claim == "rejected"
    assert status.value != "OPTIMAL"


@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=80),
            st.integers(min_value=-5, max_value=40),
        ),
        max_size=12,
    ),
    st.integers(min_value=0, max_value=8),
)
@settings(max_examples=40, deadline=None)
def test_excess_arrivals_match_the_critical_point_reference(
    spans: list[tuple[int, int]],
    capacity: int,
) -> None:
    intervals = [
        _occ(start, start + duration, f"op-{index}") for index, (start, duration) in enumerate(spans)
    ]
    assert excess_arrivals(intervals, capacity) == reference_excess(intervals, capacity)
    assert peak_concurrency(intervals) == brute_peak(intervals)
    assert (peak_concurrency(intervals) > capacity) == bool(excess_arrivals(intervals, capacity))


@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=80),
            st.integers(min_value=0, max_value=40),
            st.integers(min_value=0, max_value=20),
        ),
        max_size=8,
    ),
    st.integers(min_value=0, max_value=6),
)
@settings(max_examples=40, deadline=None)
def test_checker_setup_occupancy_matches_the_reference(
    spans: list[tuple[int, int, int]],
    capacity: int,
) -> None:
    rows = [
        _planned(f"op-{index}", start, start + duration, setup=setup)
        for index, (start, duration, setup) in enumerate(spans)
    ]
    intervals = [
        Occupancy(row.start - timedelta(minutes=row.setup_minutes), row.end, row.operation_id) for row in rows
    ]
    expected = reference_excess(intervals, capacity)
    found = _capacity_overlaps(
        {"POST": rows},
        {"POST": capacity},
        ReasonCode.CENTER_OVERLAP,
        include_setup=True,
    )
    assert [(row.operation_id, row.details["active"], row.start, row.end) for row in found] == [
        (row.operation_id, row.active, row.start, row.end) for row in expected
    ]
    assert all(row.code == ReasonCode.CENTER_OVERLAP and row.severity == "hard" for row in found)
