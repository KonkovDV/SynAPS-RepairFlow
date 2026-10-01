"""Reference tests for lane-local setup transitions."""

from __future__ import annotations

import itertools
import random
from datetime import datetime, timedelta

import pytest

from repairflow.checker import _setup
from repairflow.checker_primitives import lookup_setup_minutes
from repairflow.lane_setup import lane_local_setup_placements
from repairflow.model import PlannedAssignment
from repairflow.planner import domain_greed, plan, replan_after_disruption
from repairflow.synthetic import synthesize


def test_parallel_lanes_keep_independent_setup_state() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    loaded = problem.model_copy(
        update={
            "work_centers": [
                row.model_copy(update={"max_parallel": 2}) if row.id == post else row
                for row in problem.work_centers
            ]
        }
    )
    start = loaded.planning_horizon.start + timedelta(hours=8)
    operations = [row for row in loaded.operations if post in row.eligible_work_center_ids][:3]
    rows = [
        PlannedAssignment(
            operation_id=operations[0].id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=20),
        ),
        PlannedAssignment(
            operation_id=operations[1].id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=30),
        ),
        PlannedAssignment(
            operation_id=operations[2].id,
            work_center_id=post,
            start=start + timedelta(minutes=20),
            end=start + timedelta(minutes=40),
        ),
    ]
    placements = lane_local_setup_placements(loaded, rows)
    by_id = {row.operation_id: row for row in placements}
    assert by_id[operations[0].id].lane_index == 0
    assert by_id[operations[1].id].lane_index == 1
    assert by_id[operations[2].id].lane_index == 0
    assert by_id[operations[2].id].previous_operation_id == operations[0].id


def test_setup_occupancy_is_half_open_for_lane_reuse() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    operation_a, operation_b = [row for row in problem.operations if post in row.eligible_work_center_ids][:2]
    start = problem.planning_horizon.start + timedelta(hours=8)
    rows = [
        PlannedAssignment(
            operation_id=operation_a.id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=20),
        ),
        PlannedAssignment(
            operation_id=operation_b.id,
            work_center_id=post,
            start=start + timedelta(minutes=20),
            end=start + timedelta(minutes=40),
        ),
    ]
    placements = lane_local_setup_placements(problem, rows)
    assert [row.lane_index for row in placements] == [0, 0]


def test_parallel_capacity_overflow_is_explicit() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    start = problem.planning_horizon.start + timedelta(hours=8)
    operations = [row for row in problem.operations if post in row.eligible_work_center_ids][:2]
    rows = [
        PlannedAssignment(
            operation_id=operation.id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=20),
        )
        for operation in operations
    ]
    with pytest.raises(ValueError, match="exceed capacity"):
        lane_local_setup_placements(problem, rows)


def test_checker_reads_setup_from_the_reused_lane() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    chosen = [row for row in problem.operations if post in row.eligible_work_center_ids][:3]
    states = {chosen[0].id: "engine", chosen[1].id: "gearbox", chosen[2].id: "gearbox"}
    loaded = problem.model_copy(
        update={
            "operations": [
                row.model_copy(update={"setup_state": states[row.id]}) if row.id in states else row
                for row in problem.operations
            ],
            "work_centers": [
                row.model_copy(update={"max_parallel": 2}) if row.id == post else row
                for row in problem.work_centers
            ],
        }
    )
    start = loaded.planning_horizon.start + timedelta(hours=8)
    correct = [
        PlannedAssignment(
            operation_id=chosen[0].id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=20),
            setup_minutes=0,
        ),
        PlannedAssignment(
            operation_id=chosen[1].id,
            work_center_id=post,
            start=start,
            end=start + timedelta(minutes=40),
            setup_minutes=0,
        ),
        PlannedAssignment(
            operation_id=chosen[2].id,
            work_center_id=post,
            start=start + timedelta(minutes=45),
            end=start + timedelta(minutes=65),
            setup_minutes=25,
        ),
    ]
    assert _setup(loaded, correct) == []
    unary = [
        row.model_copy(update={"setup_minutes": 0}) if row.operation_id == chosen[2].id else row
        for row in correct
    ]
    violations = _setup(loaded, unary)
    assert [row.code for row in violations] == ["SETUP_MISMATCH"]
    assert violations[0].operation_id == chosen[2].id
    assert violations[0].details["lane_index"] == 0
    assert violations[0].details["previous_operation_id"] == chosen[0].id
    assert violations[0].details["from_state"] == "engine"


