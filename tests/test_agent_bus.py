"""Tests for the offline SynAPS agent-bus validator."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tools.agent_bus import (
    BusError,
    REQUIRED_CI_JOBS,
    SCHEMA,
    inspect_thread,
    parse_messages,
    run_failure_reason,
    validate_object,
)

_SHA = "76d09467fc60e4cb3711f7fcc074b5f97c3728df"


def message(payload: dict[str, object]) -> str:
    return f"### AGENT_BUS {SCHEMA}\n```json\n{json.dumps(payload)}\n```\n"


def claim(agent: str = "session") -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "op": "claim",
        "issue": 4,
        "agent": agent,
        "host": "cloud",
        "base_sha": _SHA[:12],
        "branch": "feat/4-agent-bus-bootstrap",
        "until": "2026-10-01T06:00:00+03:00",
    }


def run_payload(**overrides: object) -> dict[str, object]:
    jobs = [
        {
            "name": name,
            "conclusion": "success",
            "runner_id": 7,
            "runner_name": "hosted",
            "steps": [{"name": "test", "conclusion": "success"}],
        }
        for name in REQUIRED_CI_JOBS
    ]
    payload: dict[str, object] = {
        "id": 123,
        "status": "completed",
        "conclusion": "success",
        "head_sha": _SHA,
        "jobs": jobs,
        "total_count": len(jobs),
    }
    payload.update(overrides)
    return payload


def test_claim_is_parsed_and_product_fields_are_rejected() -> None:
    assert parse_messages(message(claim()))[0].agent == "session"
    invalid = claim()
    invalid["verified"] = True
    with pytest.raises(BusError):
        validate_object(invalid)


def test_foreign_schema_and_foreign_urls_are_rejected() -> None:
    invalid = claim()
    invalid["schema"] = "aerobim.agent_bus.v1"
    with pytest.raises(BusError):
        validate_object(invalid)
    done = {
        "schema": SCHEMA,
        "op": "done",
        "issue": 4,
        "agent": "session",
        "sha": _SHA[:12],
        "pr_url": "https://github.com/KonkovDV/AeroBIM/pull/1",
        "ci_run_id": "https://github.com/KonkovDV/AeroBIM/actions/runs/1",
        "test_quality_gate": ["calls production code"],
    }
    with pytest.raises(BusError):
        validate_object(done)


def test_run_requires_all_real_jobs_and_steps() -> None:
    assert run_failure_reason(run_payload()) is None
    jobs = list(run_payload()["jobs"])
    jobs[0] = {**jobs[0], "runner_id": 0}
    assert run_failure_reason(run_payload(jobs=jobs)) == "lint has no real runner"
    jobs = list(run_payload()["jobs"])
    jobs[0] = {**jobs[0], "steps": []}
    assert run_failure_reason(run_payload(jobs=jobs)) == "lint has no successful step"
    assert run_failure_reason(run_payload(total_count=999)) == "jobs list is incomplete"


def test_thread_first_claim_heartbeat_and_expiry() -> None:
    heartbeat = claim()
    heartbeat.update({"op": "heartbeat"})
    payload = {
        "comments": [
            {"createdAt": "2026-09-30T19:00:00+03:00", "body": message(claim())},
            {"createdAt": "2026-09-30T20:00:00+03:00", "body": message(heartbeat)},
        ]
    }
    holder, reason = inspect_thread(
        payload,
        issue=4,
        now=datetime.fromisoformat("2026-09-30T20:30:00+03:00"),
    )
    assert reason is None
    assert holder == "session"
    later = dict(claim("other"))
    later["until"] = "2026-10-02T06:00:00+03:00"
    payload["comments"].append(
        {"createdAt": "2026-10-01T07:00:00+03:00", "body": message(later)}
    )
    holder, reason = inspect_thread(
        payload,
        issue=4,
        now=datetime.fromisoformat("2026-10-01T07:30:00+03:00"),
    )
    assert reason is None
    assert holder == "other"


def test_done_requires_real_run_and_matching_sha() -> None:
    done = {
        "schema": SCHEMA,
        "op": "done",
        "issue": 4,
        "agent": "session",
        "sha": _SHA[:12],
        "pr_url": "https://github.com/KonkovDV/SynAPS-RepairFlow/pull/5",
        "ci_run_id": "https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/123",
        "test_quality_gate": ["production function", "specific assertion"],
    }
    payload = {
        "comments": [
            {"createdAt": "2026-09-30T19:00:00+03:00", "body": message(claim())},
            {"createdAt": "2026-09-30T20:00:00+03:00", "body": message(done)},
        ]
    }
    holder, reason = inspect_thread(
        payload,
        issue=4,
        now=datetime.fromisoformat("2026-09-30T20:00:00+03:00"),
        run=run_payload(),
    )
    assert reason is None
    assert holder is None
    bad = run_payload(head_sha="a" * 40)
    _holder, reason = inspect_thread(
        payload,
        issue=4,
        now=datetime.fromisoformat("2026-09-30T20:00:00+03:00"),
        run=bad,
    )
    assert reason == "done SHA does not match run head"
