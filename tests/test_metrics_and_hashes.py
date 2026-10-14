"""Unified metrics, hash verification, EDD, and the pinned solver stack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repairflow.cli import main
from repairflow.evidence import canonical_json, runtime_manifest, verify_plan_hashes
from repairflow.metrics import compute_metrics
from repairflow.model import RepairFlowProblem
from repairflow.planner import plan
from repairflow.sbom import PINNED_ORTOOLS, build_sbom, runtime_binding
from repairflow.synthetic import synthesize


def _without_auxiliary_calendars(problem: RepairFlowProblem) -> RepairFlowProblem:
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def test_makespan_is_measured_from_the_horizon() -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    metrics = compute_metrics(problem, list(outcome.result.assignments))
    assert outcome.result.objective["origin"] == "horizon_start"
    assert outcome.result.objective["makespan_minutes"] == metrics["makespan_minutes"]
    first = min(row.start for row in outcome.result.assignments)
    assert first > problem.planning_horizon.start
    span = (max(row.end for row in outcome.result.assignments) - first).total_seconds() / 60.0
    assert metrics["makespan_minutes"] > span
    raw = outcome.result.metadata["solver_objective"]
    assert "makespan_minutes" in raw
    assert raw["makespan_minutes"] != metrics["makespan_minutes"]


def test_schedule_hash_ignores_the_runtime_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = synthesize("tiny", seed=1)
    first = plan(problem, solver_config="GREED")

    def other_runtime() -> dict[str, str]:
        payload = runtime_manifest()
        payload["platform"] = "schedule-hash-probe"
        return payload

    monkeypatch.setattr("repairflow.planner.runtime_manifest", other_runtime)
    second = plan(problem, solver_config="GREED")
    assert first.result.result_hash != second.result.result_hash
    assert first.result.config_hash != second.result.config_hash
    assert first.result.schedule_hash == second.result.schedule_hash
    assert verify_plan_hashes(problem, second.result) == []


def test_edd_is_feasible_where_fifo_is_not() -> None:
    problem = synthesize("tiny", seed=1)
    fifo = plan(problem, solver_config="FIFO")
    edd = plan(problem, solver_config="EDD")
    assert fifo.result.exit_code == 2
    assert edd.result.exit_code == 0
    assert edd.result.verified_feasible
    assert edd.result.claim_status == "verified"
    assert edd.result.solver_class == "baseline"


def test_cpsat_records_a_domain_greed_warm_start() -> None:
    problem = _without_auxiliary_calendars(synthesize("tiny", seed=1))
    outcome = plan(problem, solver_config="CPSAT-10")
    assert outcome.result.claim_status == "optimal"
    solver = outcome.result.metadata["solver"]
    assert solver["warm_start"] == "domain_greed"
    assert solver["seed"] == 1
    assert isinstance(solver["kernel"], dict)


def test_verify_hashes_accepts_a_fresh_plan_and_rejects_tampering(tmp_path: Path) -> None:
    problem = synthesize("tiny", seed=1)
    outcome = plan(problem, solver_config="GREED")
    assert len(outcome.result.schedule_hash) == 64
    assert verify_plan_hashes(problem, outcome.result) == []
    forged = outcome.result.model_copy(update={"schedule_hash": "0" * 64})
    assert "schedule_hash does not match the schedule" in verify_plan_hashes(problem, forged)
    problem_path = tmp_path / "problem.json"
    plan_path = tmp_path / "plan.json"
    problem_path.write_text(problem.model_dump_json(), encoding="utf-8")
    plan_path.write_text(outcome.result.model_dump_json(), encoding="utf-8")
    assert (
        main(
            [
                "check",
                str(problem_path),
                str(plan_path),
                "--verify-hashes",
            ]
        )
        == 0
    )
    tampered = json.loads(plan_path.read_text(encoding="utf-8"))
    tampered["input_hash"] = "0" * 64
    plan_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert (
        main(
            [
                "check",
                str(problem_path),
                str(plan_path),
                "--verify-hashes",
            ]
        )
        == 1
    )


def test_canonical_json_refuses_arbitrary_objects() -> None:
    try:
        canonical_json({"value": object()})
        raised = False
    except TypeError:
        raised = True
    assert raised


def test_sbom_pins_ortools() -> None:
    document = build_sbom()
    assert document["bomFormat"] == "CycloneDX"
    versions = {row["name"]: row["version"] for row in document["components"]}
    assert versions["ortools"] == PINNED_ORTOOLS


def test_runtime_binding_is_reproducible_and_explicit() -> None:
    first = runtime_binding()
    second = runtime_binding()
    assert first == second
    assert first["schema"] == "repairflow.runtime_binding.v1"
    for component in first["components"]:
        assert set(component) == {"name", "version", "manifest_sha256", "file_count", "files"}
        assert component["file_count"] == len(component["files"])
        if component["version"] != "absent":
            assert len(component["manifest_sha256"]) == 64
            assert all(len(row["sha256"]) == 64 for row in component["files"])
