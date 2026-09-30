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
from urllib.parse import unquote

SCHEMA = "synaps.agent_bus.v1"
OPS = frozenset({"claim", "heartbeat", "blocked", "handoff", "steal", "done"})
REQUIRED_CI_JOBS = ("lint", "test-fast", "synaps-pin", "demo-evidence", "benchmark")
STEAL_AFTER_HOURS = 6
_HEADING = re.compile(r"^### AGENT_BUS\s+synaps\.agent_bus\.v1\s*$", re.MULTILINE)
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
_RUN_URL = re.compile(r"^https://github\.com/KonkovDV/SynAPS-RepairFlow/actions/runs/\d+$")
_PR_URL = re.compile(r"^https://github\.com/KonkovDV/SynAPS-RepairFlow/pull/\d+$")
_FORBIDDEN = {
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


class BusError(ValueError):
    """A bus message or evidence payload is invalid."""


@dataclass(frozen=True)
class BusMessage:
    op: str
    issue: int
    agent: str
    fields: Mapping[str, Any]


@dataclass(frozen=True)
class Comment:
    at: datetime
    body: str


def _parse_time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BusError("timestamp must be ISO-8601") from exc
    if result.tzinfo is None:
        raise BusError("timestamp must include a timezone")
    return result


def _reject_product_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in _FORBIDDEN:
                raise BusError(f"bus cannot carry product field {key}")
            _reject_product_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_product_fields(child)


def _branch(raw: Mapping[str, Any]) -> str:
    value = raw.get("branch")
    if not isinstance(value, str) or ".." in value or _BRANCH.fullmatch(value) is None:
        raise BusError("branch must be a safe feature branch")
    bare = value
    for prefix in ("refs/heads/", "origin/"):
        if bare.startswith(prefix):
            bare = bare[len(prefix) :]
    if bare in {"main", "master"}:
        raise BusError("main is not a claim branch")
    return bare


def _sha(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise BusError(f"{key} must be a git SHA")
    return value


def _url(raw: Mapping[str, Any], key: str, pattern: re.Pattern[str]) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise BusError(f"{key} must be a SynAPS RepairFlow URL")
    return value


def _text(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BusError(f"{key} is required")
    return value


def validate_object(raw: Mapping[str, Any]) -> BusMessage:
    _reject_product_fields(raw)
    if raw.get("schema") != SCHEMA:
        raise BusError(f"schema must be {SCHEMA}")
    op = raw.get("op")
    if op not in OPS:
        raise BusError("op is not a supported operation")
    issue = raw.get("issue")
    agent = raw.get("agent")
    if not isinstance(issue, int) or isinstance(issue, bool) or issue < 1:
        raise BusError("issue must be a positive integer")
    if not isinstance(agent, str) or not agent.strip() or len(agent) > 64:
        raise BusError("agent must be a short name")
    if op == "claim":
        if raw.get("host") not in {"local", "cloud"}:
            raise BusError("host must be local or cloud")
        _sha(raw, "base_sha")
        _branch(raw)
        _parse_time(_text(raw, "until"))
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
        if not isinstance(hours, int) or isinstance(hours, bool) or hours < STEAL_AFTER_HOURS:
            raise BusError("steal requires at least six stale hours")
        if raw.get("branch_commits_since_claim") != 0:
            raise BusError("steal requires zero branch commits")
    elif op == "done":
        _sha(raw, "sha")
        _url(raw, "pr_url", _PR_URL)
        _url(raw, "ci_run_id", _RUN_URL)
        gate = raw.get("test_quality_gate")
        if not isinstance(gate, list) or not gate or any(not isinstance(item, str) for item in gate):
            raise BusError("done requires a test quality gate")
    return BusMessage(op=str(op), issue=issue, agent=agent.strip(), fields=dict(raw))


def _json_after_heading(section: str) -> dict[str, Any]:
    marker = section.find("```json")
    if marker < 0:
        raise BusError("AGENT_BUS heading has no json block")
    start = section.find("\n", marker)
    if start < 0:
        raise BusError("AGENT_BUS json block is empty")
    try:
        value, _ = json.JSONDecoder().raw_decode(section[start + 1 :].lstrip())
    except json.JSONDecodeError as exc:
        raise BusError("AGENT_BUS json is invalid") from exc
    if not isinstance(value, dict):
        raise BusError("AGENT_BUS json must be an object")
    return value


def parse_messages(text: str) -> list[BusMessage]:
    headings = list(_HEADING.finditer(text))
    messages: list[BusMessage] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        messages.append(validate_object(_json_after_heading(text[heading.end() : end])))
    return messages


def _read_text(path: str) -> str:
    data = Path(path).read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BusError("file is not UTF-8") from exc


def _read_json(path: str) -> Mapping[str, Any]:
    try:
        value = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise BusError("JSON is invalid") from exc
    if not isinstance(value, dict):
        raise BusError("JSON root must be an object")
    return value


def _comments(payload: object) -> list[Comment]:
    rows = payload.get("comments") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        raise BusError("comments must be a list")
    result: list[Comment] = []
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("body"), str):
            raise BusError("comment needs a body")
        stamp = row.get("createdAt", row.get("created_at"))
        if not isinstance(stamp, str):
            raise BusError("comment needs createdAt")
        result.append(Comment(_parse_time(stamp), row["body"]))
    return sorted(result, key=lambda item: item.at)


def _expired(message: BusMessage, at: datetime, last: datetime) -> bool:
    until = message.fields.get("until") if message.op == "claim" else None
    if not isinstance(until, str):
        return at - last >= timedelta(hours=STEAL_AFTER_HOURS)
    return at > _parse_time(until) or at - last >= timedelta(hours=STEAL_AFTER_HOURS)


def run_failure_reason(payload: Mapping[str, Any]) -> str | None:
    if payload.get("status") != "completed" or payload.get("conclusion") != "success":
        return "run is not completed success"
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return "run has no jobs"
    total = payload.get("total_count")
    if isinstance(total, int) and not isinstance(total, bool) and total != len(jobs):
        return "jobs list is incomplete"
    by_name: dict[str, Mapping[str, Any]] = {}
    run_id = payload.get("id")
    heads: set[str] = set()
    for job in jobs:
        if not isinstance(job, Mapping) or not isinstance(job.get("name"), str):
            continue
        by_name[job["name"]] = job
        if isinstance(job.get("head_sha"), str):
            heads.add(job["head_sha"])
        if isinstance(run_id, int) and job.get("run_id") not in {None, run_id}:
            return "jobs belong to another run"
    if isinstance(payload.get("head_sha"), str) and heads and heads != {payload["head_sha"]}:
        return "jobs belong to another SHA"
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


def _compare_allows(compare: Mapping[str, Any], base_sha: str, branch: str) -> bool:
    if compare.get("ahead_by") != 0 or compare.get("total_commits") != 0:
        return False
    base = compare.get("base_commit")
    if not isinstance(base, Mapping) or not str(base.get("sha", "")).startswith(base_sha):
        return False
    html = compare.get("html_url")
    prefix = "https://github.com/KonkovDV/SynAPS-RepairFlow/compare/"
    if not isinstance(html, str) or not html.startswith(prefix) or "..." not in html:
        return False
    head = unquote(html.split("...", 1)[1].split("?", 1)[0])
    return head == branch


def inspect_thread(
    payload: object,
    *,
    issue: int,
    now: datetime,
    run: Mapping[str, Any] | None = None,
    compare: Mapping[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    holder: BusMessage | None = None
    last: datetime | None = None
    for comment in _comments(payload):
        for message in parse_messages(comment.body):
            if message.issue != issue:
                return None, "comment names another issue"
            if message.op == "claim":
                if holder is None or (last is not None and _expired(holder, comment.at, last)):
                    holder, last = message, comment.at
                continue
            if holder is None or last is None:
                return None, f"{message.op} has no holder"
            if message.op == "heartbeat":
                if message.agent != holder.agent or message.fields.get("branch") != holder.fields.get("branch"):
                    return None, "heartbeat is not from the holder"
                last = comment.at
            elif message.op == "blocked":
                if message.agent != holder.agent:
                    return None, "blocked is not from the holder"
                last = comment.at
            elif message.op == "handoff":
                if message.agent != holder.agent:
                    return None, "handoff is not from the holder"
                holder, last = None, None
            elif message.op == "steal":
                if message.fields.get("branch") != holder.fields.get("branch"):
                    return None, "steal must keep the claimed branch"
                if comment.at - last < timedelta(hours=STEAL_AFTER_HOURS):
                    return None, "steal requires six stale hours"
                if compare is None:
                    return None, "steal requires compare evidence"
                base = str(holder.fields.get("base_sha", ""))
                if not _compare_allows(compare, base, str(message.fields["branch"])):
                    return None, "compare does not prove an empty claimed branch"
                holder, last = message, comment.at
            elif message.op == "done":
                if message.agent != holder.agent:
                    return None, "done is not from the holder"
                if run is None:
                    return None, "done requires run evidence"
                reason = run_failure_reason(run)
                if reason is not None:
                    return None, reason
                head = run.get("head_sha")
                cited = str(message.fields["sha"])
                if not isinstance(head, str) or not head.startswith(cited):
                    return None, "done SHA does not match run head"
                holder, last = None, None
    if holder is None or last is None or _expired(holder, now, last):
        return None, None
    return holder.agent, None


def _merged_run(run_path: str, jobs_path: str | None) -> dict[str, Any]:
    payload = dict(_read_json(run_path))
    if jobs_path is not None:
        jobs = _read_json(jobs_path)
        if not isinstance(jobs.get("jobs"), list):
            raise BusError("jobs JSON has no jobs list")
        payload["jobs"] = jobs["jobs"]
        if "total_count" in jobs:
            payload["total_count"] = jobs["total_count"]
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    comment = sub.add_parser("check-comment")
    comment.add_argument("path")
    run = sub.add_parser("check-run")
    run.add_argument("run")
    run.add_argument("jobs", nargs="?")
    thread = sub.add_parser("check-thread")
    thread.add_argument("issue", type=int)
    thread.add_argument("comments")
    done = sub.add_parser("check-done")
    done.add_argument("issue", type=int)
    done.add_argument("comments")
    done.add_argument("run")
    done.add_argument("jobs", nargs="?")
    steal = sub.add_parser("check-steal")
    steal.add_argument("issue", type=int)
    steal.add_argument("comments")
    steal.add_argument("compare")
    args = parser.parse_args(argv)
    try:
        if args.command == "check-comment":
            messages = parse_messages(_read_text(args.path))
            if not messages:
                raise BusError("no bus message")
            print(f"{len(messages)} bus message(s)")
        elif args.command == "check-run":
            reason = run_failure_reason(_merged_run(args.run, args.jobs))
            if reason is not None:
                raise BusError(reason)
            print("run attested")
        else:
            run = _merged_run(args.run, args.jobs) if args.command == "check-done" else None
            compare = _read_json(args.compare) if args.command == "check-steal" else None
            holder, reason = inspect_thread(
                _read_json(args.comments),
                issue=args.issue,
                now=datetime.now().astimezone(),
                run=run,
                compare=compare,
            )
            if reason is not None:
                raise BusError(reason)
            print("no holder" if holder is None else holder)
    except (OSError, BusError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
