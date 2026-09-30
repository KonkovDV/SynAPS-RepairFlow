"""Offline validator for the SynAPS RepairFlow GitHub agent bus."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = "synaps.agent_bus.v1"
OPS = frozenset({"claim", "heartbeat", "blocked", "handoff", "steal", "done"})
REQUIRED_CI_JOBS = ("lint", "test-fast", "synaps-pin", "demo-evidence", "benchmark")
_STALE_HOURS = 6
_HEADING = re.compile(r"^### AGENT_BUS\s+synaps\.agent_bus\.v1\s*$", re.MULTILINE)
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
_RUN_URL = re.compile(r"^https://github\.com/KonkovDV/SynAPS-RepairFlow/actions/runs/\d+$")
_PR_URL = re.compile(r"^https://github\.com/KonkovDV/SynAPS-RepairFlow/pull/\d+$")
_FORBIDDEN = frozenset(
    {
        "summary_passed",
        "summary.passed",
        "verified",
        "verified_feasible",
        "customer_go",
        "market_go",
        "deployment_go",
        "accuracy_claim",
        "customer_accuracy",
        "mep_delivered",
    }
)


class BusError(ValueError):
    """A bus message or evidence payload is invalid."""


@dataclass(frozen=True)
class BusMessage:
    op: str
    issue: int
    agent: str
    fields: Mapping[str, Any]


def _time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BusError("timestamp must be ISO-8601") from exc
    if result.tzinfo is None:
        raise BusError("timestamp must include a timezone")
    return result


def _reject(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in _FORBIDDEN:
                raise BusError(f"bus cannot carry product field {key}")
            _reject(child)
    elif isinstance(value, list):
        for child in value:
            _reject(child)


def _text(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BusError(f"{key} is required")
    return value


def _sha(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise BusError(f"{key} must be a git SHA")
    return value


def _branch(raw: Mapping[str, Any]) -> str:
    value = raw.get("branch")
    if not isinstance(value, str) or _BRANCH.fullmatch(value) is None or ".." in value:
        raise BusError("branch must be a safe feature branch")
    bare = value.removeprefix("refs/heads/").removeprefix("origin/")
    if bare in {"main", "master"}:
        raise BusError("main is not a claim branch")
    return bare


def _url(raw: Mapping[str, Any], key: str, pattern: re.Pattern[str]) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise BusError(f"{key} must be a SynAPS RepairFlow URL")
    return value


def validate_object(raw: Mapping[str, Any]) -> BusMessage:
    _reject(raw)
    if raw.get("schema") != SCHEMA:
        raise BusError(f"schema must be {SCHEMA}")
    op = raw.get("op")
    issue = raw.get("issue")
    agent = raw.get("agent")
    if op not in OPS:
        raise BusError("op is not supported")
    if not isinstance(issue, int) or isinstance(issue, bool) or issue < 1:
        raise BusError("issue must be a positive integer")
    if not isinstance(agent, str) or not agent.strip() or len(agent) > 64:
        raise BusError("agent must be a short name")
    if op == "claim":
        if raw.get("host") not in {"local", "cloud"}:
            raise BusError("host must be local or cloud")
        _sha(raw, "base_sha")
        _branch(raw)
        _time(_text(raw, "until"))
    elif op == "heartbeat":
        _branch(raw)
    elif op == "blocked":
        _text(raw, "reason")
        blocked = raw.get("blocked_by")
        if not isinstance(blocked, list) or not blocked:
            raise BusError("blocked_by must contain issue numbers")
        if any(not isinstance(item, int) or isinstance(item, bool) or item < 1 for item in blocked):
            raise BusError("blocked_by must contain issue numbers")
    elif op == "handoff":
        _sha(raw, "sha")
        _url(raw, "pr_url", _PR_URL)
        _text(raw, "done_note")
        _text(raw, "left_note")
    elif op == "steal":
        _branch(raw)
        hours = raw.get("stale_heartbeat_hours")
        if not isinstance(hours, int) or isinstance(hours, bool) or hours < _STALE_HOURS:
            raise BusError("steal requires six stale hours")
        if raw.get("branch_commits_since_claim") != 0:
            raise BusError("steal requires zero branch commits")
    elif op == "done":
        _sha(raw, "sha")
        _url(raw, "pr_url", _PR_URL)
        _url(raw, "ci_run_id", _RUN_URL)
        gate = raw.get("test_quality_gate")
        if not isinstance(gate, list) or not gate:
            raise BusError("done requires a test quality gate")
        if any(not isinstance(item, str) or not item.strip() for item in gate):
            raise BusError("done requires a text test quality gate")
    return BusMessage(str(op), issue, agent.strip(), dict(raw))


def parse_messages(text: str) -> list[BusMessage]:
    headings = list(_HEADING.finditer(text))
    result: list[BusMessage] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[heading.end() : end]
        marker = section.find("```json")
        start = section.find("\n", marker)
        if marker < 0 or start < 0:
            raise BusError("AGENT_BUS heading has no json block")
        try:
            raw, _ = json.JSONDecoder().raw_decode(section[start + 1 :].lstrip())
        except json.JSONDecodeError as exc:
            raise BusError("AGENT_BUS json is invalid") from exc
        if not isinstance(raw, dict):
            raise BusError("AGENT_BUS json must be an object")
        result.append(validate_object(raw))
    return result


def run_failure_reason(payload: Mapping[str, Any]) -> str | None:
    if payload.get("status") != "completed" or payload.get("conclusion") != "success":
        return "run is not completed success"
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return "run has no jobs"
    total = payload.get("total_count")
    if isinstance(total, int) and not isinstance(total, bool) and total != len(jobs):
        return "jobs list is incomplete"
    by_name = {
        job["name"]: job for job in jobs if isinstance(job, Mapping) and isinstance(job.get("name"), str)
    }
    for name in REQUIRED_CI_JOBS:
        job = by_name.get(name)
        if job is None:
            return f"missing job {name}"
        if job.get("conclusion") != "success":
            return f"{name} is not success"
        runner_id = job.get("runner_id", job.get("runnerId"))
        runner_name = job.get("runner_name", job.get("runnerName"))
        if not isinstance(runner_id, int) or isinstance(runner_id, bool) or runner_id == 0:
            return f"{name} has no real runner"
        if not isinstance(runner_name, str) or not runner_name.strip():
            return f"{name} has no runner name"
        steps = job.get("steps")
        if not isinstance(steps, list) or not any(
            isinstance(step, Mapping) and step.get("conclusion") == "success" for step in steps
        ):
            return f"{name} has no successful step"
    return None


def _expired(holder: BusMessage, now: datetime, last: datetime) -> bool:
    until = holder.fields.get("until")
    if isinstance(until, str) and now > _time(until):
        return True
    return now - last >= timedelta(hours=_STALE_HOURS)


def inspect_thread(
    payload: object,
    *,
    issue: int,
    now: datetime,
    run: Mapping[str, Any] | None = None,
    compare: Mapping[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    rows = payload.get("comments") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        raise BusError("comments must be a list")
    holder: BusMessage | None = None
    last: datetime | None = None
    for row in sorted(rows, key=lambda item: str(item.get("createdAt", ""))):
        if not isinstance(row, Mapping) or not isinstance(row.get("body"), str):
            raise BusError("comment needs a body")
        stamp = row.get("createdAt", row.get("created_at"))
        if not isinstance(stamp, str):
            raise BusError("comment needs createdAt")
        at = _time(stamp)
        for message in parse_messages(row["body"]):
            if message.issue != issue:
                return None, "comment names another issue"
            if message.op == "claim":
                if holder is None or (last is not None and _expired(holder, at, last)):
                    holder, last = message, at
                continue
            if holder is None or last is None:
                return None, f"{message.op} has no holder"
            if message.op in {"heartbeat", "blocked"}:
                if message.agent != holder.agent:
                    return None, f"{message.op} is not from the holder"
                last = at
            elif message.op == "handoff":
                if message.agent != holder.agent:
                    return None, "handoff is not from the holder"
                holder, last = None, None
            elif message.op == "steal":
                if message.fields.get("branch") != holder.fields.get("branch"):
                    return None, "steal must keep the claimed branch"
                if message.agent == holder.agent or at - last < timedelta(hours=_STALE_HOURS):
                    return None, "steal requires another stale agent"
                if compare is None or compare.get("ahead_by") != 0:
                    return None, "steal lacks empty compare evidence"
                holder, last = message, at
            elif message.op == "done":
                if message.agent != holder.agent or run is None:
                    return None, "done requires holder and run evidence"
                reason = run_failure_reason(run)
                if reason is not None:
                    return None, reason
                head = run.get("head_sha")
                if not isinstance(head, str) or not head.startswith(str(message.fields["sha"])):
                    return None, "done SHA does not match run head"
                holder, last = None, None
    if holder is None or last is None or _expired(holder, now, last):
        return None, None
    return holder.agent, None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    comment = sub.add_parser("check-comment")
    comment.add_argument("path")
    run = sub.add_parser("check-run")
    run.add_argument("path")
    args = parser.parse_args(argv)
    try:
        if args.command == "check-comment":
            messages = parse_messages(Path(args.path).read_text(encoding="utf-8"))
            if not messages:
                raise BusError("no bus message")
            print(f"{len(messages)} bus message(s)")
        else:
            payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
            reason = run_failure_reason(payload)
            if reason is not None:
                raise BusError(reason)
            print("run attested")
    except (OSError, json.JSONDecodeError, BusError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
