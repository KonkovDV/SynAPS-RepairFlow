"""Oracle-labelled mutations of verified synthetic plans.

The oracle in tests.oracle_minutes decides must_reject or may_pass.
false_accept means the checker verified a plan the oracle rejected.
false_reject means the checker rejected a plan the oracle accepted.
Identity mutations are not counted. Synthetic data only.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

from tests.oracle_minutes import OracleLimit, hard_codes

from repairflow.evidence import fingerprint_payload
from repairflow.model import PlannedAssignment, RepairFlowProblem, Spare
from repairflow.planner import plan, recheck
from repairflow.synthetic import synthesize
from repairflow.versions import SYNAPS_COMMIT

PRESETS = ("tiny", "repair-site-mvp")
SEEDS = tuple(range(1, 31))
SOLVERS = ("GREED", "EDD", "ATC")
SHIFT_MINUTES = (1, -1, 5, -5, 30, -30, 240, -240)
_PER_BASELINE = 56
_EXAMPLE_CAP = 8


def run_fault_campaign(
    *,
    per_baseline: int | None = _PER_BASELINE,
    limit: int | None = None,
) -> dict[str, object]:
    """Label a round-robin sample. per_baseline None keeps every applicable mutation."""

    baselines = _baselines()
    streams = [_selected_keys(problem, rows, per_baseline) for _key, problem, rows in baselines]
    if per_baseline is not None and any(len(stream) < per_baseline for stream in streams):
        raise RuntimeError("a baseline has fewer applicable mutations than the quota")
    checked = 0
    false_accept = 0
    false_reject = 0
    must_reject = 0
    may_pass = 0
    by_mutator: dict[str, Counter[str]] = {}
    by_preset: dict[str, Counter[str]] = {}
    accept_examples: list[dict[str, object]] = []
    reject_examples: list[dict[str, object]] = []
    depth = 0
    while True:
        progressed = False
        if per_baseline is not None and depth >= per_baseline:
            break
        for (preset, seed, solver), problem, rows, stream in (
            (*baseline, stream) for baseline, stream in zip(baselines, streams, strict=True)
        ):
            if depth >= len(stream):
                continue
            progressed = True
            applied = _apply(problem, rows, stream[depth])
            if applied is None:
                raise RuntimeError(f"selected mutation {stream[depth]} did not apply")
            name, mutated, changed, operation_id = applied
            outcome = _judge(preset, seed, solver, name, operation_id, mutated, changed)
            checked += 1
            must_reject += int(outcome["label"] == "must_reject")
            may_pass += int(outcome["label"] == "may_pass")
            false_accept += int(outcome["false_accept"])
            false_reject += int(outcome["false_reject"])
            _tally(by_mutator, name, outcome)
            _tally(by_preset, preset, outcome)
            if outcome["false_accept"] and len(accept_examples) < _EXAMPLE_CAP:
                accept_examples.append(outcome["example"])
            if outcome["false_reject"] and len(reject_examples) < _EXAMPLE_CAP:
                reject_examples.append(outcome["example"])
            if limit is not None and checked >= limit:
                progressed = False
                break
        if not progressed:
            break
        depth += 1
    return {
        "schema": "repairflow.fault_campaign.v2",
        "checked": checked,
        "false_accept": false_accept,
        "false_reject": false_reject,
        "must_reject": must_reject,
        "may_pass": may_pass,
        "false_reject_reason": _reject_reason(false_reject, reject_examples),
        "presets": list(PRESETS),
        "seeds": list(SEEDS),
        "solvers": list(SOLVERS),
        "per_baseline": per_baseline,
        "mutations": _mutation_names(),
        "by_mutator": {name: dict(counts) for name, counts in sorted(by_mutator.items())},
        "by_preset": {name: dict(counts) for name, counts in sorted(by_preset.items())},
        "false_accept_examples": accept_examples,
        "false_reject_examples": reject_examples,
        "input_hash": _matrix_hash(baselines),
        "synaps_commit": SYNAPS_COMMIT,
        "claim_level": "experiment",
        "data_provenance": "synthetic",
        "oracle": "tests.oracle_minutes",
    }


def applicable_count(problem: RepairFlowProblem, rows: list[PlannedAssignment]) -> int:
    return len(_selected_keys(problem, rows, None))


def _selected_keys(
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
    limit: int | None,
) -> list[tuple[str, int, str | None]]:
    chosen: list[tuple[str, int, str | None]] = []
    for key in _keys(problem, rows):
        if _apply(problem, rows, key) is None:
            continue
        chosen.append(key)
        if limit is not None and len(chosen) >= limit:
            break
    return chosen


def covered_names(
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
    *,
    limit: int | None,
) -> set[str]:
    """Mutator names in the selected prefix. limit None is the whole stream."""

    return {name for name, _index, _variant in _selected_keys(problem, rows, limit)}


def write_nightly(path: Path) -> dict[str, object]:
    """Every applicable mutation, not a prefix. The caller stores the file.

    A 100 000 cap would drop the tail of a larger matrix. On 2026-10-08 that
    tail was about nine thousand mutations, including later operations.
    """

    report = run_fault_campaign(per_baseline=None, limit=None)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, report)
    if int(report["checked"]) < 100_000 or int(report["false_accept"]) != 0:
        raise RuntimeError(f"nightly campaign failed: {report['checked']} {report['false_accept']}")
    return report


def _baselines() -> list[tuple[tuple[str, int, str], RepairFlowProblem, list[PlannedAssignment]]]:
    found: list[tuple[tuple[str, int, str], RepairFlowProblem, list[PlannedAssignment]]] = []
    for preset in PRESETS:
        for seed in SEEDS:
            problem = synthesize(preset, seed=seed)
            for solver in SOLVERS:
                outcome = plan(problem, solver_config=solver)
                if not outcome.result.verified_feasible:
                    raise RuntimeError(f"{preset} seed {seed} {solver} baseline is not verified")
                rows = list(outcome.result.assignments)
                if len(rows) < 2:
                    raise RuntimeError(f"{preset} seed {seed} {solver} has fewer than two assignments")
                found.append(((preset, seed, solver), problem, rows))
    return found


def _keys(problem: RepairFlowProblem, rows: list[PlannedAssignment]) -> list[tuple[str, int, str | None]]:
    """Interleave families so a short prefix is not only the first operation's shifts."""

    operations = {operation.id: operation for operation in problem.operations}
    frozen = {row.operation_id for row in problem.frozen_assignments if row.immutable}
    buckets: dict[str, list[tuple[str, int, str | None]]] = {name: [] for name in _mutation_names()}
    for index, row in enumerate(rows):
        operation = operations.get(row.operation_id)
        for minutes in SHIFT_MINUTES:
            buckets[f"shift{minutes:+d}"].append((f"shift{minutes:+d}", index, None))
        for center in problem.work_centers:
            if center.id != row.work_center_id:
                buckets["change_post"].append(("change_post", index, center.id))
        for crew in problem.crews:
            if crew.id != row.crew_id:
                buckets["change_crew"].append(("change_crew", index, crew.id))
        if row.aux_ids:
            buckets["drop_aux"].append(("drop_aux", index, None))
        buckets["duplicate"].append(("duplicate", index, None))
        buckets["exit_window"].append(("exit_window", index, None))
        buckets["exit_horizon"].append(("exit_horizon", index, None))
        if operation is not None and operation.predecessor_ids:
            buckets["precedence"].append(("precedence", index, None))
        if operation is not None and operation.required_skills and row.crew_id:
            buckets["expire_permit"].append(("expire_permit", index, None))
        if row.setup_minutes > 0:
            buckets["setup_zero"].append(("setup_zero", index, None))
        if row.operation_id in frozen:
            buckets["shift_frozen"].append(("shift_frozen", index, None))
    if _used_spare(problem, rows) is not None:
        buckets["spare_overuse"].append(("spare_overuse", 0, None))
    if _shared_spare(problem, rows) is not None:
        buckets["rotable_clash"].append(("rotable_clash", 0, None))
    ordered: list[tuple[str, int, str | None]] = []
    while True:
        progressed = False
        for name in _mutation_names():
            bucket = buckets[name]
            if not bucket:
                continue
            ordered.append(bucket.pop(0))
            progressed = True
        if not progressed:
            break
    return ordered