def test_domain_greed_overlaps_independent_lanes() -> None:
    problem = synthesize("tiny", seed=1)
    post = "POST-U1"
    mechanical = [
        row
        for row in problem.operations
        if post in row.eligible_work_center_ids and "mechanical" in row.required_skills
    ]
    first, second = mechanical[:2]
    operations = [
        first.model_copy(
            update={
                "setup_state": "engine",
                "predecessor_ids": [],
                "required_aux_ids": [],
                "required_spare_ids": [],
                "duration_min": 30,
                "eligible_work_center_ids": [post],
            }
        ),
        second.model_copy(
            update={
                "setup_state": "gearbox",
                "predecessor_ids": [],
                "required_aux_ids": [],
                "required_spare_ids": [],
                "duration_min": 30,
                "eligible_work_center_ids": [post],
            }
        ),
    ]
    crew = next(row for row in problem.crews if "mechanical" in row.skills)
    jobs = []
    for job in problem.jobs:
        if job.id in {first.job_id, second.job_id}:
            jobs.append(job.model_copy(update={"release_date": problem.planning_horizon.start}))
    loaded = problem.model_copy(
        update={
            "operations": operations,
            "jobs": jobs,
            "crews": [crew, crew.model_copy(update={"id": "CREW-MECH-2", "code": "CREW-MECH-2"})],
            "work_centers": [
                row.model_copy(update={"max_parallel": 2}) if row.id == post else row
                for row in problem.work_centers
            ],
            "frozen_assignments": [],
        }
    )
    placed = domain_greed(loaded)
    assert len(placed) == 2
    left, right = placed
    assert left.start < right.end and right.start < left.end
    assert _setup(loaded, placed) == []
    assert {row.setup_minutes for row in placed} == {0}


def test_disruption_repair_does_not_borrow_the_other_lane() -> None:
    problem = synthesize("tiny", seed=1)
    post = "POST-U1"
    mechanical = [
        row
        for row in problem.operations
        if post in row.eligible_work_center_ids and "mechanical" in row.required_skills
    ]
    anchor, other = mechanical[:2]
    follower = anchor.model_copy(update={"id": f"{anchor.id}-F", "sequence": anchor.sequence + 1})
    operations = [
        anchor.model_copy(
            update={
                "setup_state": "engine",
                "predecessor_ids": [],
                "required_aux_ids": [],
                "required_spare_ids": [],
                "duration_min": 30,
                "eligible_work_center_ids": [post],
            }
        ),
        follower.model_copy(
            update={
                "setup_state": "gearbox",
                "predecessor_ids": [anchor.id],
                "required_aux_ids": [],
                "required_spare_ids": [],
                "duration_min": 30,
                "eligible_work_center_ids": [post],
            }
        ),
        other.model_copy(
            update={
                "setup_state": "compressor",
                "predecessor_ids": [],
                "required_aux_ids": [],
                "required_spare_ids": [],
                "duration_min": 30,
                "eligible_work_center_ids": [post],
            }
        ),
    ]
    crew = next(row for row in problem.crews if "mechanical" in row.skills)
    jobs = []
    for job in problem.jobs:
        if job.id in {anchor.job_id, other.job_id, follower.job_id}:
            jobs.append(job.model_copy(update={"release_date": problem.planning_horizon.start}))
    loaded = problem.model_copy(
        update={
            "operations": operations,
            "jobs": jobs,
            "crews": [
                crew,
                crew.model_copy(update={"id": "CREW-MECH-2", "code": "CREW-MECH-2"}),
            ],
            "work_centers": [
                row.model_copy(update={"max_parallel": 2}) if row.id == post else row
                for row in problem.work_centers
            ],
            "frozen_assignments": [],
        }
    )
    base = plan(loaded, solver_config="GREED")
    assert base.result.exit_code == 0
    before = lane_local_setup_placements(loaded, base.result.assignments)
    before_by_id = {row.operation_id: row for row in before}
    assert before_by_id[other.id].lane_index != before_by_id[anchor.id].lane_index
    repaired = replan_after_disruption(
        loaded,
        base=base,
        disrupted_operation_ids=[anchor.id],
    )
    assert repaired.result.exit_code == 0
    assert not any(row.code == "SETUP_MISMATCH" for row in repaired.result.violations)
    after = {row.operation_id: row for row in repaired.result.assignments}
    kept = after[other.id]
    original = next(row for row in base.result.assignments if row.operation_id == other.id)
    assert (kept.work_center_id, kept.start, kept.end, kept.setup_minutes) == (
        original.work_center_id,
        original.start,
        original.end,
        original.setup_minutes,
    )
    coloured = lane_local_setup_placements(repaired.problem, repaired.result.assignments)
    coloured_by_id = {row.operation_id: row for row in coloured}
    assert coloured_by_id[other.id].previous_state == before_by_id[other.id].previous_state
    assert coloured_by_id[other.id].previous_operation_id is None
    follower_row = coloured_by_id[follower.id]
    written = after[follower.id]
    assert follower_row.expected_setup_minutes == written.setup_minutes


