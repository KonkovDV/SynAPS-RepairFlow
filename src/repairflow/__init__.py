"""SynAPS RepairFlow: auditable repair-maintenance planning contour on SynAPS."""

from __future__ import annotations

from repairflow.model import RepairFlowProblem, RepairFlowResult
from repairflow.planner import PlanOutcome, plan, recheck, replan_after_disruption
from repairflow.safety_hardening import install as _install_safety_hardening
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT

_install_safety_hardening()

__all__ = [
    "PlanOutcome",
    "REPAIRFLOW_VERSION",
    "RepairFlowProblem",
    "RepairFlowResult",
    "SYNAPS_COMMIT",
    "plan",
    "recheck",
    "replan_after_disruption",
]
