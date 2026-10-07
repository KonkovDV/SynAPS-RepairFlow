"""Hand cases for the minute oracle. These tests do not import the checker."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.oracle_minutes import OracleLimit, hard_codes

from repairflow.model import (
    AuxResource,
    Calendar,
    CalendarWindow,
    Crew,
    DataProvenance,
    FrozenAssignment,
    Job,
    Operation,
    PlannedAssignment,
    PlanningHorizon,
    PredecessorLink,
    RepairFlowProblem,
    SetupEntry,
    Spare,
    SpareReceipt,
    WorkCenter,
)

_STATES = ("idle", "engine")


def _at(hour: int, minute: int = 0, *, day: int = 12) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def _matrix(idle_to_engine: int = 0) -> list[SetupEntry]:
    rows: list[SetupEntry] = []
    for source in _STATES:
        for target in _STATES:
            minutes = idle_to_engine if (source, target) == ("idle", "engine") else 0
            rows.append(
                SetupEntry(
                    from_state=source,
                    to_state=target,
                    duration_min=minutes,
                    work_center_id="POST",
                )
            )
    return rows


def _operation(op_id: str, *, sequence: int, preds: list[str] | None = None) -> Operation:
    return Operation(
        id=op_id,
        job_id="JOB",
        sequence=sequence,
        duration_min=60,
        predecessor_ids=preds or [],
        eligible_work_center_ids=["POST"],
        required_skills=["mechanical"],
        setup_state="engine",
    )


def _problem(
    operations: list[Operation] | None = None,
    *,
    idle_to_engine: int = 0,
    crews: list[Crew] | None = None,
    aux: list[AuxResource] | None = None,
    spares: list[Spare] | None = None,
    frozen: list[FrozenAssignment] | None = None,
    windows: list[CalendarWindow] | None = None,
    horizon_end: datetime | None = None,
    provenance: DataProvenance = "synthetic",
    calendar_id: str | None = "CAL",
    post_attributes: dict[str, object] | None = None,
    crew_attributes: dict[str, object] | None = None,
) -> RepairFlowProblem:
    start = _at(8)
    end = horizon_end or _at(18)
    calendar_windows = windows if windows is not None else [CalendarWindow(start=start, end=end)]
    crew = Crew(
        id="CREW",
        code="CREW",
        skills=["mechanical"],
        calendar_id=calendar_id,
        domain_attributes=crew_attributes or {},
    )
    return RepairFlowProblem(
        instance_id="oracle-hand",
        data_provenance=provenance,
        planning_horizon=PlanningHorizon(start=start, end=end),
        jobs=[Job(id="JOB", unit_type="engine")],
        operations=operations or [_operation("OP", sequence=1)],
        work_centers=[
            WorkCenter(
                id="POST",
                code="POST",
                calendar_id=calendar_id,
                eligible_unit_types=["engine"],
                domain_attributes=post_attributes or {},
            )
        ],
        crews=crews or [crew],
        aux_resources=aux or [],
        setup_matrix=_matrix(idle_to_engine),
        calendars=[Calendar(id="CAL", code="CAL", windows=calendar_windows)],
        frozen_assignments=frozen or [],
        spares=spares or [],
    )


def _place(
    op_id: str = "OP",
    hour: int = 8,
    minute: int = 0,
    *,
    duration: int = 60,
    setup: int = 0,
    crew: str | None = "CREW",
    aux: list[str] | None = None,
) -> PlannedAssignment:
    start = _at(hour, minute)
    return PlannedAssignment(
        operation_id=op_id,
        work_center_id="POST",
        start=start,
        end=start + timedelta(minutes=duration),
        crew_id=crew,
        setup_minutes=setup,
        aux_ids=aux or [],
    )


def test_oracle_imports_only_the_model() -> None:
    tree = ast.parse(Path("tests/oracle_minutes.py").read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    assert modules
    imported = [name for name in modules if name != "__future__"]
    assert imported
    assert all(name == "datetime" or name == "repairflow.model" for name in imported)


def test_a_clean_visit_is_accepted() -> None:
    assert hard_codes(_problem(), [_place()]) == frozenset()


def test_one_minute_of_overlap_is_rejected_and_a_shared_endpoint_is_not() -> None:
    operations = [_operation("A", sequence=1), _operation("B", sequence=2, preds=["A"])]
    problem = _problem(operations)
    overlap = [_place("A", 8), _place("B", 8, 59)]
    touching = [_place("A", 8), _place("B", 9)]
    assert "POST_OVERLAP" in hard_codes(problem, overlap)
    assert "CREW_OVERLAP" in hard_codes(problem, overlap)
    assert hard_codes(problem, touching) == frozenset()


def test_setup_occupancy_can_overlap_when_processing_only_touches() -> None:
    operations = [_operation("A", sequence=1), _operation("B", sequence=2, preds=["A"])]
    problem = _problem(operations, idle_to_engine=0)
    # B's processing starts when A ends, but 30 minutes of setup runs during A.
    # The matrix cell for the second visit is engine→engine, which is 0, so the
    # written 30 is a setup mismatch as well as an overlap.
    codes = hard_codes(problem, [_place("A", 8), _place("B", 9, setup=30)])
    assert "POST_OVERLAP" in codes


def test_skill_permit_must_reach_the_visit_end() -> None:
    problem = _problem()
    crew = problem.crews[0].model_copy(update={"skill_valid_until": {"mechanical": _at(9)}})
    covered = problem.model_copy(update={"crews": [crew]})
    assert hard_codes(covered, [_place()]) == frozenset()
    expired = crew.model_copy(update={"skill_valid_until": {"mechanical": _at(8, 59)}})
    short = problem.model_copy(update={"crews": [expired]})
    assert hard_codes(short, [_place()]) == frozenset({"SKILL_EXPIRED"})


def test_a_late_due_date_is_not_a_hard_reject_and_a_deadline_is() -> None:
    problem = _problem()
    due = problem.jobs[0].model_copy(update={"due_date": _at(8, 30)})
    assert hard_codes(problem.model_copy(update={"jobs": [due]}), [_place()]) == frozenset()
    deadline = problem.jobs[0].model_copy(update={"deadline": _at(8, 30)})
    codes = hard_codes(problem.model_copy(update={"jobs": [deadline]}), [_place()])
    assert codes == frozenset({"DEADLINE_MISSED"})


def test_closed_calendar_and_a_visit_outside_its_only_window() -> None:
    closed = _problem(windows=[])
    assert "CALENDAR_BROKEN" in hard_codes(closed, [_place()])
    narrow = _problem(windows=[CalendarWindow(start=_at(8), end=_at(8, 30))])
    # Duration stays 60, so the visit runs past the only window and stays inside the horizon.
    assert "CALENDAR_BROKEN" in hard_codes(narrow, [_place()])
    assert "HORIZON_VIOLATION" not in hard_codes(narrow, [_place()])


def test_precedence_lag_bounds() -> None:
    operations = [_operation("A", sequence=1), _operation("B", sequence=2)]
    link = operations[1].model_copy(
        update={"predecessors": [PredecessorLink(id="A", min_lag_min=15, max_lag_min=30)]}
    )
    # predecessor_ids is filled from the link list by the model.
    problem = _problem([operations[0], link])
    too_soon = hard_codes(problem, [_place("A", 8), _place("B", 9)])
    assert "PRECEDENCE_BROKEN" in too_soon
    on_time = hard_codes(problem, [_place("A", 8), _place("B", 9, 15)])
    assert on_time == frozenset()
    too_late = hard_codes(problem, [_place("A", 8), _place("B", 9, 31)])
    assert "PRECEDENCE_BROKEN" in too_late


def test_missing_coverage_duplicate_and_unknown_crew() -> None:
    assert hard_codes(_problem(), []) == frozenset({"PARTIAL_COVERAGE"})
    doubled = [_place(), _place()]
    assert "DUPLICATE_ASSIGNMENT" in hard_codes(_problem(), doubled)
    assert "UNKNOWN_RESOURCE" in hard_codes(_problem(), [_place(crew="OTHER")])


def test_frozen_slot_must_stay_put() -> None:
    frozen = FrozenAssignment(
        operation_id="OP",
        work_center_id="POST",
        crew_id="CREW",
        start=_at(8),
        end=_at(9),
        setup_minutes=0,
    )
    problem = _problem(frozen=[frozen])
    assert hard_codes(problem, [_place()]) == frozenset()
    assert hard_codes(problem, [_place(hour=10)]) == frozenset({"FROZEN_MOVED"})


def test_setup_must_match_the_idle_cell() -> None:
    problem = _problem(idle_to_engine=25)
    assert "SETUP_MISMATCH" in hard_codes(problem, [_place(minute=30)])
    assert hard_codes(problem, [_place(minute=30, setup=25)]) == frozenset()


def test_consumable_quantity_and_receipts() -> None:
    spare = Spare(id="SP", code="SP", quantity=1, available_from=_at(8))
    operation = _operation("OP", sequence=1).model_copy(update={"required_spare_ids": ["SP"]})
    other = _operation("B", sequence=2).model_copy(update={"required_spare_ids": ["SP"]})
    problem = _problem([operation, other], spares=[spare])
    assert "SPARE_UNAVAILABLE" in hard_codes(problem, [_place("OP", 8), _place("B", 10)])
    receipt = spare.model_copy(update={"quantity": 0, "receipts": [SpareReceipt(at=_at(10), qty=1)]})
    timed = _problem([operation], spares=[receipt])
    assert hard_codes(timed, [_place("OP", 10)]) == frozenset()
    assert "SPARE_UNAVAILABLE" in hard_codes(timed, [_place("OP", 8)])


def test_rotable_reuse_waits_for_the_return_lag() -> None:
    spare = Spare(
        id="SP",
        code="SP",
        quantity=1,
        domain_attributes={"kind": "rotable", "return_lag_min": 10},
    )
    operation = _operation("OP", sequence=1).model_copy(update={"required_spare_ids": ["SP"]})
    other = _operation("B", sequence=2, preds=["OP"]).model_copy(update={"required_spare_ids": ["SP"]})
    problem = _problem([operation, other], spares=[spare])
    touching = hard_codes(problem, [_place("OP", 8), _place("B", 9, 10)])
    assert touching == frozenset()
    early = hard_codes(problem, [_place("OP", 8), _place("B", 9, 9)])
    assert "SPARE_UNAVAILABLE" in early


def test_preemptive_visit_may_cross_a_closed_gap() -> None:
    windows = [
        CalendarWindow(start=_at(8), end=_at(9)),
        CalendarWindow(start=_at(10), end=_at(12)),
    ]
    plain = _operation("OP", sequence=1).model_copy(update={"duration_min": 120})
    preemptive = plain.model_copy(update={"domain_attributes": {"duration_policy": "preemptive"}})
    # 08:00–11:00 holds 180 minutes and 120 open minutes.
    gap = _problem([plain], windows=windows)
    assert "CALENDAR_BROKEN" in hard_codes(gap, [_place(duration=180)])
    crossed = _problem([preemptive], windows=windows)
    assert hard_codes(crossed, [_place(duration=180)]) == frozenset()


def test_experiment_data_without_a_declared_calendar_is_closed() -> None:
    open_horizon = _problem(
        provenance="experiment",
        calendar_id=None,
        post_attributes={"availability": "always_open"},
        crew_attributes={"availability": "always_open"},
    )
    assert hard_codes(open_horizon, [_place()]) == frozenset()
    problem = _problem()
    problem.work_centers[0].calendar_id = "MISSING"
    assert "CALENDAR_BROKEN" in hard_codes(problem, [_place()])


def test_horizon_over_eight_days_and_a_sub_minute_timestamp_are_refused() -> None:
    with pytest.raises(OracleLimit):
        hard_codes(_problem(horizon_end=_at(8, day=21)), [_place()])
    skewed = _place()
    skewed = skewed.model_copy(update={"start": _at(8).replace(second=30)})
    with pytest.raises(OracleLimit):
        hard_codes(_problem(), [skewed])


def test_release_and_earliest_start_are_hard() -> None:
    problem = _problem()
    job = problem.jobs[0].model_copy(update={"release_date": _at(8, 30)})
    assert "RELEASE_VIOLATION" in hard_codes(problem.model_copy(update={"jobs": [job]}), [_place()])
    operation = problem.operations[0].model_copy(update={"earliest_start": _at(8, 30)})
    codes = hard_codes(problem.model_copy(update={"operations": [operation]}), [_place()])
    assert "WINDOW_BROKEN" in codes


def test_two_lanes_accept_a_pair_and_reject_a_third() -> None:
    crews = [
        Crew(id=crew_id, code=crew_id, skills=["mechanical"], calendar_id="CAL")
        for crew_id in ("CREW", "CREW-2", "CREW-3")
    ]
    operations = [_operation(op_id, sequence=index) for index, op_id in enumerate(("A", "B", "C"), start=1)]
    problem = _problem(operations, crews=crews)
    problem.work_centers[0].max_parallel = 2
    pair = [_place("A", 8, crew="CREW"), _place("B", 8, crew="CREW-2")]
    assert "POST_OVERLAP" not in hard_codes(problem, pair)
    assert "CREW_OVERLAP" not in hard_codes(problem, pair)
    triple = [*pair, _place("C", 8, crew="CREW-3")]
    assert "POST_OVERLAP" in hard_codes(problem, triple)
    assert "CREW_OVERLAP" not in hard_codes(problem, triple)


def test_auxiliary_capacity_counts_setup_occupancy() -> None:
    aux = [AuxResource(id="JIG", code="JIG", capacity=1, calendar_id="CAL")]
    operations = [
        _operation("A", sequence=1).model_copy(update={"required_aux_ids": ["JIG"]}),
        _operation("B", sequence=2).model_copy(update={"required_aux_ids": ["JIG"]}),
    ]
    problem = _problem(operations, aux=aux)
    codes = hard_codes(problem, [_place("A", 8, aux=["JIG"]), _place("B", 8, 30, aux=["JIG"])])
    assert "AUX_OVERLAP" in codes
    assert "AUX_MISSING" in hard_codes(problem, [_place("A", 8), _place("B", 10)])