def _apply(
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
    key: tuple[str, int, str | None],
) -> tuple[str, RepairFlowProblem, list[PlannedAssignment], str] | None:
    name, index, variant = key
    row = rows[index % len(rows)]
    if name.startswith("shift") and name not in {"shift_frozen"}:
        minutes = int(name.removeprefix("shift"))
        changed = _replace(rows, row, _shift(row, minutes))
        return _changed(name, problem, rows, changed, row.operation_id)
    if name == "change_post" and variant is not None:
        changed = _replace(rows, row, row.model_copy(update={"work_center_id": variant}))
        return _changed(name, problem, rows, changed, row.operation_id)
    if name == "change_crew" and variant is not None:
        changed = _replace(rows, row, row.model_copy(update={"crew_id": variant}))
        return _changed(name, problem, rows, changed, row.operation_id)
    if name == "drop_aux":
        if not row.aux_ids:
            return None
        changed = _replace(rows, row, row.model_copy(update={"aux_ids": row.aux_ids[1:]}))
        return _changed(name, problem, rows, changed, row.operation_id)
    if name == "duplicate":
        return (name, problem, [*rows, row.model_copy()], row.operation_id)
    if name == "exit_window":
        moved = _outside_calendar(problem, row)
        if moved is None:
            return None
        return _changed(name, problem, rows, _replace(rows, row, moved), row.operation_id)
    if name == "exit_horizon":
        moved = _outside_horizon(problem, row)
        return _changed(name, problem, rows, _replace(rows, row, moved), row.operation_id)
    if name == "precedence":
        moved = _before_predecessor(problem, rows, row)
        if moved is None:
            return None
        return _changed(name, problem, rows, _replace(rows, row, moved), row.operation_id)
    if name == "expire_permit":
        mutated = _expire(problem, row)
        if mutated is None or _same_problem(problem, mutated):
            return None
        return (name, mutated, rows, row.operation_id)
    if name == "setup_zero":
        if row.setup_minutes <= 0:
            return None
        changed = _replace(rows, row, row.model_copy(update={"setup_minutes": 0}))
        return _changed(name, problem, rows, changed, row.operation_id)
    if name == "shift_frozen":
        changed = _replace(rows, row, _shift(row, 60))
        return _changed(name, problem, rows, changed, row.operation_id)
    if name == "spare_overuse":
        found = _used_spare(problem, rows)
        mutated = _empty_spare(problem, rows)
        if found is None or mutated is None or _same_problem(problem, mutated):
            return None
        return (name, mutated, rows, found[1])
    if name == "rotable_clash":
        mutated, changed, operation_id = _clash(problem, rows)
        if mutated is None or changed is None:
            return None
        applied = _changed(name, mutated, rows, changed, operation_id)
        if applied is None and not _same_problem(problem, mutated):
            return (name, mutated, rows, operation_id)
        return applied
    return None


