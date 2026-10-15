"""Append one operator decision after the result file has been checked."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from repairflow.decision_log import Decision, record_checked_decision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--problem", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--operator-code", required=True)
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
    args = parser.parse_args(argv)
    timestamp = None
    if args.timestamp is not None:
        timestamp = datetime.fromisoformat(args.timestamp)
    try:
        event = record_checked_decision(
            problem_path=args.problem,
            result_path=args.result,
            decision=Decision(args.decision),
            operator_code=args.operator_code,
            log_path=args.log,
            reason=args.reason,
            edit_summary=args.edit_summary,
            rollback_reference=args.rollback_reference,
            timestamp=timestamp,
        )
    except (OSError, ValueError, TypeError) as exc:
        sys.stderr.write(f"append-decision: {exc}\n")
        return 1
    sys.stdout.write(event.model_dump_json() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
