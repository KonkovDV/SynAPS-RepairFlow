"""Deterministic synthetic repair-site generator. Data provenance: synthetic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from repairflow.model import (
    AuxResource,
    Calendar,
    CalendarWindow,
    Crew,
    FrozenAssignment,
    Job,
    Operation,
    PlanningHorizon,
    Policy,
    RepairFlowProblem,
    SetupEntry,
    Spare,
    WorkCenter,
)

Preset = Literal["tiny", "repair-site-mvp", "broken-seed42"]
PRESETS: tuple[str, ...] = ("tiny", "repair-site-mvp", "broken-seed42")

_UNIT_TYPES = ("engine", "gearbox", "compressor", "electrical")
_STEPS_FULL = (
    ("diagnose", "diagnostics", 40, False, False),
    ("disassemble", "mechanical", 50, False, True),
    ("restore", "mechanical", 80, True, False),
    ("assemble", "mechanical", 50, False, True),
    ("test", "test", 40, False, False),
)
_STEPS_SHORT = (
    ("diagnose", "diagnostics", 30, False, False),
    ("restore", "mechanical", 70, True, False),
    ("test", "test", 35, False, False),
)


def synthesize(preset: str = "repair-site-mvp", *, seed: int = 42) -> RepairFlowProblem:
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; expected one of {PRESETS}")
    if preset == "tiny":
        return _tiny(seed)
    problem = _mvp(seed)
    if preset == "broken-seed42":
        problem = problem.model_copy(update={"instance_id": "broken-seed42"})
    return problem


def corrupt_plan(assignments: list[dict], *, seed: int = 42) -> list[dict]:
    """Intentionally break a feasible plan for the fail-closed demo."""

    if not assignments:
        return assignments
    broken = [dict(row) for row in assignments]
    first = dict(broken[0])
    second = dict(broken[min(1, len(broken) - 1)])
    first["start"] = second["start"]
    first["end"] = second["end"]
    first["work_center_id"] = second["work_center_id"]
    first["crew_id"] = "CREW-TEST"
    first["setup_minutes"] = 0
    first["reason"] = "intentionally corrupted overlap + skill mismatch"
    broken[0] = first
    if len(broken) > 2:
        frozen_like = dict(broken[2])
        frozen_like["start"] = _shift_iso(frozen_like["start"], hours=6)
        frozen_like["end"] = _shift_iso(frozen_like["end"], hours=6)
        frozen_like["reason"] = "intentionally moved assignment"
        broken[2] = frozen_like
    _ = seed
    return broken


def _tiny(seed: int) -> RepairFlowProblem:
    start = datetime(2026, 1, 12, tzinfo=UTC)
    end = datetime(2026, 1, 14, tzinfo=UTC)
    calendar = _shift_calendar("CAL-DAY", start, days=2)
    posts = [
        WorkCenter(
            id="POST-U1",
            code="POST-U1",
            capability_group="universal",
            calendar_id="CAL-DAY",
            eligible_unit_types=list(_UNIT_TYPES),
        ),
        WorkCenter(
            id="POST-TEST",
            code="POST-TEST",
            capability_group="test",
            calendar_id="CAL-DAY",
            eligible_unit_types=list(_UNIT_TYPES),
        ),
    ]
    crews = _crews()
    jobs, operations = _jobs(
        start,
        n_jobs=3,
        seed=seed,
        short=True,
        due_hours=(18, 24, 30),
    )
    return RepairFlowProblem(
        instance_id="tiny-repair",
        data_provenance="synthetic",
        planning_horizon=PlanningHorizon(start=start, end=end),
        jobs=jobs,
        operations=operations,
        work_centers=posts,
        crews=crews,
        aux_resources=_aux(),
        setup_matrix=_setup_matrix([post.id for post in posts]),
        calendars=[calendar],
        frozen_assignments=[],
        spares=_spares(start, delayed=False),
        policy=Policy(),
        domain_attributes={"seed": seed, "preset": "tiny", "not_customer_data": True},
    )


def _mvp(seed: int) -> RepairFlowProblem:
    start = datetime(2026, 1, 12, tzinfo=UTC)
    end = datetime(2026, 1, 19, tzinfo=UTC)
    calendar = _shift_calendar("CAL-DAY", start, days=7)
    hole = Calendar(
        id="CAL-U2",
        code="CAL-U2",
        windows=[
            CalendarWindow(start=start + timedelta(hours=6), end=start + timedelta(hours=22)),
            # Next day onwards; POST-U2 is unavailable on day 0 evening through day 1 morning.
            CalendarWindow(start=start + timedelta(days=1, hours=12), end=end),
        ],
    )
    # Test stand is listed first so naive FIFO dumps every job onto it.
    posts = [
        WorkCenter(
            id="POST-TEST",
            code="POST-TEST",
            capability_group="test",
            calendar_id="CAL-DAY",
            eligible_unit_types=list(_UNIT_TYPES),
        ),
        WorkCenter(
            id="POST-U1",
            code="POST-U1",
            capability_group="universal",
            calendar_id="CAL-DAY",
            eligible_unit_types=list(_UNIT_TYPES),
        ),
        WorkCenter(
            id="POST-U2",
            code="POST-U2",
            capability_group="universal",
            calendar_id="CAL-U2",
            eligible_unit_types=list(_UNIT_TYPES),
        ),
        WorkCenter(
            id="POST-ENG",
            code="POST-ENG",
            capability_group="engine",
            calendar_id="CAL-DAY",
            eligible_unit_types=["engine", "compressor"],
        ),
        WorkCenter(
            id="POST-ELEC",
            code="POST-ELEC",
            capability_group="electrical",
            calendar_id="CAL-DAY",
            eligible_unit_types=["electrical", "compressor"],
        ),
    ]
    jobs, operations = _jobs(start, n_jobs=12, seed=seed, short=False)
    frozen_op = next(op for op in operations if op.id == "JOB-01-03")
    frozen = FrozenAssignment(
        operation_id=frozen_op.id,
        work_center_id="POST-U1",
        crew_id="CREW-MECH",
        start=start + timedelta(days=2, hours=10),
        end=start + timedelta(days=2, hours=10, minutes=frozen_op.duration_min),
        setup_minutes=0,
        frozen_reason="agreed_slot",
        immutable=True,
    )
    return RepairFlowProblem(
        instance_id="repair-site-mvp",
        data_provenance="synthetic",
        planning_horizon=PlanningHorizon(start=start, end=end),
        jobs=jobs,
        operations=operations,
        work_centers=posts,
        crews=_crews(),
        aux_resources=_aux(),
        setup_matrix=_setup_matrix([post.id for post in posts]),
        calendars=[calendar, hole],
        frozen_assignments=[frozen],
        spares=_spares(start, delayed=True),
        policy=Policy(),
        domain_attributes={
            "seed": seed,
            "preset": "repair-site-mvp",
            "not_customer_data": True,
            "not_svarz": True,
        },
    )


def _crews() -> list[Crew]:
    return [
        Crew(id="CREW-TEST", code="CREW-TEST", skills=["test"], calendar_id="CAL-DAY"),
        Crew(id="CREW-DIAG", code="CREW-DIAG", skills=["diagnostics"], calendar_id="CAL-DAY"),
        Crew(id="CREW-MECH", code="CREW-MECH", skills=["mechanical"], calendar_id="CAL-DAY"),
        Crew(id="CREW-ELEC", code="CREW-ELEC", skills=["electrical"], calendar_id="CAL-DAY"),
    ]


def _aux() -> list[AuxResource]:
    return [
        AuxResource(id="AUX-CRANE", code="AUX-CRANE", resource_type="crane", capacity=2),
        AuxResource(id="AUX-JIG", code="AUX-JIG", resource_type="jig", capacity=1),
    ]


def _spares(start: datetime, *, delayed: bool) -> list[Spare]:
    rows = [
        Spare(id="SP-BEARING", code="SP-BEARING", quantity=8, available_from=start),
        Spare(id="SP-SEAL", code="SP-SEAL", quantity=8, available_from=start),
    ]
    if delayed:
        rows.append(
            Spare(
                id="SP-DELAYED",
                code="SP-DELAYED",
                quantity=1,
                available_from=start + timedelta(days=2, hours=8),
            )
        )
    return rows


def _shift_calendar(calendar_id: str, start: datetime, *, days: int) -> Calendar:
    windows = []
    for day in range(days):
        day0 = start + timedelta(days=day)
        windows.append(
            CalendarWindow(start=day0 + timedelta(hours=6), end=day0 + timedelta(hours=22))
        )
    return Calendar(id=calendar_id, code=calendar_id, windows=windows)


def _jobs(
    start: datetime,
    *,
    n_jobs: int,
    seed: int,
    short: bool,
    due_hours: tuple[int, ...] | None = None,
) -> tuple[list[Job], list[Operation]]:
    jobs: list[Job] = []
    operations: list[Operation] = []
    for index in range(n_jobs):
        job_id = f"JOB-{index + 1:02d}"
        unit = _UNIT_TYPES[(index + seed) % len(_UNIT_TYPES)]
        hours = due_hours[index] if due_hours is not None else 72 + index * 12
        jobs.append(
            Job(
                id=job_id,
                external_ref=job_id,
                asset_code=f"{unit[:3].upper()}-{index + 1:03d}",
                unit_type=unit,
                release_date=start + timedelta(hours=6),
                due_date=start + timedelta(hours=hours),
                priority=400 + index,
            )
        )
        steps = _STEPS_SHORT if short or index % 3 == 2 else _STEPS_FULL
        if unit == "electrical":
            steps = tuple(
                (name, "electrical" if skill == "mechanical" else skill, dur, spare, crane)
                for name, skill, dur, spare, crane in steps
            )
        previous = None
        for seq, (name, skill, duration, needs_spare, needs_crane) in enumerate(steps, start=1):
            op_id = f"{job_id}-{seq:02d}"
            eligible = _eligible_posts(name, unit, tiny=n_jobs <= 3)
            spare_ids = []
            if needs_spare:
                spare_ids = ["SP-BEARING"] if index % 2 == 0 else ["SP-SEAL"]
                if not short and index == 5 and name == "restore":
                    spare_ids = ["SP-DELAYED"]
            aux_ids = ["AUX-CRANE"] if needs_crane else []
            if name == "restore" and unit == "engine":
                aux_ids.append("AUX-JIG")
            operations.append(
                Operation(
                    id=op_id,
                    job_id=job_id,
                    sequence=seq,
                    duration_min=duration,
                    predecessor_ids=[previous] if previous else [],
                    eligible_work_center_ids=eligible,
                    required_skills=[skill],
                    required_aux_ids=aux_ids,
                    required_spare_ids=spare_ids,
                    setup_state=unit,
                    latest_finish=None,
                )
            )
            previous = op_id
    return jobs, operations


def _eligible_posts(step: str, unit: str, *, tiny: bool) -> list[str]:
    if tiny:
        if step == "test":
            return ["POST-TEST"]
        return ["POST-U1", "POST-TEST"]
    if step == "test":
        return ["POST-TEST"]
    if unit == "engine":
        return ["POST-U1", "POST-U2", "POST-ENG"]
    if unit == "electrical":
        return ["POST-U1", "POST-U2", "POST-ELEC"]
    return ["POST-U1", "POST-U2", "POST-ENG", "POST-ELEC"]


def _setup_matrix(work_center_ids: list[str]) -> list[SetupEntry]:
    states = ["idle", *_UNIT_TYPES]
    rows: list[SetupEntry] = []
    for wc_id in work_center_ids:
        for from_state in states:
            for to_state in states:
                minutes = 0 if from_state == to_state or from_state == "idle" else 25
                rows.append(
                    SetupEntry(
                        from_state=from_state,
                        to_state=to_state,
                        duration_min=minutes,
                        work_center_id=wc_id,
                    )
                )
    return rows


def _shift_iso(value: str, *, hours: int) -> str:
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (moment + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
