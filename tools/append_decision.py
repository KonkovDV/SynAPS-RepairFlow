"""Append one validated operator decision to an evidence JSONL log."""

from __future__ import annotations

import argparse
from pathlib import Path

from repairflow.decision_log import DecisionEvent, append_decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--operator-code", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--input-hash", required=True)
    parser.add_argument("--result-hash", required=True)
    parser.add_argument(
        "--decision",
        choices=("accepted", "accepted_with_edits", "rejected", "manual_fallback"),
        required=True,
    )
    parser.add_argument("--edit-summary", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--rollback-reference", default="")
    parser.add_argument(
        "--timestamp",
        default=None,
        help="ISO-8601 timestamp with timezone; defaults to current UTC",
    )
    args = parser.parse_args()
    payload = {
        "operator_code": args.operator_code,
        "instance_id": args.instance_id,
        "input_hash": args.input_hash,
        "result_hash": args.result_hash,
        "decision": args.decision,
        "edit_summary": args.edit_summary,
        "reason": args.reason,
        "rollback_reference": args.rollback_reference,
    }
    if args.timestamp is not None:
        payload["timestamp"] = args.timestamp
    event = append_decision(args.log, DecisionEvent.model_validate(payload))
    print(event.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