def _judge(
    preset: str,
    seed: int,
    solver: str,
    name: str,
    operation_id: str,
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
) -> dict[str, Any]:
    try:
        oracle = hard_codes(problem, rows)
    except OracleLimit as exc:
        raise RuntimeError(f"{name} on {operation_id} is outside the oracle") from exc
    result = recheck(problem, assignments=rows, kernel_status="feasible", solver_config="recheck")
    accepted = bool(result.result.verified_feasible)
    label = "must_reject" if oracle else "may_pass"
    false_accept = accepted and bool(oracle)
    false_reject = (not accepted) and not oracle
    example = {
        "preset": preset,
        "seed": seed,
        "solver": solver,
        "mutation": name,
        "operation_id": operation_id,
        "oracle": sorted(oracle),
        "checker": sorted({row.code for row in result.result.violations if row.severity != "kpi"}),
        "verified_feasible": accepted,
        "exit_code": result.result.exit_code,
    }
    return {
        "label": label,
        "false_accept": false_accept,
        "false_reject": false_reject,
        "example": example,
    }


def _tally(table: dict[str, Counter[str]], key: str, outcome: dict[str, Any]) -> None:
    counts = table.setdefault(key, Counter())
    counts["checked"] += 1
    counts[str(outcome["label"])] += 1
    counts["false_accept"] += int(outcome["false_accept"])
    counts["false_reject"] += int(outcome["false_reject"])


