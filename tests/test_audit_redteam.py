# ruff: noqa: E501
"""Audit regressions: malformed submissions must yield a refusal, not a crash."""

from __future__ import annotations

from pathlib import Path

import pytest

from repairflow.cli import main
from repairflow.planner import plan, recheck
from repairflow.synthetic import synthesize


@pytest.fixture(scope="module")
def greed_plan():  # type: ignore[no-untyped-def]
    problem = synthesize("repair-site-mvp", seed=42)
    return problem, plan(problem, solver_config="GREED").result


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("operation_id", "GHOST-OP", "UNKNOWN_OPERATION"),
        ("operation_id", " JOB-01-01", "UNKNOWN_OPERATION"),
        ("work_center_id", "GHOST-WC", "UNKNOWN_RESOURCE"),
    ],
)
def test_recheck_unknown_ids_fail_closed(greed_plan, field, value, code):  # type: ignore[no-untyped-def]
    problem, result = greed_plan
    rows = [row.model_copy() for row in result.assignments]
    rows[0] = rows[0].model_copy(update={field: value})
    outcome = recheck(problem, assignments=rows, kernel_status=result.kernel_status)
    assert outcome.result.exit_code == 2
    assert not outcome.result.verified_feasible
    assert code in {row.code for row in outcome.result.violations}