def test_lane_colouring_matches_lexicographic_brute_force() -> None:
    problem = synthesize("tiny", seed=1)
    post = problem.work_centers[0].id
    templates = [row for row in problem.operations if post in row.eligible_work_center_ids][:6]
    states = ["engine", "gearbox", "compressor", "electrical"]
    rng = random.Random(0)
    for trial in range(40):
        count = rng.randint(1, len(templates))
        capacity = rng.randint(1, 3)
        chosen = []
        for index, template in enumerate(templates[:count]):
            chosen.append(
                template.model_copy(
                    update={
                        "setup_state": states[(trial + index) % len(states)],
                        "predecessor_ids": [],
                    }
                )
            )
        loaded = problem.model_copy(
            update={
                "operations": [
                    *chosen,
                    *[row for row in problem.operations if row.id not in {item.id for item in chosen}],
                ],
                "work_centers": [
                    row.model_copy(update={"max_parallel": capacity}) if row.id == post else row
                    for row in problem.work_centers
                ],
            }
        )
        origin = loaded.planning_horizon.start + timedelta(hours=8)
        rows = []
        for operation in chosen:
            begin = origin + timedelta(minutes=rng.randint(0, 80))
            setup = rng.choice((0, 10))
            duration = rng.randint(5, 30)
            rows.append(
                PlannedAssignment(
                    operation_id=operation.id,
                    work_center_id=post,
                    start=begin + timedelta(minutes=setup),
                    end=begin + timedelta(minutes=setup + duration),
                    setup_minutes=setup,
                )
            )
        expected = _lexicographic_lanes(rows, capacity)
        if expected is None:
            with pytest.raises(ValueError, match="exceed capacity"):
                lane_local_setup_placements(loaded, rows)
            continue
        placements = lane_local_setup_placements(loaded, rows)
        ordered = sorted(
            rows,
            key=lambda row: (
                row.start - timedelta(minutes=row.setup_minutes),
                row.end,
                row.operation_id,
            ),
        )
        by_id = {row.operation_id: row for row in placements}
        operations = {row.id: row for row in loaded.operations}
        lane_state: dict[int, tuple[str, str | None]] = {}
        for lane, row in zip(expected, ordered, strict=True):
            previous_state, previous_id = lane_state.get(lane, ("idle", None))
            operation = operations[row.operation_id]
            minutes = lookup_setup_minutes(
                loaded,
                work_center_id=post,
                from_state=previous_state,
                to_state=operation.setup_state,
            )
            found = by_id[row.operation_id]
            assert found.lane_index == lane
            assert found.previous_state == previous_state
            assert found.previous_operation_id == previous_id
            assert found.expected_setup_minutes == minutes
            lane_state[lane] = (operation.setup_state, row.operation_id)


def _lexicographic_lanes(rows: list[PlannedAssignment], capacity: int) -> tuple[int, ...] | None:
    """Enumerate proper colourings and keep the earliest-free lane sequence.

    A reusable lane sorts by the time it became free, then by index. Opening a
    new lane is considered only when every existing lane is still busy. This
    search does not share the production loop.
    """

    ordered = sorted(
        rows,
        key=lambda row: (
            row.start - timedelta(minutes=row.setup_minutes),
            row.end,
            row.operation_id,
        ),
    )
    best_key: tuple[tuple[int, float, int], ...] | None = None
    best: tuple[int, ...] | None = None
    for coloring in itertools.product(range(capacity), repeat=len(ordered)):
        ends: list[datetime | None] = [None] * capacity
        keys: list[tuple[int, float, int]] = []
        proper = True
        for lane, row in zip(coloring, ordered, strict=True):
            start = row.start - timedelta(minutes=row.setup_minutes)
            previous = ends[lane]
            if previous is not None and previous > start:
                proper = False
                break
            if previous is None:
                keys.append((1, 0.0, lane))
            else:
                keys.append((0, previous.timestamp(), lane))
            ends[lane] = row.end
        if not proper:
            continue
        signature = tuple(keys)
        if best_key is None or signature < best_key:
            best_key = signature
            best = coloring
    return best