def _reject_reason(count: int, examples: list[dict[str, Any]]) -> str:
    if count == 0:
        return "The checker rejected no plan that the oracle accepted in this matrix."
    codes: set[str] = set()
    for example in examples:
        checker = example.get("checker", [])
        if isinstance(checker, list):
            codes.update(str(code) for code in checker)
    listed = ", ".join(sorted(codes)) or "none recorded"
    return f"{count} checker rejections of oracle-accepted plans. Example hard codes: {listed}."


def _mutation_names() -> list[str]:
    shifts = [f"shift{minutes:+d}" for minutes in SHIFT_MINUTES]
    rest = [
        "change_post",
        "change_crew",
        "drop_aux",
        "duplicate",
        "spare_overuse",
        "rotable_clash",
        "exit_window",
        "precedence",
        "expire_permit",
        "shift_frozen",
        "setup_zero",
        "exit_horizon",
    ]
    return [*shifts, *rest]


def _matrix_hash(
    baselines: list[tuple[tuple[str, int, str], RepairFlowProblem, list[PlannedAssignment]]],
) -> str:
    seen: list[dict[str, object]] = []
    recorded: set[tuple[str, int]] = set()
    for (preset, seed, _solver), problem, _rows in baselines:
        if (preset, seed) in recorded:
            continue
        recorded.add((preset, seed))
        seen.append(
            {
                "preset": preset,
                "seed": seed,
                "input_hash": fingerprint_payload(problem.model_dump(mode="json")),
            }
        )
    payload = {"presets": list(PRESETS), "seeds": list(SEEDS), "solvers": list(SOLVERS), "problems": seen}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _changed(
    name: str,
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
    changed: list[PlannedAssignment],
    operation_id: str,
) -> tuple[str, RepairFlowProblem, list[PlannedAssignment], str] | None:
    if [row.model_dump(mode="json") for row in rows] == [row.model_dump(mode="json") for row in changed]:
        return None
    return (name, problem, changed, operation_id)


def _replace(
    rows: list[PlannedAssignment],
    row: PlannedAssignment,
    updated: PlannedAssignment,
) -> list[PlannedAssignment]:
    return [updated if item.operation_id == row.operation_id else item for item in rows]


def _shift(row: PlannedAssignment, minutes: int) -> PlannedAssignment:
    delta = timedelta(minutes=minutes)
    return row.model_copy(update={"start": row.start + delta, "end": row.end + delta})


def _outside_calendar(problem: RepairFlowProblem, row: PlannedAssignment) -> PlannedAssignment | None:
    center = next((item for item in problem.work_centers if item.id == row.work_center_id), None)
    if center is None or not center.calendar_id:
        return None
    calendar = next((item for item in problem.calendars if item.id == center.calendar_id), None)
    if calendar is None or not calendar.windows:
        return None
    duration = row.end - row.start
    candidate = calendar.windows[0].end
    end = candidate + duration
    horizon = problem.planning_horizon
    if end > horizon.end or candidate < horizon.start or candidate == row.start:
        return None
    return row.model_copy(update={"start": candidate, "end": end, "setup_minutes": row.setup_minutes})


def _outside_horizon(problem: RepairFlowProblem, row: PlannedAssignment) -> PlannedAssignment:
    duration = row.end - row.start
    end = problem.planning_horizon.end + timedelta(minutes=1)
    return row.model_copy(update={"start": end - duration, "end": end})


