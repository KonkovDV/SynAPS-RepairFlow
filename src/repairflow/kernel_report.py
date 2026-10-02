"""Pinned SynAPS feasibility report.

This module is outside the domain checker. The checker does not import it.
A published verdict that also reads this report is independent of solver
search and is not independent of the SynAPS package.
"""

from __future__ import annotations

from typing import Any

from synaps.model import ScheduleProblem, ScheduleResult


def kernel_hard_violations(schedule_problem: ScheduleProblem, result: ScheduleResult) -> list[dict[str, Any]]:
    """Return hard rows from the pinned SynAPS feasibility checker."""

    from synaps.solvers.feasibility_checker import FeasibilityChecker, proven_hard_violations

    raw = FeasibilityChecker().check(
        schedule_problem,
        list(result.assignments),
        exhaustive=True,
        strict_setup_matrix=True,
    )
    hard = proven_hard_violations(raw)
    out: list[dict[str, Any]] = []
    for item in hard:
        if hasattr(item, "model_dump"):
            out.append(item.model_dump(mode="json"))
        else:
            out.append({"kind": getattr(item, "kind", "KERNEL"), "message": str(item)})
    return out