def test_cli_deeply_nested_json_is_a_usage_error(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
    assert main(["check", str(deep), str(deep)]) == 1
    assert "repairflow:" in capsys.readouterr().err


# --- backend logic review (commit f7a8a2e), counterexamples from rf_audit/repro.py ---

from repairflow.checker import check_domain_assignments  # noqa: E402
from repairflow.lane_setup import lane_setup_evidence  # noqa: E402
from repairflow.model import PlannedAssignment, RepairFlowProblem  # noqa: E402


def _t(h: int, m: int = 0, s: int = 0) -> str:
    return f"2026-01-01T{h:02d}:{m:02d}:{s:02d}+00:00"


def _base(**kw):  # type: ignore[no-untyped-def]
    d = dict(
        instance_id="x",
        planning_horizon=dict(start=_t(0), end=_t(23)),
        jobs=[dict(id="J1")],
        operations=[
            dict(
                id="A",
                job_id="J1",
                sequence=1,
                duration_min=60,
                eligible_work_center_ids=["W"],
                setup_state="s",
            )
        ],
        work_centers=[dict(id="W", code="W")],
        crews=[],
        setup_matrix=[
            dict(from_state=f, to_state=t, duration_min=0) for f in ("idle", "s") for t in ("idle", "s")
        ],
    )
    d.update(kw)
    return d


def _asn(op: str, s: str, e: str, **k):  # type: ignore[no-untyped-def]
    return PlannedAssignment(operation_id=op, work_center_id=k.pop("wc", "W"), start=s, end=e, **k)


def _codes(d, rows):  # type: ignore[no-untyped-def]
    return {v.code for v in check_domain_assignments(RepairFlowProblem.model_validate(d), rows)}


def test_f1_unknown_spare_in_required_spares_is_rejected_at_load() -> None:
    d = _base()
    d["operations"][0]["required_spares"] = [{"spare_id": "GHOST", "qty": 5}]
    with pytest.raises(ValueError, match="unknown spare GHOST"):
        RepairFlowProblem.model_validate(d)


def test_f1_checker_fails_closed_on_unknown_spare_even_without_load_check() -> None:
    d = _base()
    problem = RepairFlowProblem.model_validate(d)
    op = problem.operations[0].model_copy(update={"required_spare_ids": ["GHOST"]})
    forged = problem.model_construct(**{**dict(problem), "operations": [op]})
    from repairflow.checker import _due_release_spares

    out = _due_release_spares(forged, [_asn("A", _t(8), _t(9))])
    assert any(v.code == "UNKNOWN_RESOURCE" and v.resource_id == "GHOST" for v in out)


@pytest.mark.parametrize(
    "op_patch",
    [
        {"required_spares": [{"spare_id": "S", "qty": 1}, {"spare_id": "S", "qty": 1}]},
        {"required_spare_ids": ["S", "S"]},
    ],
)
def test_f12_duplicate_spare_demand_is_summed(op_patch) -> None:  # type: ignore[no-untyped-def]
    d = _base(spares=[{"id": "S", "code": "S", "quantity": 1}])
    d["operations"][0].update(op_patch)
    assert "SPARE_UNAVAILABLE" in _codes(d, [_asn("A", _t(8), _t(9))])


def test_f5_missing_setup_zero_policy_is_respected_after_idle() -> None:
    d = _base(
        setup_matrix=[dict(from_state="idle", to_state="s", duration_min=0)],
        policy={"missing_setup": "zero"},
    )
    d["jobs"] = [dict(id="J1"), dict(id="J2")]
    d["operations"].append(
        dict(
            id="B", job_id="J2", sequence=1, duration_min=60, eligible_work_center_ids=["W"], setup_state="s"
        )
    )
    rows = [_asn("A", _t(8), _t(9)), _asn("B", _t(9), _t(10))]
    assert "MISSING_SETUP" not in _codes(d, rows)


def test_f2_sub_minute_overrun_is_rejected() -> None:
    assert "INVALID_DURATION" in _codes(_base(), [_asn("A", _t(8), _t(9, 0, 59))])


def test_f3_adjacent_calendar_windows_are_merged() -> None:
    d = _base(
        calendars=[
            {"id": "C", "windows": [{"start": _t(8), "end": _t(12)}, {"start": _t(12), "end": _t(16)}]}
        ]
    )
    d["work_centers"][0]["calendar_id"] = "C"
    assert "CALENDAR_BROKEN" not in _codes(d, [_asn("A", _t(11, 30), _t(12, 30))])
    frozen = dict(
        d,
        frozen_assignments=[
            {"operation_id": "A", "work_center_id": "W", "start": _t(11, 30), "end": _t(12, 30)}
        ],
    )
    RepairFlowProblem.model_validate(frozen)


def test_f7_frozen_on_unattended_post_is_not_held_to_staffed_calendar() -> None:
    d = _base(
        calendars=[{"id": "C", "windows": [{"start": _t(8), "end": _t(9)}]}],
        frozen_assignments=[{"operation_id": "A", "work_center_id": "W", "start": _t(10), "end": _t(11)}],
    )
    d["work_centers"][0].update(calendar_id="C", domain_attributes={"attendance": "unattended"})
    assert _codes(d, [_asn("A", _t(10), _t(11))]) == set()


def test_f6_frozen_setup_minutes_must_match() -> None:
    d = _base(
        setup_matrix=[
            dict(from_state=f, to_state=t, duration_min=0) for f in ("idle", "s") for t in ("idle", "s")
        ],
        frozen_assignments=[{"operation_id": "A", "work_center_id": "W", "start": _t(8), "end": _t(9)}],
    )
    assert "FROZEN_MOVED" in _codes(d, [_asn("A", _t(8), _t(9), setup_minutes=5)])


def _lane_problem():  # type: ignore[no-untyped-def]
    d = _base()
    d["work_centers"][0]["max_parallel"] = 2
    d["jobs"] = [dict(id=j) for j in ("J1", "J2", "J3")]
    d["operations"] = [
        dict(
            id="A", job_id="J1", sequence=1, duration_min=60, eligible_work_center_ids=["W"], setup_state="X"
        ),
        dict(
            id="B", job_id="J2", sequence=1, duration_min=90, eligible_work_center_ids=["W"], setup_state="Y"
        ),
        dict(
            id="C", job_id="J3", sequence=1, duration_min=60, eligible_work_center_ids=["W"], setup_state="Y"
        ),
    ]
    st = ("idle", "X", "Y")
    d["setup_matrix"] = [
        dict(from_state=f, to_state=t, duration_min=(0 if f == t or f == "idle" else 30))
        for f in st
        for t in st
    ]
    return d


@pytest.mark.parametrize("claimed", [0, 30])
def test_f4_lane_ambiguity_without_lane_id_is_refused(claimed: int) -> None:
    rows = [
        _asn("A", _t(9), _t(10)),
        _asn("B", _t(9), _t(10, 30)),
        _asn("C", _t(11), _t(12), setup_minutes=claimed),
    ]
    assert "SETUP_MISMATCH" in _codes(_lane_problem(), rows)


def test_f4_explicit_lane_ids_resolve_the_ambiguity() -> None:
    d = _lane_problem()
    ok = [
        _asn("A", _t(9), _t(10), lane=0),
        _asn("B", _t(9), _t(10, 30), lane=1),
        _asn("C", _t(11), _t(12), setup_minutes=0, lane=1),
    ]
    assert _codes(d, ok) == set()
    wrong = [*ok[:2], _asn("C", _t(11), _t(12), setup_minutes=0, lane=0)]
    assert "SETUP_MISMATCH" in _codes(d, wrong)
    clash = [*ok[:2], _asn("C", _t(10), _t(11), setup_minutes=0, lane=1)]
    assert "SETUP_MISMATCH" in _codes(d, clash)
    out_of_range = [*ok[:2], _asn("C", _t(11), _t(12), setup_minutes=0, lane=5)]
    assert "SETUP_MISMATCH" in _codes(d, out_of_range)
    mixed = [*ok[:2], _asn("C", _t(11), _t(12), setup_minutes=0)]
    assert "SETUP_MISMATCH" in _codes(d, mixed)
    placed = lane_setup_evidence(RepairFlowProblem.model_validate(d), ok)
    assert {p.operation_id: p.lane_index for p in placed} == {"A": 0, "B": 1, "C": 1}


def test_f9_setup_before_release_is_rejected() -> None:
    d = _base()
    d["jobs"][0]["release_date"] = _t(8)
    d["setup_matrix"] = [
        dict(from_state="idle", to_state="s", duration_min=30),
        dict(from_state="s", to_state="s", duration_min=0),
        dict(from_state="s", to_state="idle", duration_min=0),
        dict(from_state="idle", to_state="idle", duration_min=0),
    ]
    assert "RELEASE_VIOLATION" in _codes(d, [_asn("A", _t(8), _t(9), setup_minutes=30)])
    assert "RELEASE_VIOLATION" not in _codes(d, [_asn("A", _t(8, 30), _t(9, 30), setup_minutes=30)])


def test_f9_setup_before_earliest_start_is_rejected() -> None:
    d = _base()
    d["operations"][0]["earliest_start"] = _t(8)
    d["setup_matrix"] = [
        dict(from_state=f, to_state=t, duration_min=(30 if (f, t) == ("idle", "s") else 0))
        for f in ("idle", "s")
        for t in ("idle", "s")
    ]
    assert "WINDOW_BROKEN" in _codes(d, [_asn("A", _t(8), _t(9), setup_minutes=30)])


@pytest.mark.slow
def test_cpsat_is_single_worker_and_flags_reproducibility() -> None:
    tiny = synthesize("tiny", seed=1)
    first = plan(tiny, solver_config="CPSAT-10").result
    second = plan(tiny, solver_config="CPSAT-10").result
    record = first.metadata["solver"]
    assert record["num_workers"] == 1
    assert record["reproducible"] is (first.kernel_status == "optimal")
    if record["reproducible"]:
        assert [r.model_dump() for r in first.assignments] == [r.model_dump() for r in second.assignments]


def test_randomized_checker_matches_minute_oracle() -> None:
    """Randomized cross-check: accept/reject of checker equals the minute oracle."""
    import random
    from datetime import timedelta

    from tests.oracle_minutes import OracleLimit, hard_codes

    cases = 0
    for seed in (1, 2, 3):
        problem = synthesize("tiny", seed=seed)
        base = list(plan(problem, solver_config="GREED").result.assignments)
        rng = random.Random(seed)
        for _ in range(150):
            rows = [row.model_copy() for row in base]
            for _ in range(rng.randint(0, 2)):
                i = rng.randrange(len(rows))
                row = rows[i]
                move = rng.choice(["shift", "setup", "wc", "drop", "lane"])
                if move == "shift":
                    delta = timedelta(minutes=rng.choice([-60, -15, -1, 1, 15, 60]))
                    rows[i] = row.model_copy(update={"start": row.start + delta, "end": row.end + delta})
                elif move == "setup":
                    rows[i] = row.model_copy(
                        update={"setup_minutes": max(0, row.setup_minutes + rng.choice([-5, 5]))}
                    )
                elif move == "wc":
                    op = next(o for o in problem.operations if o.id == row.operation_id)
                    rows[i] = row.model_copy(
                        update={"work_center_id": rng.choice(op.eligible_work_center_ids)}
                    )
                elif move == "lane":
                    rows[i] = row.model_copy(update={"lane": None})
                else:
                    rows.pop(i)
            try:
                oracle = hard_codes(problem, rows)
            except OracleLimit:
                continue
            checker = {v.code for v in check_domain_assignments(problem, rows) if v.severity == "hard"}
            assert bool(oracle) == bool(checker), (sorted(oracle), sorted(checker))
            cases += 1
    assert cases > 300


# --- round 2 ---


def test_r2_repeated_aux_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="aux_ids must not repeat"):
        PlannedAssignment(operation_id="A", work_center_id="W", start=_t(8), end=_t(9), aux_ids=["T1", "T1"])


def test_r2_cli_check_refuses_plan_with_repeated_aux(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    problem = synthesize("repair-site-mvp", seed=42)
    result = plan(problem, solver_config="GREED").result
    payload = result.model_dump(mode="json")
    row = next(r for r in payload["assignments"] if r["aux_ids"])
    row["aux_ids"] = row["aux_ids"] * 2
    ppath, rpath = tmp_path / "p.json", tmp_path / "r.json"
    ppath.write_text(problem.model_dump_json(), encoding="utf-8")
    import json

    rpath.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["check", str(ppath), str(rpath)]) == 1
    assert "aux_ids" in capsys.readouterr().err


def test_r2_decision_log_read_is_size_limited(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from repairflow import io as rf_io
    from repairflow.decision_log import read_decision_log

    monkeypatch.setattr(rf_io.__dict__["read_text_limited"], "__kwdefaults__", {"max_bytes": 10})
    log = tmp_path / "log.jsonl"
    log.write_text("x" * 100, encoding="utf-8")
    with pytest.raises(ValueError, match="larger than"):
        read_decision_log(log)