def _before_predecessor(
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
    row: PlannedAssignment,
) -> PlannedAssignment | None:
    operation = next((item for item in problem.operations if item.id == row.operation_id), None)
    if operation is None or not operation.predecessor_ids:
        return None
    by_id = {item.operation_id: item for item in rows}
    predecessor = by_id.get(operation.predecessor_ids[0])
    if predecessor is None or predecessor.start == row.start:
        return None
    duration = row.end - row.start
    return row.model_copy(update={"start": predecessor.start, "end": predecessor.start + duration})


def _expire(problem: RepairFlowProblem, row: PlannedAssignment) -> RepairFlowProblem | None:
    operation = next((item for item in problem.operations if item.id == row.operation_id), None)
    if operation is None or not operation.required_skills or not row.crew_id:
        return None
    crews = []
    found = False
    until = row.end - timedelta(minutes=1)
    for crew in problem.crews:
        if crew.id != row.crew_id:
            crews.append(crew)
            continue
        skill = operation.required_skills[0]
        if skill not in crew.skills:
            return None
        permits = dict(crew.skill_valid_until)
        permits[skill] = until
        crews.append(crew.model_copy(update={"skill_valid_until": permits}))
        found = True
    if not found:
        return None
    return problem.model_copy(update={"crews": crews})


def _empty_spare(problem: RepairFlowProblem, rows: list[PlannedAssignment]) -> RepairFlowProblem | None:
    found = _used_spare(problem, rows)
    if found is None:
        return None
    spare_id, _operation_id = found
    spares = [_zero_spare(spare) if spare.id == spare_id else spare for spare in problem.spares]
    return problem.model_copy(update={"spares": spares})


def _zero_spare(spare: Spare) -> Spare:
    return spare.model_copy(update={"quantity": 0, "receipts": [], "available_from": spare.available_from})


def _clash(
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
) -> tuple[RepairFlowProblem | None, list[PlannedAssignment] | None, str]:
    shared = _shared_spare(problem, rows)
    if shared is None:
        return None, None, ""
    spare_id, first, second = shared
    duration = second.end - second.start
    moved = second.model_copy(update={"start": first.start, "end": first.start + duration})
    changed = [moved if item.operation_id == second.operation_id else item for item in rows]
    spares: list[Spare] = []
    for spare in problem.spares:
        if spare.id != spare_id:
            spares.append(spare)
            continue
        attributes = dict(spare.domain_attributes)
        attributes["kind"] = "rotable"
        attributes["return_lag_min"] = 30
        spares.append(
            spare.model_copy(update={"quantity": 1, "receipts": [], "domain_attributes": attributes})
        )
    return problem.model_copy(update={"spares": spares}), changed, second.operation_id


def _same_problem(problem: RepairFlowProblem, mutated: RepairFlowProblem) -> bool:
    return problem.model_dump(mode="json") == mutated.model_dump(mode="json")


def _used_spare(problem: RepairFlowProblem, rows: list[PlannedAssignment]) -> tuple[str, str] | None:
    operations = {operation.id: operation for operation in problem.operations}
    for row in rows:
        operation = operations.get(row.operation_id)
        if operation is None:
            continue
        demand = operation.spare_demand()
        if demand:
            return next(iter(demand)), row.operation_id
    return None


def _shared_spare(
    problem: RepairFlowProblem,
    rows: list[PlannedAssignment],
) -> tuple[str, PlannedAssignment, PlannedAssignment] | None:
    operations = {operation.id: operation for operation in problem.operations}
    users: dict[str, list[PlannedAssignment]] = {}
    for row in rows:
        operation = operations.get(row.operation_id)
        if operation is None:
            continue
        for spare_id in operation.spare_demand():
            users.setdefault(spare_id, []).append(row)
    for spare_id, group in users.items():
        if len(group) >= 2:
            return spare_id, group[0], group[1]
    return None


def _write_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
